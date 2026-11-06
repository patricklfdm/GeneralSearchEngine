"""Compose admitted carried file inventories with their original owner budgets.

The complete seven-collector prerequisite is mandatory. Projection helpers do
not admit captured bytes; even full callback coverage is not every internal write.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
from . import native_carried_replay_prefixes as prerequisite
from . import native_ledger_files as ledgers
from . import replica_storage_coverage as coverage
from . import native_carried_floor_prefixes as floor
from . import native_campaign_files as campaign
from . import native_completion_files as completion
from . import native_vote_files as votes

r=prerequisite.r;resource=prerequisite.resource;need=r.need


def plans(observed):
    history=Path(observed)/'history';result=r.forces.process.read(history/'process/result.json')
    parts=[[] for _ in range(6)]
    r.forces.replay(history,result['carriedKind'],result['cut'],prefixes=parts[0],floor_prefixes=parts[1],
                   campaign_prefixes=parts[2],vote_prefixes=parts[3],completion_prefixes=parts[4],replay_prefixes=parts[5])
    ledger,_=ledgers.plans(history,result['carriedKind'],result['cut']);parts.append(ledger)
    return sorted((v for part in parts for v in part),key=lambda v:(v['life'],v['eventIndex']))


def complete_callbacks(rows,events,life,*,families='all-seven'):
    need(families in ('all-seven','retirement-floor-campaign'),'storage coverage supported family scope')
    simple=('RETIREMENT_','SOURCE_RETIREMENT_','JOURNAL_ROTATION_',
            *(v for values in floor.KINDS.values() for v in values))
    expected={i for i,event in enumerate(events) if event['event'].startswith(simple)}
    expected.update(i for i,_,_ in campaign.observed(events))
    if families=='all-seven':
        expected.update(i for i,event in enumerate(events) if event['event'].startswith('REPLAY_') or
                        event['event'] in votes.POINTS or event['event'] in ledgers.POINTS)
        expected.update(i for i,_,_ in completion.observed(events))
    actual=[v['eventIndex'] for v in rows if v['life']==life]
    need(len(actual)==len(set(actual)) and set(actual)==expected,'storage coverage complete family callbacks: '+families)


def project(observed,rows,*,families='all-seven'):
    """Expected file extents plus real accounting; no captured-byte claim here."""
    ordinals=coverage.ordinal_plans(rows);owners=[]
    for life in (1,2):
        directory=Path(observed)/f'resources/life-{life}'
        events=resource.read(directory,'events.json',32*1024*1024)
        boundaries=resource.read(directory,'boundaries.json',32*1024*1024)
        complete_callbacks(rows,events,life,families=families)
        for node in r.forces.process.NODES:
            _,trace=coverage.t.read(directory/(node+'.json'))
            owners.append(coverage.bind(rows,trace,events,boundaries,node,life,closed=life==2,ordinals=ordinals))
    need(sum(v['callbacks'] for v in owners)==len(rows),'storage coverage complete owner assignment')
    return dict(status='PARTIAL',expectedCallbacks=len(rows),owners=owners,families=families,capturedBytesQualified=False,
                wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=r.collection.inventory(root)
    original=prerequisite.validate(root)  # Includes exact inventories, original events and every physical prefix.
    observed=root/'previous/previous/previous/previous/maintenance/prefixes/observed'
    result=project(observed,plans(observed))
    need(r.collection.inventory(root)==before,'storage coverage original changed')
    return dict(status='PARTIAL',original=original,coverage=result,capturedCallbackBytesQualified=True,
                wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


OWNER_CASES={'GENERATION','SOURCE','JOURNAL','MISC','generation-image','floor-image',
             'source-image','retirement-image','replay-input','applied-end'}


def ownership_targets(projected):
    """Pick actual required charges, never unbound reservations or invented files."""
    result={}
    for owner in projected['owners']:
        for point in owner['snapshots']:
            for charge in point['required']:
                unit,name=charge['unit'],charge['owner']
                label=unit
                if unit=='APPLICATION':
                    label=('generation-image' if name.startswith('generation-') else
                           'floor-image' if name.startswith('floor:') else
                           'retirement-image' if name.startswith('retirement:') else
                           'source-image' if re.fullmatch(coverage.UUID+':'+coverage.HEX,name) else
                           'replay-input' if name=='application-replay-input' else
                           'applied-end' if name=='applied-end' else None)
                need(label in OWNER_CASES,'storage coverage supported original owner case')
                result.setdefault(label,dict(life=owner['life'],node=owner['node'],unit=unit,owner=name,
                                            eventIndex=point['eventIndex'],point=point['point']))
    need(set(result)==OWNER_CASES,'storage coverage complete original owner cases')
    return result


def rename_owner(trace,unit,owner):
    """Preserve every usage/checkpoint while substituting one required owner."""
    replacement='unrelated-storage';key=(unit,owner);other=(unit,replacement)
    charges=[v for row in trace['changes'] for side in ('removed','added') for v in row[side]]
    need(key!=other and any(coverage.t.key(v)==key for v in charges) and
         all(coverage.t.key(v)!=other for v in charges),'storage coverage distinct original mutation owner')
    changed=copy.deepcopy(trace)
    for row in changed['changes']:
        for side in ('removed','added'):
            for charge in row[side]:
                if coverage.t.key(charge)==key:charge['owner']=replacement
            row[side].sort(key=coverage.t.order_key)
    return changed


def qualify(root):
    root=Path(root);before=r.collection.inventory(root);original=validate(root)
    observed=root/'previous/previous/previous/previous/maintenance/prefixes/observed'
    rows=plans(observed);ordinals=coverage.ordinal_plans(rows);results=[]
    for case,target in sorted(ownership_targets(original['coverage']).items()):
        life,node=target['life'],target['node'];directory=observed/f'resources/life-{life}'
        events=resource.read(directory,'events.json',32*1024*1024)
        boundaries=resource.read(directory,'boundaries.json',32*1024*1024)
        _,trace=coverage.t.read(directory/(node+'.json'))
        changed=rename_owner(trace,target['unit'],target['owner'])
        need(coverage.t.replay(changed,require_closed=life==2)==coverage.t.replay(trace,require_closed=life==2),
             'storage coverage mutation changed accounting totals')
        try:coverage.bind(rows,changed,events,boundaries,node,life,closed=life==2,ordinals=ordinals)
        except ValueError as error:
            need(str(error)=='storage coverage original charge owner','storage coverage unrelated negative '+case+': '+str(error))
        else:raise ValueError('storage coverage accepted unrelated owner '+case)
        results.append(dict(case=case,**target,status='REJECTED',reason='storage coverage original charge owner',
                            balancedOriginalTotals=True,mutationScope='in-memory-resource-owner'))
        print(json.dumps(dict(stage='storage-ownership-negative',completed=len(results),total=len(OWNER_CASES),case=case)),file=sys.stderr,flush=True)
    need(r.collection.inventory(root)==before,'storage coverage qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
                negativePrecondition='complete original seven-family captures; unchanged physical/event/checkpoint inputs; balanced accounting')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
