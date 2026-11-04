"""Semantic replay of the native five-member replacement requiring four voters.

Old voters 1/2/3 and joining voter 6 are reachable; common voters 4/5 are
offline. This is an explicit development topology, not another frozen profile
or a claim of complete physical/network/process qualification.
"""
import argparse
import itertools
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_catalog_evidence as c
from . import joining_publication_evidence as publication

OLD = ['node-1', 'node-2', 'node-3', 'node-4', 'node-5']
NEW = ['node-1', 'node-2', 'node-4', 'node-5', 'node-6']
OLD_LIVE = ['node-1', 'node-2', 'node-3']
JOINT_LIVE = ['node-1', 'node-2', 'node-3', 'node-6']
STABLE_LIVE = ['node-1', 'node-2', 'node-6']
PROFILE = '5-REPLACE-required-four'
need = c.need


def required_joint(view, voters):
    need(view['old'] == OLD and view['new'] == NEW and voters == JOINT_LIVE,
         'required-four exact joint topology')
    c.catalog.majority(view, voters)
    rejected = []
    for subset in itertools.combinations(voters, 3):
        try: c.catalog.majority(view, list(subset))
        except ValueError as error:
            need(str(error) == 'both governing majorities', 'required-four subset rejection')
            rejected.append(list(subset))
        else: raise ValueError('required-four three voters sufficient')
    return rejected


def validate(root, *, publication_observer=None):
    root = Path(root); inventory = c.collection.inventory(root)
    original = c.validate(root, size=5, kind='REPLACE', required_four=True)
    replay = c.Replay(root, size=5, kind='REPLACE', required_four=True)
    for index in range(1, 12): replay.step(index)
    need(original['slots'] == 11 and original['internalReadyCuts'] == [1, 3, 5, 7, 11],
         'required-four complete native history')
    # The phase reader has already checked each original local vote, receipt,
    # selected BASIS, installed source, reduced catalog and published checkpoint.
    # No result/profile label supplies any of the identities below.
    for index, parts in enumerate(replay.phases, 1):
        certificate = c.f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE', replay.root)
        expected = OLD_LIVE if index <= 9 else JOINT_LIVE if index == 10 else STABLE_LIVE
        for phase in ('accepts', 'proofs'):
            need([v['voter'] for v in certificate[phase]] == expected,
                 'required-four actual phase voters')
    subsets = required_joint(replay.states[9]['cut']['view'], JOINT_LIVE)
    need(replay.entries[9]['kind'] == 'FINAL' and replay.entries[10]['kind'] == 'BARRIER' and
         replay.states[10]['cut']['view']['old'] == replay.states[10]['cut']['view']['new'] == NEW,
         'required-four final successor')
    final_statement = c.f.encode('records', 'CHECKPOINT', replay.checkpoint(9, 10, 'MEMBERSHIP'))
    need(sorted(n for h, n in replay.acks if h == c.sha(final_statement)) == STABLE_LIVE,
         'required-four successor checkpoint voters')
    publications = publication.validate(root, size=5, kind='REPLACE', required_four=True,
                                        publication_observer=publication_observer)
    need(publications['publications'] == 34, 'required-four complete publications')
    need(c.collection.inventory(root) == inventory, 'required-four original changed')
    return dict(status='PASS', scope='required-four-native-semantic-chain', profile=PROFILE,
        original=original, publications=publications, jointVoters=JOINT_LIVE, refusedThreeVoterSubsets=subsets,
        successorVoters=STABLE_LIVE, departingCheckpointVotes=0,
        semanticChainQualified=True, publicationPhysicalQualified=True, completePhysicalQualified=False,
        forceAndNetworkQualified=False, processDeathQualified=False,
        finalSourceCohortQualified=False, phase3Complete=False)


NEGATIVES = {
    **{'missing-joint-proof-'+node: 'both governing majorities' for node in JOINT_LIVE},
    'departing-successor-ack': 'joining applied end voting eligibility',
    'missing-successor-ack': 'joining applied end voting eligibility',
    'joining-original-ack': 'joining retained pending ACK bytes',
    'offline-owner': 'joining offline voter changed',
    'missing-final-ready': 'joining complete round lifecycle',
    'ready-before-barrier': 'joining readiness before stable barrier',
    'departing-grant': 'joining exact publication inventory',
    'departing-future': 'joining exact publication inventory',
    'departing-ack-force': 'joining exact slot force order: node-3',
}


def mutate(root, case):
    need(case in NEGATIVES, 'required-four declared mutation')
    if case.startswith('missing-joint-proof-'):
        path = root/'applied-10/node-1/pending.accept'
        parts, values = c.disk.pending(path.read_bytes(), ('PROOF', 'CERTIFICATE'))
        value = values['CERTIFICATE']; node = case.removeprefix('missing-joint-proof-')
        value['proofs'] = [v for v in value['proofs'] if v['voter'] != node]
        parts['CERTIFICATE'] = c.f.encode('records', 'CERTIFICATE', value)
        path.write_bytes(c.packed_phases(parts))
    elif case == 'departing-successor-ack':
        (root/'applied-10/node-3/applied-end/ack.gsr').write_bytes(
            (root/'applied-10/node-1/applied-end/ack.gsr').read_bytes())
    elif case == 'missing-successor-ack': (root/'applied-10/node-1/applied-end/ack.gsr').unlink()
    elif case == 'joining-original-ack': (root/'joining-forced-ack.gsr').write_bytes(b'changed')
    elif case == 'offline-owner': (root/'applied-1/node-4/unexpected').write_bytes(b'changed')
    elif case in ('departing-grant', 'departing-future'):
        name = 'grants.gsr' if case == 'departing-grant' else publication.phases.future.FILE
        (root/'published-10/node-3'/name).write_bytes(b'changed')
    elif case == 'departing-ack-force':
        rows = c.collection.read_json(root, 'events.json', c.collection.EVENT_BYTES)
        at = next(i for i, r in enumerate(rows) if r.get('node') == 'node-3' and r.get('event') == 'APPLY_NONVOTING_DIRECTORY_FORCED')
        rows.insert(at, dict(rows[at], event='APPLY_ACK_FORCED'))
        (root/'events.json').write_bytes(c.f.canonical(rows))
    else: c.mutate(root, case)


def qualify(root, progress=None):
    root = Path(root); inventory = c.collection.inventory(root); original = validate(root); results = []
    for case, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-required-four-negative-') as temp:
            changed = Path(temp)/'raw'; shutil.copytree(root, changed); mutate(changed, case)
            try: validate(changed)
            except ValueError as error:
                need(str(error) == reason, 'required-four unrelated negative: '+case+': '+str(error))
            else: raise ValueError('required-four mutation accepted: '+case)
        row = dict(case=case, status='REJECTED', reason=reason); results.append(row)
        if progress: progress(row)
    need(c.collection.inventory(root) == inventory, 'required-four original changed')
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    import sys
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root')
    parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    progress = lambda row: print(json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)
    print(json.dumps(qualify(args.root, progress) if args.qualify else validate(args.root), sort_keys=True))
