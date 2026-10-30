"""Replay the original stable round and its diagnostic heartbeat separately.

The temporary projection removes only heartbeat snapshots/events/frames. It is
never a replacement for the original: every removed item is checked below,
against the physically replayed fresh barrier and its actual member cuts.
"""
import argparse
import base64
from collections import Counter, defaultdict
import json
import re
from pathlib import Path
import shutil
import tempfile
import uuid
from . import round_driver_evidence as r

n=r.d
b,c,e,f,need=n.b,n.c,n.e,n.f,n.need
MARKERS={'HEARTBEAT_BEGIN','HEARTBEAT_SEND','HEARTBEAT_CONTACT'}


def unselected_rejections(failures, observed):
    """Diagnostics never supply authority or prove the unretained request body.

    Heartbeat observation advances node 3's volatile fence, but cannot install
    the chosen quorum there. The subsequent unselected request consequently
    fails at its installation check, rather than the earlier ballot check.
    """
    old='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required'
    uninstalled='java.lang.IllegalArgumentException: retention intent installed selection required'
    need(type(failures) is list and len(failures)<=6,'heartbeat round bounded unselected rejection')
    groups={};finished=set();previous=None
    for row in failures:
        need(set(row)=={'node','kind','request','failure'} and row['node']=='node-3' and row['kind']=='FUTURE_RETENTION_INTENT'
             and type(row['request']) is str and re.fullmatch('[0-9a-f]{64}',row['request'])
             and row['failure'] in ({old,uninstalled} if observed else {old}), 'heartbeat round bounded unselected rejection')
        digest=row['request']
        if digest!=previous:
            need(digest not in finished,'heartbeat round bounded unselected rejection')
            if previous is not None:finished.add(previous)
        previous=digest;group=groups.setdefault(digest,[]);group.append(row['failure'])
        need(len(groups)<=2 and len(group)<=3 and len(set(group))==1,'heartbeat round bounded unselected rejection')


def heartbeat(root, rows, events):
    group={node:c.inventory(root/'published-1'/node) for node in ('node-1','node-2','node-3')}
    b.match(root,'heartbeat-before',group); b.match(root,'heartbeat-after',group)
    ids={node:n.future.identity(files) for node,files in group.items()}
    cuts={node:c.current(files)[2]['capsule']['cut'] for node,files in group.items()}
    selected=f.decode((root/'selected.gsr').read_bytes(),'records','SELECTED')
    begin=[i for i,v in enumerate(events) if v['event']=='HEARTBEAT_BEGIN']
    end=[i for i,v in enumerate(events) if v['event']=='HEARTBEAT_CONTACT']
    ready=[i for i,v in enumerate(events) if v['event']=='ROUND_BEFORE_READY']
    writes=[i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_BEGIN']
    need(len(begin)==len(end)==len(ready)==1 and len(writes)==2 and ready[0]<begin[0]<end[0]<writes[1],
         'heartbeat round after readiness before next slot')
    begin,end=begin[0],end[0]
    need(events[begin]==dict(node='node-1',event='HEARTBEAT_BEGIN'),'heartbeat round begin owner')
    sent=defaultdict(list); traces=set()
    for at,row in enumerate(events):
        if row['event']!='HEARTBEAT_SEND':continue
        need(set(row)=={'node','event','bytes'} and row['node']=='node-1' and begin<at,
             'heartbeat round original send')
        raw=base64.b64decode(row['bytes'],validate=True);request=f.decode(raw,'wire','HEARTBEAT')
        peer=request['recipient']['node'];need(peer in ('node-2','node-3'),'heartbeat round peer')
        trace=request['trace'];need(uuid.UUID(trace).int!=0,'heartbeat round trace');traces.add(trace)
        expected=dict(root=selected['root'],view=selected['view'],ballot=selected['ballot'],sender=ids['node-1'],
            recipient=ids[peer],trace=trace,sequence=int(peer[-1])-1,payload=dict(cut=cuts['node-1'],activated=True))
        need(request==expected,'heartbeat round current proposer/cut')
        sent[peer].append((raw,at))
    need(len(traces)==1 and 1<=len(sent)<=2 and all(1<=len(v)<=3 and all(raw==v[0][0] for raw,_ in v) for v in sent.values()),
         'heartbeat round immutable bounded sends')
    expected_events=Counter(); delivered={}; replies=defaultdict(list)
    for row in rows:
        need(set(row)=={'request','response','withheld'} and row['withheld'] is False,'heartbeat round wire row')
        raw,answer=(base64.b64decode(row[k],validate=True) for k in ('request','response'))
        request=f.decode(raw,'wire','HEARTBEAT');response=f.decode(answer,'wire','HEARTBEAT_ACK');peer=request['recipient']['node']
        need(peer in sent and raw==sent[peer][0][0],'heartbeat round response without send')
        replies[peer].append(answer)
        need(response==dict(request,sender=ids[peer],recipient=ids['node-1'],payload=dict(cut=cuts[peer])),
             'heartbeat round original reply cut/correlation')
        stamp=dict(node=peer,event='WIRE_RESPONSE',request=e.digest(raw),response=e.digest(answer))
        expected_events[f.canonical(stamp)]+=1
        response_at=[i for i,v in enumerate(events) if v==stamp]
        need(response_at and min(at for _,at in sent[peer])<min(response_at),'heartbeat round response after send')
        delivery=dict(node='node-1',event='NETWORK_RECEIVED',kind='HEARTBEAT_ACK',response=e.digest(answer))
        arrivals=[i for i,v in enumerate(events) if v==delivery]
        need(len(arrivals)<=len(response_at) and all(any(start<at for start in response_at) for at in arrivals),
             'heartbeat round actual delivery')
        if any(at<end for at in arrivals):delivered[peer]=cuts[peer]
    need(all(len(v)<=len(sent[peer]) for peer,v in replies.items()),'heartbeat round bounded responses')
    response_hashes={e.digest(raw) for v in sent.values() for raw,_ in v}
    observed=Counter(f.canonical(v) for v in events if v['event']=='WIRE_RESPONSE' and v.get('request') in response_hashes)
    need(observed==expected_events,'heartbeat round complete response events')
    known={e.digest(answer) for values in replies.values() for answer in values}
    need(all(set(v)=={'node','event','kind','response'} and v['node']=='node-1' and v['response'] in known
        for v in events if v['event']=='NETWORK_RECEIVED' and v.get('kind')=='HEARTBEAT_ACK'),'heartbeat round unknown delivery')
    contact=events[end]
    need(set(contact)=={'node','event','responding','hints'} and contact['node']=='node-1'
         and type(contact['responding']) is list and len(contact['responding'])==2
         and contact['responding']==sorted(set(contact['responding'])) and 'node-1' in contact['responding'],
         'heartbeat round diagnostic majority')
    peers=set(contact['responding'])-{'node-1'}
    need(peers<=set(delivered) and contact['hints']==[dict(node=peer,cut=delivered[peer]) for peer in sorted(peers)],
         'heartbeat round contact requires delivered original ACK')
    for row in events[begin+1:end]:
        allowed=(row['event']=='HEARTBEAT_SEND' or row['event']=='WIRE_RESPONSE' and row.get('request') in response_hashes
            or row['event']=='NETWORK_RECEIVED' and row.get('kind')=='HEARTBEAT_ACK' and row.get('response') in known)
        need(allowed,'heartbeat round no authority work during sample')
    return dict(status='PASS',exchanges=len(rows),sentAttempts=sum(map(len,sent.values())),responding=contact['responding'],
        authorityWrites=False,readLease=False)


def validate(root):
    root=Path(root);r.projection(root)
    b.selection.layout(root,{'initial','original-plan.gsbp','original-application.image','before-network','installed',
        'applied-1','published-1','applied-2','published-2','after-close','calls.json','events.json','wire.json',
        'failures.json','result.json','selected.gsr','round-result.json','heartbeat-before','heartbeat-after'},'heartbeat round inventory')
    rows=n.read(root/'wire.json');events=n.read(root/'events.json')
    hb=[row for row in rows if n.transfer.t.wire(row['request'])[0]=='HEARTBEAT']
    other=[row for row in rows if n.transfer.t.wire(row['request'])[0]!='HEARTBEAT']
    hashes={e.digest(base64.b64decode(row['request'],validate=True)) for row in hb}
    def extension(row):
        return (row['event'] in MARKERS or row['event']=='WIRE_RESPONSE' and row.get('request') in hashes
                or row['event']=='NETWORK_RECEIVED' and row.get('kind')=='HEARTBEAT_ACK')
    with tempfile.TemporaryDirectory(prefix='v53-heartbeat-round-original-') as temp:
        path=Path(temp)/'raw';shutil.copytree(root,path)
        for name in ('heartbeat-before','heartbeat-after'):shutil.rmtree(path/name)
        (path/'wire.json').write_bytes(f.canonical(other));(path/'events.json').write_bytes(f.canonical([v for v in events if not extension(v)]))
        observed=any(n.transfer.t.wire(row['request'])[1]['recipient']['node']=='node-3' for row in hb)
        original=r.validate(path,rejection_check=lambda failures:unselected_rejections(failures,observed))
    sample=heartbeat(root,hb,events)
    return dict(status='PASS',scope='single-native-ready-round-heartbeat',original=original,heartbeat=sample,
        originalFirst=True,autonomousElection=False,publicRuntime=False,phase3Complete=False)


NEGATIVES={
    'base-selector':'admitted exact published-2: node-1',
    'heartbeat-write':'admitted exact heartbeat-after: node-2',
    'heartbeat-missing-before':'admitted exact heartbeat-before: node-1',
    'early-contact':'heartbeat round after readiness before next slot',
    'wrong-send-cut':'heartbeat round current proposer/cut',
    'changed-retry':'heartbeat round immutable bounded sends',
    'forged-reply-cut':'heartbeat round original reply cut/correlation',
    'foreign-reply':'heartbeat round original reply cut/correlation',
    'invented-contact':'heartbeat round diagnostic majority',
    'forged-hint':'heartbeat round contact requires delivered original ACK',
    'missing-contact-delivery':'heartbeat round contact requires delivered original ACK',
    'hidden-force':'heartbeat round no authority work during sample',
    'hidden-failure':'heartbeat round bounded unselected rejection',
}


def mutate(root,name):
    if name=='base-selector':(root/'published-2/node-1/selector.gsr').write_bytes(b'changed');return
    if name=='heartbeat-write':(root/'heartbeat-after/node-2/allocator.gsr').write_bytes(b'changed');return
    if name=='heartbeat-missing-before':(root/'heartbeat-before/node-1/selector.gsr').unlink();return
    if name=='hidden-failure':(root/'failures.json').write_bytes(f.canonical([dict(node='node-2',kind='ACCEPT',request='0'*64,failure='hidden')]));return
    rows=n.read(root/'wire.json');events=n.read(root/'events.json')
    contact=next(v for v in events if v['event']=='HEARTBEAT_CONTACT')
    peer=next(v for v in contact['responding'] if v!='node-1')
    if name=='early-contact':events.remove(contact);events.insert(0,contact)
    elif name=='invented-contact':contact['responding']=['node-1']
    elif name=='forged-hint':contact['hints'][0]['cut']['index']+=1
    elif name=='hidden-force':events.insert(events.index(contact),dict(node='node-1',event='UNACCOUNTED_WRITE'))
    elif name in ('wrong-send-cut','changed-retry'):
        sent=next(v for v in events if v['event']=='HEARTBEAT_SEND')
        if name=='wrong-send-cut':
            value=f.decode(base64.b64decode(sent['bytes']),'wire','HEARTBEAT');value['payload']['cut']['index']+=1
            sent['bytes']=base64.b64encode(f.encode('wire','HEARTBEAT',value)).decode()
        else:
            # More than the finite attempt bound cannot be legitimized by any ACK.
            at=events.index(contact);events[at:at]=[dict(sent) for _ in range(3)]
    else:
        row=next(v for v in rows if (lambda p:p[0]=='HEARTBEAT' and p[1]['recipient']['node']==peer)(n.transfer.t.wire(v['request'])))
        answer=f.decode(base64.b64decode(row['response']),'wire','HEARTBEAT_ACK');old=e.digest(base64.b64decode(row['response']))
        if name=='missing-contact-delivery':events=[v for v in events if not(v['event']=='NETWORK_RECEIVED' and v.get('response')==old)]
        else:
            if name=='forged-reply-cut':answer['payload']['cut']['index']+=1
            elif name=='foreign-reply':answer['root']='0'*64
            else:raise ValueError('unknown heartbeat round mutation')
            raw=f.encode('wire','HEARTBEAT_ACK',answer);row['response']=base64.b64encode(raw).decode()
            for ev in events:
                if ev.get('response')==old:ev['response']=e.digest(raw)
    (root/'wire.json').write_bytes(f.canonical(rows));(root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-heartbeat-round-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);mutate(path,name)
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'heartbeat round unrelated negative '+name+': '+str(error))
            else:raise ValueError('heartbeat round accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
