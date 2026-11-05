"""Bind original native events and disk identities to complete budget journals.

Accounting peaks include successful temporary reservations between callbacks.
Publication bytes still require their independent physical reader; this does
not establish every non-publication physical ownership/queue lifetime.
"""
import argparse
import json
from pathlib import Path

from . import resource_transitions as transitions
from . import publication_resource_evidence as publication

collection,need=transitions.collection,transitions.need
DIRECTORY='resource-transition-captures'


def load(root):
    root=Path(root);directory=root/DIRECTORY
    need(directory.is_dir() and not directory.is_symlink(),'native resources missing collection')
    index=collection.read_json(directory,'index.json',16384)
    need(type(index) is dict and set(index)=={'schema','root','eventsSha256','boundariesSha256','owners'} and
         index['schema']=='gse-v53-resource-capture-index-v1' and type(index['owners']) is list and
         1<=len(index['owners'])<=6,'native resources index')
    event_raw=collection.snapshot.s.regular(root/'events.json',collection.EVENT_BYTES)
    boundary_raw=collection.snapshot.s.regular(directory/'boundaries.json',collection.EVENT_BYTES)
    need(collection.digest(event_raw)==index['eventsSha256'] and collection.digest(boundary_raw)==index['boundariesSha256'],
         'native resources original event/boundary digest')
    events=collection.read_json(root,'events.json',collection.EVENT_BYTES)
    boundaries=collection.read_json(directory,'boundaries.json',collection.EVENT_BYTES)
    traces={};names={'index.json','boundaries.json'};total=len(boundary_raw)
    for owner in index['owners']:
        need(type(owner) is dict and set(owner)=={'identity','path','sha256','registeredAt'} and
             type(owner['identity']) is dict and type(owner['identity'].get('node')) is str,
             'native resources owner reference')
        node=owner['identity']['node'];name=node+'.json'
        need(node in {'node-'+str(i) for i in range(1,7)} and owner['path']==name and node not in traces,
             'native resources unique owner path')
        raw,value=transitions.read(directory/name);total+=len(raw)
        need(total<=256*transitions.MIB and collection.digest(raw)==owner['sha256'],'native resources trace digest/capacity')
        traces[node]=value;names.add(name)
    need({p.name for p in directory.iterdir()}==names,'native resources unobserved member')
    return index,traces,boundaries,events


def replay(index,traces,boundaries,events,identities,root):
    owners=index['owners'];nodes=[v['identity']['node'] for v in owners]
    need(index['root']==root and nodes==sorted(identities) and set(traces)==set(identities) and
         all(v['identity']==identities[v['identity']['node']] for v in owners),
         'native resources original complete identities')
    need(type(events) is list and type(boundaries) is list and 0<len(events)==len(boundaries)<=65536,
         'native resources complete event boundaries')
    registered={};results={}
    for owner in owners:
        node=owner['identity']['node'];start=owner['registeredAt']
        need(type(start) is int and 0<=start<len(events),'native resources registration position')
        registered[node]=start
        trace=traces[node]
        need((trace.get('metadataLimit'),trace.get('stagingLimit'),trace.get('queueLimit'))==
             (384*transitions.MIB,512*transitions.MIB,64*transitions.MIB),'native resources original limits')
        results[node]=transitions.replay(trace)
        need(results[node]['transitions']>1,'native resources unobserved budget lifetime')
    previous={n:0 for n in nodes};counts={n:0 for n in nodes}
    for at,(event,boundary) in enumerate(zip(events,boundaries)):
        need(type(event) is dict and event.get('node') in identities and type(event.get('event')) is str,
             'native resources original event owner')
        node=event['node'];rows=traces[node]['changes']
        need(type(boundary) is dict and set(boundary)=={'eventIndex','node','sequence','usage'} and
             type(boundary['eventIndex']) is int and boundary['eventIndex']==at and boundary['node']==node and
             type(boundary['sequence']) is int and previous[node]<=boundary['sequence']<len(rows) and at>=registered[node],
             'native resources exact event sequence')
        sequence=boundary['sequence'];transitions.same_usage(boundary['usage'],rows[sequence]['usage'])
        previous[node]=sequence;counts[node]+=1
    need(all(counts.values()),'native resources omitted owner events')
    return dict(status='PASS',owners=results,eventBoundaries=len(boundaries),ownerEvents=counts,
                nativeBudgetAccountingQualified=True,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def bind_publications(transactions,boundaries):
    count=0
    for transaction in transactions:
        for row in transaction:
            point=boundaries[row['eventIndex']]
            need(point['node']==row['node'] and publication.usage(point['usage'])==row['storage'],
                 'native resources original publication storage boundary')
            count+=1
    return count


def validate(directory,profile='stable',progress=None):
    root=Path(directory);before=collection.inventory(root)
    physical=publication.validate(root,profile,progress,resource_transitions=True)
    if profile=='stable':
        _,_,selection,identities=publication.native.physical(root,confirmed_retention=True)
        authority=selection['root'];preceding=physical
    elif profile=='5-REPLACE-required-four':
        from . import required_four_ledgers as ledgers
        preceding=ledgers.validate(root,progress)
        model=ledgers.maintenance.exports.control_reader(root).model
        network=ledgers.maintenance.exports.network.network
        identities=network.s.catalog.identities(model.states[-1]['identities']);authority=model.root
    else:raise ValueError('native resources unknown profile')
    index,traces,boundaries,events=load(root)
    result=replay(index,traces,boundaries,events,identities,authority)
    count=bind_publications(publication.collect(root,events),boundaries)
    transport=None;floors=None;receiving=None
    if profile=='5-REPLACE-required-four':
        from . import transport_resource_evidence
        wires=collection.read_json(root,'wire.json',collection.WIRE_BYTES)
        # Attempts that never reached a connected wire boundary must remain
        # explicit gaps, not be assigned to a later identical connected retry.
        transport=transport_resource_evidence.replay(events,wires,traces,boundaries,identities,authority,require_all_frames=False)
        from . import floor_resource_evidence, receive_resource_evidence
        reader=floor_resource_evidence.maintenance.Replay(root);reader.run()
        need(reader.events==events,'native resources original maintenance event input')
        floors=floor_resource_evidence.replay(floor_resource_evidence.plans(reader),events,traces,boundaries)
        receiving=receive_resource_evidence.replay(receive_resource_evidence.derive(reader),events,traces,boundaries)
    need(collection.inventory(root)==before,'native resources original changed')
    return dict(result,scope='native-owner-accounting-with-original-publication-boundaries',profile=profile,
                precondition=preceding,publicationResources=physical,publicationBoundaries=count,transportResources=transport,
                floorResources=floors,receivingResources=receiving,
                physicalPeakQualified=False,controlLifetimesQualified=False,finalSourceCohortQualified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root')
    p.add_argument('--profile',choices=('stable','5-REPLACE-required-four'),default='stable');a=p.parse_args()
    print(json.dumps(validate(a.root,a.profile),sort_keys=True))
