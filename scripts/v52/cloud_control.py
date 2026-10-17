"""V5.2 renewable ownership and exact-ID cleanup, qualified memory/HTTP offline entries only.

No engine work or paid admission is claimed here. The shared V5.1 deletion
algorithm is namespace-free; all keys, requests and ledger formats below are V5.2.
"""
from copy import deepcopy
import threading
import time
from scripts.v51.cloud_runner import cleanup as exact_cleanup
from . import cloud_authority as a, cloud_offline as offline
from .evidence import need, encoded, digest

UNCERTAIN = (ConnectionError, TimeoutError)


def adapters(store, provider, req=None):
    from . import cloud_provider
    memory = type(store) is offline.Store and type(provider) is offline.Provider and provider.store is store
    need(memory or cloud_provider.qualified(store, provider), 'V5.2 live control entry not admitted')
    if not memory and req is not None: need(provider.request == req, 'V5.2 provider request changed')


def put(store, key, value, expected):
    """Submit a CAS once; a lost reply may only observe that original value."""
    try:
        generation = store.put(key, deepcopy(value), expected)
        need(store.get(key) == (generation, value), 'V5.2 CAS read-back changed')
    except UNCERTAIN:
        for _ in range(3):
            try: seen = store.get(key)
            except UNCERTAIN: continue
            if seen is not None and seen[0] > expected and seen[1] == value:
                return seen[0]
        raise ValueError('V5.2 original CAS outcome unresolved') from None
    return generation


def retain(store, key, value):
    old = store.get(key)
    if old is None: generation = put(store, key, value, 0)
    else:
        generation, original = old; need(original == value, 'V5.2 immutable evidence changed')
    need(store.get(key) == (generation, value), 'V5.2 retained read-back changed')
    return digest(encoded(value))


def attempt_key(req): return a.PREFIX+'attempts/'+a.validate_request(req, domain='offline')+'/'


def reservation(store, lease):
    a.validate_lease(lease); req = lease['request']; sha = a.validate_request(req, domain='offline')
    observed = store.get(a.LEDGER)
    view = a.inspect_ledger(observed[1], domain='offline') if observed else dict(attempts={})
    row = view['attempts'].get(sha)
    need(row is None and not any(r['attempted'] for r in lease['resources']) or
         row is not None and row['request'] == req, 'V5.2 missing/changed resource reservation')
    return observed, row


def release(store, generation, lease):
    """No blind retry of DELETE after a lost reply; a replacement is never deleted."""
    def original_absent(current):
        if current is None: return True
        if current[0] == generation: return False
        a.validate_lease(current[1]); req = current[1]['request']
        a.validate_request(req, domain='offline')
        # Another reconciler can advance the same lease's generation. That is
        # fencing, not proof that the original lease was released.
        return req['selection']['attempt'] != lease['request']['selection']['attempt']
    need(store.get(a.LEASE) == (generation, lease), 'V5.2 lease release ownership changed')
    try: store.delete(a.LEASE, generation)
    except UNCERTAIN:
        for _ in range(3):
            try: current = store.get(a.LEASE)
            except UNCERTAIN: continue
            if original_absent(current): return
        raise ValueError('V5.2 original lease release unresolved') from None
    current = store.get(a.LEASE)
    need(original_absent(current), 'V5.2 lease still retained')


def clean(store, provider, generation, lease):
    """Owner-finally and expired watchdog converge on the same fenced path."""
    adapters(store, provider); lease = deepcopy(lease); reservation(store, lease)
    need(store.get(a.LEASE) == (generation, lease), 'V5.2 cleanup ownership changed')
    lease['phase'] = 'CLEANING'; generation = put(store, a.LEASE, lease, generation)
    claim = generation
    def persist():
        nonlocal generation
        a.validate_lease(lease)
        generation = put(store, a.LEASE, lease, generation)
    outcome = exact_cleanup(provider, lease, persist, authority=a)
    result = dict(status='FAIL', scope='offline-v52-cleanup-only', cleanup=outcome,
                  leaseReleased=False, fullRemoteQualification=False, paidCloud=False)
    key = attempt_key(lease['request'])
    # A failed cleanup remains retryable by reconciliation. Its immutable record
    # is retained separately from the immutable original workload completion.
    cleanup_sha = retain(store, key+f'cleanup-{claim}.json', outcome)
    req = lease['request']; sha = a.validate_request(req, domain='offline')
    old = store.get(key+'completion.json')
    completion = old[1] if old else dict(schema='gse-v52-owned-completion-v1', execution=req['execution'],
        requestSha256=sha, status='FAIL', evidenceSha256=None, cleanupSha256=cleanup_sha)
    a.validate_completion(completion, req)
    retain(store, key+'completion.json', completion)
    current, row = reservation(store, lease)
    if row is not None:
        version, ledger = current
        if row['status'] == 'PENDING': put(store, a.LEDGER, a.finish(ledger, req, completion), version)
        else: need(any(r.get('completionSha256') == digest(encoded(completion)) and r['requestSha256'] == sha
                       for r in ledger['entries']), 'V5.2 terminal completion changed')
    if outcome['status'] == 'PASS':
        release(store, generation, lease); result.update(status='PASS', leaseReleased=True)
    return result


def reconcile(store, provider, *, trigger, now):
    adapters(store, provider); need(trigger in ('schedule', 'workflow_dispatch'), 'V5.2 cleanup trigger')
    a.integer(now, 1); current = store.get(a.LEASE)
    if current is None:
        return dict(status='PASS', scope='offline-v52-cleanup-only', trigger=trigger, activeLease=False,
                    paidCloud=False, fullRemoteQualification=False)
    generation, lease = current; a.validate_lease(lease); reservation(store, lease)
    if lease['phase'] != 'CLEANING' and now < lease['expiresAt']+lease['graceSeconds']:
        return dict(status='WAITING', scope='offline-v52-cleanup-only', trigger=trigger, activeLease=True,
                    paidCloud=False, fullRemoteQualification=False)
    return dict(clean(store, provider, generation, lease), trigger=trigger)


class OfflineOwner:
    """Original provisioning owner. No workload can be marked PASS by this entry."""
    def __init__(self, store, provider, req, *, wall=lambda: int(time.time())):
        adapters(store, provider, req); a.validate_request(req, domain='offline')
        self.store, self.provider, self.request = store, provider, deepcopy(req)
        self.wall = wall; self.lease = None; self.generation = None; self.closed = False; self.consumed = False
        self.lock = threading.RLock(); self.preparation_failure = None; self.cleanup_result = None

    def persist(self, lease):
        a.validate_lease(lease)
        version = put(self.store, a.LEASE, lease, self.generation)
        self.lease, self.generation = deepcopy(lease), version

    def checkpoint(self):
        with self.lock:
            need(not self.closed and self.lease is not None and self.lease['phase'] == 'ACTIVE' and
                 self.lease['renewedAt'] <= self.wall() < self.lease['expiresAt'], 'V5.2 active owner unavailable/expired')
            need(self.store.get(a.LEASE) == (self.generation, self.lease), 'V5.2 active owner fenced')
            _, row = reservation(self.store, self.lease)
            need(row is not None and row['status'] == 'PENDING', 'V5.2 original charge unavailable')
            return deepcopy(self.lease)

    def renew(self):
        with self.lock:
            self.checkpoint(); self.persist(a.renew(self.lease, self.wall()))
            return deepcopy(self.lease)

    def resource_claim(self):
        with self.lock:
            return a.resource_claim(self.checkpoint())

    def acquire(self, *, previous_cost, cost):
        with self.lock:
            need(not self.closed and not self.consumed and self.generation is None, 'V5.2 owner already consumed')
            self.consumed = True
            need(self.store.get(a.LEASE) is None, 'V5.2 unreconciled active lease')
            current = self.store.get(a.LEDGER); version, ledger = current if current else (0, a.empty_ledger(domain='offline'))
            reserved = a.reserve(ledger, self.request, previous_cost=previous_cost, cost=cost)
            lease = a.lease(self.request, self.wall())
            self.generation = put(self.store, a.LEASE, lease, 0); self.lease = lease
            put(self.store, a.LEDGER, reserved, version)
            lease = deepcopy(lease); lease['phase'] = 'ACTIVE'; self.persist(lease)
            self.provider.prepare_context(self.request)
            self.checkpoint(); return a.budget_warning(self.request, reserved)

    def provision(self):
        self.checkpoint()
        for index in range(len(self.lease['resources'])):
            with self.lock:
                self.checkpoint(); row = self.lease['resources'][index]; spec = row['spec']
                need(not row['attempted'] and self.provider.describe(spec) is None and
                     self.provider.operation(spec)['state'] == 'UNKNOWN', 'V5.2 resource intent already consumed')
                changed = deepcopy(self.lease); changed['resources'][index]['attempted'] = True
                self.persist(changed); self.checkpoint()
            # A heartbeat can renew while the original insert is in flight.
            # The individual exchange stays finite; there is no stage deadline.
            answer = self.provider.create(spec, self.wall()+300)
            with self.lock:
                self.checkpoint()
                need(type(answer) is dict and set(answer) == {'spec', 'id'} and answer['spec'] == spec,
                     'V5.2 inserted resource changed')
                a.numeric(answer['id']); changed = deepcopy(self.lease); changed['resources'][index]['id'] = answer['id']
                self.persist(changed)
        return self.checkpoint()

    def prepare(self, *, previous_cost, cost):
        with self.lock:
            # Reject duplicate entry outside failure cleanup: it cannot tear down
            # a previously prepared original owner or interfere with its work.
            need(not self.consumed and not self.closed, 'V5.2 owner already consumed')
            try: warning = self.acquire(previous_cost=previous_cost, cost=cost)
            except BaseException as error:
                self.failed(error); raise
        try:
            self.provision()
            return dict(status='RESOURCES_PREPARED_NOT_QUALIFIED', warning=warning,
                        lease=deepcopy(self.lease), fullRemoteQualification=False, paidCloud=False)
        except BaseException as error:
            self.failed(error); raise

    def failed(self, error):
        self.preparation_failure = dict(type=type(error).__name__, message=str(error))
        try: self.close()
        except BaseException as cleanup_error:
            self.cleanup_result = dict(status='FAIL', failure=dict(type=type(cleanup_error).__name__, message=str(cleanup_error)))

    def close(self):
        with self.lock:
            if self.closed: return deepcopy(self.cleanup_result)
            self.closed = True
            if self.generation is None: return None
            self.cleanup_result = clean(self.store, self.provider, self.generation, self.lease)
            return deepcopy(self.cleanup_result)
