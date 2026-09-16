"""Closed, separately versioned full cloud workload contract; no cloud execution admission."""
import hashlib
import json
from pathlib import Path
from .admission_format import check
from .performance_model import document, encoded, blob

PLAN = Path(__file__).resolve().parents[2] / 'docs/v5x/v5.0/phase6-cloud-workload-plan.json'
PLAN_SHA256 = '148e7808680b51f1427d9be535291ec7629c7a64eac59bf8ac96691b7a6086fa'


def read_plan(path=PLAN):
    raw = Path(path).read_bytes()
    check(len(raw) < 65536 and hashlib.sha256(raw).hexdigest() == PLAN_SHA256, 'unreviewed cloud workload plan')
    return json.loads(raw)


def arithmetic(plan):
    corpus = [encoded(document(i, 0)) for i in range(1, plan['corpusDocuments'] + 1)]
    check(hashlib.sha256(b''.join(map(blob, corpus))).hexdigest() == plan['workload']['corpusSha256'], 'cloud corpus identity')
    totals = {}
    for name, profile in plan['profiles'].items():
        measured = sum(c['seconds'] for c in profile['cells'])
        check(measured == profile['reservationsSeconds'][3], 'cell budget')
        check(sum(profile['reservationsSeconds']) <= plan['resources']['maximumTopologySeconds'], 'topology budget')
        totals[name] = measured
    check(totals == {'experiment': 300, 'failure-drill': 900, 'canonical': 1800}, 'profile budget')
    entries = 480 * 8 + 300 * 20 * 3 // 4 + 20 * 8 + plan['maximumFaultCalls'] + plan['maximumRecoveryEntries']
    check(entries == 21524 < plan['maximumLogIndex'] < 1000000, 'ancestry headroom')
    log_bytes = plan['maximumLogIndex'] * (plan['maximumEncodedEntryBytes'] + plan['maximumEncodedProofBytes'])
    check(log_bytes + 2 * plan['maximumSnapshotImageBytes'] + (16 << 20) < plan['replicationBounds']['maxRetainedLogBytes'], 'log headroom')
    maximum = 0
    for cycle in range(plan['maximumClientCalls'] // 10):
        for keys in (range(100000 + cycle * 100, 100016 + cycle * 100), [1 + (cycle + i) % 4096 for i in range(16)]):
            sizes = [len(encoded(document(k, cycle + 1))) for k in keys]
            check(max(sizes) <= plan['maximumEncodedDocumentBytes'], 'document bound')
            maximum = max(maximum, 6 + sum(12 + size for size in sizes))
    check(maximum <= plan['maximumEncodedApplicationPayloadBytes'], 'application payload bound')
    return dict(corpusDocuments=len(corpus), corpusBytes=sum(map(len, corpus)), maximumBulkPayloadBytes=maximum,
                reservedEntries=entries, remainingEntries=plan['maximumLogIndex'] - entries, measurementSeconds=totals)
