"""Continuous original peer ledgers for actual ADD/REPLACE profile owners.

Every semantic change consumes its own force transaction. Original grants,
installed/adopted generations and cold snapshots compare against the derived
chain, rather than initializing a new chain from reported endpoint bytes.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_maintenance_evidence as maintenance
from . import joining_peer_evidence as peer
from . import joining_same_view_authority as authority
from .joining_profile_evidence import PROFILES, topology

need,collection=maintenance.need,maintenance.collection
NEGATIVES=peer.NEGATIVES


class Replay(peer.Replay,maintenance.Replay):
    expected_write_counts=None

    def __init__(self,root,profile):
        maintenance.Replay.__init__(self,root,profile)
        self.initialize_chain()

    # Both parents capture floor inputs. Select the profile path once, preserving
    # original copy order and exact direct-owner accounting without duplicates.
    acquired=maintenance.Replay.acquired
    direct=maintenance.Replay.direct
    governing=maintenance.Replay.governing
    floors=maintenance.Replay.floors

    # A future covering copy protects the old cut but is not a same-cut peer
    # observation. This shared derivation preserves unresolved retention debt.
    floor=authority.PeerReplay.floor


def replay(root,profile):return Replay(root,profile).run()


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root)
    original=maintenance.validate(root,profile);result=replay(root,profile)
    need(collection.inventory(root)==before,'joining profile peer original changed')
    return dict(status='PARTIAL',scope='profile-original-continuous-peer-ledger',profile=profile,
                precondition=original,peers=result,peerLedgerCompositionQualified=True,
                learnerLedgerCompositionQualified=False,futureLedgerCompositionQualified=False,
                allMembershipProfilesQualified=False,processDeathQualified=False,phase3Complete=False)


def qualify(root,profile,progress=None):
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);results=[]
    protected={k:v for k,v in before['files'].items() if k!='events.json'}
    size,kind,_,_=topology(profile)
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-profile-peer-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:peer.mutate(changed,name,reader=Replay(changed,profile))
            except StopIteration as error:raise ValueError('joining profile peer missing negative target: '+name) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k!='events.json'}==protected and
                 after['directories']==before['directories'],'joining profile peer negative changed physical inputs')
            peer.n.network(changed,size=size,kind=kind)
            prior=maintenance.control.exports.replay(changed,profile);maintenance.control.replay(changed,profile,prior)
            maintenance.replay(changed,profile)
            try:replay(changed,profile)
            except ValueError as error:need(str(error)==reason,'joining profile unrelated peer negative: '+name+': '+str(error))
            else:raise ValueError('joining profile peer mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkExportControlMaintenancePrecondition='PASS',reason=reason))
        if progress:progress(dict(profile=profile,case=name,completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'joining profile peer qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    result=qualify(args.root,args.profile,progress) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))
