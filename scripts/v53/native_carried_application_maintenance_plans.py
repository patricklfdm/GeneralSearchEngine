"""Derive maintenance/campaign file plans for original application-ACK histories.

This is projection coverage, not writer-held capture qualification. The complete
original resource/history chain must pass before these plans earn any credit.
"""
import argparse
import json
from pathlib import Path
from . import native_carried_application_protocol as protocol
from . import native_carried_application_resources as original

need=protocol.need;collection=original.collection
FAMILIES={'retirement':'prefixes','floor':'floor_prefixes','campaign':'campaign_prefixes'}


def plans(observed):
    history=Path(observed)/'history';result=protocol.p.process.read(history/'process/result.json')
    need(result['carriedKind'] in ('INTENT','FINAL') and result['cut']==protocol.application.CUT,
         'application maintenance exact original axis')
    result_plans={family:[] for family in FAMILIES}
    protocol.forces.replay(history,result['carriedKind'],result['cut'],handlers=protocol,
        **{argument:result_plans[family] for family,argument in FAMILIES.items()})
    used=set()
    for family,rows in result_plans.items():
        need(rows and {row['life'] for row in rows}=={1,2},'application maintenance both original lifetimes: '+family)
        for row in rows:
            key=(row['life'],row['eventIndex'])
            need(key not in used,'application maintenance duplicate callback ownership');used.add(key)
    return result_plans


def validate(observed):
    observed=Path(observed);before=collection.inventory(observed)
    prerequisite=original.validate(observed);projected=plans(observed)
    need(collection.inventory(observed)==before,'application maintenance original changed')
    return dict(status='PARTIAL',original=prerequisite,
        projectedFamilies={key:dict(prefixes=len(rows),lifetimes=[dict(life=life,
            prefixes=sum(row['life']==life for row in rows)) for life in (1,2)]) for key,rows in projected.items()},
        originalCallbackCoverage=True,expectedFilesFromOriginal=True,capturedBytesQualified=False,
        fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,
        cohortAdmitted=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('observed');args=parser.parse_args()
    print(json.dumps(validate(args.observed),sort_keys=True))
