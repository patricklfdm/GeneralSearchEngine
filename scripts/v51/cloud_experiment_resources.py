"""Ordinary experiment resource lifecycle, qualified only through offline HTTP.

This is the resource stage, not a paid Runner entry or an engine result. Native
request/lease bytes remain distinct from the fake owned-workload domain. The
separate Runner entry authenticates source/build/package, current preflight,
prices and exact approval before using this private shared driver with a native
creation policy. The public preparer in this module stays offline-only.
"""
from copy import deepcopy
from pathlib import Path
import time
from . import cloud_authority as a, cloud_native_authority as n
from . import cloud_gcp as g, cloud_http as h, cloud_cleanup as cleanup
from . import cloud_workload_contract as workload, performance_model as m
from . import guest_setup, remote_command as c
from .cloud_resource_creation import CreationPolicy

SCHEMA = 'gse-v51-experiment-resource-plan-v1'
EXECUTION = 'offline-native-experiment-resources'
FLAGS = dict(paidCloud=False, paidAdmission=False, nativeResourcesQualified=False,
             engineWorkloadExecuted=False, fullRemoteQualification=False)


def make(configuration, req, guest_access, baseline, inputs, *, now, maximum_cost):
    """Bind already selected inputs; hashes here do not authenticate build bytes."""
    sha = n.validate_request(req)
    from . import native_preset_timing as full
    m.need(full.selected(req) or req['member'] == 'experiment' and req['order'] == 'experiment-first', 'resource experiment scope')
    m.need(g.config(configuration) == req['configurationSha256'], 'resource configuration binding')
    guest_setup.access(guest_access)
    m.need(guest_access['attempt'] == req['attempt'] and
           m.sha(m.canonical(guest_access)) == req['guestAccessSha256'], 'resource guest access binding')
    a.integer(now, req['createdAt'], req['createdAt']+899)
    m.need(type(inputs) is dict and set(inputs) == {'source', 'archiveSha256', 'buildManifestSha256',
           'packageManifestSha256', 'workloadSha256', 'pricesSha256'}, 'resource input fields')
    a.digest(inputs['source'], 40)
    for key in set(inputs)-{'source'}: a.digest(inputs[key])
    m.need((inputs['source'], inputs['archiveSha256'], inputs['workloadSha256']) ==
           (req['source'], req['bundleSha256'], workload.PLAN_SHA256), 'resource input binding')
    if baseline is not None:
        m.need(type(baseline) in (tuple, list) and len(baseline) == 2, 'resource ledger observation')
        a.integer(baseline[0], 1)
    old = baseline[1] if baseline is not None else n.empty_ledger()
    total, attempts = n.inspect_ledger(old)
    m.need(not any(v['status'] == 'PENDING' for v in attempts.values()), 'resource pending reservation')
    approval = dict(requestSha256=sha, previousCostMicrousd=total,
                    maximumCostMicrousd=a.integer(maximum_cost, 1, a.MAXIMUM_BUDGET_MICROUSD))
    n.reserve(old, req, approval)  # Includes sequence, attempt uniqueness and cumulative ceiling.
    return m.strict_json(m.canonical(dict(schema=SCHEMA, execution=EXECUTION, request=deepcopy(req),
        configuration=deepcopy(configuration), guestAccess=deepcopy(guest_access), baseline=deepcopy(baseline),
        inputs=deepcopy(inputs), reservation=approval, expiresAt=req['createdAt']+900, **FLAGS)))


def validate(value, *, now):
    expected = make(value['configuration'], value['request'], value['guestAccess'], value['baseline'],
                    value['inputs'], now=now, maximum_cost=value['reservation']['maximumCostMicrousd'])
    m.need(value == expected, 'resource plan drift')
    return m.sha(m.canonical(value))


def marker_key(req):
    return n.PREFIX+'attempts/'+n.validate_request(req)+'/resources-prepared.json'


def plan_key(req):
    return n.PREFIX+'attempts/'+n.validate_request(req)+'/resource-plan.json'


class _Policy(CreationPolicy):
    def initialize(self, value, now):
        validate(value, now=now)
        self.value = deepcopy(value)
        # No topology qualification manifest: ordinary DELETE-on-expiry profile.
        self.initialize_creation(value['configuration'], value['request'], value['guestAccess'],
                                 value['baseline'], value['reservation'], now, intent_record=(plan_key(value['request']), value))

    def marker_key(self):
        return marker_key(self.req)

    def marker_value(self):
        return dict(schema='gse-v51-experiment-resources-prepared-v1', plan=self.value,
                    planSha256=m.sha(m.canonical(self.value)), lease=deepcopy(self.lease),
                    leaseGeneration=self.generation, **FLAGS)


class OfflineApi(_Policy, h.Api):
    def __init__(self, value, now, *, transport, tokens, clock):
        m.need(transport.offline is True, 'resource qualifier requires offline HTTP')
        h.Api.__init__(self, transport=transport, tokens=tokens, clock=clock)
        self.initialize(value, now)


def prepare(value, api, output, *, now, sleep=time.sleep):
    """Retain charged authority and exact IDs for the next stage or cleanup.

    Returning RESOURCES_PREPARED deliberately leaves the active lease/reservation;
    it cannot finish a successful experiment or refund an interrupted attempt.
    """
    m.need(type(api) is OfflineApi and api.offline is True and api.value == value,
           'resource preparation offline binding')
    return _prepare(value, api, output, now=now, sleep=sleep, execution=EXECUTION, flags=FLAGS)


def _prepare(value, api, output, *, now, sleep, execution, flags, before_mutation=None):
    """Shared stage driver; public entries own admission and transport selection."""
    digest = validate(value, now=now)
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    c.write_once(root/'plan.json', value)
    receipt = dict(schema='gse-v51-experiment-resource-stage-v1', status='FAIL', execution=execution,
                   planSha256=digest, requestSha256=n.validate_request(api.req), **flags)
    phase = 'original-state'
    try:
        m.need(api.state == 'lease' and not api.failed and api.store.get(n.LEASE) is None and
               m.canonical(api.store.get(n.LEDGER)) == m.canonical(value['baseline']), 'resource original state changed')
        for key in (cleanup.context_key(api.req, authority=n), plan_key(api.req), marker_key(api.req)):
            m.need(api.store.get(key) is None, 'resource retained object already exists')
        provider = api.provider(sleep)
        for row in api.lease['resources']:
            spec = row['spec']
            m.need(provider.describe(spec) is None and provider.operation(spec)['state'] == 'UNKNOWN',
                   'resource name/operation already exists')
        phase = 'admission-recheck'
        if before_mutation is not None: before_mutation()
        while api.state != 'done':
            phase = api.state
            if phase == 'insert': api.insert(sleep)
            else: api.upload()
        m.need(api.clock() <= api.deadline, 'resource preparation deadline')
        receipt.update(status='RESOURCES_PREPARED', leaseGeneration=api.generation,
                       resources=deepcopy(api.lease['resources']), reservedCostMicrousd=value['reservation']['maximumCostMicrousd'],
                       expiresAt=api.lease['expiresAt'], cleanupEligibleAt=api.lease['expiresAt']+api.lease['graceSeconds'])
    except (Exception, KeyboardInterrupt) as error:
        api.failed = True
        receipt['failure'] = dict(phase=phase, type=type(error).__name__)
        if isinstance(error, h.ApiError): receipt['failure']['httpStatus'] = error.status
    finally:
        c.write_once(root/'http.json', api.requests)
        c.write_once(root/'receipt.json', receipt)
    return receipt
