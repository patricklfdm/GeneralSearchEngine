"""Fresh admitted native resource creation and fixed IAP identity probes.

Internal integration entry only: no CLI or workflow dispatch is installed.
Success is PARTIAL and leaves a charged lease for the future owned workload or
independent expiry cleanup. Native failure enters immediate owner recovery.
The default entry stops after IAP; the separate fixed
guest-preparation entry continues under this invocation's original deadline.
Neither entry performs an engine workload or successful ledger completion.
"""
from copy import deepcopy
from pathlib import Path
import time
from urllib.parse import urlsplit, parse_qsl
from . import cloud_runner_admission as admission, cloud_runner_iap as iap
from . import cloud_experiment_resources as resources, cloud_http as h, cloud_native_authority as n
from . import guest_setup, performance_model as m
from .remote_command import write_once


class _Api(resources._Policy, h.Api):
    def __init__(self, inspected, *, now, deadline):
        m.need(type(inspected) in (admission.NetworkAdmission, admission.OfflineAdmission) and
               inspected.result['status'] == 'REQUEST_BOUND', 'resource admission constructor')
        source = inspected.api
        h.Api.__init__(self, transport=source.transport, tokens=source.tokens, clock=source.clock)
        self.token, self.expires = source.token, source.expires
        self.initialize(inspected.result['resourcePlan'], now)
        self.deadline = min(self.deadline, deadline)
        self.gate_open = False
        self.owner_deadline = self.clock()+admission.workload.load()['budgets']['leaseSeconds']
        self.last_lease_write = None
        self.failure_claimed = False
        self.owner_claimed = False

    def marker_value(self):
        return dict(super().marker_value(), execution='offline-runner-resources' if self.offline else 'native-runner-resources',
                    paidCloud=not self.offline, paidAdmission=not self.offline)

    def authorize(self, method, url, body):
        # Enforced even for a direct call through h.Api.call.
        m.need(self.clock() < self.deadline and not self.failed and not self.owner_claimed, 'Runner resource original deadline/failed stage')
        if method != 'GET': m.need(self.gate_open, 'Runner mutation admission gate closed')
        if method == 'GET' and self.state == 'done':
            parsed = urlsplit(url); pairs = parse_qsl(parsed.query, strict_parsing=True) if parsed.query else []
            if parsed._replace(query='').geturl() in {self.provider().url(row['spec'])+'/getGuestAttributes'
                    for row in self.lease['resources'] if row['spec']['kind'] == 'instance' and row['id'] is not None}:
                m.need(body is None and pairs == [('queryPath','hostkeys/')], 'Runner host-key read scope')
                return
        super().authorize(method, url, body)
        if method == 'POST' and self.state in ('lease', 'intent', 'identity'):
            # Before transport: a lost CAS response is still our original write.
            self.last_lease_write = deepcopy(self.write_step())


def _run(root, value, key, inspect, recheck, *, clock, wall, sleep, exchange, offline, guest_stage=None, on_failure=None):
    root = Path(root); root.mkdir(parents=True, exist_ok=False)
    start = clock(); deadline = start+admission.workload.load()['budgets']['preparationSeconds']
    api = None; inspected = None; phase = 'admission'
    receipt = dict(schema='gse-v51-runner-resource-entry-v1', status='FAIL',
        execution='offline-runner-resource-entry' if offline else 'native-runner-resource-entry',
        paidCloud=False, paidAdmission=False, resourcesCreated=False,
        engineWorkloadExecuted=False, fullRemoteQualification=False)
    try:
        m.need(not Path(key).resolve().is_relative_to(root.resolve()), 'Runner private key inside evidence')
        guest_setup.check_private_key(key, value['resourcePlan']['guestAccess'])
        inspected = inspect()  # Never accept a copied REQUEST_BOUND receipt.
        m.need(inspected.api.offline is offline, 'Runner preparation transport domain')
        write_once(root/'inspection.json', inspected.result)
        write_once(root/'plan.json', value)
        receipt.update(planSha256=inspected.result['planSha256'],
                       requestSha256=n.validate_request(inspected.result['resourcePlan']['request']))
        deadline = min(deadline, clock()+inspected.result['expiresAt']-wall())
        m.need(clock() < deadline, 'Runner preparation original deadline')
        api = _Api(inspected, now=int(wall()), deadline=deadline)

        def gate():
            # Resource-name scans may take time. Recheck the original request,
            # source/prechecks/CI/archives/controls just before the lease CAS.
            recheck(inspected)
            m.need(api.store.get(n.LEASE) is None and
                   m.canonical(api.store.get(n.LEDGER)) == m.canonical(api.value['baseline']), 'Runner allocation control drift')
            m.need(clock() < deadline and wall() < inspected.result['expiresAt'], 'Runner allocation admission expired')
            api.gate_open = True
            receipt.update(paidCloud=not offline, paidAdmission=not offline)

        phase = 'resources'
        flags = dict(resources.FLAGS, paidCloud=not offline, paidAdmission=not offline)
        stage = resources._prepare(api.value, api, root/'resources', now=int(wall()), sleep=sleep,
            execution=receipt['execution'], flags=flags, before_mutation=gate)
        m.need(stage['status'] == 'RESOURCES_PREPARED', 'Runner resource stage failed')
        receipt.update(resourcesCreated=True, requestSha256=n.validate_request(api.req), leaseGeneration=api.generation,
                       reservedCostMicrousd=api.value['reservation']['maximumCostMicrousd'],
                       expiresAt=api.lease['expiresAt'], cleanupEligibleAt=api.lease['expiresAt']+api.lease['graceSeconds'])
        phase = 'iap'
        receipt['guests'] = iap.probe(api, key, root/'iap', exchange=exchange)
        m.need(clock() <= deadline, 'Runner preparation late result')
        receipt.update(status='PARTIAL', stage='RESOURCES_AND_IAP_READY')
        if guest_stage is not None:
            phase = 'guest-setup'; receipt['status'] = 'FAIL'
            with iap.preparation_connections(api,root/'iap-preparation.json'):
                receipt['guestSetup'] = guest_stage(api,key,root,receipt['guests'])
            m.need(clock() < deadline, 'Runner guest setup original deadline')
            receipt.update(status='PARTIAL',stage='GUEST_PACKAGES_READY')
    except (Exception, KeyboardInterrupt) as error:
        if api is not None: api.failed = True
        receipt['failure'] = dict(phase=phase, type=type(error).__name__)
        if isinstance(error, h.ApiError): receipt['failure']['httpStatus'] = error.status
        if api is not None:
            observed = getattr(api,'guest_failure_at',clock())
            receipt['failure']['code'] = ('PREPARATION_DEADLINE' if observed>=deadline else
                'PROVIDER_HTTP' if isinstance(error,h.ApiError) else
                'GUEST_TIMEOUT' if isinstance(error,TimeoutError) else
                'GUEST_TRANSPORT' if isinstance(error,ConnectionError) else 'PREPARATION_REJECTED')
            receipt['failure']['deadlineNanos'] = int(deadline*1e9)
            receipt['failure']['observedNanos'] = int(observed*1e9)
            if hasattr(api,'guest_operation'): receipt['failure']['operation'] = deepcopy(api.guest_operation)
    finally:
        try:
            if inspected is not None: write_once(root/'admission-http.json', inspected.api.requests)
            if api is not None:
                write_once(root/'http.json', api.requests)
                # A local snapshot is diagnostic; only retained CAS bytes authorize cleanup.
                write_once(root/'lease-observation.json', dict(generation=api.generation, lease=api.lease))
                known = sum(row['id'] is not None for row in api.lease['resources'])
                unresolved = sum(row['attempted'] and row['id'] is None for row in api.lease['resources'])
                receipt.update(confirmedResourceCount=known, unresolvedIntentCount=unresolved,
                               resourcesCreated=True if known else None if unresolved else False)
            receipt['elapsedSeconds'] = max(0, clock()-start)
            write_once(root/'receipt.json', receipt)
        except (Exception, KeyboardInterrupt) as error:
            if on_failure is None: raise
            if api is not None: api.failed = True
            receipt['status'] = 'FAIL'
            receipt.setdefault('failure', dict(phase='local-evidence', type=type(error).__name__))
    if receipt['status'] == 'FAIL' and api is not None and api.gate_open and on_failure is not None:
        recovery = on_failure(api, root, receipt)
        if recovery is not None: receipt = dict(receipt, ownerRecovery=recovery)
    return receipt


def _recheck(cfg, env, source, checkout, preflight, precheck_root, value, approved, artifacts, inspected,
             *, get, wall, binding, controls=None):
    bound = admission.context(cfg, env, source, checkout, preflight, precheck_root, value, approved, get=get, now=int(wall()))
    m.need(bound['binding'] == inspected.result['binding'] and bound['prerequisites'] == inspected.result['prerequisites'],
           'Runner allocation prerequisite drift')
    # Re-run original byte verification and fresh provider/GitHub checks under a
    # read-only API. Its first inspection deadline is never renewed.
    again = admission.inspect(inspected.api, value, bound, artifacts, binding(), get=get, wall=wall, offline_controls=controls)
    m.need(again['planSha256'] == inspected.result['planSha256'], 'Runner allocation plan drift')


def prepare_native(cfg, env, source, checkout, preflight, precheck_root, value, approved, artifacts, key, output):
    """No transport/account/clock/probe override. No installed paid caller yet."""
    return _prepare_native(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts,key,output)


def _prepare_native(cfg, env, source, checkout, preflight, precheck_root, value, approved, artifacts, key, output, *, guest_stage=None, on_failure=None):
    from .cloud_runner_failure import recover
    cfg, env, value, approved = map(deepcopy, (cfg, env, value, approved))
    def inspect():
        return admission.NetworkAdmission(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts)
    def recheck(inspected):
        _recheck(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts,inspected,
                 get=admission.ci.github, wall=time.time, binding=lambda:admission.build.binding(admission.ci.ROOT,source))
    return _run(output,value,key,inspect,recheck,clock=time.monotonic,wall=time.time,sleep=time.sleep,
                exchange=iap._network_probe,offline=False,guest_stage=guest_stage,on_failure=on_failure or recover)


def prepare_offline(cfg, env, source, preflight, precheck_root, value, approved, artifacts, key, output, *,
                    transport, issuer, descriptor, clock, wall, sleep, get, binding, probe, controls=None, on_failure=None):
    m.need(transport.offline is True and issuer.offline is True and probe.offline is True, 'Runner resource offline dependencies')
    def inspect():
        return admission.OfflineAdmission(cfg,env,source,preflight,precheck_root,value,approved,artifacts,binding,
            transport=transport,issuer=issuer,descriptor=descriptor,clock=clock,wall=wall,get=get,controls=controls)
    def recheck(inspected):
        _recheck(cfg,env,source,source,preflight,precheck_root,value,approved,artifacts,inspected,
                 get=get,wall=wall,binding=lambda:binding,controls=controls)
    return _run(output,value,key,inspect,recheck,clock=clock,wall=wall,sleep=sleep,
                exchange=lambda api,target,deadline:probe.identity(target,deadline),offline=True,on_failure=on_failure)
