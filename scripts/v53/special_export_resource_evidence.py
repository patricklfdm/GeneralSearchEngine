"""Native vote and learner ROOT export accounting after original physical replay.

Direct probes are delimited inside real native histories. This does not bind
every network session to its export or establish a whole-runtime physical peak.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from uuid import UUID
from . import resource_transitions as t
from . import native_voting_evidence as vote
from . import learner_root_evidence as learner

need=t.need
FILES=('special-export-resources.json','special-export-history.json')
EVENTS=('BEGIN','OPENED','READS_FINISHED','RELEASE_BEGIN','INVALIDATED','RELEASED','REUSE_REFUSED','FINISHED')
NAME=re.compile(r'(vote-export|learner-root-export|prefix-export)-([0-9a-f]{64})-([0-9a-f-]{36})\Z')


def originals(root,family):
    if family=='vote':
        result=vote.validate(root);need(result['kind']=='DATA','special exports native DATA scope')
        files=vote.c.inventory(root/'after-voting/node-1')
        identity=vote.e.f.decode(files['node.gsr'],'records','NODE')['identity']
        proof=(root/'proof.gsr').read_bytes();fields=vote.e.f.decode(proof,'records','PROOF')
        accept=vote.e.f.encode('records','ACCEPT',{k:v for k,v in fields.items() if k!='accepts'})
        payload=(root/'payload.bin').read_bytes();expected={('vote-export',vote.e.digest(payload)):len(payload)}
        for phase,record in (('ACCEPT',accept),('PROOF',proof)):
            content=vote.e.f.canonical(dict(root=fields['root'],voter='node-1',incarnation=identity['storage'],phase=phase,record=vote.e.digest(record)))
            alias=vote.e.digest(vote.e.f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=vote.e.digest(content))))
            expected['vote-export',alias]=len(content)
    else:
        need(family=='learner-root','special exports family')
        result=learner.validate(root,additional=FILES,current_retention=True)
        files=learner.c.inventory(root/'before-learner-discovery/node-1');prefix,_,_=learner.c.current(files)
        expected={('learner-root-export',vote.e.digest(files['root.gsr'])):2*len(files['root.gsr'])+4096,
                  ('prefix-export',vote.e.digest(files[prefix+'generation.gsr'])):4096}
    return result,expected


def replay(trace,history,expected):
    account=t.replay(trace)
    need(type(history) is dict and set(history)=={'schema','family','status','cases','completeMembershipHistory'} and
         history['schema']=='gse-v53-special-export-resources-v1' and history['family'] in ('vote','learner-root') and
         history['status']=='PASS' and history['completeMembershipHistory'] is False,'special exports original scope')
    family=history['family'];roles={'vote-export':3} if family=='vote' else {'learner-root-export':1,'prefix-export':1}
    need(type(expected) is dict and all(type(k) is tuple and len(k)==2 and type(k[0]) is str and type(k[1]) is str and
         re.fullmatch('[0-9a-f]{64}',k[1]) and type(v) is int and v>0 for k,v in expected.items()) and
         Counter(k[0] for k in expected)==roles,'special exports original expectations')
    cases=history['cases'];rows=trace['changes'];previous=-1;wanted=set()
    need(type(cases) is list and len(cases)==2,'special exports complete case pair')
    for case,mode in zip(cases,('close','expiry')):
        need(type(case) is dict and set(case)=={'mode','events'} and case['mode']==mode and type(case['events']) is list and
             len(case['events'])==len(EVENTS),'special exports complete case pair')
        for event,name in zip(case['events'],EVENTS):
            need(type(event) is dict and set(event)=={'event','point'} and event['event']==name,'special exports exact call order')
            p=event['point'];need(type(p) is dict and set(p)=={'sequence','usage'} and type(p['sequence']) is int and
                0<=p['sequence']<len(rows) and p['sequence']>=previous,'special exports original boundaries')
            previous=p['sequence'];wanted.add(previous);t.same_usage(p['usage'],rows[previous]['usage'])
    states={};state={};changes=defaultdict(list)
    for row in rows:
        for side in ('removed','added'):
            for value in row[side]:
                key=t.key(value);changes[key].append((row['sequence'],row['event'],side))
                if side=='removed':state.pop(key)
                else:state[key]=value
        if row['sequence'] in wanted:states[row['sequence']]=dict(state)
    used=set()
    for case in cases:
        points={p['event']:p['point']['sequence'] for p in case['events']};begin=points['BEGIN'];end=points['FINISHED']
        base=states[begin];need(base,'special exports live native baseline');allocations={};claims={}
        for row in rows[begin+1:end+1]:
            need(not any(t.key(v) in base for v in row['added']+row['removed']),'special exports continuous original custody')
            for side in ('added','removed'):
                for value in row[side]:
                    match=NAME.fullmatch(value['owner'])
                    need(value['unit']=='CONTROL' and not value['claimSource'] and match is not None,'special exports observed binding')
                    role,reference,nonce=match.groups()
                    try:identifier=UUID(nonce)
                    except ValueError:raise ValueError('special exports observed binding') from None
                    need(identifier.int and str(identifier)==nonce,'special exports observed binding')
                    need((role,reference) in expected,'special exports original content binding')
                    need(value['bytes']==expected[role,reference],'special exports original extent')
                    key=t.key(value)
                    if side=='added':
                        need(row['event']=='RESERVE' and key not in used and (role,reference) not in claims,
                             'special exports unique immutable allocation')
                        allocations[key]=value;claims[role,reference]=key;used.add(key)
                    else:need(row['event']=='RELEASE' and key in allocations,'special exports original release')
        need(set(claims)==set(expected),'special exports complete acquisitions')
        for key in allocations:
            own=changes[key]
            need(len(own)==2 and own[0][1:]==('RESERVE','added') and own[1][1:]==('RELEASE','removed'),
                 'special exports unique immutable allocation')
            start,finish=own[0][0],own[1][0]
            need(begin<start<=points['OPENED'] and points['READS_FINISHED']<finish,'special exports overlapping reads')
            need(points['RELEASE_BEGIN']<finish<=points['RELEASED'],'special exports release inside call')
        opened=dict(base)
        opened.update(allocations)
        need(states[points['OPENED']]==states[points['READS_FINISHED']]==states[points['RELEASE_BEGIN']]==opened,
             'special exports complete overlapping custody')
        invalidated=opened if family=='learner-root' and case['mode']=='expiry' else base
        need(states[points['INVALIDATED']]==invalidated,'special exports expiry release policy')
        need(states[points['RELEASED']]==base and states[end]==base,'special exports original baseline restored')
        need(points['RELEASED']==points['REUSE_REFUSED']==end,'special exports no revival')
    return dict(status='PASS',scope='native-vote-or-root-direct-export-accounting',family=family,
                exportReservations=len(used),resourceTransitions=account['transitions'],exportReservationBindingsQualified=True,
                networkReservationCompositionQualified=False,expiryClockIndependentlyQualified=False,
                allExportFamiliesQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def load(root):
    root=Path(root);history=t.collection.read_json(root,FILES[1],t.MIB)
    need(type(history) is dict,'special exports original scope')
    original,expected=originals(root,history.get('family'))
    return (t.read(root/FILES[0])[1],history,expected),original


def validate(root):
    root=Path(root);before=t.collection.inventory(root);data,physical=load(root);result=replay(*data)
    need(before==t.collection.inventory(root),'special exports changed original')
    return dict(result,physical=physical)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args();print(json.dumps(validate(a.root),sort_keys=True))
