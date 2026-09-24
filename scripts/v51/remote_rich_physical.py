"""Concurrent rich calls bound to original per-read runtime observations."""
from . import performance_model as m, performance_projection as projection, format_inspector as f


class Calls:
    def __init__(self,calls):
        self.expected={c['opId']:c for c in calls}
        m.need(len(self.expected)==len(calls),'duplicate rich operation ID')
        self.active={};self.invocations={};self.captures={};self.validations={};self.call_reads={}
        self.successes=set();self.mutations=set();self.read_barriers=set()

    def key(self,node,row):
        if row.get('readId',0):
            key=node,row['readId']
            m.need(key in self.invocations,'read cut without original invocation identity')
            return key
        auxiliary=[(key,value) for key,value in self.active.items() if key[0]==node and value['command']=='backup']
        m.need(len(auxiliary)==1,'unowned auxiliary read cut')
        return node,'backup:'+auxiliary[0][0][1]

    def event(self,node,row,projected,published,votes,promise):
        event=row['event'];manifest=projected['manifest']
        if event=='CLIENT_INVOKE':
            key=node,row['opId'];m.need(key not in self.active,'overlapping duplicate command')
            self.active[key]=row
        elif event=='PUBLIC_READ_INVOKE':
            key=node,row['readId'];client=node,row['opId']
            m.need(type(row['readId']) is int and row['readId']>0 and key not in self.invocations,'reused read identity')
            m.need(client in self.active and self.active[client]['command']=='call' and
                   self.active[client]['operation'] in ('GET','QUERY'),'read invocation ownership')
            m.need(client not in self.call_reads,'multiple barriers for one public call')
            m.need(self.active[client]['order']<row['order'],'read invocation before client call')
            self.invocations[key]=row;self.call_reads[client]=key
        elif event=='READ_CAPTURE_VALIDATED':
            key=self.key(node,row)
            m.need(key not in self.validations and row['index'] in published,'duplicate/unpublished read validation')
            snapshot,order=published[row['index']]
            proof=f.contextual_frame(projection.raw(snapshot['terminalProof']),'PROOF',manifest)
            m.need((row['epoch'],proof['incarnation'])==promise,'capture after changed promise')
            self.validations[key]=row
        elif event=='READ_CAPTURED':
            key=self.key(node,row)
            m.need(key in self.validations and key not in self.captures,'read capture identity')
            validated=self.validations[key]
            m.need(all(row[k]==validated[k] for k in ('epoch','index','sequence')) and validated['order']<row['order'],'read validation/capture mismatch')
            invocation=self.invocations.get(key)
            if invocation:
                client=self.active[node,invocation['opId']]
            else:
                client=next(v for k,v in self.active.items() if k[0]==node and v['command']=='backup')
            snapshot,order=published[row['index']]
            digest=snapshot['anchors'][-1]['entryDigest'];entry=projected['entries'][digest]
            proof=f.contextual_frame(projection.raw(snapshot['terminalProof']),'PROOF',manifest)
            vote=(proof['epoch'],proof['incarnation'],proof['index'],digest)
            m.need(entry['operation']==9 and digest not in self.read_barriers and
                   client['order']<votes.get(vote,-1)<order<validated['order'],'missing/reused/pre-invocation read barrier')
            if invocation:m.need(invocation['order']<votes[vote],'barrier predates public read invocation')
            m.need(snapshot['applicationSequence']==row['sequence'],'capture sequence differs from actual snapshot')
            self.read_barriers.add(digest)
            self.captures[key]=dict(row=row,snapshot=snapshot,released=False)
        elif event=='READ_RELEASED':
            key=self.key(node,row)
            m.need(key in self.captures and not self.captures[key]['released'],'unowned/repeated read release')
            capture=self.captures[key]
            m.need(all(row[k]==capture['row'][k] for k in ('epoch','index','sequence')) and row['order']>capture['row']['order'],'release changed captured prefix')
            capture['released']=True;capture['releaseOrder']=row['order']
        elif event=='CLIENT_RESULT':
            key=node,row['opId'];m.need(key in self.active,'unmatched cloud client response')
            invoke=self.active.pop(key)
            m.need(row['outcome']=='SUCCESS' and row['order']>invoke['order'],'failed/reordered client response')
            if row['command']=='call':
                call=self.expected.get(row['opId'])
                m.need(call is not None and call['pid']==row['pid'] and call['node']==node and
                       all(call[k]==v for k,v in row['call'].items()),'unrecorded/changed cloud call response')
                m.need(call['outcome']=='SUCCESS','unsuccessful cloud API call')
                if call['operation'] in m.OP_IDS:
                    matches=[(i,d) for i,d in projected['chosen'].items() if projected['entries'][d]['operation']==m.OP_IDS[call['operation']]
                             and projected['entries'][d]['payloadDigest']==call['payloadSha256'] and i in published and
                             invoke['order']<published[i][1]<row['order']]
                    m.need(len(matches)==1 and matches[0][1] not in self.mutations,'mutation lacks unique own publication')
                    m.need(key not in self.call_reads,'mutation used hidden strong read')
                    self.mutations.add(matches[0][1])
                else:
                    m.need(key in self.call_reads,'read lacks bound invocation')
                    capture=self.captures.get(self.call_reads[key])
                    m.need(capture is not None and capture['released'] and capture['releaseOrder']<row['order'],'read response before its release')
                    state=m.application(projection.raw(capture['snapshot']['application']),capture['snapshot']['applicationSequence'])
                    answer=m.display(state.documents[call['keys'][0]]) if call['operation']=='GET' else state.answer('QUERY',0)
                    m.need(call['answer']==answer and call['answerSha256']==m.sha(m.canonical(answer)),'answer differs from exact concurrent captured cut')
                self.successes.add(row['opId'])
            elif row['command']=='backup':
                capture=self.captures.get((node,'backup:'+row['opId']))
                m.need(capture and capture['released'] and capture['releaseOrder']<row['order'] and row['sequence']==capture['row']['sequence'],'backup cut')

    def finish(self):
        m.need(not self.active and self.successes==set(self.expected),'missing/unfinished cloud client calls')
        reads=sum(c['operation'] not in m.OP_IDS for c in self.expected.values())
        mutations=len(self.expected)-reads
        m.need(len(self.mutations)==mutations and len(self.read_barriers)==reads+1 and len(self.call_reads)==reads,'cloud read/mutation/auxiliary accounting')
        m.need(len(self.captures)==reads+1 and all(v['released'] for v in self.captures.values()),'unreleased cloud captures')
