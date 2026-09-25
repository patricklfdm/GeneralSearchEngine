"""V5.1 control-plane identities and conservative admission; no paid entry point.

Provider observations and prices are synthetic until the separately qualified GCP
adapter exists. These receipts deliberately cannot authorize a paid execution.
"""
from copy import deepcopy
import re
from . import cloud_workload_contract as workload, performance_model as m
from .cloud_plan import SUITE

EXECUTION = 'fake-v51-cloud-control'
PREFIX = 'v5.1-automatic-leadership/control/'
LEASE = PREFIX + 'active.json'
LEDGER = PREFIX + 'ledger.json'
RUNNER_WORKFLOW = '.github/workflows/v51-replication-evidence.yml'
CLEANUP_WORKFLOWS = {'schedule': '.github/workflows/v51-expired-cleanup.yml',
                     'workflow_dispatch': '.github/workflows/v51-manual-cleanup.yml'}
# Reserved identities, not assertions that these workflows/environments exist.
ENVIRONMENT = 'v51-cloud-benchmark'
CHECKS = ('configuration', 'iam', 'image', 'quota', 'retention', 'exactSourceCI', 'remoteQualification')
ORDERS = {'experiment-first': ('experiment', 'failure-drill', 'canonical-1', 'canonical-2', 'canonical-3'),
          'canonical-first': ('canonical-1', 'canonical-2', 'canonical-3', 'experiment', 'failure-drill')}
REQUEST_FIELDS = {'schema', 'suite', 'execution', 'paidCloud', 'source', 'bundleSha256',
                  'configurationSha256', 'workloadSha256', 'sequence', 'attempt', 'order', 'member', 'createdAt'}


def digest(value, size=64):
    m.need(isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % size, value), 'cloud identity digest')
    return value


def integer(value, minimum=0, maximum=(1 << 63)-1):
    m.need(type(value) is int and minimum <= value <= maximum, 'cloud bounded integer')
    return value


def request(source, bundle, configuration, sequence, attempt, member, *, now, order='experiment-first'):
    result = dict(schema='gse-v51-cloud-request-v1', suite=SUITE, execution=EXECUTION, paidCloud=False,
                  source=source, bundleSha256=bundle, configurationSha256=configuration,
                  workloadSha256=workload.PLAN_SHA256, sequence=sequence, attempt=attempt,
                  order=order, member=member, createdAt=now)
    validate_request(result)
    return result


def validate_request(value):
    m.need(type(value) is dict and set(value) == REQUEST_FIELDS, 'cloud request fields')
    m.need((value['schema'], value['suite'], value['execution'], value['paidCloud']) ==
           ('gse-v51-cloud-request-v1', SUITE, EXECUTION, False) and value['paidCloud'] is False,
           'V5.1 control-only request')
    for key, length in (('source', 40), ('bundleSha256', 64), ('configurationSha256', 64),
                        ('sequence', 32), ('attempt', 32)):
        digest(value[key], length)
    m.need(value['workloadSha256'] == workload.PLAN_SHA256 and value['order'] in ORDERS and
           value['member'] in ORDERS[value['order']], 'cloud workload/order/member')
    integer(value['createdAt'], 1, (1 << 63)-6481)
    return m.sha(m.canonical(value))


def identity(value):
    return {k: value[k] for k in ('source', 'bundleSha256', 'configurationSha256', 'workloadSha256', 'order')}


def admit(req, preflight, approval, now):
    """Validate trusted synthetic observations; success remains control-only."""
    sha = validate_request(req)
    integer(now, req['createdAt'])
    m.need(type(preflight) is dict and set(preflight) == {'schema', 'execution', 'requestSha256',
           'checkedAt', 'expiresAt', 'checks', 'cleanup', 'workflow', 'ref', 'environment'}, 'preflight fields')
    m.need(preflight['schema'] == 'gse-v51-control-preflight-v1' and preflight['execution'] == EXECUTION and
           preflight['requestSha256'] == sha, 'preflight request binding')
    checked = integer(preflight['checkedAt'], req['createdAt'])
    expires = integer(preflight['expiresAt'], checked+1, checked+900)
    m.need(checked <= now < expires, 'preflight expired/future')
    m.need((preflight['workflow'], preflight['ref'], preflight['environment']) ==
           (RUNNER_WORKFLOW, 'refs/heads/master', ENVIRONMENT), 'runner identity')
    m.need(type(preflight['checks']) is dict and set(preflight['checks']) == set(CHECKS) and
           all(v is True for v in preflight['checks'].values()), 'preflight blockers')
    cleanup = preflight['cleanup']
    m.need(type(cleanup) is dict and set(cleanup) == {'source', 'event', 'workflow', 'ref', 'completedAt',
           'runId', 'executed', 'conclusion', 'reconciliation'}, 'cleanup receipt fields')
    m.need(cleanup['source'] == req['source'] and cleanup['event'] in CLEANUP_WORKFLOWS and
           cleanup['workflow'] == CLEANUP_WORKFLOWS[cleanup['event']] and cleanup['ref'] == 'refs/heads/master' and
           cleanup['executed'] is True and cleanup['conclusion'] == 'success' and
           cleanup['reconciliation'] == 'PASS', 'cleanup receipt identity/outcome')
    integer(cleanup['runId'], 1)
    integer(cleanup['completedAt'], max(1, now-7200), checked)
    m.need(type(approval) is dict and set(approval) == {'schema', 'execution', 'requestSha256',
           'preflightSha256', 'confirmed', 'maximumCostMicrousd', 'previousCostMicrousd'}, 'approval fields')
    m.need(approval['schema'] == 'gse-v51-control-approval-v1' and approval['execution'] == EXECUTION and
           approval['requestSha256'] == sha and approval['preflightSha256'] == m.sha(m.canonical(preflight)) and
           approval['confirmed'] is True, 'exact control approval')
    cost = integer(approval['maximumCostMicrousd'], 1, 100_000_000)
    previous = integer(approval['previousCostMicrousd'], 0, 100_000_000)
    m.need(previous+cost <= 100_000_000, 'aggregate budget ceiling')
    return sha


def empty_ledger():
    return dict(schema='gse-v51-cloud-ledger-v1', suite=SUITE, execution=EXECUTION, entries=[])


def inspect_ledger(value):
    m.need(type(value) is dict and set(value) == {'schema', 'suite', 'execution', 'entries'} and
           (value['schema'], value['suite'], value['execution']) ==
           ('gse-v51-cloud-ledger-v1', SUITE, EXECUTION), 'V5.1 ledger scope')
    m.need(type(value['entries']) is list and len(value['entries']) <= 4096 and
           len(m.canonical(value)) <= 4 << 20, 'ledger bound')
    attempts, sequences, total, ids = {}, {}, 0, set()
    for row in value['entries']:
        m.need(type(row) is dict and row.get('kind') in ('RESERVED', 'FINISHED'), 'ledger event')
        sha = digest(row['requestSha256'])
        if row['kind'] == 'RESERVED':
            m.need(set(row) == {'kind', 'requestSha256', 'request', 'maximumCostMicrousd'}, 'reservation fields')
            req = row['request']
            m.need(validate_request(req) == sha and sha not in attempts and req['attempt'] not in ids,
                   'duplicate/changed request')
            m.need(all(a['status'] != 'PENDING' for a in attempts.values()), 'unresolved prior attempt')
            seq = sequences.setdefault(req['sequence'], dict(identity=identity(req), passed=[], blocked=False))
            m.need(seq['identity'] == identity(req) and not seq['blocked'], 'sequence changed/failed canonical set')
            order = ORDERS[req['order']]
            m.need(len(seq['passed']) < len(order) and req['member'] == order[len(seq['passed'])], 'sequence order')
            total += integer(row['maximumCostMicrousd'], 1, 100_000_000)
            m.need(total <= 100_000_000, 'ledger budget ceiling')
            attempts[sha] = dict(request=req, status='PENDING')
            ids.add(req['attempt'])
        else:
            m.need(set(row) == {'kind', 'requestSha256', 'status', 'completionSha256'} and
                   row['status'] in ('PASS', 'FAIL') and sha in attempts and
                   attempts[sha]['status'] == 'PENDING', 'terminal ledger event')
            digest(row['completionSha256'])
            attempt = attempts[sha]
            attempt['status'] = row['status']
            req = attempt['request']; seq = sequences[req['sequence']]
            if row['status'] == 'PASS': seq['passed'].append(req['member'])
            elif req['member'].startswith('canonical-'): seq['blocked'] = True
    return total, attempts


def reserve(ledger, req, approval):
    result = deepcopy(ledger)
    total, _ = inspect_ledger(result)
    m.need(total == approval['previousCostMicrousd'], 'stale budget observation')
    result['entries'].append(dict(kind='RESERVED', requestSha256=validate_request(req),
                                  request=deepcopy(req), maximumCostMicrousd=approval['maximumCostMicrousd']))
    inspect_ledger(result)
    return result


def finish(ledger, req, completion):
    m.need(completion['requestSha256'] == validate_request(req), 'completion request identity')
    result = deepcopy(ledger)
    result['entries'].append(dict(kind='FINISHED', requestSha256=validate_request(req),
                                  status=completion['status'], completionSha256=m.sha(m.canonical(completion))))
    inspect_ledger(result)
    return result


def resources(req):
    sha = validate_request(req)
    owner = 'gse-v51-' + req['attempt']
    specs = [dict(kind='firewall', name=owner+'-'+name, purpose=name)
             for name in ('peer', 'deny-replication', 'iap', 'deny-ssh')]
    for node in (1, 2, 3):
        for kind, size in (('boot', 50), ('data', 100)):
            specs.append(dict(kind='disk', name=f'{owner}-n{node}-{kind}', purpose=kind, node=node, sizeGiB=size))
    specs += [dict(kind='instance', name=f'{owner}-n{node}', purpose='voter', node=node) for node in (1, 2, 3)]
    return [dict(spec, owner=owner, requestSha256=sha,
                 operationId=m.sha(m.canonical([sha, spec['name']]))) for spec in specs]


def lease(req, now):
    validate_request(req); integer(now, req['createdAt'], (1 << 63)-6481)
    return dict(schema='gse-v51-cloud-lease-v1', suite=SUITE, execution=EXECUTION, request=deepcopy(req),
                startedAt=now, expiresAt=now+5400, graceSeconds=1080,
                resources=[dict(spec=spec, attempted=False, id=None) for spec in resources(req)])


def validate_lease(value):
    m.need(type(value) is dict and set(value) == {'schema', 'suite', 'execution', 'request', 'startedAt',
           'expiresAt', 'graceSeconds', 'resources'}, 'lease fields')
    expected = lease(value['request'], value['startedAt'])
    m.need(all(value[k] == v for k, v in expected.items() if k != 'resources'), 'lease authority/expiry')
    rows = value['resources']
    m.need(type(rows) is list and len(rows) == len(expected['resources']), 'closed resource inventory')
    for row, template in zip(rows, expected['resources']):
        m.need(set(row) == set(template) and row['spec'] == template['spec'] and
               type(row['attempted']) is bool, 'resource scope')
        if row['id'] is not None:
            m.need(row['attempted'] and isinstance(row['id'], str) and
                   re.fullmatch('[1-9][0-9]{0,19}', row['id']), 'resource exact ID')
    return value
