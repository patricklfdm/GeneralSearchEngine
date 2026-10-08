"""Owned V5.1 lifecycle and expired reconciliation, currently fake-adapter only.

Store writes/deletes are generation-conditional. Compute adapters must resolve
original operation IDs and delete with an exact resource ID, never by name alone.
"""
from copy import deepcopy
from pathlib import Path
import time
import re
from . import cloud_authority as a, performance_model as m
from .remote_budget import Budget
from .remote_command import write_once


def adapters(store, provider, *, authority=a):
    m.need(store.execution == provider.execution == authority.ADAPTER_EXECUTION, 'unqualified cloud adapter; paid execution disabled')


def failure(phase, error, *, redact=False):
    value = dict(phase=phase, type=type(error).__name__)
    if not redact: value['message'] = str(error)[:2000]
    return value


def retain(store, key, value):
    """Immutable upload plus exact read-back; failed/partial uploads are not success."""
    old = store.get(key)
    if old is None:
        generation = store.put(key, value, 0)
    else:
        generation, previous = old
        m.need(previous == value, 'retention object changed')
    m.need(store.get(key) == (generation, value), 'retention read-back')
    return m.sha(value if isinstance(value, bytes) else m.canonical(value))


def cleanup(provider, lease, persist, *, authority=a, redact=False):
    """One shared cleanup path for finally, schedule and manual reconciliation."""
    authority.validate_lease(lease)
    from . import cloud_native_authority as native
    redact = redact or getattr(provider, 'execution', None) == native.CLEANUP_EXECUTION
    if provider is not None: provider.begin_cleanup()
    errors, checks = [], []
    rows = sorted(lease['resources'], key=lambda r: {'instance': 0, 'disk': 1, 'firewall': 2}[r['spec']['kind']])
    resolved = {}
    for row in rows:
        if not row['attempted']: continue
        spec = row['spec']
        try:
            operation = provider.operation(spec)
            m.need(operation['spec'] == spec and operation['state'] == 'DONE', 'unresolved create operation')
            observed_id = operation['id']
            if observed_id is not None:
                m.need(isinstance(observed_id, str) and re.fullmatch('[1-9][0-9]{0,19}', observed_id),
                       'operation exact ID')
            m.need(row['id'] is None or row['id'] == observed_id, 'operation ID changed')
            current = provider.describe(spec)
            if current is not None:
                m.need(observed_id is not None and current == dict(spec=spec, id=observed_id), 'ownership/resource ID mismatch')
            # Resolve the operation even when describe is absent: no late insert may
            # be mistaken for final absence. Adopt IDs only from this exact intent.
            row['id'] = observed_id
            persist()
            resolved[spec['name']] = observed_id
            if current is not None: provider.delete(spec, observed_id)
        except (Exception, KeyboardInterrupt) as error:
            errors.append(failure('delete:'+spec['name'], error, redact=redact))
    for row in rows:
        if not row['attempted']: continue
        spec = row['spec']
        try:
            current = provider.describe(spec)
            absent = spec['name'] in resolved and current is None
            checks.append(dict(name=spec['name'], expectedId=row['id'], absent=absent, observed=current))
        except (Exception, KeyboardInterrupt) as error:
            errors.append(failure('absence:'+spec['name'], error, redact=redact))
            checks.append(dict(name=spec['name'], expectedId=row['id'], absent=False))
    return dict(status='PASS' if not errors and all(r['absent'] for r in checks) else 'FAIL',
                checks=checks, errors=errors, leftovers=[r['name'] for r in checks if not r['absent']])


def finalize(store, lease, completion, *, authority=a):
    """Retention precedes the append-only terminal event and lease release."""
    req = lease['request']; sha = authority.validate_request(req)
    key = a.PREFIX+'attempts/'+sha+'/completion.json'
    retain(store, key, completion)
    current = store.get(a.LEDGER)
    if current is not None:
        generation, ledger = current
        _, attempts = authority.inspect_ledger(ledger)
        if sha in attempts:
            if attempts[sha]['status'] == 'PENDING':
                store.put(a.LEDGER, authority.finish(ledger, req, completion), generation)
            else:
                m.need(any(r.get('completionSha256') == m.sha(m.canonical(completion)) and
                           r['requestSha256'] == sha for r in ledger['entries']), 'terminal completion changed')


class Runner:
    def __init__(self, store, provider, probe, output, *, clock=time.monotonic_ns, wall=time.time, startup=None,
                 qualification=None):
        adapters(store, provider)
        m.need(probe.execution == a.EXECUTION, 'unqualified workload adapter')
        self.store, self.provider, self.probe = store, provider, probe
        self.output, self.clock, self.wall = Path(output), clock, wall
        self.generation = None
        if startup is not None: m.need(startup.execution == a.EXECUTION, 'unqualified startup adapter')
        self.startup = startup
        from .guest_owned_workload import SCOPES as singles
        from .guest_owned_three_mode import MODE, SCOPE
        from . import guest_owned_faults as faults
        from . import guest_owned_experiment as experiment
        from . import guest_owned_network as network
        from . import guest_owned_drill as drill
        SCOPES={**singles,MODE:SCOPE,faults.MODE:faults.SCOPE,experiment.MODE:experiment.SCOPE,faults.MaintenanceProbe.mode:faults.MaintenanceProbe.scope,network.MODE:network.SCOPE,drill.MODE:drill.SCOPE}
        self.qualification_cells=(list(drill.CASES) if qualification==drill.SCOPE else list(network.CASES) if qualification==network.SCOPE else list(experiment.CELLS) if qualification==experiment.SCOPE else ['maintenance'] if qualification==faults.MaintenanceProbe.scope else list(faults.CASES) if qualification==faults.SCOPE else ['healthy'])
        m.need((qualification is None and getattr(probe,'scope',None) not in SCOPES.values()) or
               qualification in SCOPES.values() and getattr(probe,'scope',None)==qualification and
               SCOPES.get(getattr(probe,'mode',None))==qualification and
               getattr(probe,'services',None) is not None and startup is not None and
               getattr(startup,'services',None) is probe.services,
               'owned workload qualification scope/startup')
        self.qualification=qualification

    def persist(self):
        a.validate_lease(self.lease)
        self.generation = self.store.put(a.LEASE, self.lease, self.generation)

    def run(self, req, preflight, approval):
        sha = a.admit(req, preflight, approval, int(self.wall()))
        m.need(self.qualification is None or req['member']=='experiment', 'owned qualification is not a full preset')
        self.output.mkdir(parents=True, exist_ok=False)
        self.lease = a.lease(req, int(self.wall()))
        result = dict(schema='gse-v51-control-completion-v1', execution=a.EXECUTION, paidCloud=False,
                      engineWorkloadExecuted=False, fullRemoteQualification=False, requestSha256=sha,
                      errors=[], status='RUNNING', cleanup=None, retention='INCOMPLETE', leaseReleased=False)
        budget = Budget(clock=self.clock)
        if self.qualification: result['qualificationScope']=self.qualification
        try:
            # A pre-existing lease, even expired, blocks allocation until reconciled.
            stored = self.store.get(a.LEDGER)
            version, ledger = stored if stored else (0, a.empty_ledger())
            reservation = a.reserve(ledger, req, approval)
            self.generation = self.store.put(a.LEASE, self.lease, 0)
            self.store.put(a.LEDGER, reservation, version)
            with budget.stage('preparation') as deadline:
                # Publish the public reconstruction inputs before any create
                # intent. An independent watchdog cannot use runner memory/keys.
                context = getattr(self.provider, 'cleanup_context', None)
                if context is not None:
                    from .cloud_cleanup import retain_context
                    retain_context(self.store, req, context())
                for row in self.lease['resources']:
                    m.need(self.clock() < deadline, 'provisioning deadline')
                    spec = row['spec']
                    m.need(self.provider.describe(spec) is None, 'resource name exists')
                    row['attempted'] = True
                    self.persist()  # Durable intent BEFORE issuing the create.
                    observed = self.provider.create(spec, deadline)
                    m.need(observed['spec'] == spec, 'created resource identity')
                    row['id'] = observed['id']
                    self.persist()
                if self.startup is not None:
                    result['guestStartup'] = self.startup.prepare(req, deepcopy(self.lease), deadline)
                self.probe.prepare(req, deadline)
            plan = a.workload.load()
            preset = 'failureDrill' if req['member'] == 'failure-drill' else ('canonical' if req['member'].startswith('canonical-') else 'experiment')
            for cell in (self.qualification_cells if self.qualification else plan['presets'][preset]['cells']):
                with budget.stage(cell) as deadline:
                    self.probe.cell(cell, deadline)
        except (Exception, KeyboardInterrupt) as error:
            result['errors'].append(failure('execution', error))
        finally:
            if self.generation is not None:
                # Stop, collection and cleanup are each attempted even after another fails.
                try: self.probe.stop()
                except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('stop', error))
                if self.qualification: result['engineWorkloadExecuted']=self.probe.engineWorkloadExecuted
                startup_stopped = False
                def stop_startup(deadline):
                    nonlocal startup_stopped
                    startup_stopped = True
                    if self.startup is not None:
                        try: self.startup.stop(deadline)
                        except (Exception, KeyboardInterrupt) as error:
                            result['errors'].append(failure('guest-stop', error))
                def retain_startup():
                    if self.startup is not None:
                        for name, data in self.startup.retention_files():
                            retain(self.store, a.PREFIX+'attempts/'+sha+'/startup/'+name, data)
                try:
                    with budget.stage('validation-retention') as deadline:
                        try:
                            result['evidence'] = self.probe.collect_validate(self.output, deadline)
                        finally:
                            stop_startup(deadline)
                            retain_startup()
                        evidence=result['evidence']
                        m.need(evidence['execution']==a.EXECUTION and
                               (evidence['engineWorkloadExecuted'] is False if self.qualification is None else
                                evidence['scope']==self.qualification and evidence['paidCloud'] is False and
                                evidence['mode']==self.probe.mode and
                                evidence['fullRemoteQualification'] is False and type(evidence['physicalHistoryQualified']) is bool and
                                evidence['engineWorkloadExecuted'] is result['engineWorkloadExecuted']), 'probe evidence scope')
                        for name, data in self.probe.retention_files():
                            retain(self.store, a.PREFIX+'attempts/'+sha+'/parts/'+name, data)
                        result['evidenceSha256'] = retain(self.store, a.PREFIX+'attempts/'+sha+'/evidence.json', result['evidence'])
                        if self.qualification:
                            m.need(evidence['status']=='PASS' and evidence['cells']==self.qualification_cells and
                                   evidence['engineWorkloadExecuted'] is True and
                                   evidence['physicalHistoryQualified'] is self.probe.require_physical and
                                   (not getattr(self.probe,'require_backup',False) or evidence.get('backupRestoreQualified') is True),
                                   'owned workload qualification failed')
                except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('retention', error))
                try:
                    with budget.stage('cleanup') as deadline:
                        if not startup_stopped:
                            stop_startup(deadline)
                            try: retain_startup()
                            except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('startup-retention', error))
                        result['cleanup'] = cleanup(self.provider, self.lease, self.persist)
                except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('cleanup', error))
                result['budget'] = budget.finish()
                result['status'] = ('PASS' if not result['errors'] and result['cleanup']['status'] == 'PASS' and
                                    result['budget']['status'] == 'PASS' else 'FAIL')
                completion = {k: deepcopy(v) for k, v in result.items() if k not in ('retention', 'leaseReleased')}
                try:
                    # Even failures need a retained terminal record. Evidence upload
                    # failure keeps the lease for explicit expired reconciliation.
                    finalize(self.store, self.lease, completion)
                    result['retention'] = 'VERIFIED'
                    if result['cleanup'] and result['cleanup']['status'] == 'PASS' and 'evidenceSha256' in result:
                        self.store.delete(a.LEASE, self.generation)
                        result['leaseReleased'] = True
                except (Exception, KeyboardInterrupt) as error:
                    result['errors'].append(failure('completion', error)); result['status'] = 'FAIL'
            else:
                result['status'] = 'FAIL'
            write_once(self.output/'receipt.json', result)
        return result


def cleanup_adapters(store, provider, authority):
    """Network authorization is specific to cleanup; Runner still uses adapters()."""
    if store.execution == authority.ADAPTER_EXECUTION:
        if provider is not None: adapters(store, provider, authority=authority)
        return store.execution
    from . import cloud_gcp as g, cloud_native_authority as n
    from .cloud_native_cleanup import NetworkCleanupApi
    m.need(authority is n and type(store) is g.Store and type(store.api) is NetworkCleanupApi and
           store.execution == n.CLEANUP_EXECUTION, 'unqualified cleanup store; paid execution disabled')
    if provider is not None:
        m.need(type(provider) is g.Compute and provider.api is store.api and
               provider.execution == n.CLEANUP_EXECUTION, 'unqualified cleanup provider')
    return n.CLEANUP_EXECUTION


def reconcile(store, provider, output, *, trigger, now, provider_factory=None, authority=a, on_expired=None):
    execution = cleanup_adapters(store, provider, authority)
    if provider_factory is None:
        m.need(provider is not None, 'cleanup provider missing')
    else:
        m.need(provider is None and callable(provider_factory), 'cleanup provider factory')
    m.need(trigger in ('schedule', 'manual'), 'cleanup trigger')
    a.integer(now, 1)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    current = store.get(a.LEASE)
    if current is None:
        result = dict(status='PASS', activeLease=False, trigger=trigger, execution=execution)
    else:
        generation, lease = current
        authority.validate_lease(lease)
        if now < lease['expiresAt']+lease['graceSeconds']:
            result = dict(status='WAITING', activeLease=True, trigger=trigger, execution=execution)
        else:
            if provider_factory is not None or on_expired is not None:
                try:
                    if on_expired is not None: on_expired(deepcopy(lease), generation)
                    if provider_factory is not None and any(row['attempted'] for row in lease['resources']):
                        provider = provider_factory(deepcopy(lease))
                        cleanup_adapters(store, provider, authority)
                except (Exception, KeyboardInterrupt) as error:
                    result = dict(status='FAIL', trigger=trigger, execution=execution,
                                  leaseReleased=False, failure=failure('reconstruction', error, redact=execution != authority.ADAPTER_EXECUTION))
                    write_once(output/'receipt.json', result)
                    return result
            # A lease lost before its first create intent needs no provider or
            # SSH descriptor. The same terminal ledger/retention path still runs.
            def persist():
                nonlocal generation
                generation = store.put(a.LEASE, lease, generation)
            outcome = cleanup(provider, lease, persist, authority=authority)
            sha = authority.validate_request(lease['request'])
            result = dict(status='FAIL', trigger=trigger, execution=execution, cleanup=outcome, leaseReleased=False)
            try:
                # Preserve a previous completion if upload succeeded but read-back or
                # finalization was interrupted. Otherwise retain an explicit failed attempt.
                key = a.PREFIX+'attempts/'+sha+'/completion.json'
                old = store.get(key)
                completion = old[1] if old else dict(schema=authority.COMPLETION_SCHEMA,
                    execution=authority.EXECUTION, requestSha256=sha, status='FAIL', paidCloud=authority.PAID_CLOUD,
                    engineWorkloadExecuted=False, fullRemoteQualification=False, reason='expired interrupted owner')
                m.need(completion['requestSha256'] == sha and completion['execution'] == authority.EXECUTION,
                       'reconciled completion identity')
                retain(store, a.PREFIX+'attempts/'+sha+f'/cleanup-{generation}.json', result)
                finalize(store, lease, completion, authority=authority)
                if outcome['status'] == 'PASS':
                    store.delete(a.LEASE, generation)
                    result.update(status='PASS', leaseReleased=True)
            except (Exception, KeyboardInterrupt) as error:
                result['failure'] = failure('reconciliation', error, redact=execution != authority.ADAPTER_EXECUTION)
    write_once(output/'receipt.json', result)
    return result
