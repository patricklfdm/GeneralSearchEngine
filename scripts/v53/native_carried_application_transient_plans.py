"""Original vote, normal completion, ledger and replay states across ACK death.

The first interrupted application has its own existing sidecar; normal completion
belongs to life two. Old-end replay appears in two capture families and must agree
exactly before any later physical-union accounting. Projection is not capture.
"""
import argparse
import json
from pathlib import Path
from . import native_carried_application_maintenance_plans as maintenance
from . import native_carried_application_protocol as protocol
from . import native_carried_application_retention as retention
from . import native_ledger_files as ledger

need=protocol.need;collection=maintenance.collection


class Peers(ledger.Peers,retention.PeerReplay):pass
class Future(ledger.Future,retention.FutureReplay):pass


def plans(observed):
    history=Path(observed)/'history';result=protocol.p.process.read(history/'process/result.json')
    need(result['carriedKind'] in ('INTENT','FINAL') and result['cut']==protocol.application.CUT,
         'application transient exact original axis')
    parts={family:[] for family in ('votes','completion','replay')}
    protocol.forces.replay(history,result['carriedKind'],result['cut'],handlers=protocol,
        vote_prefixes=parts['votes'],completion_prefixes=parts['completion'],replay_prefixes=parts['replay'])
    parts['ledgers'],details=ledger.plans(history,result['carriedKind'],result['cut'],peer_factory=Peers,future_factory=Future,handlers=protocol)
    used=set()
    for family,rows in parts.items():
        need(rows and {v['life'] for v in rows}==({2} if family=='completion' else {1,2}),
             'application transient original lifetimes: '+family)
        for row in rows:
            key=(row['life'],row['eventIndex'])
            need(key not in used,'application transient duplicate callback ownership');used.add(key)
    return parts,details


def validate(observed):
    observed=Path(observed);before=collection.inventory(observed)
    original=maintenance.original.validate(observed);parts,details=plans(observed)
    need(collection.inventory(observed)==before,'application transient original changed')
    return dict(status='PARTIAL',original=original,ledger=details,
        projectedFamilies={family:dict(prefixes=len(rows),lifetimes=[dict(life=life,prefixes=sum(row['life']==life for row in rows))
            for life in sorted({v['life'] for v in rows})]) for family,rows in parts.items()},
        capturedBytesQualified=False,fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('observed');args=parser.parse_args()
    print(json.dumps(validate(args.observed),sort_keys=True))
