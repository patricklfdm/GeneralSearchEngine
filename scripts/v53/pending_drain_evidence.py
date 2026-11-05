"""Retained storage continuity across a failed listener close and external retry.

The authority in this component history is conditional. File hash observations
are compared, not promoted to independently replayed native membership history.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
from . import resource_transitions as t
from .membership_model import need

EVENTS=('BASELINE','REQUEST_HELD','OWNER_CLOSE_BEGIN','OWNER_CLOSE_FAILED',
        'RETRY_CLOSE_BEGIN','OWNER_CLOSE_RETURNED','FIXTURE_CLOSED')


def storage(values):return {t.key(v):v for v in values if v['unit'] not in ('CONTROL','WAITER')}


def error(listener,mode):
    return ('java.io.IOException: joining '+('checkpoint' if listener=='checkpoint' else 'progress')+' listener not drained'
            if mode=='callback' else 'java.lang.IllegalStateException: membership transport close interrupted')


def replay(trace,history,*,store=False):
    need(type(store) is bool,'pending drain scope option')
    accounting=t.replay(trace)
    fields={'schema','listener','mode','status','rows','inventories','completeMembershipHistory'}|({'locks'} if store else set())
    need(type(history) is dict and set(history)==fields and
         history['schema']==('gse-v53-store-drain-v1' if store else 'gse-v53-pending-drain-v1') and history['listener'] in ('checkpoint','head') and
         history['mode'] in ('callback','interrupt') and history['status']=='PASS' and history['completeMembershipHistory'] is False,
         'pending drain complete conditional history')
    points=history['rows'];changes=trace['changes']
    need(type(points) is list and len(points)==len(EVENTS),'pending drain exact call sequence')
    previous=-1
    for point,event in zip(points,EVENTS):
        need(type(point) is dict and set(point)=={'event','sequence','usage','error','interrupted'} and point['event']==event and
             type(point['sequence']) is int and previous<=point['sequence']<len(changes) and
             type(point['error']) is str and type(point['interrupted']) is bool,'pending drain exact call sequence')
        previous=point['sequence'];t.same_usage(point['usage'],changes[previous]['usage'])
        need(point['error']==(error(history['listener'],history['mode']) if event=='OWNER_CLOSE_FAILED' else ''),
             'pending drain exact failed close outcome')
        if history['mode']=='interrupt' and event in ('OWNER_CLOSE_BEGIN','OWNER_CLOSE_FAILED'):
            need(point['interrupted'],'pending drain interrupt preserved')
    seq={v['event']:v['sequence'] for v in points};state={};states={}
    for row in changes:
        for v in row['removed']:state.pop(t.key(v))
        for v in row['added']:state[t.key(v)]=v
        if row['sequence'] in seq.values():states[row['sequence']]=storage(state.values())
    baseline=states[seq['BASELINE']];held=states[seq['REQUEST_HELD']]
    need(baseline and held!=baseline and all(held.get(k)==v for k,v in baseline.items()),'pending drain original retained storage')
    for row in changes[seq['BASELINE']+1:seq['OWNER_CLOSE_FAILED' if store else 'OWNER_CLOSE_RETURNED']+1]:
        need(not (set(storage(row['removed']))&set(baseline)),'pending drain continuous baseline custody')
    for row in changes[seq['REQUEST_HELD']+1:seq['OWNER_CLOSE_FAILED']+1]:
        need(not storage(row['removed']+row['added']),'pending drain storage survives failed close')
    for row in changes[seq['OWNER_CLOSE_FAILED']+1:seq['OWNER_CLOSE_RETURNED']+1]:
        need(not storage(row['added']),'pending drain release-only retry')
    need(states[seq['OWNER_CLOSE_RETURNED']]==({} if store else baseline),
         'store drain resources released before return' if store else 'pending drain original baseline restored')
    if store:need(points[5]['usage']['leases']==0,'store drain resources released before return')
    need(seq['FIXTURE_CLOSED']==len(changes)-1 and not states[seq['FIXTURE_CLOSED']], 'pending drain final fixture close')
    inventories=history['inventories']
    need(type(inventories) is dict and set(inventories)=={'before','afterFailure','afterSuccess'},'pending drain file observations')
    before=inventories['before'];need(type(before) is list and 0<len(before)<=4096,'pending drain file observations')
    names=[]
    for row in before:
        need(type(row) is dict and set(row)=={'path','sha256'} and type(row['path']) is str and
             0<len(row['path'])<=1024 and not PurePosixPath(row['path']).is_absolute() and
             all(v not in ('','..','.') for v in row['path'].split('/')) and
             type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']), 'pending drain file observations')
        names.append(row['path'])
    need(len(set(names))==len(names) and before==inventories['afterFailure']==inventories['afterSuccess'],
         'pending drain unchanged retained files')
    if store:lock_count=locks(history['locks'])
    result=dict(status='PASS',scope='conditional-store-failed-close' if store else 'conditional-retained-owner-failed-close',listener=history['listener'],mode=history['mode'],
                retainedStorageLeases=len(held)-len(baseline),baselineStorageLeases=len(baseline),fileObservations=len(before),
                resourceTransitions=accounting['transitions'],failedCloseStorageContinuityQualified=True,
                physicalStorageQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
    if store:result.update(storeLockContinuityObserved=True,originalLocks=lock_count)
    return result


def locks(observations):
    need(type(observations) is dict and set(observations)=={'before','afterFailure','afterSuccess'},'store drain complete lock observations')
    original=None
    for event in ('before','afterFailure','afterSuccess'):
        rows=observations[event]
        need(type(rows) is list and len(rows)==3,'store drain exact original locks')
        identities=[]
        for row in rows:
            need(type(row) is dict and set(row)=={'scope','path','key','held'} and
                 type(row['scope']) is str and type(row['path']) is str and
                 0<len(row['path'])<=4096 and row['path'].startswith('/') and
                 type(row['key']) is str and 0<len(row['key'])<=256 and type(row['held']) is bool,'store drain exact original locks')
            identities.append({k:row[k] for k in ('scope','path','key')})
        need([v['scope'] for v in identities]==['operation','replica','typed'] and
             len({v['path'] for v in identities})==len({v['key'] for v in identities})==3,'store drain exact original locks')
        if original is None:original=identities
        need(identities==original,'store drain original lock identity')
        need(all(v['held']==(event!='afterSuccess') for v in rows),'store drain lock lifetime')
    return len(original)


def load(root):
    root=Path(root);inventory=t.collection.inventory(root)
    need(set(inventory['files'])=={'history.json','resources.json'} and not inventory['directories'],'pending drain exact original inventory')
    trace=t.read(root/'resources.json')[1]
    history=t.collection.read_json(root,'history.json',4*t.MIB)
    return trace,history


def validate(root,*,store=False):return replay(*load(root),store=store)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--store',action='store_true');args=parser.parse_args()
    print(json.dumps(validate(args.root,store=args.store),sort_keys=True))
