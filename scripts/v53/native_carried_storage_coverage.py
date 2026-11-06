"""Compose admitted carried file inventories with their original owner budgets.

The complete seven-collector prerequisite is mandatory. Projection helpers do
not admit captured bytes; even full callback coverage is not every internal write.
"""
import argparse
import json
from pathlib import Path
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
