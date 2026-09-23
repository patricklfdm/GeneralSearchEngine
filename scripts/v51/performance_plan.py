"""Closed, reviewed local preset admission. This never admits cloud execution."""
import argparse
from pathlib import Path
from . import performance_model as model

PLAN = Path(__file__).resolve().parents[2] / 'docs/v5x/v5.1/phase6-plan.json'
# Canonical content pin, deliberately independent of the supplied plan/evidence.
# Changing a preset requires review of this pin and the human-readable contract.
PLAN_SHA256 = '1dff2117631534ead866cfbd2ea7da3ec29ab57e510a6a5e8e5bf17a32092c33'


def load(path=PLAN):
    path = Path(path)
    model.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536, 'local plan file/bound')
    value = model.strict_json(path.read_bytes())
    validate(value)
    return value


def validate(value):
    model.need(model.sha(model.canonical(value)) == PLAN_SHA256, 'unreviewed local measurement plan')
    smoke, budgets, fault = value['localSmoke'], value['budgets'], value['failover']
    result = model.expected(value)
    rows, state = result['rows'], result['state']
    corpus = b''.join(model.blob(model.encode_document(d)) for d in model.initial(value).documents.values())
    model.need(model.sha(corpus) == smoke['corpusSha256'], 'corpus digest')
    mutations = sum(r['operation'] in model.OP_IDS for r in rows)
    reads = len(rows) - mutations
    model.need((len(rows), mutations, reads, state.sequence, len(state.documents), result['peakDocuments']) ==
               (90, 72, 18, 76, 64, 68), 'healthy workload arithmetic')
    model.need(sum(v['seconds'] for v in budgets['stages']) == budgets['wholeSeconds'] == 900, 'whole stage budget')
    model.need(budgets['healthyStartupWarmupSeconds'] + len(smoke['windows']) * budgets['windowSeconds'] == 150,
               'healthy stage budget')
    fault_calls = len(fault['initialCalls']) + len(fault['concurrentWave']) + 2 * fault['progressPairs'] + fault['finalReadAttempts']
    model.need(fault_calls == 18 and fault_calls <= fault['historyOperationLimit'], 'fault history ceiling')
    slots = {name: calls + budgets['auxiliaryBarriersPerGroup'] + budgets['activationRecoverySlotsPerGroup']
             for name, calls in [('healthy', len(rows)), ('failover', fault_calls)]}
    model.need(max(slots.values()) <= budgets['logicalSlotsPerGroup'], 'automatic logical slot ceiling')
    program = list(model.program(value))
    docs = [d for call in program for d in call['documents']] + list(model.initial(value).documents.values())
    peak_document = max(len(model.encode_document(d)) for d in docs)
    peak_payload = max(len(c['payload']) for c in program)
    model.need(peak_document <= value['encodingLimits']['documentBytes'] and
               peak_payload <= value['encodingLimits']['payloadBytes'], 'generated workload byte admission')
    return dict(status='PASS', execution='local-plan-admission-only', planSha256=PLAN_SHA256,
                calls=len(rows), mutations=mutations, reads=reads, measuredCalls=sum(r['window'] != 'warmup' for r in rows),
                baseSequence=4, finalSequence=state.sequence, finalDocuments=len(state.documents), peakDocuments=result['peakDocuments'],
                corpusBytes=len(corpus), corpusDocumentBytes=len(corpus) - 4 * smoke['corpusDocuments'], maximumDocumentBytes=peak_document, maximumPayloadBytes=peak_payload,
                faultHistoryCalls=fault_calls, logicalSlotBounds=slots, maximumRunSeconds=budgets['wholeSeconds'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, default=PLAN)
    args = parser.parse_args()
    print(model.canonical(validate(load(args.plan))).decode())
