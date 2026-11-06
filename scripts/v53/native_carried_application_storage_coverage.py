"""Original application-crash maintenance files bound to their live resource owners.

The complete original five-capture prerequisite passes first. The default binds
three maintenance families. The explicit application option also binds original
first-ACK and old-end retirement callbacks; remaining families stay unqualified.
"""
import argparse
import json
from pathlib import Path
import sys
from . import native_carried_application_maintenance_prefixes as prerequisite
from . import native_carried_storage_coverage as shared

need=shared.need;collection=prerequisite.collection
FAMILIES='retirement-floor-campaign'
OWNER_CASES=shared.OWNER_CASES-{'replay-input'}


def plans(observed):
    parts=prerequisite.plans(observed)
    need(set(parts)==set(prerequisite.FAMILIES),'application coverage complete maintenance plans')
    return sorted((row for part in parts.values() for row in part),key=lambda v:(v['life'],v['eventIndex']))


def application_plans(observed):
    parts=prerequisite.plans(observed)
    need(set(parts)==set(prerequisite.FAMILIES),'application coverage complete maintenance plans')
    parts['application']=[dict(row,life=1) for row in prerequisite.prerequisite.prerequisite.plans(observed)]
    parts['old-end']=prerequisite.prerequisite.plans(observed)
    need(all(parts.values()),'application coverage nonempty captured families')
    return parts


def captured_projection(observed,parts,original):
    """The exact five admitted families, not all callbacks in the process."""
    need(set(parts)==set(prerequisite.FAMILIES)|{'application','old-end'},'application coverage exact five families')
    counts={family:value['capturedPrefixes'] for family,value in original['maintenance']['families'].items()}
    counts.update(application=original['original']['original']['application']['capturedPrefixes'],
                  **{'old-end':original['original']['retirement']['lifetime']['capturedPrefixes']})
    need(all(len(parts[family])==count and count>0 for family,count in counts.items()),
         'application coverage exact family capture counts')
    rows=sorted((row for part in parts.values() for row in part),key=lambda v:(v['life'],v['eventIndex']))
    ordinals=shared.coverage.ordinal_plans(rows);owners=[]
    maintenance=[row for family in prerequisite.FAMILIES for row in parts[family]]
    for life in (1,2):
        directory=Path(observed)/f'resources/life-{life}'
        events=shared.resource.read(directory,'events.json',32*1024*1024)
        boundaries=shared.resource.read(directory,'boundaries.json',32*1024*1024)
        shared.complete_callbacks(maintenance,events,life,families=FAMILIES)
        for node in shared.r.forces.process.NODES:
            _,trace=shared.coverage.t.read(directory/(node+'.json'))
            owners.append(shared.coverage.bind(rows,trace,events,boundaries,node,life,closed=life==2,ordinals=ordinals))
    need(sum(v['callbacks'] for v in owners)==len(rows),'application coverage complete owner assignment')
    return dict(status='PARTIAL',expectedCallbacks=len(rows),owners=owners,families='application-five-captured-families',
                capturedFamilyCounts=counts,capturedBytesQualified=False,wholeRuntimeResourcesQualified=False,
                cohortAdmitted=False,phase3Complete=False)


def validate(root,*,include_application=False):
    root=Path(root);before=collection.inventory(root)
    original=prerequisite.validate(root)
    observed=root/'previous/previous/observed'
    if include_application:projected=captured_projection(observed,application_plans(observed),original)
    else:
        projected=shared.project(observed,plans(observed),families=FAMILIES)
        need(projected['expectedCallbacks']==original['maintenance']['capturedPrefixes'],
             'application coverage original capture count')
    need(collection.inventory(root)==before,'application coverage original changed')
    return dict(status='PARTIAL',original=original,coverage=projected,
        capturedCallbackBytesQualified=True,captureScope='application-five-captured-families' if include_application else 'application-maintenance-three-families',
        allSevenFamiliesCaptured=False,applicationAndRetirementChargeBindingQualified=include_application,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def qualify(root,*,include_application=False):
    root=Path(root);before=collection.inventory(root);original=validate(root,include_application=include_application)
    observed=root/'previous/previous/observed'
    rows=(sorted((row for part in application_plans(observed).values() for row in part),key=lambda v:(v['life'],v['eventIndex']))
          if include_application else plans(observed))
    ordinals=shared.coverage.ordinal_plans(rows);results=[]
    targets=(shared.ownership_targets(original['coverage']) if include_application else
             shared.ownership_targets(original['coverage'],families=FAMILIES))
    for case,target in sorted(targets.items()):
        life,node=target['life'],target['node'];directory=observed/f'resources/life-{life}'
        events=shared.resource.read(directory,'events.json',32*1024*1024)
        boundaries=shared.resource.read(directory,'boundaries.json',32*1024*1024)
        _,trace=shared.coverage.t.read(directory/(node+'.json'))
        changed=shared.rename_owner(trace,target['unit'],target['owner'])
        need(shared.coverage.t.replay(changed,require_closed=life==2)==
             shared.coverage.t.replay(trace,require_closed=life==2),'application coverage mutation changed accounting totals')
        try:shared.coverage.bind(rows,changed,events,boundaries,node,life,closed=life==2,ordinals=ordinals)
        except ValueError as error:
            need(str(error)=='storage coverage original charge owner','application coverage unrelated negative '+case+': '+str(error))
        else:raise ValueError('application coverage accepted unrelated owner '+case)
        results.append(dict(case=case,**target,status='REJECTED',reason='storage coverage original charge owner',
                            balancedOriginalTotals=True,mutationScope='in-memory-resource-owner'))
        print(json.dumps(dict(stage='application-maintenance-ownership-negative',completed=len(results),
                              total=len(targets),case=case)),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application coverage qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original application/old-end/maintenance captures; unchanged physical/event/checkpoint inputs; balanced accounting')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--include-application',action='store_true',help='also bind first-ACK and old-end retirement inventories')
    args=parser.parse_args();print(json.dumps((qualify if args.qualify else validate)(args.root,include_application=args.include_application),sort_keys=True))
