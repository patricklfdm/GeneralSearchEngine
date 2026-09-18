"""Closed full-workload policy; a descriptor is never a paid admission receipt."""
import re
from .cloud_common import canonical, plan, request, require, sha
from .cloud_workload_plan import PLAN_SHA256, read_plan
from .cloud_workload_io import parse_json

PROFILES = ('experiment', 'failure-drill', 'canonical')
ORDER = (('experiment', 1), ('failure-drill', 1), ('canonical', 1), ('canonical', 2), ('canonical', 3))
SEQUENCE_ORDERS = {'experiment-first': ORDER, 'canonical-first': ORDER[2:] + ORDER[:2]}
SEQUENCES = 'v5.0-replicated-single-shard/control/workload-sequences.json'
EXECUTION = 'fake-cloud-preset-runner-only'


def preset(profile):
    require(profile in PROFILES, 'unknown workload profile')
    workload, runner = read_plan(), plan()
    require(workload['resources']['maximumCompleteSequenceMicrousd'] == runner['maximumSequenceCostMicrousd'],
            'runner/workload budget drift')
    selected = workload['profiles'][profile]
    return dict(schema='gse-v50-cloud-runner-preset-v3', execution='paid-admission-required', requiresPaidAdmission=True,
        profile=profile, workloadPlanSha256=PLAN_SHA256, runnerPlanSha256=sha(canonical(runner)),
        cells=selected['cells'], reservationsSeconds=selected['reservationsSeconds'],
        plannedMaximumSeconds=sum(selected['reservationsSeconds']),
        maximumTopologySeconds=workload['resources']['maximumTopologySeconds'],
        cleanupReserveSeconds=workload['resources']['cleanupReserveSeconds'],
        sequenceOrders={name: [dict(profile=p, repetition=n) for p, n in order]
                        for name, order in SEQUENCE_ORDERS.items()},
        replacementNodes=[] if profile == 'experiment' else [3, 1],
        resources=workload['resources'], evidenceBounds=workload['evidenceBounds'])


def workload_request(source, run_id, attempt, bundle_sha, profile, sequence, repetition=1, nonce=None):
    require(type(repetition) is int and (profile, repetition) in ORDER, 'profile/repetition')
    require(isinstance(sequence, str) and re.fullmatch('[0-9a-f]{32}', sequence), 'sequence identity')
    result = request(source, run_id, attempt, bundle_sha, nonce)
    result.update(profile=profile, sequence=sequence, repetition=repetition,
                  presetSha256=sha(canonical(preset(profile))))
    return result


def validate_request(value):
    expected = workload_request(value['source'], value['runId'], value['attempt'], value['bundleSha256'],
        value['profile'], value['sequence'], value['repetition'], value['nonce'])
    require(type(value['createdAt']) is int and value['createdAt'] > 0, 'request timestamp')
    expected['createdAt'] = value['createdAt']
    require(value == expected, 'workload request identity')
    return preset(value['profile'])


def sequence_ledger(backend):
    stored = backend.get_object(SEQUENCES)
    ledger = parse_json(stored[1]) if stored else dict(schema='gse-v50-workload-sequences-v1', attempts=[])
    require(ledger['schema'] == 'gse-v50-workload-sequences-v1' and len(ledger['attempts']) <= 1000,
            'sequence ledger schema/bound')
    return stored, ledger


def sequence_order(members):
    """The first member selects one fixed order; later members cannot switch it."""
    slots = tuple((v['profile'], v['repetition']) for v in members)
    for name, order in SEQUENCE_ORDERS.items():
        if slots and slots == order[:len(slots)]: return name
    raise ValueError('sequence order/repetition: start with experiment or canonical 1 and follow that order')


def reserve_sequence(backend):
    """Append before resource creation; any unresolved/failed member poisons its set."""
    r = backend.request; validate_request(r)
    stored, ledger = sequence_ledger(backend)
    require(len(ledger['attempts']) < 1000, 'sequence ledger full')
    entries = [v for v in ledger['attempts'] if v['sequence'] == r['sequence']]
    require(len(entries) < len(ORDER), 'sequence already complete')
    sequence_order([*entries, r])
    for entry in entries:
        require(entry['source'] == r['source'] and
                entry['workloadPlanSha256'] == PLAN_SHA256 and entry['status'] == 'PASS', 'failed, unresolved or different-source sequence')
        # A ledger claim alone is not completion. Bind it to immutable retained bytes.
        completion = backend.get_object(entry['completionObject'])
        require(completion is not None and sha(completion[1]) == entry['completionSha256'], 'missing sequence completion')
        state = parse_json(completion[1])
        previous = state['request']; validate_request(previous)
        require(all(previous[k] == entry[k] for k in ('sequence', 'source', 'profile', 'repetition')) and
                state['plan'] == backend.plan and not state['errors'], 'previous topology identity')
        require(state['execution']==backend.execution and state['status'] == 'PASS' and state['cleanup']['status'] == 'PASS' and
                state['retention'] == 'VERIFIED' and sha(canonical(state['request'])) == entry['requestSha256'],
                'previous topology lacks verified cleanup/retention')
    digest = sha(canonical(r))
    require(not any(v['requestSha256'] == digest for v in ledger['attempts']), 'sequence request already attempted')
    ledger['attempts'].append(dict(sequence=r['sequence'], source=r['source'], profile=r['profile'],
        repetition=r['repetition'], workloadPlanSha256=PLAN_SHA256, requestSha256=digest, status='RUNNING'))
    backend.put_object(SEQUENCES, canonical(ledger), stored[0] if stored else '0')
    return digest


def finish_sequence(backend, completion_object, state):
    stored, ledger = sequence_ledger(backend)
    digest = sha(canonical(backend.request))
    entries = [v for v in ledger['attempts'] if v['requestSha256'] == digest]
    require(len(entries) == 1 and entries[0]['status'] == 'RUNNING', 'sequence reservation identity')
    completed = backend.get_object(completion_object)
    require(completed is not None and completed[1] == canonical(state), 'sequence completion not retained')
    entries[0].update(status=state['status'], completionObject=completion_object, completionSha256=sha(completed[1]))
    backend.put_object(SEQUENCES, canonical(ledger), stored[0])
