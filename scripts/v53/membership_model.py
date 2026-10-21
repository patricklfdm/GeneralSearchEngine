"""Exhaustive, finite quorum arithmetic and synthetic receipt-context checks.

This does NOT model elections, persistence, configuration activation, recovery or
liveness. A receipt is assumed to represent one authentic durable acknowledgement.
The dataclasses are research values, not a public API or proposed wire encoding.
"""
import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
from itertools import combinations, combinations_with_replacement
import json
from pathlib import Path
import subprocess


NODES = tuple(f'node-{i}' for i in range(1, 7))
MIN_VOTERS, MAX_VOTERS = 3, 5
STAGES = ('old', 'joint', 'new')
PHASES = ('accept', 'proof')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def configuration(nodes):
    need(type(nodes) is tuple and MIN_VOTERS <= len(nodes) <= MAX_VOTERS,
         'model configuration size/type')
    need(all(type(n) is str and n in NODES for n in nodes), 'model voter identity')
    need(nodes == tuple(sorted(set(nodes))), 'model voters must be distinct and ordered')
    return frozenset(nodes)


def transition_kind(old, new):
    before, after = configuration(old), configuration(new)
    added, removed = len(after - before), len(before - after)
    kinds = {(1, 0): 'add', (0, 1): 'remove', (1, 1): 'replace'}
    need((added, removed) in kinds, 'model requires one add/remove/replace')
    return kinds[(added, removed)]


def subsets(nodes):
    ordered = sorted(nodes)
    for size in range(len(ordered) + 1):
        for row in combinations(ordered, size):
            yield frozenset(row)


def majority(voters, witnesses):
    return len(voters & witnesses) > len(voters) // 2


def joint(old, new, witnesses):
    return majority(old, witnesses) and majority(new, witnesses)


def minimal_joint_quorums(old, new):
    """Independent construction: union one minimal majority from each side.

    Intentionally does not call majority() or joint(). The produced family may
    contain supersets; subset admission still gives the exact joint predicate.
    """
    return frozenset(
        frozenset(left) | frozenset(right)
        for left in combinations(sorted(old), len(old) // 2 + 1)
        for right in combinations(sorted(new), len(new) // 2 + 1)
    )


@dataclass(frozen=True)
class Claim:
    group: str
    history: str
    operation: str
    generation: int
    old: tuple
    new: tuple
    stage: str
    ballot: int
    proposer: str
    incarnation: str
    index: int
    entry_digest: str
    phase: str

    def validate(self):
        transition_kind(self.old, self.new)
        for label in ('group', 'history', 'operation', 'incarnation'):
            text = getattr(self, label)
            need(type(text) is str and 0 < len(text) <= 128 and text.isascii(),
                 'model context identity')
        for value in (self.generation, self.ballot, self.index):
            need(type(value) is int and 0 < value < (1 << 63), 'model positive counter')
        need(self.stage in STAGES and self.phase in PHASES, 'model certificate stage/phase')
        need(type(self.proposer) is str and self.proposer in set(self.old) | set(self.new),
             'model ballot proposer')
        need(type(self.entry_digest) is str and len(self.entry_digest) == 64 and
             all(c in '0123456789abcdef' for c in self.entry_digest), 'model entry digest')
        return self


@dataclass(frozen=True)
class Receipt:
    voter: str
    claim: Claim


def certified(expected, receipts):
    """Check exact context and distinct voters; never infer an actual disk force."""
    need(type(expected) is Claim, 'model expected claim')
    expected.validate()
    need(type(receipts) is tuple and len(receipts) <= len(NODES), 'model receipt bound/type')
    old, new = frozenset(expected.old), frozenset(expected.new)
    eligible = old if expected.stage == 'old' else new if expected.stage == 'new' else old | new
    voters = set()
    for row in receipts:
        need(type(row) is Receipt and type(row.claim) is Claim, 'model receipt type')
        row.claim.validate()
        need(row.claim == expected, 'foreign certificate context')
        need(type(row.voter) is str and row.voter in eligible, 'ineligible certificate voter')
        need(row.voter not in voters, 'duplicate certificate voter')
        voters.add(row.voter)
    witnesses = frozenset(voters)
    return joint(old, new, witnesses) if expected.stage == 'joint' else majority(eligible, witnesses)


def claim(old=NODES[:3], new=NODES[:4], *, stage='joint', phase='accept'):
    return Claim('group-a', 'history-a', 'operation-a', 1, old, new, stage,
                 2, old[0], 'incarnation-a', 7, 'a' * 64, phase)


def receipts(expected, nodes):
    return tuple(Receipt(n, expected) for n in sorted(nodes))


def require_certificate(expected, rows):
    need(certified(expected, rows), 'insufficient certificate quorum')


def context_negatives():
    """First validate originals, then alter one authority component per case."""
    expected = claim()
    rows = receipts(expected, NODES[:4])
    require_certificate(expected, rows)
    mutations = dict(group='group-b', history='history-b', operation='operation-b',
                     generation=2, old=NODES[1:4], new=NODES[:3] + (NODES[4],),
                     stage='new', ballot=3, proposer=NODES[1], incarnation='incarnation-b',
                     index=8, entry_digest='b' * 64, phase='proof')
    negatives = {}
    for name, value in mutations.items():
        foreign = replace(expected, **{name: value}).validate()
        negatives['foreign-' + name] = (expected, receipts(foreign, NODES[:4]))
    # An old-config-only voter must not count after finalization. That cannot be
    # checked by the quorum number alone, even with a correct receipt context.
    replacement = claim(NODES[:3], (NODES[0], NODES[1], NODES[3]), stage='new')
    require_certificate(replacement, receipts(replacement, replacement.new))
    negatives['removed-voter'] = (replacement, receipts(replacement, NODES[:3]))
    stable = replace(expected, stage='old')
    require_certificate(stable, receipts(stable, stable.old))
    negatives['learner-voter'] = (stable, receipts(stable, (NODES[0], NODES[3])))
    negatives['duplicate-voter'] = (stable, (Receipt(NODES[0], stable),) * 2)
    negatives['foreign-voter'] = (expected, rows + (Receipt('foreign-node', expected),))
    negatives['insufficient-quorum'] = (expected, receipts(expected, NODES[:2]))
    negatives['one-foreign-receipt'] = (expected, rows[:-1] + (replace(rows[-1], claim=replace(expected, ballot=3)),))
    results = {}
    for name, (wanted, changed) in negatives.items():
        try:
            require_certificate(wanted, changed)
        except ValueError as error:
            results[name] = str(error)
        else:
            raise ValueError('negative accepted: ' + name)
    return results


def explore(max_transitions=None):
    if max_transitions is not None:
        need(type(max_transitions) is int and max_transitions >= 0, 'model traversal limit')
    configs = [row for size in range(MIN_VOTERS, MAX_VOTERS + 1) for row in combinations(NODES, size)]
    pairs = []
    for old in configs:
        for new in configs:
            delta = (len(set(new) - set(old)), len(set(old) - set(new)))
            if delta in ((1, 0), (0, 1), (1, 1)):
                pairs.append((old, new))
    counts = dict(configurations=len(configs), expectedTransitions=len(pairs), transitions=0,
                  receiptSubsets=0, certificateChecks=0, intersectionChecks=0,
                  add=0, remove=0, replace=0)
    witnesses = {}
    for old, new in pairs:
        if max_transitions is not None and counts['transitions'] >= max_transitions:
            return dict(status='INCOMPLETE', execution='finite-quorum-arithmetic-only',
                        productionQualified=False, counts=counts, limit=max_transitions)
        before, after = frozenset(old), frozenset(new)
        union = before | after
        oracle = minimal_joint_quorums(before, after)
        accepted = []
        for votes in subsets(union):
            result = joint(before, after, votes)
            need(result == any(q <= votes for q in oracle), 'joint differs from independent construction')
            counts['receiptSubsets'] += 1
            if result:
                accepted.append(votes)
            details = dict(old=old, new=new, votes=sorted(votes))
            if not result and majority(union, votes):
                witnesses.setdefault('union-majority', details)
            if not result and (majority(before, votes) or majority(after, votes)):
                witnesses.setdefault('either-majority', details)
        need(bool(accepted), 'no joint quorum')
        old_quorums = [q for q in subsets(before) if majority(before, q)]
        new_quorums = [q for q in subsets(after) if majority(after, q)]
        for left, right in combinations_with_replacement(accepted, 2):
            need(bool(left & right), 'disjoint joint quorums')
            counts['intersectionChecks'] += 1
        for previous in old_quorums + new_quorums:
            for current in accepted:
                need(bool(previous & current), 'disjoint stable and joint quorums')
                counts['intersectionChecks'] += 1
        for left in old_quorums:
            for right in new_quorums:
                if not left & right:
                    witnesses.setdefault('direct-switch', dict(old=old, new=new,
                        oldVotes=sorted(left), newVotes=sorted(right)))
        # Check complete synthetic certificate context for both force phases and
        # all three logical views. This deliberately does not choose when a
        # distributed replica adopts any of those views.
        for stage, eligible in (('old', before), ('joint', union), ('new', after)):
            for phase in PHASES:
                expected = claim(old, new, stage=stage, phase=phase)
                for votes in subsets(eligible):
                    result = certified(expected, receipts(expected, votes))
                    family = oracle if stage == 'joint' else frozenset(
                        frozenset(q) for q in combinations(sorted(eligible), len(eligible) // 2 + 1))
                    need(result == any(q <= votes for q in family), 'certificate differs from independent construction')
                    counts['certificateChecks'] += 1
        counts['transitions'] += 1
        counts[transition_kind(old, new)] += 1
    need(set(witnesses) == {'direct-switch', 'union-majority', 'either-majority'}, 'missing arithmetic counterexample')
    negatives = context_negatives()
    return dict(schema='gse-v53-membership-research-v1', status='PASS',
        execution='finite-quorum-arithmetic-only', productionQualified=False,
        phase0Accepted=False, nodes=list(NODES), voterBounds=[MIN_VOTERS, MAX_VOTERS],
        counts=counts, counterexamples=witnesses, negativeCases=negatives,
        assumptions=['receipts are authentic durable acknowledgements',
                     'expected configuration and claim were independently established'],
        excluded=['configuration activation', 'elections', 'network schedules', 'crashes',
                  'recovery', 'storage bytes', 'token continuity', 'liveness', 'performance', 'cloud'])


def source_binding():
    root = Path(__file__).resolve().parents[2]
    names = ('scripts/v53/__init__.py', 'scripts/v53/membership_model.py', 'scripts/v53/test_membership_model.py')
    return dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        worktreeDirty=bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=root)),
        files={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-transitions', type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    binding = source_binding()
    try:
        result = explore(args.max_transitions)
        need(source_binding() == binding, 'model source changed during traversal')
        result['source'] = binding
    except Exception as error:
        result = dict(status='FAIL', errorType=type(error).__name__, message=str(error),
                      productionQualified=False, source=binding)
    (args.output/'receipt.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('source', 'negativeCases', 'counterexamples')}))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
