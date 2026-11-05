"""Reconstruct charged extents at every observed resource mutation.

This is accounting observation, not independent physical-file authority or a
proof that every runtime owner was instrumented. Whole-history admission must
bind the per-owner traces and original files separately.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from . import joining_history_run as collection
from .membership_model import need

MIB=1024*1024
COUNTS=dict(GENERATION=2,SOURCE=6,LEARNER=1,JOURNAL=1,CATALOG=1,MISC=1,APPLICATION=7,CONTROL=256,WAITER=64)
BYTES={**dict.fromkeys(('GENERATION','SOURCE','LEARNER','JOURNAL'),32*MIB),
       'CATALOG':2*MIB,'MISC':2*MIB,'APPLICATION':64*MIB,'CONTROL':8*MIB,'WAITER':0}
META={'GENERATION','SOURCE','LEARNER','JOURNAL','CATALOG','MISC'}
STAGING={'SOURCE','LEARNER','APPLICATION'}
PROTECTED={'JOURNAL','CATALOG','MISC'}
EVENTS={'START','RESERVE','RELEASE','CONTROL_GROW','APPLICATION_MAXIMUM','STORAGE_GROW','MISC_GROW',
        'GENERATION_CLAIM','SOURCE_CLAIM','GENERATION_CANCEL','SOURCE_CANCEL','GENERATION_COMMIT','SOURCE_COMMIT',
        'GENERATION_RELOAD','EXTEND_BEGIN','EXTEND_COMMIT','EXTEND_ROLLBACK','TRANSFER','REPLACE'}
EMPTY=dict(metadata=0,staging=0,queued=0,leases=0,counts={})


def key(charge):return charge['unit'],charge['owner']


def order_key(charge):return tuple(v.encode('utf-16-be','surrogatepass') for v in key(charge))


def charges(values):
    need(type(values) is list and len(values)<=sum(COUNTS.values()),'resource transitions charge collection')
    previous=None
    for value in values:
        need(type(value) is dict and set(value)=={'unit','owner','bytes','claimSource'} and
             type(value['unit']) is str and value['unit'] in COUNTS and
             type(value['owner']) is str and 0<len(value['owner'].encode('utf-16-le','surrogatepass'))<=256 and
             type(value['bytes']) is int and 0<=value['bytes']<=BYTES[value['unit']] and
             type(value['claimSource']) is str and len(value['claimSource'].encode('utf-16-le','surrogatepass'))<=256,'resource transitions charge shape')
        unit=value['unit']
        need((unit in ('GENERATION','SOURCE') and value['bytes']==0) if value['claimSource'] else
             (value['bytes']==0 if unit=='WAITER' else value['bytes']>0),'resource transitions charge extent')
        current=order_key(value);need(previous is None or previous<current,'resource transitions ordered unique charges');previous=current
    return values


def usage(state,limits):
    counts=Counter();metadata=staging=queued=protected=0;claimed=set()
    for value in state.values():
        unit,owner=key(value);size=value['bytes'];counts[unit]+=1
        if value['claimSource']:
            source=state.get(('LEARNER',value['claimSource']))
            need(source is not None and not source['claimSource'] and value['claimSource'] not in claimed,
                 'resource transitions live original claim source')
            claimed.add(value['claimSource']);continue
        if unit in META:metadata+=size
        if unit in STAGING:staging+=size
        if unit=='CONTROL':queued+=size
        if unit in PROTECTED:protected+=size
    need(all(count<=COUNTS[unit] for unit,count in counts.items()) and metadata<=limits[0] and
         staging<=limits[1] and queued<=limits[2] and metadata+36*MIB-protected<=limits[0],
         'resource transitions capacity or completion headroom')
    return dict(metadata=metadata,staging=staging,queued=queued,leases=sum(counts.values()),counts=dict(counts))


def same_usage(actual,expected):
    need(type(actual) is dict and set(actual)==set(EMPTY) and
         all(type(actual[k]) is int for k in ('metadata','staging','queued','leases')) and type(actual['counts']) is dict and
         all(type(k) is str and type(v) is int for k,v in actual['counts'].items()) and actual==expected,
         'resource transitions derived usage')


def operation(event,removed,added,before,after):
    ordinary=lambda rows:all(not v['claimSource'] for v in rows)
    pairs=(len(removed)==len(added) and all(key(a)==key(b) and not a['claimSource'] and not b['claimSource'] for a,b in zip(removed,added)))
    if event=='RESERVE':valid=not removed and len(added)==1 and ordinary(added)
    elif event=='RELEASE':valid=len(removed)==1 and ordinary(removed) and not added
    elif event.endswith('_CLAIM'):
        valid=not removed and len(added)==1 and added[0]['unit']==event.split('_')[0] and bool(added[0]['claimSource'])
    elif event.endswith('_CANCEL'):
        valid=len(removed)==1 and removed[0]['unit']==event.split('_')[0] and bool(removed[0]['claimSource']) and not added
    elif event in ('GENERATION_COMMIT','SOURCE_COMMIT'):
        claims=[v for v in removed if v['claimSource']];sources=[v for v in removed if not v['claimSource']]
        valid=(len(removed)==2 and len(claims)==len(sources)==len(added)==1 and claims[0]['unit']==event.split('_')[0] and
               key(sources[0])==('LEARNER',claims[0]['claimSource']) and
               added[0]==dict(claims[0],bytes=sources[0]['bytes'],claimSource=''))
    elif event in ('CONTROL_GROW','APPLICATION_MAXIMUM','STORAGE_GROW','MISC_GROW'):
        units={'CONTROL_GROW':{'CONTROL'},'APPLICATION_MAXIMUM':{'APPLICATION'},
               'STORAGE_GROW':{'GENERATION','SOURCE','LEARNER','APPLICATION'},'MISC_GROW':{'MISC'}}[event]
        valid=pairs and len(removed)<=1 and all(a['unit'] in units and b['bytes']>=a['bytes'] for a,b in zip(removed,added))
        valid=valid and any(v['unit'] in units and not v['claimSource'] for v in after.values())
        if event=='APPLICATION_MAXIMUM':valid=valid and any(v['unit']=='APPLICATION' and v['bytes']==64*MIB for v in after.values())
    elif event in ('GENERATION_RELOAD','EXTEND_ROLLBACK'):
        units={'GENERATION','MISC','APPLICATION'} if event=='GENERATION_RELOAD' else {'GENERATION','SOURCE','APPLICATION'}
        valid=pairs and all(a['unit'] in units and b['bytes']<=a['bytes'] for a,b in zip(removed,added))
    elif event=='EXTEND_BEGIN':valid=not removed and not added
    elif event=='EXTEND_COMMIT':
        valid=(not removed and not added or len(removed)==len(added)==1 and
               removed[0]['unit']==added[0]['unit']=='APPLICATION' and removed[0]['bytes']==added[0]['bytes']==64*MIB and
               ordinary(removed+added))
    elif event=='TRANSFER':
        valid=ordinary(removed+added) and all(v['unit'] not in ('CONTROL','WAITER') for v in removed+added) and \
              Counter((v['unit'],v['bytes']) for v in removed)==Counter((v['unit'],v['bytes']) for v in added)
    elif event=='REPLACE':
        valid=ordinary(list(before.values())+list(after.values())) and len(after)<=32 and \
              all(v['unit'] not in ('CONTROL','WAITER') for v in list(before.values())+list(after.values()))
    else:valid=event=='START' and not before and not after and not removed and not added
    need(valid,'resource transitions operation delta: '+event)


def replay(value,*,require_closed=True):
    need(type(require_closed) is bool,'resource transitions closure option')
    fields={'schema','metadataLimit','stagingLimit','queueLimit','transitions','truncated','failed','changes','current'}
    need(type(value) is dict and set(value)==fields and value['schema']=='gse-v53-resource-transitions-v1',
         'resource transitions schema')
    limits=tuple(value[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
    need(all(type(v) is int for v in limits) and 36*MIB<=limits[0]<=384*MIB and 0<limits[1]<=2**63-1 and 0<limits[2]<=64*MIB,
         'resource transitions limits')
    need(value['truncated'] is False and value['failed'] is False,'resource transitions incomplete observation')
    rows=value['changes'];need(type(rows) is list and 0<len(rows)<=262144 and type(value['transitions']) is int and
                             value['transitions']==len(rows),'resource transitions complete sequence')
    state={};group=None;maximum=dict(metadata=0,staging=0,queued=0,leases=0);counts=Counter();events=Counter()
    for index,row in enumerate(rows):
        need(type(row) is dict and set(row)=={'sequence','event','removed','added','usage'} and
             type(row['sequence']) is int and row['sequence']==index and type(row['event']) is str and row['event'] in EVENTS and
             ((row['event']=='START')==(index==0)),'resource transitions exact event sequence')
        removed=charges(row['removed']);added=charges(row['added']);before=dict(state)
        for old in removed:
            need(state.pop(key(old),None)==old,'resource transitions original removed charge')
        for new in added:
            need(key(new) not in state,'resource transitions occupied added charge');state[key(new)]=new
        operation(row['event'],removed,added,before,state)
        if row['event']=='EXTEND_BEGIN':
            need(group is None,'resource transitions overlapping expansion');group=dict(state)
        elif row['event'] in ('EXTEND_COMMIT','EXTEND_ROLLBACK'):
            need(group is not None,'resource transitions expansion without original')
            if row['event']=='EXTEND_ROLLBACK':need(state==group,'resource transitions exact expansion rollback')
            group=None
        elif group is not None:
            need(row['event'] in ('RESERVE','STORAGE_GROW','RELEASE'),'resource transitions interleaved expansion')
        derived=usage(state,limits);same_usage(row['usage'],derived);events[row['event']]+=1
        for name in maximum:maximum[name]=max(maximum[name],derived[name])
        for unit,count in derived['counts'].items():counts[unit]=max(counts[unit],count)
    same_usage(value['current'],derived)
    need(group is None,'resource transitions incomplete expansion')
    need(not require_closed or not state,'resource transitions outstanding charges at close')
    return dict(status='PASS',scope='one-observed-resource-accounting-lifetime',transitions=len(rows),events=dict(events),
                maximumObservedReservations=maximum,maximumObservedCounts=dict(counts),closed=not state,
                observedAccountingQualified=True,physicalStorageQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def validate(path):
    path=Path(path);value=collection.read_json(path.parent,path.name,128*MIB)
    return replay(value)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace');a=p.parse_args()
    print(json.dumps(validate(a.trace),sort_keys=True))
