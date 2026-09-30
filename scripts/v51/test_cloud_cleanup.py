from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from . import cloud_authority as a, cloud_cleanup as c, cloud_cleanup_qualification as q
from . import cloud_fake, cloud_gcp as g, cloud_http_fake as f, cloud_runner as r, performance_model as m
from .cloud_http import Api


class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.req, self.lease, self.http = q.interrupted()
        self.now = self.lease['expiresAt']+self.lease['graceSeconds']

    def run_cleanup(self, state=None, *, trigger='manual', now=None, name='cleanup', hook=None):
        state = state or q.snapshot(self.http)
        _, http, api, store = q.restore(state); http.hook = hook(http) if hook else None
        result = c.reconcile(state['configuration'], api, self.root/name, trigger=trigger,
                             now=self.now if now is None else now)
        return result, http, store

    def test_schedule_and_manual_reconstruct_same_expired_authority(self):
        outcomes = []
        for trigger in ('manual', 'schedule'):
            result, http, store = self.run_cleanup(trigger=trigger, name=trigger)
            self.assertEqual(result['status'], 'PASS'); self.assertTrue(result['leaseReleased'])
            self.assertFalse(http.resources); self.assertIsNone(store.get(a.LEASE))
            total, attempts = a.inspect_ledger(store.get(a.LEDGER)[1])
            self.assertEqual(total, 1_000_000); self.assertEqual(attempts[a.validate_request(self.req)]['status'], 'FAIL')
            outcomes.append([v for v in http.requests if v['path'].startswith('/compute/')])
        self.assertEqual(outcomes[0], outcomes[1])

    def test_active_and_grace_need_no_context_or_provider(self):
        del self.http.objects[c.context_key(self.req)]
        for now in (self.lease['startedAt'], self.lease['expiresAt'], self.now-1):
            result, http, _ = self.run_cleanup(now=now, name=str(now))
            self.assertEqual(result['status'], 'WAITING')
            self.assertEqual(q.snapshot(http), q.snapshot(self.http))
            self.assertTrue(all(v['method'] == 'GET' and '/compute/' not in v['path'] for v in http.requests))

    def test_empty_lease_before_reservation_needs_no_context(self):
        _, lease, http = q.interrupted(allocate=False)
        del http.objects[a.LEDGER]
        result, after, store = self.run_cleanup(q.snapshot(http))
        self.assertEqual(result['status'], 'PASS'); self.assertIsNone(store.get(a.LEASE))
        self.assertFalse(any('/compute/' in v['path'] for v in after.requests))

    def test_legacy_unkeyed_request_also_reconstructs(self):
        _, _, http = q.interrupted(ssh=False)
        result, after, _ = self.run_cleanup(q.snapshot(http))
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(after.resources)

    def test_missing_or_altered_context_blocks_before_compute(self):
        key = c.context_key(self.req)
        mutations = [lambda v: v.update(requestSha256='0'*64),
                     lambda v: v['configuration'].update(project='foreign-project'),
                     lambda v: v.update(guestAccess=None),
                     lambda v: v['guestAccess'].update(publicKey=q.KEY[:-4]+'AAAA'),
                     lambda v: v['guestAccess'].update(user='root'),
                     lambda v: v['guestAccess'].update(privateKey='not-allowed'),
                     lambda v: v.update(execution='gcp-owned-runtime'),
                     lambda v: v.update(paidCloud=True)]
        for index, mutate in enumerate([None]+mutations):
            original = deepcopy(self.http)
            if mutate is None: del original.objects[key]
            else: q.rewrite(original, key, mutate)
            state = q.snapshot(original)
            with self.subTest(index=index):
                result, http, _ = self.run_cleanup(state, name=str(index))
                self.assertEqual(result['status'], 'FAIL'); self.assertEqual(result['failure']['phase'], 'reconstruction')
                self.assertEqual(q.snapshot(http), state)
                self.assertTrue(all(v['method'] == 'GET' and '/compute/' not in v['path'] for v in http.requests))

    def test_configuration_and_reservation_must_match_lease(self):
        states = []
        wrong = q.snapshot(self.http); wrong['configuration']['network'] = 'foreign-network'; states.append(wrong)
        other = deepcopy(self.http); del other.objects[a.LEDGER]; states.append(q.snapshot(other))
        other = deepcopy(self.http); q.rewrite(other, a.LEDGER, lambda value: value.update(entries=[])); states.append(q.snapshot(other))
        for index, state in enumerate(states):
            result, http, _ = self.run_cleanup(state, name=str(index))
            self.assertEqual(result['status'], 'FAIL'); self.assertFalse(any('/compute/' in v['path'] for v in http.requests))
            self.assertEqual(q.snapshot(http), state)

    def test_context_generation_change_during_read_blocks_deletion(self):
        def race(http):
            def hook(method, path, query, body):
                if query.get('alt') == 'media' and 'cleanup-context.json' in path.path:
                    q.rewrite(http, c.context_key(self.req), lambda value: None)
            return hook
        result, http, _ = self.run_cleanup(hook=race)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(all(v['method'] == 'GET' for v in http.requests))
        self.assertFalse(any('/compute/' in v['path'] for v in http.requests))

    def test_lease_cas_conflict_blocks_every_resource_delete(self):
        def race(http):
            changed = []
            def hook(method, path, query, body):
                if method == 'POST' and query.get('name') == a.LEASE and not changed:
                    changed.append(True); q.rewrite(http, a.LEASE, lambda value: None)
            return hook
        result, http, store = self.run_cleanup(hook=race)
        self.assertEqual(result['status'], 'FAIL'); self.assertIsNotNone(store.get(a.LEASE))
        self.assertEqual(len(http.resources), 13)
        self.assertFalse(any(v['method'] == 'DELETE' for v in http.requests))

    def test_pending_original_operation_never_becomes_absence_or_allocation(self):
        state, now, trigger = q.case_state('pending-insert')
        result, http, store = self.run_cleanup(state, now=now)
        self.assertEqual(result['status'], 'FAIL'); self.assertIsNotNone(store.get(a.LEASE))
        self.assertEqual(len(http.resources), 1)
        self.assertFalse(any(v['method'] == 'POST' and '/compute/' in v['path'] for v in http.requests))
        pending = next(v for v in http.operations.values() if v['status'] == 'RUNNING'); pending['status'] = 'DONE'
        result, after, store = self.run_cleanup(q.snapshot(http), name='resolved')
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(after.resources)
        self.assertEqual(a.inspect_ledger(store.get(a.LEDGER)[1])[0], 1_000_000)

    def test_retained_completion_survives_restart_without_rewriting_history(self):
        sha = a.validate_request(self.req)
        clock, http, api, store = q.restore(q.snapshot(self.http))
        completion = dict(schema='gse-v51-control-completion-v1', requestSha256=sha,
                          execution=a.EXECUTION, status='FAIL', reason='original failure')
        r.finalize(store, self.lease, completion)
        old = deepcopy(http.objects[a.LEDGER])
        result, after, store = self.run_cleanup(q.snapshot(http))
        self.assertEqual(result['status'], 'PASS'); self.assertEqual(after.objects[a.LEDGER], old)
        self.assertEqual(store.get(a.PREFIX+'attempts/'+sha+'/completion.json')[1], completion)

    def test_native_adapter_rejected_before_credentials_or_output(self):
        transport = Mock(offline=False); tokens = Mock()
        api = Api(transport=transport, tokens=tokens)
        with self.assertRaisesRegex(ValueError, 'native cleanup disabled'):
            c.reconcile(self.http.configuration, api, self.root/'native', trigger='manual', now=self.now)
        tokens.assert_not_called(); transport.send.assert_not_called(); self.assertFalse((self.root/'native').exists())

    def test_context_is_immutable_and_contains_only_public_access(self):
        _, _, _, store = q.restore(q.snapshot(self.http))
        retained = store.get(c.context_key(self.req))[1]
        self.assertEqual(set(retained['guestAccess']), {'attempt', 'user', 'publicKey'})
        self.assertNotIn('PRIVATE KEY', str(retained)); c.retain_context(store, self.req, retained)
        # Existing bytes at the immutable key must never be overwritten.
        generation, _ = store.get(c.context_key(self.req))
        store.put(c.context_key(self.req), dict(retained, requestSha256='0'*64), generation)
        with self.assertRaisesRegex(ValueError, 'retention object changed'):
            c.retain_context(store, self.req, retained)

    def test_context_cannot_be_retained_in_another_bucket(self):
        _, _, api, store = q.restore(q.snapshot(self.http))
        value = store.get(c.context_key(self.req))[1]
        configuration = dict(self.http.configuration, bucket='foreign-evidence')
        wrong = g.Store(configuration, api)
        with self.assertRaisesRegex(ValueError, 'storage bucket'):
            c.retain_context(wrong, self.req, value)

    def test_runner_retains_context_before_first_create_intent(self):
        req, pre, app, clock, http, store, provider = f.fixture()
        original = http.storage
        def checked(method, path, query, body, content):
            if method == 'POST' and query.get('name') == a.LEASE and any(row['attempted'] for row in m.strict_json(body)['resources']):
                self.assertIn(c.context_key(req), http.objects)
            return original(method, path, query, body, content)
        http.storage = checked
        result = r.Runner(store, provider, cloud_fake.Probe(self.root/'guest', clock), self.root/'run',
                          clock=clock.nanos, wall=clock.wall).run(req, pre, app)
        self.assertEqual(result['status'], 'PASS'); self.assertEqual(http.inserts, 13)
        self.assertEqual(store.get(c.context_key(req))[1], provider.cleanup_context())

    def test_lost_context_upload_ack_prevents_every_create(self):
        req, pre, app, clock, http, store, provider = f.fixture()
        def hook(method, path, query, body):
            if method == 'POST' and query.get('name') == c.context_key(req):
                http.storage(method, path.path, query, body, 'application/json')
                raise ConnectionError('lost context upload ACK')
        http.hook = hook
        result = r.Runner(store, provider, cloud_fake.Probe(self.root/'guest', clock), self.root/'run',
                          clock=clock.nanos, wall=clock.wall).run(req, pre, app)
        self.assertEqual(result['status'], 'FAIL'); self.assertEqual(http.inserts, 0)
        self.assertEqual(a.inspect_ledger(store.get(a.LEDGER)[1])[0], 1_000_000)
        self.assertEqual(store.get(c.context_key(req))[1], provider.cleanup_context())


if __name__ == '__main__': unittest.main()
