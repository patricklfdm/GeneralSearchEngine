"""Original owner budgets through carried application-ACK death and recovery.

Application storage/protocol/export/FLOOR/ledger replay is mandatory before the
shared resource decoder. An interrupted ACK is not a successful owner close or
publication. This component does not admit transient captures or a whole cohort.
"""
import argparse
import json
from pathlib import Path
import sys
from . import native_carried_application_retention as application
from . import native_carried_resource_evidence as resources

need=resources.need;collection=resources.collection
NEGATIVES=resources.NEGATIVES


def validate(root):
    root=Path(root);before=collection.inventory(root)
    original=application.validate(root/'history')
    result=resources.replay(root)
    need(collection.inventory(root)==before,'application resource original changed')
    return dict(status='PARTIAL',original=original,resources=result,phase3Complete=False)


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root)
    history=collection.inventory(root/'history');results=[]
    for name in NEGATIVES:
        results.append(resources.negative(root,history,name))
        print(json.dumps(dict(stage='application-resource-negative',case=name,
            completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application resource qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original application storage/process/protocol/export/floor/ledger replay; exact unchanged history inventory')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
