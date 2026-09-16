"""One owned topology; real and fake adapters use this exact lifecycle and cleanup."""
import signal
import time
import uuid
from pathlib import Path
from .cloud_common import canonical, inventory, prefix, require, resources, save, sha

LEASE = 'v5.0-replicated-single-shard/control/active-run.json'
BUDGET = 'v5.0-replicated-single-shard/control/budget.json'


def reserve_budget(backend, approval):
    """Conservative append-only reservations; failed attempts are never refunded automatically."""
    import json
    current = backend.get_object(BUDGET)
    ledger = json.loads(current[1]) if current else dict(schema='gse-v50-budget-v1', reservations=[])
    require(ledger['schema'] == 'gse-v50-budget-v1', 'budget ledger schema')
    total = sum(r['maximumCostMicrousd'] for r in ledger['reservations'])
    require(all(type(r['maximumCostMicrousd']) is int and r['maximumCostMicrousd'] > 0 for r in ledger['reservations']), 'budget ledger values')
    request_sha = sha(canonical(backend.request))
    require(not any(r['requestSha256'] == request_sha for r in ledger['reservations']), 'paid request already attempted; prepare a fresh attempt')
    require(total == approval['previousAttemptsCostMicrousd'] and total + approval['maximumCostMicrousd'] <= backend.plan['maximumSequenceCostMicrousd'], 'remaining sequence budget changed')
    ledger['reservations'].append(dict(requestSha256=request_sha, maximumCostMicrousd=approval['maximumCostMicrousd'],
        source=backend.request['source'], approvalSha256=sha(canonical(approval))))
    backend.put_object(BUDGET, canonical(ledger), current[0] if current else '0')
    return ledger


class Runner:
    def __init__(self, backend, probe, workspace, *, approval=None):
        self.backend, self.probe = backend, probe
        self.approval = approval
        self.root = Path(workspace)
        require(not self.root.exists(), 'fresh runner workspace required')
        self.root.mkdir(parents=True)
        p, r = backend.plan, backend.request
        self.state = dict(schema='gse-v50-cloud-lifecycle-v1', execution=backend.execution,
            request=r, plan=p, startedAt=int(time.time()), status='RUNNING', events=[], errors=[],
            resources=[dict(v, requestId=str(uuid.uuid4()), attempted=False) for v in resources(p, r)])
        self.generation = None
        self.deadline = time.monotonic() + p['maximumTopologySeconds'] - p['cleanupReserveSeconds']
        self.persist()

    def update_lease(self):
        lease = dict(schema='gse-v50-cloud-lease-v1', request=self.state['request'], plan=self.state['plan'],
            resources=self.state['resources'], expiresAt=self.state['startedAt'] + self.backend.plan['maximumTopologySeconds'])
        self.generation = self.backend.put_object(LEASE, canonical(lease), self.generation)

    def persist(self):
        save(self.root / 'lifecycle.json', self.state)

    def event(self, phase, **values):
        self.state['events'].append(dict(phase=phase, at=int(time.time()), **values)); self.persist()

    def bounded(self):
        require(time.monotonic() < self.deadline, 'topology workload deadline')

    def rows(self, kind):
        return [r for r in self.state['resources'] if r['kind'] == kind]

    def failure(self, phase, error):
        self.state['errors'].append(dict(phase=phase, type=type(error).__name__, message=str(error)[:2000])); self.persist()

    def upload(self, label):
        files = inventory(self.root)
        destination = prefix(self.backend.plan, self.backend.request) + '/' + label
        # Immutable object names and read-back; a partial upload is retained, never overwritten.
        for name in files:
            self.backend.put_object(destination + '/' + name, (self.root / name).read_bytes())
        self.backend.put_object(destination + '/inventory.json', canonical(files))

    def cleanup(self):
        """Continue after every individual failure, then inspect *all* intent names."""
        for row in reversed(self.rows('instances')):
            if not row.get('id'): continue
            try: self.probe.stop(row)
            except Exception as error: self.failure('stop:' + row['name'], error)
        for row in self.rows('instances'):
            if not row.get('id'): continue
            try: self.probe.collect(row, self.root / 'guests' / str(row['node']))
            except Exception as error: self.failure('collect:' + row['name'], error)
        # Instances first: deleting an instance releases/deletes its attached owned disks.
        for row in reversed(self.state['resources']):
            if not row['attempted']: continue
            try:
                if hasattr(self.backend, 'insert_finished'):
                    require(self.backend.insert_finished(row), 'insert is still unresolved; keep lease')
                current = self.backend.describe(row)
                if current is None:
                    # A timed-out insert could still create the object. Only an observed
                    # resource ID or a conclusively finished insert makes absence final.
                    require(row.get('id') or row.get('insertFinished'), 'unresolved insert; keep lease for reconciliation')
                    continue
                require(self.backend.owns(current), 'refusing foreign resource')
                actual = str(current['id'])
                require('id' not in row or row['id'] == actual, 'resource name reused with another ID')
                row['id'] = actual; self.persist()  # Lost create acknowledgement: adopt only our nonce.
                self.backend.delete(row, actual)
            except Exception as error: self.failure('delete:' + row['name'], error)
        leftovers = []; checks = []
        for row in self.state['resources']:
            if not row['attempted']: continue
            try:
                value = self.backend.describe(row)
                checks.append(dict(name=row['name'], expectedId=row.get('id'), observedId=str(value['id']) if value else None,
                    absent=value is None and bool(row.get('id') or row.get('insertFinished'))))
                if value is not None or not (row.get('id') or row.get('insertFinished')):
                    leftovers.append(dict(name=row['name'], id=str(value['id']) if value else None, unresolved=True))
            except Exception as error:
                leftovers.append(dict(name=row['name'], error=str(error)[:500]))
        self.state['cleanup'] = dict(status='PASS' if not leftovers else 'FAIL', leftovers=leftovers, checks=checks, checkedAt=int(time.time()))
        self.persist()

    def run(self):
        lease = dict(schema='gse-v50-cloud-lease-v1', request=self.state['request'], plan=self.state['plan'],
            resources=self.state['resources'], expiresAt=self.state['startedAt'] + self.backend.plan['maximumTopologySeconds'])
        try:
            # Store the complete immutable intent before any Compute mutation. A pre-existing
            # lease (even expired) blocks creation until its owner is reconciled explicitly.
            self.generation = self.backend.put_object(LEASE, canonical(lease))
            self.event('lease-acquired', generation=self.generation)
            if self.backend.execution == 'gcp-owned-runtime':
                require(self.approval is not None, 'paid runner requires admitted budget')
                self.state['budgetReservation'] = reserve_budget(self.backend, self.approval); self.persist()
            for row in self.state['resources']:
                self.bounded()
                require(self.backend.describe(row) is None, 'resource name already exists')
                row['attempted'] = True; self.persist(); self.update_lease()
                value = self.backend.create(row)
                require(self.backend.owns(value), 'created resource ownership')
                row.update(id=str(value['id']), insertFinished=True, observation=value); self.persist(); self.update_lease()
            nodes = self.rows('instances')
            disks = [r for r in self.rows('disks') if r['purpose'] == 'data']
            for node in nodes:
                self.bounded(); self.probe.prepare(node)
            for disk in disks:
                self.bounded(); self.backend.attach(nodes[0], disk)
            self.bounded(); self.probe.bootstrap(nodes[0])
            for disk, node in zip(disks[1:], nodes[1:]):
                self.bounded(); self.probe.unmount(nodes[0], disk)
                self.backend.attach(nodes[0], disk, False)
                self.backend.attach(node, disk)
            for node in nodes:
                self.bounded(); self.probe.start(node)
            self.bounded(); self.probe.exercise()
            self.event('probe-completed')
        except (Exception, KeyboardInterrupt) as error:
            self.failure('execution', error)
        finally:
            # Cancellation must not repeatedly interrupt deletion and evidence retention.
            previous = signal.signal(signal.SIGTERM, signal.SIG_IGN)
            if hasattr(signal, 'SIGALRM'): signal.alarm(0)
            try:
                if self.generation is not None:
                    self.cleanup()
                    try:
                        self.state['probeValidation'] = self.probe.validate(self.root)
                    except Exception as error: self.failure('validation', error)
                    self.state['status'] = 'FAIL' if self.state['errors'] else 'PASS'
                    self.state['finishedAt'] = int(time.time()); self.persist()
                    try:
                        self.upload('final')
                        self.state['retention'] = 'VERIFIED'
                        self.backend.put_object(prefix(self.backend.plan, self.backend.request) + '/completion.json', canonical(self.state))
                        save(self.root / 'completion.json', self.state)
                    except Exception as error:
                        self.failure('retention', error); self.state['retention'] = 'INCOMPLETE'; self.state['status'] = 'FAIL'
                    # Failed retention also holds the lease; a later recovery can retain
                    # failure evidence before allowing any new paid topology.
                    if self.state['cleanup']['status'] == 'PASS' and self.state['retention'] == 'VERIFIED':
                        try:
                            self.backend.delete_object(LEASE, self.generation)
                            self.state['leaseReleased'] = True
                        except Exception as error:
                            self.failure('lease-release', error); self.state['status'] = 'FAIL'
            finally:
                signal.signal(signal.SIGTERM, previous)
                if self.state['status'] == 'RUNNING': self.state['status'] = 'FAIL'
                self.persist()
        return self.state


def reconcile(backend, root):
    """Explicit recovery of one retained lease, including ambiguous create results."""
    stored = backend.get_object(LEASE)
    require(stored is not None, 'no active lease')
    generation, raw = stored
    import json
    lease = json.loads(raw)
    require(lease['schema'] == 'gse-v50-cloud-lease-v1' and lease['request'] == backend.request and
            lease['plan'] == backend.plan, 'lease identity mismatch')
    require(int(time.time()) > lease['expiresAt'] + backend.plan['commandTimeoutSeconds'], 'active owner may still be running')
    expected = resources(backend.plan, backend.request)
    require([{k: r[k] for k in e} for r, e in zip(lease['resources'], expected)] == expected and
            len(lease['resources']) == len(expected), 'cleanup inventory scope')
    if hasattr(backend, 'known_ids'):
        backend.known_ids.update({r['name']: r['id'] for r in lease['resources'] if 'id' in r})
    errors = []; observations = []
    for row in reversed(lease['resources']):
        try:
            if hasattr(backend, 'insert_finished'):
                require(backend.insert_finished(row), 'insert is still unresolved; retain lease')
            value = backend.describe(row)
            if value is not None:
                require(backend.owns(value), 'foreign resource at owned intent name')
                require('id' not in row or row['id'] == str(value['id']), 'reused ID at owned intent name')
                observations.append(dict(name=row['name'], id=str(value['id'])))
                backend.delete(row, str(value['id']))
        except Exception as error: errors.append(dict(name=row['name'], error=str(error)))
    for row in lease['resources']:
        try: require(backend.describe(row) is None, 'remaining resource: ' + row['name'])
        except Exception as error: errors.append(dict(name=row['name'], error=str(error)))
    result = dict(schema='gse-v50-cloud-reconciliation-v1', request=backend.request, leaseSha256=sha(raw),
                  observations=observations, errors=errors, status='FAIL' if errors else 'PASS', checkedAt=int(time.time()))
    save(Path(root) / 'reconciliation.json', result)
    backend.put_object(prefix(backend.plan, backend.request) + '/reconciliation-' + uuid.uuid4().hex + '.json', canonical(result))
    if not errors: backend.delete_object(LEASE, generation)
    return result
