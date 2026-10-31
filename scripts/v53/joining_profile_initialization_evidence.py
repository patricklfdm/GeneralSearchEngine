"""Profile-bound placement, custody retirement and native initialization replay.

The prefix is independently derived once per original/disposable history. Each
negative must pass its preceding stages before the designated rejection. This
does not qualify continuation, all control attempts, or complete Phase 3.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_initialization_evidence as initialization
from .joining_profile_evidence import PROFILES, topology

retirement = initialization.retirement
placement = retirement.placement
s, need = placement.s, placement.need
STAGES = ('placement', 'retirement', 'initialization')
READERS = dict(placement=placement, retirement=retirement, initialization=initialization)
NEGATIVES = {
    'placement': ('pending-retained-inode', 'adopted-manifest-forgery', 'premature-peer-ledger',
                  'custody-missing-pending', 'placement-move-order', 'joined-record-inode'),
    'retirement': ('deletion-live-generation', 'reservation-alias-images', 'native-journal-charge',
                   'predecessor-payload-survives', 'generation-inode-replaced', 'unowned-sidecar-file'),
    'initialization': ('head-foreign-owner', 'old-standalone-source-changed', 'seed-changed',
                       'initialized-learner-debt-lost', 'native-new-promise-changed', 'native-source-image-changed',
                       'native-extra-allocation', 'initialization-force-missing', 'repeated-basis-rewritten'),
}


def stages(root, profile):
    size, kind, _, _ = topology(profile)
    root = Path(root)
    placement.transition.publication.validate(root, size=size, kind=kind)
    replay = s.Replay(root, size=size, kind=kind)
    for index in range(1, 12): replay.step(index)
    replay.publication_receipts = placement.transition.publication.CheckpointReceipts(root, replay)
    history = placement.History(root, replay); history.run()
    owner = placement.Placement(root, history)
    yield 'placement', owner
    handoff = retirement.Retirement(root, owner)
    yield 'retirement', handoff
    yield 'initialization', initialization.Initialization(root, handoff)


def validate(root, profile):
    topology(profile); root = Path(root); original = s.collection.inventory(root)
    results = {name: reader.run() for name, reader in stages(root, profile)}
    need(tuple(results) == STAGES, 'joining profile initialization stages')
    need(s.collection.inventory(root) == original, 'joining profile initialization original changed')
    return dict(status='PARTIAL', profile=profile, scope='original-placement-retirement-native-initialization', gates=results,
        completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False,
        pendingQualification=['joining continuation/adoption', 'complete control attempts and export authority',
                              'maintenance and peer chain', 'process death', 'complete profile cohort', 'frozen mapping'])


def qualify(root, profile):
    size, kind, _, _ = topology(profile)
    root = Path(root); original_inventory = s.collection.inventory(root); original = validate(root, profile); results = []
    for target, cases in NEGATIVES.items():
        module = READERS[target]
        for case in cases:
            with tempfile.TemporaryDirectory(prefix='v53-joining-profile-init-') as temp:
                copied = Path(temp)/'raw'; shutil.copytree(root, copied)
                if target == 'initialization': module.mutate(copied, case, size=size, kind=kind)
                else: module.mutate(copied, case)
                reached = False; prior = ['publication', 'transition']
                for name, reader in stages(copied, profile):
                    if name != target:
                        reader.run(); prior.append(name); continue
                    reached = True
                    try: reader.run()
                    except ValueError as error:
                        need(str(error) == module.NEGATIVES[case],
                             'joining profile initialization unrelated negative: '+case+': '+str(error))
                    else: raise ValueError('joining profile initialization accepted mutation: '+case)
                    break
                need(reached, 'joining profile initialization missing rejection stage')
            results.append(dict(case=case, gate=target, status='REJECTED', reason=module.NEGATIVES[case], priorGates=prior))
    need(s.collection.inventory(root) == original_inventory, 'joining profile initialization original changed')
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root')
    parser.add_argument('--profile', required=True, choices=PROFILES); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root, args.profile), sort_keys=True))
