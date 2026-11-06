"""Coverage of existing native campaign/retirement/FLOOR captures, not all seven families."""
import argparse
import json
from pathlib import Path
from . import native_carried_campaign_prefixes as prerequisite
from . import native_carried_storage_coverage as m


def validate(root):
    root=Path(root);before=m.r.collection.inventory(root)
    original=prerequisite.validate(root)
    observed=root/'maintenance/prefixes/observed';history=observed/'history'
    result=m.r.forces.process.read(history/'process/result.json');parts=[[] for _ in range(3)]
    m.r.forces.replay(history,result['carriedKind'],result['cut'],prefixes=parts[0],floor_prefixes=parts[1],campaign_prefixes=parts[2])
    rows=sorted((v for part in parts for v in part),key=lambda v:(v['life'],v['eventIndex']))
    coverage=m.project(observed,rows,families='retirement-floor-campaign')
    m.need(m.r.collection.inventory(root)==before,'campaign storage coverage original changed')
    return dict(status='PARTIAL',original=original,coverage=coverage,capturedCallbackBytesQualified=True,
                captureScope='retirement-floor-campaign-only',allSevenFamiliesCaptured=False,
                wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
