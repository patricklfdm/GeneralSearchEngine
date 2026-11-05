"""Observed owner accounting and independently derived publication headroom.

Call only after complete conditional-continuation physical replay. The original
prefix, unrelated control lifetimes and simultaneous runtime maxima stay outside
this scope. Every original open is counted, including maintenance and final reads.
"""
from collections import Counter
from pathlib import Path
from . import resource_transitions as r
from . import publication_resource_evidence as p
from . import carried_publication_evidence as c

need=r.need;read=p.history.read_json
DIRECTORY='completion-resources'


def schedule(profile):
    need(profile in ('capacity-231','replay-smoke-1'),'completion resources explicit profile')
    first=7*(231 if profile=='capacity-231' else 1)-1;nodes=['node-1','node-2','node-3'];rows=[]
    def group(label=''):
        rows.extend((node,label) for node in nodes)
    def maintenance():group();group()
    def publish(slot):
        for kind in ('accept','proof','certificate','apply','publish'):group(kind+'-'+str(slot))
        maintenance();rows.append(('node-1',''))
    def campaign(counter):
        maintenance();rows.append(('node-1',''))
        for kind in ('prepare','select','install'):group(kind+'-'+str(counter))
        group();group()
    publish(first);campaign(4);publish(first+1);campaign(5);publish(first+2);publish(first+3)
    if profile=='capacity-231':
        rows.extend((node,'') for node in nodes for _ in range(2))
    publish(first+4);group();return rows


def validate(root,profile,root_digest,calls):
    root=Path(root);directory=root/DIRECTORY;index=read(directory,'index.json',r.MIB)
    need(type(index) is dict and set(index)=={'schema','root','owners','eventsSha256','boundariesSha256'} and
         index['schema']=='gse-v53-completion-resources-v1' and index['root']==root_digest,'completion resources original root')
    owners=index['owners'];expected=schedule(profile)
    need(type(owners) is list and len(owners)==len(expected) and
         all(type(o) is dict and set(o)=={'scope','node','operation','path','sha256'} and
             (o['node'],o['operation'])==pair and o['scope']==f'open-{i:04d}' and o['path']==f'open-{i:04d}.json'
             for i,(o,pair) in enumerate(zip(owners,expected))),'completion resources original owner schedule')
    events=read(directory,'events.json',32*r.MIB);points=read(directory,'boundaries.json',32*r.MIB)
    need(p.sha(p.f.canonical(events))==index['eventsSha256'] and p.sha(p.f.canonical(points))==index['boundariesSha256'],
         'completion resources original event hashes')
    need(type(events) is list and 0<len(events)<=65536 and type(points) is list and len(events)==len(points),
         'completion resources complete checkpoints')
    by_owner={o['scope']:[] for o in owners};last=-1
    for at,(event,point) in enumerate(zip(events,points)):
        need(type(event) is dict and set(event)=={'node','event','scope'} and type(event['event']) is str and
             event['scope'] in by_owner and type(point) is dict and set(point)=={'eventIndex','sequence','usage'} and
             type(point['eventIndex']) is int and point['eventIndex']==at,'completion resources exact event/checkpoint')
        ordinal=int(event['scope'].split('-')[1]);owner=owners[ordinal]
        need(ordinal>=last and event['node']==owner['node'],'completion resources original event owner');last=ordinal
        by_owner[event['scope']].append((event,point))
    maximum=dict(metadata=0,staging=0,queued=0,leases=0);counts=Counter();transitions=0;observed_calls=[]
    for owner in owners:
        raw,value=r.read(directory/owner['path']);need(p.sha(raw)==owner['sha256'],'completion resources original trace hash')
        need(tuple(value.get(k) for k in ('metadataLimit','stagingLimit','queueLimit'))==(384*r.MIB,512*r.MIB,64*r.MIB),
             'completion resources frozen limits')
        result=r.replay(value);transitions+=result['transitions'];rows=by_owner[owner['scope']]
        names=[row[0]['event'] for row in rows]
        need(names and names[0]=='OWNER_OPEN_BEGIN' and names.count('OWNER_OPEN_BEGIN')==names.count('OWNER_OPEN_RETURNED')==1,
             'completion resources lifetime boundaries')
        previous=-1
        for event,point in rows:
            seq=point['sequence'];need(type(seq) is int and previous<=seq<len(value['changes']),'completion resources checkpoint sequence')
            r.same_usage(point['usage'],value['changes'][seq]['usage']);previous=seq
        need(rows[0][1]['sequence']==0 and rows[0][1]['usage']==r.EMPTY,'completion resources original empty start')
        returned=rows[names.index('OWNER_OPEN_RETURNED')][1]['usage']['counts']
        need(returned.get('JOURNAL')==1 and returned.get('MISC')==1 and returned.get('GENERATION',0)>0,
             'completion resources opened original storage')
        if owner['operation']:
            observed_calls.append(dict(operation=owner['operation'],node=owner['node'],events=[n for n in names if not n.startswith('OWNER_OPEN_')]))
        for key in maximum:maximum[key]=max(maximum[key],result['maximumObservedReservations'][key])
        for key,count in result['maximumObservedCounts'].items():counts[key]=max(counts[key],count)
    need(observed_calls==calls,'completion resources original call correspondence')
    need({v.name for v in directory.iterdir()}=={'index.json','events.json','boundaries.json',*(o['path'] for o in owners)},
         'completion resources exact inventory')
    # Owning physical replay has already derived all these before/after files.
    # Load one original pair at a time; never retain every large prefix in memory.
    transactions=p.collect(root,events);first=7*(231 if profile=='capacity-231' else 1)-1
    expected=[(node,slot) for slot in range(first,first+5) for node in ('node-1','node-2','node-3')]
    need(len(transactions)==len(expected),'completion resources exact publications')
    publication_max=dict(metadata=0,staging=0,applications=0,sources=0)
    for transaction,(node,slot) in zip(transactions,expected):
        before=c.inventory(root/f'slot-{slot}-applied'/node);after=c.inventory(root/f'slot-{slot}-published'/node)
        result=p.compare([transaction],{(node,slot):(before,after)})
        for row in transaction:
            need(row['usageBefore']==row['usageAfter']==points[row['eventIndex']]['usage'],
                 'completion resources publication checkpoint binding')
        for key in publication_max:publication_max[key]=max(publication_max[key],result['maximumObservedStorage'][key])
    return dict(status='PASS',scope='conditional-owner-accounting-and-publication-storage',ownerLifetimes=len(owners),
                mutations=transitions,eventCheckpoints=len(events),publications=len(transactions),publicationBoundaries=len(transactions)*len(p.POINTS),
                maximumObservedReservations=maximum,maximumObservedCounts=dict(counts),maximumPublicationStorage=publication_max,
                observedAccountingQualified=True,publicationStorageQualified=True,closeIntervalsQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


def check_summary(value,profile):
    fields={'status','scope','ownerLifetimes','mutations','eventCheckpoints','publications','publicationBoundaries',
            'maximumObservedReservations','maximumObservedCounts','maximumPublicationStorage','observedAccountingQualified',
            'publicationStorageQualified','closeIntervalsQualified','wholeRuntimeResourcesQualified','phase3Complete'}
    need(type(value) is dict and set(value)==fields and value['status']=='PASS' and
         value['scope']=='conditional-owner-accounting-and-publication-storage' and
         type(value['ownerLifetimes']) is int and value['ownerLifetimes']==len(schedule(profile)) and
         type(value['publications']) is int and value['publications']==15 and
         type(value['publicationBoundaries']) is int and value['publicationBoundaries']==165 and
         all(type(value[k]) is int and value[k]>value['ownerLifetimes'] for k in ('mutations','eventCheckpoints')) and
         all(value[k] is True for k in ('observedAccountingQualified','publicationStorageQualified')) and
         all(value[k] is False for k in ('closeIntervalsQualified','wholeRuntimeResourcesQualified','phase3Complete')),
         'completion resources qualification scope')
    maximum=value['maximumObservedReservations'];counts=value['maximumObservedCounts'];publication=value['maximumPublicationStorage']
    bounds=dict(metadata=384*r.MIB,staging=512*r.MIB,queued=64*r.MIB,leases=sum(r.COUNTS.values()))
    need(type(maximum) is dict and set(maximum)==set(bounds) and
         all(type(v) is int and 0<=v<=bounds[k] for k,v in maximum.items()) and
         type(counts) is dict and counts and all(k in r.COUNTS and type(v) is int and 0<v<=r.COUNTS[k] for k,v in counts.items()) and
         type(publication) is dict and set(publication)=={'metadata','staging','applications','sources'} and
         all(type(v) is int and 0<=v<=dict(metadata=bounds['metadata'],staging=bounds['staging'],applications=7,sources=6)[k]
             for k,v in publication.items()),'completion resources qualification maxima')
    need(publication['metadata']<=maximum['metadata'] and publication['staging']<=maximum['staging'] and
         publication['applications']<=counts.get('APPLICATION',0) and publication['sources']<=counts.get('SOURCE',0),
         'completion resources publication/accounting maxima')


VARIANTS={
    'resource-owner':'completion resources original owner schedule',
    'resource-root':'completion resources original root',
    'resource-limits':'completion resources frozen limits',
    'resource-checkpoint':'resource transitions derived usage',
    'resource-open':'completion resources lifetime boundaries',
    'resource-unclosed':'resource transitions outstanding charges at close',
    'publication-charge':'publication resources exact charges: PUBLICATION_VALIDATED',
    'publication-missing':'publication resources unobserved metadata',
    'publication-checkpoint':'completion resources publication checkpoint binding',
}


def mutate(copy,name):
    directory=Path(copy)/DIRECTORY;index=read(directory,'index.json',r.MIB)
    def write(path,value):path.write_bytes(p.f.canonical(value))
    if name=='resource-owner':index['owners'].pop()
    elif name=='resource-root':index['root']='0'*64
    elif name in ('resource-limits','resource-unclosed'):
        owner=index['owners'][0 if name=='resource-limits' else -1];path=directory/owner['path'];_,value=r.read(path)
        if name=='resource-limits':value['metadataLimit']+=1
        else:
            value['changes'].pop();value['transitions']-=1;value['current']=value['changes'][-1]['usage']
        write(path,value);owner['sha256']=p.sha(path.read_bytes())
    elif name in ('resource-checkpoint','resource-open'):
        file='boundaries.json' if name=='resource-checkpoint' else 'events.json';value=read(directory,file,32*r.MIB)
        if name=='resource-checkpoint':value[0]['sequence']=1
        else:next(v for v in value if v['event']=='OWNER_OPEN_RETURNED')['event']='OWNER_NOT_RETURNED'
        write(directory/file,value);index['boundariesSha256' if name=='resource-checkpoint' else 'eventsSha256']=p.sha((directory/file).read_bytes())
    elif name=='publication-checkpoint':
        events=read(directory,'events.json',32*r.MIB);points=read(directory,'boundaries.json',32*r.MIB)
        scope=next(v['scope'] for v in events if v['event']=='PUBLICATION_VALIDATED')
        start=next(i for i,v in enumerate(events) if v['scope']==scope and v['event']=='OWNER_OPEN_RETURNED')
        for i in range(start,len(events)):
            if events[i]['scope']==scope:points[i].update(sequence=points[start]['sequence'],usage=points[start]['usage'])
        write(directory/'boundaries.json',points);index['boundariesSha256']=p.sha((directory/'boundaries.json').read_bytes())
    elif name in ('publication-charge','publication-missing'):
        folder=Path(copy)/p.DIRECTORY;manifest=read(folder,'index.json',r.MIB)
        if name=='publication-missing':manifest['captures'].pop()
        else:
            ref=manifest['captures'][0];path=folder/ref['path'];value=read(folder,ref['path'],r.MIB)
            for key in ('usageBefore','usageAfter'):value[key]['staging']+=1
            write(path,value);ref['sha256']=p.sha(path.read_bytes())
        write(folder/'index.json',manifest)
    else:raise ValueError('unknown completion resource mutation')
    write(directory/'index.json',index)
