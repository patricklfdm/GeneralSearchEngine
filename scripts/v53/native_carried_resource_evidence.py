"""Original node-budget observations through carried group crash and reopen.

The complete original storage/ledger chain is mandatory. Accounting snapshots
at a crash are prefixes, never successful drains or physical storage authority.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_transition_retention as retention
from . import resource_transitions as resources

t=retention;r=resources;f=t.f;c=t.c;need=t.need;sha=t.sha;collection=t.x.process.collection
LIMITS=(384*r.MIB,16*1024*r.MIB,64*r.MIB) # Actual unchanged ReplicationBounds.defaults() staging.


def read(root,name,maximum):return collection.read_json(root,name,maximum)


def linked(directory,index,name,key,maximum):
    raw=collection.snapshot.s.regular(directory/name,maximum)
    need(sha(raw)==index[key],'carried resource original file digest: '+name)
    return read(directory,name,maximum)


def lifecycle(trace,rows,node,last_event_sequence,event_count):
    need(len(rows)==2 and [v.get('event') for v in rows]==['BEGIN','RETURNED'],'carried resource exact close pair')
    seq=[]
    for row in rows:
        need(set(row)=={'node','event','eventCount','sequence','usage'} and row['node']==node and
             type(row['eventCount']) is int and 0<=row['eventCount']<=event_count and
             type(row['sequence']) is int and 0<=row['sequence']<trace['transitions'],'carried resource close checkpoint')
        r.same_usage(row['usage'],trace['changes'][row['sequence']]['usage']);seq.append(row['sequence'])
    need(last_event_sequence<=seq[1] and seq[0]<seq[1]==trace['transitions']-1 and
         rows[0]['eventCount']<=rows[1]['eventCount']==event_count and rows[0]['usage']['leases']>0,
         'carried resource original close interval')
    r.same_usage(rows[1]['usage'],r.EMPTY)
    return dict(begin=seq[0],returned=seq[1],changes=seq[1]-seq[0])


def lifetime(directory,history,life):
    index=read(directory,'index.json',16384);terminal='CUT_PREFIX' if life==1 else 'CLOSED'
    children=read(history/'process','result.json',65536)['children'];child=children[life-1]
    fields={'schema','root','life','pid','terminal','owners','eventsSha256','boundariesSha256','closesSha256'}
    root=f.decode(c.inventory(history/'before-network/node-1')['selector.gsr'],'records','SELECTOR')['root']
    need(type(index) is dict and set(index)==fields and index['schema']=='gse-v53-node-resource-lifetime-v1' and
         index['root']==root and type(index['life']) is int and index['life']==life and
         type(index['pid']) is int and index['pid']==child['pid'] and index['terminal']==terminal,
         'carried resource original process identity')
    events=linked(directory,index,'events.json','eventsSha256',32*r.MIB)
    boundaries=linked(directory,index,'boundaries.json','boundariesSha256',32*r.MIB)
    closes=linked(directory,index,'closes.json','closesSha256',65536)
    messages=t.x.process.process.process.transcript(history/f'process/life-{life}.jsonl')
    expected=[row['value'] if row['action']=='event' else row['value']['event'] for row in messages if row['action'] in ('event','response')]
    need(f.canonical(events)==f.canonical(expected) and type(boundaries) is list and len(boundaries)==len(events),
         'carried resource exact original event prefix')
    owners=index['owners'];nodes=t.x.process.NODES
    need(type(owners) is list and len(owners)==len(nodes) and
         [v.get('identity',{}).get('node') for v in owners]==list(nodes),'carried resource exact original owners')
    need(type(closes) is list and all(type(v) is dict and v.get('node') in nodes for v in closes) and
         (not closes if life==1 else len(closes)==2*len(nodes)),'carried resource crash is not successful close')
    maximum=dict(metadata=0,staging=0,queued=0,leases=0);results=[]
    for owner in owners:
        node=owner['identity']['node'];files=c.inventory(history/f'life-{life}-opened'/node)
        need(set(owner)=={'identity','registeredAt','path','sha256'} and
             f.canonical(owner['identity'])==f.canonical(f.decode(files['node.gsr'],'records','NODE')['identity']) and
             owner['path']==node+'.json' and type(owner['registeredAt']) is int and
             owner['registeredAt']==next(i for i,v in enumerate(events) if v.get('node')==node),
             'carried resource original owner registration')
        raw,value=r.read(directory/owner['path'])
        need(sha(raw)==owner['sha256'],'carried resource original trace digest')
        need(tuple(value[k] for k in ('metadataLimit','stagingLimit','queueLimit'))==LIMITS,'carried resource unchanged configured limits')
        result=r.replay(value,require_closed=life==2);last=0;opened=0
        for at,(event,point) in enumerate(zip(events,boundaries)):
            need(type(point) is dict and set(point)=={'eventIndex','node','sequence','usage'} and
                 type(point['eventIndex']) is int and point['eventIndex']==at and point['node']==event.get('node'),
                 'carried resource original checkpoint owner')
            if event.get('node')!=node:continue
            seq=point['sequence'];need(type(seq) is int and last<=seq<value['transitions'],'carried resource checkpoint order')
            r.same_usage(point['usage'],value['changes'][seq]['usage']);last=seq
            if event['event']=='NODE_OPEN':
                opened+=1;need(event['counts']==point['usage']['counts'] and point['usage']['leases']>0,'carried resource original open usage')
        need(opened==1,'carried resource exact original open')
        close=None
        if life==2:
            rows=[v for v in closes if v['node']==node]
            # A node may finish closing while peers still drain. Its RETURNED
            # boundary binds the local final sequence, not the group's last event.
            own_count=rows[-1]['eventCount'] if rows else -1
            close=lifecycle(value,rows,node,last,own_count)
            need(0<=own_count<=len(events) and not any(v.get('node')==node for v in events[own_count:]),
                 'carried resource event after owner close')
            for row in rows:
                need(all((point['sequence']<=row['sequence'] if at<row['eventCount'] else point['sequence']>=row['sequence'])
                         for at,point in enumerate(boundaries) if point['node']==node),
                     'carried resource close event interval')
        else:need(not result['closed'],'carried resource crash prefix cannot claim drained')
        for key in maximum:maximum[key]=max(maximum[key],result['maximumObservedReservations'][key])
        results.append(dict(node=node,transitions=result['transitions'],lastEventSequence=last,closed=result['closed'],close=close,
            maximumObservedReservations=result['maximumObservedReservations'],maximumObservedCounts=result['maximumObservedCounts']))
    need({p.name for p in directory.iterdir()}=={'index.json','events.json','boundaries.json','closes.json',*(n+'.json' for n in nodes)},
         'carried resource exact lifetime inventory')
    return dict(life=life,pid=index['pid'],terminal=terminal,events=len(events),owners=results,maximumPerOwnerReservations=maximum)


def replay(root):
    root=Path(root);need({v.name for v in root.iterdir()}=={'history','resources'},'carried resource wrapper inventory')
    directory=root/'resources';need({v.name for v in directory.iterdir()}=={'life-1','life-2'},'carried resource exact two lifetimes')
    lives=[lifetime(directory/f'life-{life}',root/'history',life) for life in (1,2)]
    need(lives[0]['pid']!=lives[1]['pid'],'carried resource distinct processes')
    return dict(status='PARTIAL',lifetimes=lives,ownerLifetimes=8,normalOwnerCloses=4,crashedOwnerPrefixes=4,
        observedAccountingQualified=True,postCutTailObserved=False,physicalStorageQualified=False,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root);original=t.validate(root/'history');result=replay(root)
    need(collection.inventory(root)==before,'carried resource original changed')
    return dict(status='PARTIAL',original=original,resources=result,phase3Complete=False)


NEGATIVES={
    'process-pid': 'carried resource original process identity',
    'crash-labelled-closed': 'carried resource original process identity',
    'owner-storage': 'carried resource original owner registration',
    'registration-late': 'carried resource original owner registration',
    'limits-relabelled': 'carried resource unchanged configured limits',
    'truncated-trace': 'resource transitions incomplete observation',
    'failed-observer': 'resource transitions incomplete observation',
    'missing-transition': 'resource transitions complete sequence',
    'transition-gap': 'resource transitions exact event sequence',
    'charge-size': 'resource transitions derived usage',
    'event-omitted': 'carried resource exact original event prefix',
    'event-number-type': 'carried resource exact original event prefix',
    'checkpoint-owner': 'carried resource original checkpoint owner',
    'checkpoint-sequence': 'carried resource checkpoint order',
    'checkpoint-usage': 'resource transitions derived usage',
    'open-empty-checkpoint': 'carried resource original open usage',
    'crash-close': 'carried resource crash is not successful close',
    'close-missing': 'carried resource crash is not successful close',
    'close-reversed': 'carried resource exact close pair',
    'close-before-final': 'carried resource original close interval',
    'close-event-count': 'carried resource close event interval',
    'trace-unlinked': 'carried resource original trace digest',
    'extra-file': 'carried resource exact lifetime inventory',
}


def mutate(root,name):
    need(name in NEGATIVES,'carried resource unknown negative')
    life=2 if name in ('close-missing','close-reversed','close-before-final','close-event-count') else 1
    directory=Path(root)/'resources'/f'life-{life}';index=read(directory,'index.json',16384)
    target='index.json';value=index
    if name=='process-pid':index['pid']+=1
    elif name=='crash-labelled-closed':index['terminal']='CLOSED'
    elif name=='owner-storage':index['owners'][0]['identity']['storage']='other-original'
    elif name=='registration-late':index['owners'][0]['registeredAt']+=1
    elif name=='trace-unlinked':index['owners'][0]['sha256']='0'*64
    elif name=='extra-file':
        (directory/'extra.json').write_bytes(b'{}');return
    elif name in ('event-omitted','event-number-type','checkpoint-owner','checkpoint-sequence','checkpoint-usage','open-empty-checkpoint'):
        target='events.json' if name.startswith('event-') else 'boundaries.json';value=read(directory,target,32*r.MIB)
        if name=='event-omitted':value.pop()
        elif name=='event-number-type':value[0]['incarnation']=True
        elif name=='checkpoint-owner':value[0]['node']='not-original'
        elif name=='checkpoint-sequence':value[0]['sequence']=2**63-1
        elif name=='checkpoint-usage':value[0]['usage']['metadata']+=1
        else:
            events=read(directory,'events.json',32*r.MIB);at=next(i for i,v in enumerate(events) if v['event']=='NODE_OPEN')
            for point in value[:at+1]:
                if point['node']==events[at]['node']:point.update(sequence=0,usage=dict(r.EMPTY,counts={}))
    elif name in ('crash-close','close-missing','close-reversed','close-before-final','close-event-count'):
        target='closes.json';value=read(directory,target,65536)
        if name=='crash-close':value.append(dict(node='node-1',event='RETURNED'))
        elif name=='close-missing':value.pop()
        else:
            rows=[v for v in value if v['node']=='node-1']
            if name=='close-reversed':rows[1]['event']='BEGIN'
            elif name=='close-event-count':rows[0]['eventCount']=0
            else:rows[1].update(sequence=rows[0]['sequence'],usage=rows[0]['usage'])
    else:
        target='node-1.json';_,value=r.read(directory/target)
        if name=='limits-relabelled':value['stagingLimit']=512*r.MIB
        elif name=='truncated-trace':value['truncated']=True
        elif name=='failed-observer':value['failed']=True
        elif name=='missing-transition':value['changes'].pop()
        elif name=='transition-gap':value['changes'][1]['sequence']+=1
        else:
            change=next(v for v in value['changes'] if v['event']=='RESERVE' and v['added'][0]['unit']=='JOURNAL')
            change['added'][0]['bytes']-=1
    encoded=f.canonical(value);(directory/target).write_bytes(encoded)
    if target=='index.json':return
    keys={'events.json':'eventsSha256','boundaries.json':'boundariesSha256','closes.json':'closesSha256'}
    if target in keys:index[keys[target]]=sha(encoded)
    else:next(v for v in index['owners'] if v['path']==target)['sha256']=sha(encoded)
    (directory/'index.json').write_bytes(f.canonical(index))


def negative(root,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-carried-resource-negative-') as temporary:
        changed=Path(temporary)/'raw';shutil.copytree(root,changed);mutate(changed,name)
        need(collection.inventory(changed/'history')==before,'carried resource negative changed original history')
        try:replay(changed)
        except ValueError as error:need(str(error)==NEGATIVES[name],'carried resource wrong negative '+name+': '+str(error))
        else:raise ValueError('carried resource accepted mutation '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],originalHistoryUnchanged=True)


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root);history=collection.inventory(root/'history');results=[]
    for name in NEGATIVES:
        results.append(negative(root,history,name))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried resource qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full original storage/process/callback/network/export/floor/ledger replay; exact unchanged history inventory')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
