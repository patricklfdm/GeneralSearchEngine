"""V5.1 control-plane identities and conservative admission; no paid entry point.

Provider observations and prices are synthetic until the separately qualified GCP
adapter exists. These receipts deliberately cannot authorize a paid execution.
"""
from copy import deepcopy
import re
from . import cloud_workload_contract as workload, performance_model as m
from .cloud_plan import SUITE, MAXIMUM_BUDGET_MICROUSD
from . import native_experiment_timing as timing, native_preset_timing as full

EXECUTION = 'fake-v51-cloud-control'
ADAPTER_EXECUTION = EXECUTION
PAID_CLOUD = False
COMPLETION_SCHEMA = 'gse-v51-control-completion-v1'
CONTEXT_SCHEMA = 'gse-v51-cleanup-context-v1'


def formats(domain):
    # Explicit domains, never inferred from untrusted input or converted between.
    m.need(domain in ('fake', 'native'), 'cloud authority domain')
    if domain == 'native':
        return dict(execution='gcp-v51-owned-control', paid=True,
                    requests=('gse-v51-native-request-v1', timing.REQUEST_SCHEMA, full.REQUEST_SCHEMA), access='gse-v51-native-request-v1',
                    lease='gse-v51-native-lease-v1', ledger='gse-v51-native-ledger-v1')
    return dict(execution=EXECUTION, paid=False,
                requests=('gse-v51-cloud-request-v1', 'gse-v51-cloud-request-v2'), access='gse-v51-cloud-request-v2',
                lease='gse-v51-cloud-lease-v1', ledger='gse-v51-cloud-ledger-v1')

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


def request(source, bundle, configuration, sequence, attempt, member, *, now, order='experiment-first', guest_access_sha256=None, domain='fake', timing_profile=None, timing_plan_sha256=None):
    fmt = formats(domain)
    result = dict(schema=fmt['requests'][0], suite=SUITE, execution=fmt['execution'], paidCloud=fmt['paid'],
                  source=source, bundleSha256=bundle, configurationSha256=configuration,
                  workloadSha256=workload.PLAN_SHA256, sequence=sequence, attempt=attempt,
                  order=order, member=member, createdAt=now)
    if guest_access_sha256 is not None:
        result.update(schema=fmt['access'], guestAccessSha256=guest_access_sha256)
    if timing_profile is not None:
        m.need(domain == 'native', 'timing profile requires native experiment')
        result.update(schema=timing.REQUEST_SCHEMA, timingProfile=timing_profile)
    if timing_plan_sha256 is not None:
        m.need(domain == 'native', 'native preset domain')
        result.update(schema=full.REQUEST_SCHEMA, timingPlanSha256=timing_plan_sha256)
    validate_request(result, domain=domain)
    return result


def validate_request(value, *, domain='fake'):
    fmt = formats(domain)
    m.need(type(value) is dict, 'cloud request type')
    version = value.get('schema'); extra = {'guestAccessSha256'} if version == fmt['access'] else set()
    if domain == 'native' and version == timing.REQUEST_SCHEMA:
        extra = {'guestAccessSha256', 'timingProfile'}
        m.need(value.get('timingProfile') == timing.PROFILE and value.get('member') == 'experiment',
               'native experiment timing profile/scope')
    if domain == 'native' and version == full.REQUEST_SCHEMA:
        full.validate(value); extra = {'guestAccessSha256', 'timingProfile', 'timingPlanSha256'}
    m.need(version in fmt['requests'] and set(value) == REQUEST_FIELDS | extra, 'cloud request fields')
    if extra: digest(value['guestAccessSha256'])
    m.need((value['schema'], value['suite'], value['execution'], value['paidCloud']) ==
           (version, SUITE, fmt['execution'], fmt['paid']) and value['paidCloud'] is fmt['paid'],
           'V5.1 '+domain+' authority request')
    for key, length in (('source', 40), ('bundleSha256', 64), ('configurationSha256', 64),
                        ('sequence', 32), ('attempt', 32)):
        digest(value[key], length)
    if domain == 'native' and full.selected(value):
        order_valid = value['order'] in full.ORDERS and value['member'] in full.MEMBERS
    else:
        order_valid = value['order'] in ORDERS and value['member'] in ORDERS[value['order']]
    m.need(value['workloadSha256'] == workload.PLAN_SHA256 and order_valid, 'cloud workload/order/member')
    maximum=(1 << 63)-(timing.allocation(value)['leaseSeconds']+timing.allocation(value)['operationGraceSeconds']+1 if timing.selected(value) else 6481)
    integer(value['createdAt'], 1, maximum)
    return m.sha(m.canonical(value))


def identity(value):
    keys = ('source', 'bundleSha256', 'configurationSha256', 'workloadSha256', 'order')
    if full.selected(value): keys += ('timingPlanSha256',)
    return {k: value[k] for k in keys}


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
    cost = integer(approval['maximumCostMicrousd'], 1, MAXIMUM_BUDGET_MICROUSD)
    previous = integer(approval['previousCostMicrousd'], 0, MAXIMUM_BUDGET_MICROUSD)
    m.need(previous+cost <= MAXIMUM_BUDGET_MICROUSD, 'aggregate budget ceiling')
    return sha


def empty_ledger(*, domain='fake'):
    fmt = formats(domain)
    return dict(schema=fmt['ledger'], suite=SUITE, execution=fmt['execution'], entries=[])


def inspect_ledger(value, *, domain='fake'):
    fmt = formats(domain)
    m.need(type(value) is dict and set(value) == {'schema', 'suite', 'execution', 'entries'} and
           (value['schema'], value['suite'], value['execution']) ==
           (fmt['ledger'], SUITE, fmt['execution']), 'V5.1 ledger scope')
    m.need(type(value['entries']) is list and len(value['entries']) <= 4096 and
           len(m.canonical(value)) <= 4 << 20, 'ledger bound')
    attempts, sequences, total, ids = {}, {}, 0, set()
    for row in value['entries']:
        m.need(type(row) is dict and row.get('kind') in ('RESERVED', 'FINISHED'), 'ledger event')
        sha = digest(row['requestSha256'])
        if row['kind'] == 'RESERVED':
            m.need(set(row) == {'kind', 'requestSha256', 'request', 'maximumCostMicrousd'}, 'reservation fields')
            req = row['request']
            m.need(validate_request(req, domain=domain) == sha and sha not in attempts and req['attempt'] not in ids,
                   'duplicate/changed request')
            m.need(all(a['status'] != 'PENDING' for a in attempts.values()), 'unresolved prior attempt')
            seq = sequences.setdefault(req['sequence'], dict(identity=identity(req), passed=[], blocked=False))
            m.need(seq['identity'] == identity(req) and not seq['blocked'], 'sequence changed/failed canonical set')
            if domain == 'native' and full.selected(req) and req['order'] == 'any-order':
                m.need(req['member'] not in seq['passed'], 'sequence order')
            else:
                order = ORDERS[req['order']]
                m.need(len(seq['passed']) < len(order) and req['member'] == order[len(seq['passed'])], 'sequence order')
            total += integer(row['maximumCostMicrousd'], 1, MAXIMUM_BUDGET_MICROUSD)
            m.need(total <= MAXIMUM_BUDGET_MICROUSD, 'ledger budget ceiling')
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


def reserve(ledger, req, approval, *, domain='fake'):
    result = deepcopy(ledger)
    total, _ = inspect_ledger(result, domain=domain)
    m.need(total == approval['previousCostMicrousd'], 'stale budget observation')
    result['entries'].append(dict(kind='RESERVED', requestSha256=validate_request(req, domain=domain),
                                  request=deepcopy(req), maximumCostMicrousd=approval['maximumCostMicrousd']))
    inspect_ledger(result, domain=domain)
    return result


def finish(ledger, req, completion, *, domain='fake'):
    m.need(completion['requestSha256'] == validate_request(req, domain=domain), 'completion request identity')
    result = deepcopy(ledger)
    result['entries'].append(dict(kind='FINISHED', requestSha256=validate_request(req, domain=domain),
                                  status=completion['status'], completionSha256=m.sha(m.canonical(completion))))
    inspect_ledger(result, domain=domain)
    return result


def resources(req, *, domain='fake'):
    sha = validate_request(req, domain=domain)
    owner = 'gse-v51-' + req['attempt']
    specs = [dict(kind='firewall', name=owner+'-'+name, purpose=name)
             for name in ('peer', 'deny-replication', 'iap', 'deny-ssh')]
    for node in (1, 2, 3):
        for kind, size in (('boot', 50), ('data', 100)):
            specs.append(dict(kind='disk', name=f'{owner}-n{node}-{kind}', purpose=kind, node=node, sizeGiB=size))
    specs += [dict(kind='instance', name=f'{owner}-n{node}', purpose='voter', node=node) for node in (1, 2, 3)]
    return [dict(spec, owner=owner, requestSha256=sha,
                 operationId=m.sha(m.canonical([sha, spec['name']]))) for spec in specs]


def lease(req, now, *, domain='fake'):
    fmt = formats(domain)
    validate_request(req, domain=domain)
    seconds, grace = (timing.allocation(req)['leaseSeconds'], timing.allocation(req)['operationGraceSeconds']) if timing.selected(req) else (5400, 1080)
    integer(now, req['createdAt'], (1 << 63)-seconds-grace-1)
    return dict(schema=fmt['lease'], suite=SUITE, execution=fmt['execution'], request=deepcopy(req),
                startedAt=now, expiresAt=now+seconds, graceSeconds=grace,
                resources=[dict(spec=spec, attempted=False, id=None) for spec in resources(req, domain=domain)])


def validate_lease(value, *, domain='fake'):
    m.need(type(value) is dict and set(value) == {'schema', 'suite', 'execution', 'request', 'startedAt',
           'expiresAt', 'graceSeconds', 'resources'}, 'lease fields')
    expected = lease(value['request'], value['startedAt'], domain=domain)
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
