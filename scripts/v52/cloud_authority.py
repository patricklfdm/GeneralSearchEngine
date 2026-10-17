"""V5.2 owned control records. Data validation never grants network authority.

Native and offline records are disjoint. There is no live adapter in this module.
Operational time/cost are soft; renewable ownership and decoder bounds are not.
"""
from copy import deepcopy
import re
from . import cloud_suite as suite
from .evidence import need, encoded, digest

PREFIX = 'v5.2-bounded-follower-reads/control/'
LEASE = PREFIX + 'active.json'
LEDGER = PREFIX + 'ledger.json'
MAX_INTEGER = (1 << 63) - 1
MAX_LEDGER_BYTES = 4 << 20
DOMAINS = {'offline': 'offline-v52-owned-control', 'native': 'gcp-v52-owned-control'}


def integer(value, minimum=0, maximum=MAX_INTEGER):
    need(type(value) is int and minimum <= value <= maximum, 'V5.2 bounded integer')
    return value


def hex_value(value, length=64):
    need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value), 'V5.2 control digest')
    return value


def numeric(value):
    need(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value), 'V5.2 exact resource ID')
    return value


def fields(value, names, label):
    need(type(value) is dict and set(value) == set(names.split()), 'V5.2 '+label+' fields')


def policy(value):
    fields(value, 'leaseSeconds operationGraceSeconds budgetMicrousd', 'ownership policy')
    # Bounds on the ownership protocol, not the duration of a running experiment.
    integer(value['leaseSeconds'], 60, 86400)
    integer(value['operationGraceSeconds'], 30, 86400)
    integer(value['budgetMicrousd'], 1)
    return value


def layout(value):
    fields(value, 'bootDiskGiB dataDiskGiB', 'resource layout')
    for size in value.values(): integer(size, 1, 4096)
    return value


def request(selection, configuration_sha256, resource_layout, ownership_policy, *, now, domain):
    need(domain in DOMAINS, 'V5.2 authority domain')
    value = dict(schema='gse-v52-owned-request-v1', execution=DOMAINS[domain],
                 paidCloud=domain == 'native', selection=deepcopy(selection),
                 configurationSha256=configuration_sha256, layout=deepcopy(resource_layout),
                 policy=deepcopy(ownership_policy), createdAt=now)
    validate_request(value, domain=domain)
    return value


def validate_request(value, *, domain):
    extended = type(value) is dict and value.get('schema') == 'gse-v52-owned-request-v2'
    fields(value, 'schema execution paidCloud selection configurationSha256 layout policy createdAt'+
           (' guestAccess' if extended else ''), 'request')
    need(domain in DOMAINS and value['schema'] in ('gse-v52-owned-request-v1','gse-v52-owned-request-v2') and
         value['execution'] == DOMAINS[domain] and value['paidCloud'] is (domain == 'native'), 'V5.2 request domain')
    suite.validate_selection(value['selection']); hex_value(value['configurationSha256'])
    if extended:
        from .cloud_access import validate
        validate(value['guestAccess'], value['selection']['attempt'])
    layout(value['layout']); policy(value['policy'])
    integer(value['createdAt'], 1, MAX_INTEGER-value['policy']['leaseSeconds']-value['policy']['operationGraceSeconds'])
    return digest(encoded(value))


def with_access(value, access):
    """Bind per-attempt public access before allocation, preserving cohort identity."""
    validate_request(value, domain=domain(value))
    need(value['schema']=='gse-v52-owned-request-v1', 'V5.2 access already bound')
    result=deepcopy(value);result.update(schema='gse-v52-owned-request-v2',guestAccess=deepcopy(access))
    validate_request(result, domain=domain(result));return result


def domain(value):
    need(type(value) is dict, 'V5.2 authority record type')
    found = [name for name, execution in DOMAINS.items() if value.get('execution') == execution]
    need(len(found) == 1, 'V5.2 unknown authority domain')
    return found[0]


def identity(req):
    return dict(binding=deepcopy(req['selection']['binding']), configurationSha256=req['configurationSha256'],
                layout=deepcopy(req['layout']), policy=deepcopy(req['policy']))


def resources(req):
    sha = validate_request(req, domain=domain(req)); owner = 'gse-v52-'+req['selection']['attempt']
    specs = [dict(kind='firewall', name=owner+'-'+purpose, purpose=purpose)
             for purpose in ('peer', 'deny-replication', 'iap', 'deny-ssh')]
    for node in (1, 2, 3):
        for purpose, key in (('boot', 'bootDiskGiB'), ('data', 'dataDiskGiB')):
            specs.append(dict(kind='disk', name=f'{owner}-n{node}-{purpose}', node=node,
                              purpose=purpose, sizeGiB=req['layout'][key]))
    specs += [dict(kind='instance', name=f'{owner}-n{node}', node=node, purpose='voter') for node in (1, 2, 3)]
    return [dict(spec, owner=owner, requestSha256=sha, operationId=digest(encoded([sha, spec['name']]))) for spec in specs]


def lease(req, now):
    validate_request(req, domain=domain(req)); p = req['policy']
    integer(now, req['createdAt'], MAX_INTEGER-p['leaseSeconds']-p['operationGraceSeconds'])
    return dict(schema='gse-v52-owned-lease-v1', execution=req['execution'], request=deepcopy(req),
                phase='ACQUIRING', startedAt=now, renewedAt=now, expiresAt=now+p['leaseSeconds'],
                graceSeconds=p['operationGraceSeconds'], resources=[dict(spec=s, attempted=False, id=None) for s in resources(req)])


def validate_lease(value):
    fields(value, 'schema execution request phase startedAt renewedAt expiresAt graceSeconds resources', 'lease')
    expected = lease(value['request'], value['startedAt']); p = value['request']['policy']
    need(value['schema'] == expected['schema'] and value['execution'] == expected['execution'] and
         value['phase'] in ('ACQUIRING', 'ACTIVE', 'CLEANING'), 'V5.2 lease identity/phase')
    integer(value['renewedAt'], value['startedAt'], MAX_INTEGER-p['leaseSeconds']-p['operationGraceSeconds'])
    need(value['expiresAt'] == value['renewedAt']+p['leaseSeconds'] and value['graceSeconds'] == p['operationGraceSeconds'],
         'V5.2 lease expiry/grace')
    rows = value['resources']
    need(type(rows) is list and len(rows) == len(expected['resources']), 'V5.2 closed resource inventory')
    ids = {kind: set() for kind in ('disk', 'instance', 'firewall')}
    unattempted = False
    for row, original in zip(rows, expected['resources']):
        fields(row, 'spec attempted id', 'resource')
        need(row['spec'] == original['spec'] and type(row['attempted']) is bool, 'V5.2 resource intent changed')
        need(not unattempted or not row['attempted'], 'V5.2 resource intent gap')
        unattempted = unattempted or not row['attempted']
        if row['id'] is not None:
            numeric(row['id']); seen = ids[row['spec']['kind']]
            need(row['attempted'] and row['id'] not in seen, 'V5.2 resource identity collision'); seen.add(row['id'])
        need(value['phase'] != 'ACQUIRING' or not row['attempted'], 'V5.2 uncharged resource intent')
    return value


def renew(value, now):
    validate_lease(value)
    need(value['phase'] == 'ACTIVE', 'V5.2 renewal requires active ownership')
    integer(now, value['renewedAt'], value['expiresAt']-1)
    result = deepcopy(value); result.update(renewedAt=now, expiresAt=now+value['request']['policy']['leaseSeconds'])
    return validate_lease(result)


def resource_claim(value):
    """Stable original allocation identity, not fresh provider/guest observation.

    Renewals change expiry, not this captured owner. A native adapter must still
    verify exact live IDs, attachments, host keys and mounted storage separately.
    """
    validate_lease(value)
    need(value['phase'] == 'ACTIVE' and all(r['attempted'] and r['id'] is not None for r in value['resources']),
         'V5.2 resource claim needs complete active allocation')
    req = value['request']; sha = validate_request(req, domain=domain(req)); nodes = {}
    for number in (1, 2, 3):
        rows = [deepcopy(r) for r in value['resources'] if r['spec'].get('node') == number]
        identity = dict(requestSha256=sha, configurationSha256=req['configurationSha256'], node='node-'+str(number), resources=rows)
        nodes[identity['node']] = dict(identity=identity, resourceIdentitySha256=digest(encoded(identity)))
    return dict(schema='gse-v52-owned-resource-claim-v1', requestSha256=sha, startedAt=value['startedAt'],
                source={k:req['selection']['binding'][k] for k in ('source','checkoutSha256')},
                attempt=req['selection']['attempt'], nodes=nodes,
                firewalls=[deepcopy(r) for r in value['resources'] if r['spec']['kind'] == 'firewall'])


def empty_ledger(*, domain):
    need(domain in DOMAINS, 'V5.2 authority domain')
    return dict(schema='gse-v52-owned-ledger-v1', execution=DOMAINS[domain], entries=[])


def inspect_ledger(value, *, domain):
    fields(value, 'schema execution entries', 'ledger')
    need(domain in DOMAINS and value['schema'] == 'gse-v52-owned-ledger-v1' and value['execution'] == DOMAINS[domain],
         'V5.2 ledger domain')
    need(type(value['entries']) is list and len(value['entries']) <= 4096 and len(encoded(value)) <= MAX_LEDGER_BYTES,
         'V5.2 ledger bound')
    total = 0; attempts = {}; ids = set(); sequences = {}
    for row in value['entries']:
        need(type(row) is dict and row.get('kind') in ('RESERVED', 'FINISHED'), 'V5.2 ledger event')
        sha = hex_value(row.get('requestSha256'))
        if row['kind'] == 'RESERVED':
            fields(row, 'kind requestSha256 request reservedCostMicrousd', 'reservation')
            req = row['request']; need(validate_request(req, domain=domain) == sha, 'V5.2 reservation changed')
            selected = req['selection']; name = selected['member']['name']; attempt = selected['attempt']
            need(sha not in attempts and attempt not in ids and all(v['status'] != 'PENDING' for v in attempts.values()),
                 'V5.2 reused or unresolved attempt')
            seq = sequences.setdefault(selected['binding']['sequence'], dict(identity=identity(req), passed=[]))
            need(seq['identity'] == identity(req), 'V5.2 sequence identity changed')
            need(name not in seq['passed'], 'V5.2 member already passed')
            total += integer(row['reservedCostMicrousd'], 1); integer(total)
            ids.add(attempt); attempts[sha] = dict(request=deepcopy(req), status='PENDING')
        else:
            fields(row, 'kind requestSha256 status completionSha256', 'terminal event')
            hex_value(row['completionSha256'])
            need(row['status'] in ('PASS', 'FAIL') and sha in attempts and attempts[sha]['status'] == 'PENDING',
                 'V5.2 terminal attempt changed')
            attempts[sha]['status'] = row['status']
            req = attempts[sha]['request']
            if row['status'] == 'PASS': sequences[req['selection']['binding']['sequence']]['passed'].append(req['selection']['member']['name'])
    return dict(reservedCostMicrousd=total, attempts=attempts, sequences=sequences)


def reserve(ledger, req, *, previous_cost, cost):
    d = domain(req); view = inspect_ledger(ledger, domain=d)
    need(view['reservedCostMicrousd'] == integer(previous_cost), 'V5.2 stale cost observation')
    result = deepcopy(ledger)
    result['entries'].append(dict(kind='RESERVED', requestSha256=validate_request(req, domain=d),
                                  request=deepcopy(req), reservedCostMicrousd=integer(cost, 1)))
    inspect_ledger(result, domain=d); return result


def validate_completion(value, req):
    fields(value, 'schema execution requestSha256 status evidenceSha256 cleanupSha256', 'completion')
    need(value['schema'] == 'gse-v52-owned-completion-v1' and value['execution'] == req['execution'] and
         value['requestSha256'] == validate_request(req, domain=domain(req)) and value['status'] in ('PASS', 'FAIL'),
         'V5.2 completion identity/outcome')
    hex_value(value['cleanupSha256'])
    if value['status'] == 'PASS' or value['evidenceSha256'] is not None: hex_value(value['evidenceSha256'])
    return value


def finish(ledger, req, completion):
    validate_completion(completion, req); result = deepcopy(ledger)
    result['entries'].append(dict(kind='FINISHED', requestSha256=validate_request(req, domain=domain(req)),
                                  status=completion['status'], completionSha256=digest(encoded(completion))))
    inspect_ledger(result, domain=domain(req)); return result


def budget_warning(req, ledger):
    total = inspect_ledger(ledger, domain=domain(req))['reservedCostMicrousd']
    return dict(reservedCostMicrousd=total, softBudgetMicrousd=req['policy']['budgetMicrousd'],
                exceeded=total > req['policy']['budgetMicrousd'], estimateOnly=True)
