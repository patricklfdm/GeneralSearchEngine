"""Finite schedule matrix for the single-slot durable ballot research model.

Exhaustive over the declared matrix, NOT over all asynchronous interleavings.
No Java, Maven, sockets, cloud or model-checker claim of unbounded correctness.
"""
import argparse
from dataclasses import asdict, is_dataclass
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

from . import ballot_model as m
from .membership_model import NODES, need

CUTS = ('lost-accept-acks', 'one-unforced-accept', 'all-unforced-accepts', 'partial-proof')
FILES = ('scripts/v53/__init__.py', 'scripts/v53/membership_model.py',
         'scripts/v53/ballot_model.py', 'scripts/v53/ballot_research.py',
         'scripts/v53/test_ballot_model.py')


def encode(value):
    return json.dumps(value, default=lambda obj: asdict(obj) if is_dataclass(obj) else sorted(obj),
                      sort_keys=True, separators=(',', ':')).encode()


def contexts():
    for old_size, new_size in ((3, 3), (3, 4), (4, 3), (4, 4), (4, 5), (5, 4), (5, 5)):
        old = NODES[:old_size]
        new = NODES[:new_size] if old_size != new_size else NODES[1:new_size+1]
        for stage in ('old', 'joint', 'new'):
            yield m.Context('immutable-genesis', 1, old, new, stage, 7, 'prefix-6')


def minimal_quorums(context):
    family = context.oracle_quorums()
    return sorted((tuple(sorted(q)) for q in family if not any(p < q for p in family)))


def exchange(model, kind, ballot, nodes):
    """One directed schedule: force each request, then deliver its own response."""
    for message_id in model.send(kind, ballot, nodes):
        message = model.messages[message_id]
        model.deliver(message_id)
        need(model.voters[message.voter].pending is not None, 'scheduled request rejected')
        model.force(message.voter)
        model.deliver(model.next_message)


def recover(context, first, second, cut, *, mutant=None):
    need(cut in CUTS, 'schedule cut')
    model = m.Model(context, mutant=mutant)
    try:
        # Proposers are voters but are not assumed to belong to every recovery quorum.
        # Adapting GSE's local-basis inclusion is a separate production obligation.
        nodes = sorted(context.voters)
        low = m.Ballot(1, nodes[0], 'process-a')
        high = m.fresh_ballot(low, 1, nodes[1], 'process-b')
        model.start(low, 'operation-A')
        exchange(model, 'prepare', low, first)
        model.select(low)
        requests = model.send('accept', low, first)
        late = [model.duplicate(message_id) for message_id in requests]
        for index, message_id in enumerate(requests):
            node = model.messages[message_id].voter
            model.deliver(message_id)
            force = cut != 'all-unforced-accepts' and not (cut == 'one-unforced-accept' and index == len(first)-1)
            if force:
                model.force(node)
                if cut == 'partial-proof':
                    model.deliver(model.next_message)
        if cut == 'partial-proof':
            for index, message_id in enumerate(model.send('proof', low, first)):
                node = model.messages[message_id].voter
                model.deliver(message_id)
                if index < len(first)-1:
                    model.force(node)
        # Every voter restarts. In-flight requests survive; undelivered ACKs are lost.
        for node in nodes:
            model.crash(node); model.restart(node)
        for message_id in list(model.messages):
            if message_id not in late:
                model.drop(message_id)
        model.start(high, 'operation-B')
        exchange(model, 'prepare', high, second)
        selected = model.select(high)
        if cut in ('lost-accept-acks', 'partial-proof') and mutant is None:
            need(selected == 'operation-A', 'lost acknowledgement discarded chosen value')
        exchange(model, 'accept', high, second)
        exchange(model, 'proof', high, second)
        model.publish(high)
        # Delayed old requests cannot roll back a higher durable promise.
        for message_id in late:
            node = model.messages[message_id].voter
            model.deliver(message_id)
            if model.voters[node].pending:
                model.force(node)
        result = m.audit(context, model.events)
        need(result['publications'] == 1, 'missing recovered publication')
        return model, result
    except Exception as error:
        error.research_case = dict(context=context, first=first, second=second, cut=cut, events=model.events)
        raise


def unsealed_switch():
    """Two valid local histories are unsafe without an activation protocol."""
    histories = []
    traces = []
    for stage, votes, value in (('old', ('node-1','node-3'), 'operation-A'),
                                ('new', ('node-2','node-4'), 'operation-B')):
        context = m.Context('immutable-genesis', 1 if stage == 'old' else 2,
                            NODES[:3], ('node-1','node-2','node-4'), stage, 7, 'prefix-6')
        model = m.Model(context); ballot = m.Ballot(1, votes[0], 'process-'+stage)
        model.start(ballot, value); exchange(model, 'prepare', ballot, votes); model.select(ballot)
        exchange(model, 'accept', ballot, votes); exchange(model, 'proof', ballot, votes); model.publish(ballot)
        m.audit(context, model.events)
        histories.append((context, model.events)); traces.append(dict(context=context, events=model.events))
    try:
        m.audit_slot_family(histories)
    except m.SafetyViolation as error:
        return dict(status='EXPECTED_REJECTION', reason=str(error), histories=traces)
    raise ValueError('unsafe direct switch accepted')


def run(max_cases=None):
    if max_cases is not None:
        need(type(max_cases) is int and max_cases >= 0, 'matrix limit')
    domain = list(contexts())
    expected = sum(len(minimal_quorums(context))**2 * len(CUTS) for context in domain)
    counts = dict(contexts=len(domain), expectedCases=expected, cases=0, events=0, publications=0)
    digest = hashlib.sha256()
    examples = {}
    result = dict(schema='gse-v53-ballot-research-v1', execution='finite-single-slot-schedule-matrix',
                  productionQualified=False, phase0Accepted=False, allInterleavings=False,
                  counts=counts, cuts=list(CUTS), profiles=[[3,3],[3,4],[4,3],[4,4],[4,5],[5,4],[5,5]])
    for context in domain:
        quorums = minimal_quorums(context)
        for first, second, cut in product(quorums, quorums, CUTS):
            if max_cases is not None and counts['cases'] >= max_cases:
                return dict(result, status='INCOMPLETE', traceSha256=digest.hexdigest())
            model, audit = recover(context, first, second, cut)
            record = dict(context=context, first=first, second=second, cut=cut, events=model.events)
            digest.update(encode(record) + b'\n')
            counts['cases'] += 1; counts['events'] += audit['events']; counts['publications'] += audit['publications']
            # Retain one full replayable trace for each stage/cut, not just counts.
            examples.setdefault(context.stage+'/'+cut, record)
    counterexample = unsealed_switch()
    examples['unsealed-switch'] = counterexample
    return dict(result, status='PASS', traceSha256=digest.hexdigest(), examples=examples,
                directSwitchCounterexample=counterexample['reason'],
                assumptions=['one independently established configuration and prefix',
                             'authentic non-Byzantine messages', 'atomic force; crash discards only unforced work',
                             'unique proposal ballot; fresh persistent counter allocation not implemented'],
                excluded=['configuration handoff', 'multi-slot prefix recovery', 'snapshot and compaction',
                          'learner installation', 'network fairness and liveness', 'disk and wire bytes',
                          'public reads and operation API', 'production qualification'])


def replay_examples(raw):
    """Deserialize retained JSON and independently check its force histories."""
    need(set(raw) == {stage+'/'+cut for stage in ('old','joint','new') for cut in CUTS}
         | {'unsealed-switch'}, 'retained trace inventory')

    def context(value):
        return m.Context(**dict(value, old=tuple(value['old']), new=tuple(value['new'])))

    def accepted(value):
        return None if value is None else m.Accepted(m.Ballot(**value['ballot']),value['value'])

    def message(value):
        return m.Message(**dict(value, ballot=m.Ballot(**value['ballot']), context=context(value['context']),
                                accepted=accepted(value['accepted']),
                                evidence=tuple(message(row) for row in value['evidence'])))

    def history(value):
        rows=[]
        for row in value['events']:
            row=dict(row)
            if 'message' in row:row['message']=message(row['message'])
            if 'ballot' in row:row['ballot']=m.Ballot(**row['ballot'])
            if 'accepted' in row:row['accepted']=accepted(row['accepted'])
            if 'bases' in row:row['bases']=tuple(message(item) for item in row['bases'])
            rows.append(row)
        return context(value['context']),rows

    for name,row in raw.items():
        if name != 'unsealed-switch':
            cfg,events=history(row)
            need(name.split('/')[0] == cfg.stage, 'retained trace stage')
            need(m.audit(cfg,events)['publications'] == 1, 'retained publication')
    histories=[history(row) for row in raw['unsealed-switch']['histories']]
    need(len(histories)==2, 'counterexample history count')
    for cfg,events in histories:m.audit(cfg,events)
    try:m.audit_slot_family(histories)
    except m.SafetyViolation as error:
        need(str(error)==raw['unsealed-switch']['reason'] and
             raw['unsealed-switch']['status']=='EXPECTED_REJECTION','counterexample reason')
    else:raise ValueError('retained counterexample accepted')
    return len(raw)-1+len(histories)


def binding():
    root = Path(__file__).resolve().parents[2]
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'], cwd=root)),
                files={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-cases', type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = binding()
    try:
        result = run(args.max_cases)
        need(binding() == source, 'model source changed during traversal')
        examples = result.pop('examples', {})
        trace_path = args.output/'examples.json'
        trace_path.write_bytes(encode(examples) + b'\n')
        result['examplesSha256'] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
        if result['status'] == 'PASS':
            result['replayedRetainedTraces'] = replay_examples(json.loads(trace_path.read_bytes()))
    except Exception as error:
        result = dict(status='FAIL', errorType=type(error).__name__, message=str(error), productionQualified=False)
        if hasattr(error, 'research_case'):
            failed = args.output/'failed-case.json'
            failed.write_bytes(encode(error.research_case)+b'\n')
            result['failedCaseSha256'] = hashlib.sha256(failed.read_bytes()).hexdigest()
    result['source'] = source
    (args.output/'receipt.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
