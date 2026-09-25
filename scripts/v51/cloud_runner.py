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


def adapters(store, provider):
    m.need(store.execution == provider.execution == a.EXECUTION, 'unqualified cloud adapter; paid execution disabled')


def failure(phase, error):
    return dict(phase=phase, type=type(error).__name__, message=str(error)[:2000])


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


def cleanup(provider, lease, persist):
    """One shared cleanup path for finally, schedule and manual reconciliation."""
    a.validate_lease(lease)
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
            errors.append(failure('delete:'+spec['name'], error))
    for row in rows:
        if not row['attempted']: continue
        spec = row['spec']
        try:
            current = provider.describe(spec)
            absent = spec['name'] in resolved and current is None
            checks.append(dict(name=spec['name'], expectedId=row['id'], absent=absent, observed=current))
        except (Exception, KeyboardInterrupt) as error:
            errors.append(failure('absence:'+spec['name'], error))
            checks.append(dict(name=spec['name'], expectedId=row['id'], absent=False))
    return dict(status='PASS' if not errors and all(r['absent'] for r in checks) else 'FAIL',
                checks=checks, errors=errors, leftovers=[r['name'] for r in checks if not r['absent']])


def finalize(store, lease, completion):
    """Retention precedes the append-only terminal event and lease release."""
    req = lease['request']; sha = a.validate_request(req)
    key = a.PREFIX+'attempts/'+sha+'/completion.json'
    retain(store, key, completion)
    current = store.get(a.LEDGER)
    if current is not None:
        generation, ledger = current
        _, attempts = a.inspect_ledger(ledger)
        if sha in attempts:
            if attempts[sha]['status'] == 'PENDING':
                store.put(a.LEDGER, a.finish(ledger, req, completion), generation)
            else:
                m.need(any(r.get('completionSha256') == m.sha(m.canonical(completion)) and
                           r['requestSha256'] == sha for r in ledger['entries']), 'terminal completion changed')


class Runner:
    def __init__(self, store, provider, probe, output, *, clock=time.monotonic_ns, wall=time.time):
        adapters(store, provider)
        m.need(probe.execution == a.EXECUTION, 'unqualified workload adapter')
        self.store, self.provider, self.probe = store, provider, probe
        self.output, self.clock, self.wall = Path(output), clock, wall
        self.generation = None

    def persist(self):
        a.validate_lease(self.lease)
        self.generation = self.store.put(a.LEASE, self.lease, self.generation)

    def run(self, req, preflight, approval):
        sha = a.admit(req, preflight, approval, int(self.wall()))
        self.output.mkdir(parents=True, exist_ok=False)
        self.lease = a.lease(req, int(self.wall()))
        result = dict(schema='gse-v51-control-completion-v1', execution=a.EXECUTION, paidCloud=False,
                      engineWorkloadExecuted=False, fullRemoteQualification=False, requestSha256=sha,
                      errors=[], status='RUNNING', cleanup=None, retention='INCOMPLETE', leaseReleased=False)
        budget = Budget(clock=self.clock)
        try:
            # A pre-existing lease, even expired, blocks allocation until reconciled.
            stored = self.store.get(a.LEDGER)
            version, ledger = stored if stored else (0, a.empty_ledger())
            reservation = a.reserve(ledger, req, approval)
            self.generation = self.store.put(a.LEASE, self.lease, 0)
            self.store.put(a.LEDGER, reservation, version)
            with budget.stage('preparation') as deadline:
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
                self.probe.prepare(req, deadline)
            plan = a.workload.load()
            preset = 'failureDrill' if req['member'] == 'failure-drill' else ('canonical' if req['member'].startswith('canonical-') else 'experiment')
            for cell in plan['presets'][preset]['cells']:
                with budget.stage(cell) as deadline:
                    self.probe.cell(cell, deadline)
        except (Exception, KeyboardInterrupt) as error:
            result['errors'].append(failure('execution', error))
        finally:
            if self.generation is not None:
                # Stop, collection and cleanup are each attempted even after another fails.
                try: self.probe.stop()
                except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('stop', error))
                try:
                    with budget.stage('validation-retention') as deadline:
                        result['evidence'] = self.probe.collect_validate(self.output, deadline)
                        # This is only diagnostic control evidence, never engine acceptance.
                        m.need(result['evidence']['execution'] == a.EXECUTION and
                               result['evidence']['engineWorkloadExecuted'] is False, 'probe evidence scope')
                        for name, data in self.probe.retention_files():
                            retain(self.store, a.PREFIX+'attempts/'+sha+'/parts/'+name, data)
                        result['evidenceSha256'] = retain(self.store, a.PREFIX+'attempts/'+sha+'/evidence.json', result['evidence'])
                except (Exception, KeyboardInterrupt) as error: result['errors'].append(failure('retention', error))
                try:
                    with budget.stage('cleanup'):
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


def reconcile(store, provider, output, *, trigger, now):
    adapters(store, provider)
    m.need(trigger in ('schedule', 'manual'), 'cleanup trigger')
    a.integer(now, 1)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    current = store.get(a.LEASE)
    if current is None:
        result = dict(status='PASS', activeLease=False, trigger=trigger, execution=a.EXECUTION)
    else:
        generation, lease = current
        a.validate_lease(lease)
        if now < lease['expiresAt']+lease['graceSeconds']:
            result = dict(status='WAITING', activeLease=True, trigger=trigger, execution=a.EXECUTION)
        else:
            def persist():
                nonlocal generation
                generation = store.put(a.LEASE, lease, generation)
            outcome = cleanup(provider, lease, persist)
            sha = a.validate_request(lease['request'])
            result = dict(status='FAIL', trigger=trigger, execution=a.EXECUTION, cleanup=outcome, leaseReleased=False)
            try:
                # Preserve a previous completion if upload succeeded but read-back or
                # finalization was interrupted. Otherwise retain an explicit failed attempt.
                key = a.PREFIX+'attempts/'+sha+'/completion.json'
                old = store.get(key)
                completion = old[1] if old else dict(schema='gse-v51-control-completion-v1',
                    execution=a.EXECUTION, requestSha256=sha, status='FAIL', paidCloud=False,
                    engineWorkloadExecuted=False, fullRemoteQualification=False, reason='expired interrupted owner')
                m.need(completion['requestSha256'] == sha and completion['execution'] == a.EXECUTION,
                       'reconciled completion identity')
                retain(store, a.PREFIX+'attempts/'+sha+f'/cleanup-{generation}.json', result)
                finalize(store, lease, completion)
                if outcome['status'] == 'PASS':
                    store.delete(a.LEASE, generation)
                    result.update(status='PASS', leaseReleased=True)
            except (Exception, KeyboardInterrupt) as error:
                result['failure'] = failure('reconciliation', error)
    write_once(output/'receipt.json', result)
    return result
