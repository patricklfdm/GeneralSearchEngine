"""Current process heartbeat observations, separate from voting authority.

The enclosing reader first reconstructs every original snapshot. These samples
can prove contact only; they cannot supply any grant, source, vote or READY.
"""
from collections import defaultdict
import uuid
from . import node_inflight_evidence as p

n, c, e, f, need = p.n, p.c, p.e, p.f, p.need


INSTALL_RETENTION = ('RETENTION_BEFORE_WRITE','RETENTION_PREFIX_WRITTEN','RETENTION_WRITTEN',
    'RETENTION_FORCED','RETENTION_CANDIDATE_PARENT_FORCED','RETENTION_RENAMED',
    'RETENTION_PARENT_FORCED','SELECTED_RETENTION_COMPLETED')


def installation_retention(events, start, stop, group, selected):
    for source in selected['sources']:
        node=source['voter'];files=group[node]
        promise,_,_,packet=p.net.a.frozen(files,selected['ballot'])
        originals=[n.s.s.unwrap(raw) for raw in packet['objects'].values() if raw[:4]==b'GSRP']
        prior=[raw for grant,raw in originals if grant==promise]
        need(len(prior)==1,'current node original frozen retention')
        changes=prior[0]!=files[n.s.FILE]
        lower=[i for i in range(start+1,stop) if events[i]['node']==node and events[i]['event']=='INSTALL_PARENT_FORCED']
        upper=[i for i in range(start+1,stop) if events[i]['node']==node and events[i]['event']=='INSTALL_BEFORE_RETURN']
        need(len(lower)==len(upper)==1 and lower[0]<upper[0],'current node installed retention lifetime')
        observed=[v['event'] for v in events[lower[0]+1:upper[0]] if v['node']==node and v['event'] in INSTALL_RETENTION]
        need(observed==list(INSTALL_RETENTION if changes else ()), 'current node selected retention forces: '+node)


def heartbeats(root, events, entries, sent, boundaries, *, stages=None):
    a=p.net.a; timelines=defaultdict(list); installations=[]
    if stages is None:
        stages={0:'installed-1',1:'published-1',3:'installed-2',4:'published-2',5:'published-3',
                6:'installed-3',7:'published-4',8:'published-5'}
    need(type(stages) is dict and stages and
         all(type(i) is int and 0<=i<len(boundaries) and type(v) is str and
             v.startswith(('installed-','published-')) and v.split('-',1)[1].isdigit() and
             str(int(v.split('-',1)[1]))==v.split('-',1)[1] and int(v.split('-',1)[1])>0 for i,v in stages.items()) and
         list(stages)==sorted(stages),
         'current heartbeat physical stage schedule')
    for node, files in a.group(root,'before-network').items():
        timelines[node].append((-1,c.current(files)[2]['capsule']['cut']))
    for ordinal,stage in stages.items():
        start,stop=boundaries[ordinal]; group=a.group(root,stage)
        selected=f.decode(c.current(group['node-1'])[1]['selected.gsr'],'records','SELECTED')
        installing=stage.startswith('installed')
        if installing:
            installations.append((stop,selected)); installation_retention(events,start,stop,group,selected)
        for source in selected['sources']:
            node=source['voter']; force='INSTALL_SELECTOR_FORCED' if installing else 'PUBLICATION_SELECTOR_FORCED'
            at=[i for i in range(start+1,stop) if events[i]['node']==node and events[i]['event']==force]
            need(len(at)==1,'current heartbeat original selector boundary')
            timelines[node].append((at[0],c.current(group[node])[2]['capsule']['cut']))

    def cut_at(node, at):
        return max((v for v in timelines[node] if v[0]<at),key=lambda v:v[0])[1]

    samples=defaultdict(list); hashes=set(); reply_hashes=set(); ignored=set(); responses=0
    for digest,attempts in sent.items():
        if attempts[0]['kind']!='HEARTBEAT': continue
        first=attempts[0]; q=first['request']; at=first['at']; peer=q['recipient']['node']; trace=q['trace']
        held=[v for pos,v in installations if pos<at]
        need(held and q['sender']['node']=='node-1' and peer in ('node-2','node-3') and
             str(uuid.UUID(trace))==trace and uuid.UUID(trace).int!=0,'current heartbeat installed owner')
        selected=held[-1]
        need(q['ballot']==selected['ballot'] and q['sequence']==int(peer[-1])-1 and
             q['payload']==dict(cut=cut_at('node-1',at),activated=True), 'current heartbeat original request cut')
        need(all(v['raw']==first['raw'] for v in attempts),'current heartbeat immutable retries')
        samples[trace].append((digest,attempts,selected)); hashes.add(digest)
        matches=[v for v in entries if v['kind']=='HEARTBEAT' and v['request']==q]
        for row in matches:
            need(row['answer']=='HEARTBEAT_ACK' and row['response']['payload']==dict(cut=cut_at(peer,row['offered'])),
                 'current heartbeat original reply cut')
            reply_hashes.add(e.digest(f.encode('wire','HEARTBEAT_ACK',row['response']))); responses+=1
    ordered=sorted(samples.items(),key=lambda item:min(v[1][0]['at'] for v in item[1]))
    for ordinal,(trace,rows) in enumerate(ordered):
        peers=[v[1][0]['request']['recipient']['node'] for v in rows]
        requests=[v[1][0]['request'] for v in rows]; first=min(v[1][0]['at'] for v in rows)
        selected=rows[0][2]
        need(len(peers)==len(set(peers)) and all(q['payload']==requests[0]['payload'] and q['ballot']==selected['ballot'] for q in requests),
             'current heartbeat immutable sample')
        stops=[stop for start,stop in boundaries if start<first<stop]
        need(len(stops)==1,'current heartbeat original lifetime')
        upper=stops[0]
        if ordinal+1<len(ordered):upper=min(upper,min(v[1][0]['at'] for v in ordered[ordinal+1][1]))
        responding={'node-1'}|{v['request']['recipient']['node'] for v in entries if v['kind']=='HEARTBEAT'
            and v['request']['trace']==trace and any(first<at<upper for at in v['deliveries'])}
        view=selected['cut']['view']
        need(all(len(responding&set(view[k]))>len(view[k])//2 for k in ('old','new')),
             'current heartbeat contact before continuation')
    for at,row in enumerate(events):
        if (row['event'] in ('NETWORK_SEND','NETWORK_REQUEST','WIRE_RESPONSE') and row.get('request') in hashes
                or row['event']=='NETWORK_RECEIVED' and row.get('kind')=='HEARTBEAT_ACK' and row.get('response') in reply_hashes):
            ignored.add(at)
    need(responses==sum(v['kind']=='HEARTBEAT' for v in entries),'current heartbeat complete response coverage')
    return dict(samples=len(samples),exchanges=responses,contactOnly=True,
        silentRequests=sum(len(v) for h,v in sent.items() if h in hashes and not any(r['response'] is not None for r in v)),
        _events=ignored,_traces=set(samples))
