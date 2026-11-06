"""Original application-crash maintenance files bound to their live resource owners.

The complete original five-capture prerequisite passes first. This entry binds
only its three maintenance families; interrupted application/old-end retirement
resource mapping and remaining transient families remain separate obligations.
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


def validate(root):
    root=Path(root);before=collection.inventory(root)
    original=prerequisite.validate(root)
    observed=root/'previous/previous/observed'
    projected=shared.project(observed,plans(observed),families=FAMILIES)
    need(projected['expectedCallbacks']==original['maintenance']['capturedPrefixes'],
         'application coverage original capture count')
    need(collection.inventory(root)==before,'application coverage original changed')
    return dict(status='PARTIAL',original=original,coverage=projected,
        capturedCallbackBytesQualified=True,captureScope='application-maintenance-three-families',
        allSevenFamiliesCaptured=False,applicationAndRetirementChargeBindingQualified=False,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def qualify(root):
    root=Path(root);before=collection.inventory(root);original=validate(root)
    observed=root/'previous/previous/observed';rows=plans(observed)
    ordinals=shared.coverage.ordinal_plans(rows);results=[]
    targets=shared.ownership_targets(original['coverage'],families=FAMILIES)
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
                              total=len(OWNER_CASES),case=case)),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application coverage qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original application/old-end/maintenance captures; unchanged physical/event/checkpoint inputs; balanced accounting')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
