"""Original transport across carried context group death and fresh campaigns.

The owning physical/callback reader is mandatory. These retained messages are
never a replacement for original storage or a new source of voting authority.
"""
import argparse
import base64
from collections import defaultdict
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from types import SimpleNamespace
from . import native_carried_transition_forces as forces
from . import remove_network_evidence as network
from . import node_owner_network as attempts
from . import native_carried_network as mutation

p=forces.p;process=p.process
c,d,e,f,need=p.c,p.d,p.e,p.f,p.need


class History(network.History):
    def __init__(self,root,kind,events):
        self.root=Path(root);self.old=process.NODES
        self.phases=[];self.states=[None];self.applied={};self.published={};self.installed={};self.ranges=[];self.nonvoting=set()
        first,count,_=p.t.shape(kind)
        start=-1;life=1;ordinal=0;prior='life-1-opened'
        for at,row in enumerate(events):
            point=row['event']
            if point=='ROUND_INSTALLED':
                ordinal+=1;name=f'life-{life}-installed-{ordinal}'
                self.ranges.append(dict(start=start,stop=at,life=life,kind='campaign',before=prior,after=name))
                start=at;prior=name
            elif point=='GROUP_CRASH':
                self.ranges.append(dict(start=start,stop=at,life=1,kind='interrupted',before=prior,after='at-cut'))
                life=2;ordinal=0;start=at;prior='life-2-opened'
            elif point=='ROUND_SLOT_COMPLETE':
                index=first+ordinal-1;after=f'life-2-published-{index}'
                self.ranges.append(dict(start=start,stop=at,life=2,kind='slot',index=index,before=prior,after=after))
                selected=(root/(prior+'.gsr')).read_bytes()
                for node in self.old:
                    self.installed[ordinal,node]=c.inventory(root/prior/node)
                    self.applied[ordinal,node]=c.inventory(root/f'life-2-applied-{index}'/node)
                    if 'applied-end/statement.gsr' in self.applied[ordinal,node] and 'applied-end/ack.gsr' not in self.applied[ordinal,node]:
                        self.nonvoting.add((ordinal,node))
                    self.published[ordinal,node]=c.inventory(root/after/node)
                frames,_=p.data.pending(self.applied[ordinal,'node-1'])
                self.phases.append(dict(SELECTED=selected,**{k:frames[k] for k in ('ENTRY','ACCEPT','PROOF','CERTIFICATE')}))
                packet=c.current(self.published[ordinal,'node-1'])[2]
                self.states.append(f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG'))
                start=at;prior=after
        need(len(self.phases)==count and len(self.ranges)==2+2*count,'transition network complete phase inventory')

    def activations(self):
        phases=[];installed={};unselected={}
        for stage in self.ranges:
            if stage['kind']!='campaign':continue
            ordinal=len(phases)+1;raw=(self.root/(stage['after']+'.gsr')).read_bytes()
            phases.append(dict(SELECTED=raw))
            selected=f.decode(raw,'records','SELECTED');voters={v['voter'] for v in selected['sources']}
            for node in self.old:
                files=c.inventory(self.root/stage['after']/node);installed[ordinal,node]=files
                if node not in voters and any(kind=='BASIS' and value['ballot']==selected['ballot']
                        for kind,_,value in c.journal(files['grants.gsr'],selected['root'],node)):
                    unselected[ordinal,node]=files
        return SimpleNamespace(phases=phases,installed=installed,unselected=unselected)


def unselected_prepare(row,stage,history):
    if stage.get('kind')!='campaign' or row['kind']!='PREPARE' or row['answer']!='PROMISE':return False
    selected=f.decode((history.root/(stage['after']+'.gsr')).read_bytes(),'records','SELECTED')
    return (row['request']['ballot']==selected['ballot'] and
            row['request']['recipient']['node'] not in {v['voter'] for v in selected['sources']})


def recovered_delivery(row,rows,stage):
    """Require a real identical ACK in this phase; never mark a lost ACK delivered.

    An old server response can arrive after the successful retry. Legacy capture
    cannot assign identical responses to sockets, so no attempt-order claim is
    made here. The immutable request, reply, phase and actual delivery must match.
    """
    if row['kind'] not in ('PREPARE','SELECTED','ACCEPT','PROOF','APPLY'):return False
    return any(other['delivered'] is not None and stage['start']<other['offered']<other['delivered']<stage['stop']
               and other['kind']==row['kind'] and other['answer']==row['answer']
               and other['request']==row['request'] and other['response']==row['response'] for other in rows)


def transport(root,history,original):
    events=[{'node':None,**{k:v for k,v in row.items() if k!='incarnation'}} for row in original]
    identities={node:d.future.identity(files) for node,files in forces.group(root,'before-network').items()}
    root_id=c.current(forces.group(root,'before-network')['node-1'])[2]['capsule']['root']
    wires=process.read(root/'wire.json');rows=network.phase.exchanges(events,wires,identities,root_id)
    adapted=[dict(offered=v['offered'],row=dict(request=base64.b64encode(f.encode('wire',v['kind'],v['request'])).decode())) for v in rows]
    sent={};stages={};traces={}
    for ordinal,stage in enumerate(history.ranges):
        start,stop=stage['start'],stage['stop'];before=forces.group(root,stage['before'])
        view=e.authority(root_id,c.current(before['node-1'])[2]['capsule']['cut']['view'])
        observed=[v if start<at<stop else dict(event='OUTSIDE_PHASE') for at,v in enumerate(events)]
        own=attempts.request_attempts(observed,[v for v in adapted if start<v['offered']<stop],identities,root_id,view)
        for digest,values in own.items():
            need(digest not in sent,'transition network request reused across phases')
            sent[digest]=values
            for value in values:
                need(all(start<value[k]<stop and original[value[k]].get('incarnation')==stage['life']
                         for k in ('at','received','response') if value[k] is not None),
                     'transition network request crosses phase or group death')
                stages[value['at']]=ordinal
                trace=value['request']['trace']
                need(traces.setdefault(trace,ordinal)==ordinal,'transition network trace reused across phases')
    need(sum(len(v) for v in sent.values())==sum(v['event']=='NETWORK_SEND' for v in events),
         'transition network send outside history')
    offered={v['response']:v for values in sent.values() for v in values if v['response'] is not None}
    for row in rows:
        value=offered.get(row['offered'])
        need(value is not None and value['request']==row['request'],'transition network unmatched response')
        stage=history.ranges[stages[value['at']]]
        if row['delivered'] is None:
            # HeartbeatRound returns on a governing majority and cancels the
            # remaining callers. A server may have offered an exact ACK whose
            # client was already cancelled. contacts() still requires the
            # original delivered majority; this observation gives no credit.
            # Slot delivery also retries identical requests. Retain late or
            # lost duplicate ACKs, requiring an exact delivered ACK in this phase.
            need((row['kind']=='HEARTBEAT' and row['answer']=='HEARTBEAT_ACK') or recovered_delivery(row,rows,stage)
                 or unselected_prepare(row,stage,history),
                 'transition network undelivered required response')
        else:
            need(stage['start']<row['delivered']<stage['stop'] and
                 original[row['delivered']].get('incarnation')==stage['life'],
                 'transition network delivery crosses phase or group death')
        row.update(sent=value['at'],received=value['received'])
    return events,rows,sent,identities


def contacts(root,history,events,rows,sent):
    timelines={node:[(-1,c.current(files)[2]['capsule']['cut'])] for node,files in forces.group(root,'before-network').items()}
    for stage in history.ranges:
        if stage['kind']=='interrupted':continue
        group=forces.group(root,stage['after']);selected=f.decode(c.current(group['node-1'])[1]['selected.gsr'],'records','SELECTED')
        point='INSTALL_SELECTOR_FORCED' if stage['kind']=='campaign' else 'PUBLICATION_SELECTOR_FORCED'
        for source in selected['sources']:
            node=source['voter'];positions=[i for i,v in enumerate(events) if stage['start']<i<stage['stop'] and v.get('node')==node and v['event']==point]
            need(len(positions)==1,'transition network original contact timeline')
            timelines[node].append((positions[0],c.current(group[node])[2]['capsule']['cut']))
    def cut_at(node,at):return max((v for v in timelines[node] if v[0]<at),key=lambda v:v[0])[1]
    status=0;samples=defaultdict(list);silent=set()
    for row in rows:
        if row['kind']!='STATUS_PROBE':continue
        q,a=row['request'],row['response'];node=q['recipient']['node']
        possibilities=[cut_at(node,row['received'])]+[cut for at,cut in timelines[node] if row['received']<at<row['offered']]
        need(row['answer']=='STATUS' and set(q['payload'])=={'nonce'} and
             a['payload']==dict(nonce=q['payload']['nonce'],cut=a['payload'].get('cut'),ready=False) and
             a['payload']['cut'] in possibilities,'transition network original status cut')
        status+=1
    for digest,values in sent.items():
        if values[0]['kind']!='HEARTBEAT':continue
        first=values[0];q=first['request'];peer=q['recipient']['node'];at=first['at']
        stage=next(v for v in history.ranges if v['start']<at<v['stop'])
        need(stage['kind']!='campaign','transition network heartbeat before activation')
        selected=f.decode(c.current(c.inventory(root/stage['before']/'node-1'))[1]['selected.gsr'],'records','SELECTED')
        view=selected['cut']['view'];peers=sorted(set(view['old']+view['new'])-{'node-1'})
        need(q['sender']['node']=='node-1' and peer in peers and q['ballot']==selected['ballot'] and
             q['sequence']==peers.index(peer)+1 and q['payload']==dict(cut=cut_at('node-1',at),activated=True) and
             all(v['raw']==first['raw'] for v in values),'transition network original heartbeat request')
        answers=[v for v in rows if v['requestHash']==digest]
        for row in answers:
            need(row['answer']=='HEARTBEAT_ACK' and row['response']['payload']==dict(cut=cut_at(peer,row['offered'])),
                 'transition network original heartbeat reply')
        samples[q['trace']].append((q,at,selected,stage['stop']))
        if not answers:silent.add(digest)
    ordered=sorted(samples.items(),key=lambda item:min(v[1] for v in item[1]))
    for index,(trace,group) in enumerate(ordered):
        first=min(v[1] for v in group);stop=min(v[3] for v in group)
        if index+1<len(ordered):stop=min(stop,min(v[1] for v in ordered[index+1][1]))
        peers=[v[0]['recipient']['node'] for v in group];selected=group[0][2];view=selected['cut']['view']
        need(len(peers)==len(set(peers)) and all(v[0]['payload']==group[0][0]['payload'] and v[2]==selected for v in group),
             'transition network immutable heartbeat sample')
        responding={'node-1'}|{v['request']['recipient']['node'] for v in rows if v['kind']=='HEARTBEAT' and
            v['request']['trace']==trace and v['delivered'] is not None and first<v['delivered']<stop}
        need(all(len(responding&set(view[k]))>len(view[k])//2 for k in ('old','new')),
             'transition network heartbeat governing contact')
    return dict(statusReplies=status,heartbeatSamples=len(samples),heartbeatReplies=sum(v['kind']=='HEARTBEAT' for v in rows),
        deliveredHeartbeatReplies=sum(v['kind']=='HEARTBEAT' and v['delivered'] is not None for v in rows),
        unreceivedHeartbeatReplies=sum(v['kind']=='HEARTBEAT' and v['delivered'] is None for v in rows)),silent


def interrupted(root,history,events,rows):
    stage=next(v for v in history.ranges if v['kind']=='interrupted')
    before=forces.group(root,stage['before']);selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    peers=[v['voter'] for v in selected['sources'] if v['voter']!='node-1']
    frames,_=p.data.pending(c.inventory(root/'at-cut/node-1'))
    point=process.read(root/'process/result.json')['cut']
    own=[v for v in rows if stage['start']<v['offered']<stage['stop'] and v['kind'] not in ('CHUNK','TRANSFER_COMMIT','STATUS_PROBE','HEARTBEAT')]
    if point=='ACCEPT_RENAMED':need(not own,'transition network accept crash cannot have peer votes');return 0
    need(point=='PROOF_RENAMED','transition network interrupted cut')
    stop=next(i for i,v in enumerate(events) if stage['start']<i<stage['stop'] and v==dict(node='node-1',event='PROOF_RENAMED'))
    used=set()
    for node in peers:
        forced=[i for i,v in enumerate(events) if stage['start']<i<stop and v==dict(node=node,event='ACCEPT_BEFORE_RETURN')]
        need(len(forced)==1,'transition network original interrupted acceptance')
        receipt=f.canonical(dict(root=selected['root'],voter=node,incarnation=d.future.identity(before[node])['storage'],phase='ACCEPT',record=e.digest(frames['ACCEPT'])))
        held=network.phase.control(own,'ACCEPT',node,dict(acceptance=e.digest(frames['ACCEPT'])),
            dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(receipt)),selected,forced[0],stop)
        used.update(v['offered'] for v in held)
    need(used=={v['offered'] for v in own},'transition network unbound interrupted control')
    return len(used)


def unused_checkpoint(history,values,blocks):
    """Bind an unanswered lookup to a derived statement and unselected voter.

    Publication may probe old voters before obtaining the selected majority.
    Such an absent response supplies no endorsement; physical publication and
    the successful export history must independently establish the real quorum.
    """
    if not values or values[0]['kind']!='CHUNK':return False
    q=values[0]['request'];sender=q['sender']['node'];recipient=q['recipient']['node']
    for ordinal,parts in enumerate(history.phases,1):
        selected=f.decode(parts['SELECTED'],'records','SELECTED');voters={v['voter'] for v in selected['sources']}
        if sender not in voters or recipient in voters or (ordinal,sender) not in blocks:continue
        original=history.applied[ordinal,sender];identity=d.future.identity(history.applied[ordinal,recipient])
        lower=blocks[ordinal,sender]['APPLY_BEFORE_RETURN'];upper=blocks[ordinal,sender]['PUBLICATION_VALIDATED']
        if q['ballot']!=selected['ballot'] or not lower<values[0]['at']<upper:continue
        for name,raw in original.items():
            if not name.startswith('applied-end/') or not name.endswith('statement.gsr'):continue
            statement=f.decode(raw,'records','CHECKPOINT');view=statement['end']['view']
            if recipient not in set(view['old']+view['new']):continue
            ack=f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter=recipient,
                incarnation=identity['storage'],cut=statement['end'],statement=e.digest(raw)))
            if q['payload'].get('digest')!=e.digest(ack):continue
            trace=q['trace'];identifier=q['payload'].get('id')
            need(str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0 and
                 str(uuid.UUID(identifier))==identifier and uuid.UUID(identifier).int!=0,
                 'transition network checkpoint lookup identity')
            need(q==dict(root=statement['root'],view=selected['view'],ballot=selected['ballot'],
                sender=d.future.identity(original),recipient=identity,trace=trace,sequence=1,
                payload=dict(id=identifier,action='REQUEST',offset=0,digest=e.digest(ack),bytes=''))
                and 0<len(values)<=3 and all(v['request']==q and v['kind']=='CHUNK' and v['response'] is None
                    and lower<v['at']<upper and (v['received'] is None or v['at']<v['received']<upper) for v in values),
                 'transition network unused checkpoint lookup')
            return True
    return False


def unanswered_prepare(history,events,values):
    if not values or values[0]['kind']!='PREPARE':return False
    q=values[0]['request'];peer=q['recipient']['node']
    for stage in history.ranges:
        if stage['kind']!='campaign' or not stage['start']<values[0]['at']<stage['stop']:continue
        files=c.inventory(history.root/stage['after']/'node-1');members=c.current(files)[1]
        selected=f.decode(members['selected.gsr'],'records','SELECTED');voters={v['voter'] for v in selected['sources']}
        if peer in voters or peer not in set(selected['cut']['view']['old']+selected['cut']['view']['new']):continue
        local=[(at,v['event']) for at,v in enumerate(events) if stage['start']<at<stage['stop'] and v.get('node')=='node-1']
        granted=[at for at,point in local if point=='GRANT_BEFORE_RETURN'];selected_at=[at for at,point in local if point=='SELECTED_FORCED']
        need(len(granted)==len(selected_at)==1,'transition network unanswered prepare interval')
        need(q['sender']['node']=='node-1' and q['ballot']==selected['ballot'] and q['view']==selected['view'] and
             q['payload']==dict(promise=e.digest(members['promise.gsr'])) and 0<len(values)<=3 and
             all(v['request']==q and v['kind']=='PREPARE' and v['response'] is None and granted[0]<v['at']<selected_at[0]
                 for v in values),'transition network unanswered prepare authority')
        return True
    return False


def silents(history,events,rows,sent,heartbeat_silent,blocks):
    classified=set(heartbeat_silent);results=[];checkpoint_traces=set();checkpoint_ids=set()
    for digest,values in sent.items():
        unanswered=[v for v in values if v['response'] is None]
        if not unanswered:continue
        if digest in heartbeat_silent:
            results.append(dict(kind='HEARTBEAT',attempts=len(unanswered)));continue
        if unused_checkpoint(history,values,blocks):
            q=values[0]['request'];trace=q['trace'];identifier=q['payload']['id']
            need(trace not in checkpoint_traces and identifier not in checkpoint_ids and
                 all(v['request']['trace']!=trace for v in rows),'transition network reused checkpoint lookup')
            checkpoint_traces.add(trace);checkpoint_ids.add(identifier)
            classified.add(digest);results.append(dict(kind='CHECKPOINT_ACK_LOOKUP',attempts=len(values)));continue
        if unanswered_prepare(history,events,values):
            classified.add(digest);results.append(dict(kind='PREPARE',attempts=len(values)));continue
        q=values[0]['request'];recipient=q['recipient']['node'];matched=False
        for ordinal,parts in enumerate(history.phases,1):
            selected=f.decode(parts['SELECTED'],'records','SELECTED');voters=[v['voter'] for v in selected['sources']]
            peers=sorted(set(selected['cut']['view']['old']+selected['cut']['view']['new'])-{'node-1'})
            parent=c.anchor(c.current(history.applied[ordinal,'node-1'])[2]['capsule'])
            upper=c.anchor(c.current(history.published[ordinal,'node-1'])[2]['capsule'])
            for target in voters[1:]:
                intent=dict(selection=e.digest(parts['SELECTED']),certificate=e.digest(parts['CERTIFICATE']),
                    peer=d.future.identity(history.applied[ordinal,target]),lower=history.future_lower(ordinal,target),parent=parent,upper=upper)
                if not(values[0]['kind']=='FUTURE_RETENTION_INTENT' and q['payload']==intent and recipient in peers and recipient not in voters):continue
                successful=[v for v in rows if v['kind']=='FUTURE_RETENTION_INTENT' and v['request']['payload']==intent]
                lower_at=max(blocks[ordinal,node]['APPLY_BEFORE_RETURN'] for node in voters)
                upper_at=min(blocks[ordinal,node]['PUBLICATION_VALIDATED'] for node in voters)
                need(q['sender']['node']=='node-1' and q['ballot']==selected['ballot'] and q['sequence']==peers.index(recipient)+2 and
                     successful and all(v['request']['trace']==q['trace'] for v in successful) and
                     all(lower_at<v['at']<upper_at and v['response'] is None for v in values),
                     'transition network exact unanswered retention')
                matched=True
        need(matched,'transition network unclassified unanswered request')
        classified.add(digest);results.append(dict(kind='FUTURE_RETENTION_INTENT',attempts=len(values)))
    need(classified=={key for key,values in sent.items() if any(v['response'] is None for v in values)},
         'transition network unanswered inventory')
    return results


def slot_envelopes(history,events,rows):
    for stage in history.ranges:
        if stage['kind']=='campaign':continue
        selected=f.decode(c.current(c.inventory(history.root/stage['before']/'node-1'))[1]['selected.gsr'],'records','SELECTED')
        peers=sorted(set(selected['cut']['view']['old']+selected['cut']['view']['new'])-{'node-1'})
        voters=[v['voter'] for v in selected['sources']]
        own=[v for v in rows if stage['start']<v['offered']<stage['stop']]
        for row in own:
            kind,q=row['kind'],row['request'];peer=q['recipient']['node']
            if kind not in ('ACCEPT','PROOF','APPLY','PUBLISH','FUTURE_RETENTION_INTENT'):continue
            sequence=peers.index(peer)+2 if kind=='FUTURE_RETENTION_INTENT' else len(peers)+2 if kind=='PUBLISH' else 1
            need(q['sender']['node']=='node-1' and peer in voters[1:] and q['ballot']==selected['ballot'] and q['sequence']==sequence,
                 'transition network original slot envelope')
        if stage['kind']!='slot':continue
        quorums=[v for at,v in enumerate(events) if stage['start']<at<stage['stop'] and v['event']=='FUTURE_QUORUM_COMPLETE']
        need(quorums==[dict(node='node-1',event='FUTURE_QUORUM_COMPLETE',index=stage['index'],voters=voters)]*(len(voters)-1),
             'transition network exact original recording quorums')


def replay(root,kind,*,interrupted_replay=interrupted,slot_projection=None):
    original=process.read(root/'events.json');history=History(root,kind,original)
    events,rows,sent,identities=transport(root,history,original)
    contents=[];transfers=network.transcript.transfers(rows,contents=contents)
    activation=network.activations(events,rows,history.activations())
    complete=[stage for stage in history.ranges if stage['kind']=='slot']
    def in_slot(at):return any(v['start']<at<v['stop'] for v in complete)
    slot_events=[v if in_slot(at) else dict(event='OUTSIDE_SLOT') for at,v in enumerate(events)]
    if slot_projection is not None:slot_events=slot_projection(root,history,slot_events)
    slot_rows=[v for v in rows if in_slot(v['offered'])]
    blocks=network.phase.blocks(slot_events,history)
    slots=network.phase.phase_replay(slot_events,slot_rows,history,blocks)
    contact,heartbeat_silent=contacts(root,history,events,rows,sent)
    interrupted_votes=interrupted_replay(root,history,events,rows)
    silent=silents(history,events,rows,sent,heartbeat_silent,blocks)
    slot_envelopes(history,events,rows)
    need(all(v['kind'] in {'CHUNK','TRANSFER_COMMIT','PREPARE','SELECTED','STATUS_PROBE','HEARTBEAT','ACCEPT','PROOF','APPLY','PUBLISH','FUTURE_RETENTION_INTENT'} for v in rows),
         'transition network unclassified response')
    return dict(status='PARTIAL',scope='carried-transition-network-components',**transfers,**activation,**slots,
        exchanges=len(rows),requests=sum(len(v) for v in sent.values()),
        silentRequests=sum(v['response'] is None for values in sent.values() for v in values),silent=silent,
        **contact,interruptedVoteReplies=interrupted_votes,
        fullWireReplay=False,exportAuthorityQualified=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=process.collection.inventory(root);original=forces.validate(root)
    result=replay(root,original['original']['physical']['kind'])
    need(process.collection.inventory(root)==before,'transition network original changed')
    return dict(original=original,network=result,status='PARTIAL',phase3Complete=False)


NEGATIVES={
    'network-missing-send':'node network received request without write',
    'network-missing-receipt':'node network response without original receipt',
    'network-invented-delivery':'joining delivery without original response',
    'network-early-delivery':'joining delivery without original response',
    'network-cross-life-delivery':'transition network delivery crosses phase or group death',
    'network-discovery-cut':'transition network original status cut',
    'network-source-bytes':'joining network complete transfer commit',
    'network-source-offer':'joining network exact transfer chunk',
    'network-basis-reply':'REMOVE network prepare authority',
    'network-reply-identity':'joining wire correlation',
    'network-vote-receipt':'joining original phase ACK',
    'network-apply-statement':'joining original phase ACK',
    'network-future-revision':'joining original phase ACK',
    'network-future-digest':'joining original phase ACK',
    'network-install-reply':'REMOVE network installation authority',
    'network-publish-generation':'joining original phase ACK',
    'network-heartbeat-request':'transition network original heartbeat request',
    'network-heartbeat-reply':'transition network original heartbeat reply',
    'network-heartbeat-no-contact':'transition network heartbeat governing contact',
    'network-wrong-quorum':'transition network exact original recording quorums',
    'network-silent-retention-reference':'transition network unclassified unanswered request',
}


def qualify(root):
    root=Path(root);before=process.collection.inventory(root);original=validate(root);results=[]
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inventory:{key:value for key,value in inventory['files'].items() if key not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-transition-network-') as temporary:
        for name,reason in NEGATIVES.items():
            copied=Path(temporary)/name;shutil.copytree(root,copied);mutation.mutate(copied,name)
            after=process.collection.inventory(copied)
            need(protected(before)==protected(after) and before['directories']==after['directories'],
                 'transition network negative changed storage input')
            try:validate(copied)
            except ValueError as error:need(str(error)==reason,'transition network wrong negative '+name+': '+str(error))
            else:raise ValueError('transition network accepted mutation '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason));shutil.rmtree(copied)
            print(json.dumps(dict(stage='network-negative',completed=len(results),total=len(NEGATIVES),case=name)),file=sys.stderr,flush=True)
    need(process.collection.inventory(root)==before,'transition network qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
