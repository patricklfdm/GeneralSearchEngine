from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from . import cloud_authority as a, cloud_fake as fake, cloud_runner as runner, remote_collection as collection, performance_model as m


class CloudRunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = fake.Clock(); self.store = fake.Store(); self.provider = fake.Provider(self.store)
        self.counter = 0

    def run_case(self, fault=None, **kwargs):
        self.counter += 1; root = self.root/str(self.counter); root.mkdir()
        self.store.fault = self.provider.fault = fault
        probe = fake.Probe(root/'guest', self.clock, fault)
        req, pre, app = fake.fixture(now=self.clock.wall(), **kwargs)
        result = runner.Runner(self.store, self.provider, probe, root/'run', clock=self.clock.nanos,
                               wall=self.clock.wall).run(req, pre, app)
        return result, probe, req

    def test_success_retains_binary_parts_before_releasing_lease(self):
        result, probe, req = self.run_case()
        self.assertEqual('PASS', result['status']); self.assertTrue(result['leaseReleased'])
        self.assertFalse(self.provider.objects)
        self.assertEqual(13, sum(e['action'] == 'create' for e in self.provider.events))
        self.assertEqual(13, sum(e['action'] == 'delete' for e in self.provider.events))
        self.assertEqual(a.LEASE, self.store.events[-1]['key']); self.assertEqual('delete', self.store.events[-1]['action'])
        restored = self.root/'download'; restored.mkdir()
        prefix = a.PREFIX+'attempts/'+a.validate_request(req)+'/parts/'
        for key, (_, value) in self.store.objects.items():
            if key.startswith(prefix): (restored/key[len(prefix):]).write_bytes(value)
        self.assertEqual(result['evidence']['collection'], collection.unpack(restored, self.root/'restored', m.sha(m.canonical(probe.owner))))
        self.assertEqual('PASS', a.inspect_ledger(self.store.get(a.LEDGER)[1])[1][a.validate_request(req)]['status'])

    def test_lost_response_only_queries_and_retains_one_handler_per_cell(self):
        result, probe, _ = self.run_case('lost-submit')
        self.assertEqual('PASS', result['status'])
        self.assertEqual((4, 4, 4), (probe.handlers, probe.submits, probe.queries))

    def test_unreachable_unknown_command_cannot_resubmit_or_extend_deadline(self):
        result, probe, _ = self.run_case('unreachable')
        self.assertEqual('FAIL', result['status'])
        self.assertEqual((0, 1), (probe.handlers, probe.submits)); self.assertGreater(probe.queries, 1)
        self.assertEqual(10_600_000_000, self.clock.nanos())
        self.assertIn('never resubmit', result['errors'][0]['message'])
        self.assertFalse(self.provider.objects)

    def test_partial_create_adopts_only_resolved_original_operation_id(self):
        result, _, _ = self.run_case('partial-create')
        self.assertEqual('FAIL', result['status']); self.assertTrue(result['leaseReleased'])
        self.assertEqual(3, sum(e['action'] == 'create' for e in self.provider.events))
        self.assertEqual(3, sum(e['action'] == 'delete' for e in self.provider.events))
        self.assertFalse(self.provider.objects)

    def test_unresolved_absence_keeps_lease_and_blocks_another_topology(self):
        result, _, _ = self.run_case('unresolved-create')
        self.assertEqual('FAIL', result['cleanup']['status']); self.assertFalse(result['leaseReleased'])
        count = len(self.provider.events)
        next_result, _, _ = self.run_case(attempt='2'*32, previous=1_000_000)
        self.assertEqual('FAIL', next_result['status']); self.assertEqual(count, len(self.provider.events))
        self.assertIn('generation conflict', next_result['errors'][0]['message'])

    def test_schedule_and_manual_use_same_expiry_grace_and_reconciliation(self):
        self.run_case('unresolved-create')
        before = deepcopy(self.store.objects)
        for trigger in ('manual', 'schedule'):
            answer = runner.reconcile(self.store, self.provider, self.root/trigger, trigger=trigger, now=16480)
            self.assertEqual('WAITING', answer['status']); self.assertEqual(before, self.store.objects)
        pending = next(op for op in self.provider.operations.values() if op['state'] == 'PENDING')
        pending.update(state='DONE', id=None)  # Provider proves insertion conclusively rejected.
        result = runner.reconcile(self.store, self.provider, self.root/'expired', trigger='manual', now=16481)
        self.assertEqual('PASS', result['status']); self.assertTrue(result['leaseReleased'])
        self.assertEqual(1_000_000, a.inspect_ledger(self.store.get(a.LEDGER)[1])[0])
        absent = runner.reconcile(self.store, self.provider, self.root/'again', trigger='schedule', now=16482)
        self.assertEqual('PASS', absent['status']); self.assertFalse(absent['activeLease'])

    def test_foreign_or_reused_id_never_deleted_even_by_manual_cleanup(self):
        for fault in ('foreign-owner', 'reused-id'):
            with self.subTest(fault=fault):
                self.store = fake.Store(); self.provider = fake.Provider(self.store)
                result, _, _ = self.run_case(fault)
                self.assertEqual('FAIL', result['cleanup']['status']); self.assertEqual(1, len(self.provider.objects))
                before = deepcopy(self.provider.objects)
                answer = runner.reconcile(self.store, self.provider, self.root/(fault+'-cleanup'), trigger='manual', now=16481)
                self.assertEqual('FAIL', answer['status']); self.assertEqual(before, self.provider.objects)
                self.assertIsNotNone(self.store.get(a.LEASE))

    def test_retention_failures_still_remove_resources_and_preserve_charge(self):
        for fault in ('upload-failure', 'readback-failure', 'completion-failure', 'collection-failure'):
            with self.subTest(fault=fault):
                self.store = fake.Store(); self.provider = fake.Provider(self.store)
                result, _, _ = self.run_case(fault)
                self.assertEqual('FAIL', result['status']); self.assertFalse(self.provider.objects)
                self.assertIsNotNone(self.store.get(a.LEASE))
                self.assertEqual(1_000_000, a.inspect_ledger(self.store.get(a.LEDGER)[1])[0])
                self.store.fault = None
                answer = runner.reconcile(self.store, self.provider, self.root/(fault+'-cleanup'), trigger='schedule', now=16481)
                self.assertEqual('PASS', answer['status']); self.assertIsNone(self.store.get(a.LEASE))
                self.assertEqual(1_000_000, a.inspect_ledger(self.store.get(a.LEDGER)[1])[0])

    def test_delete_errors_do_not_stop_remaining_cleanup(self):
        result, _, _ = self.run_case('delete-failure')
        self.assertEqual('FAIL', result['status']); self.assertEqual(1, len(self.provider.objects))
        self.assertEqual(13, sum(e['action'] == 'delete' for e in self.provider.events))
        self.provider.fault = None
        answer = runner.reconcile(self.store, self.provider, self.root/'repair', trigger='manual', now=16481)
        self.assertEqual('PASS', answer['status']); self.assertFalse(self.provider.objects)

    def test_delete_success_response_without_absence_is_failure(self):
        result, _, _ = self.run_case('false-delete')
        self.assertEqual('FAIL', result['cleanup']['status'])
        self.assertEqual(1, len(result['cleanup']['leftovers']))

    def test_cancel_and_budget_overruns_keep_cleanup_reservation(self):
        for fault in ('cancel', 'preparation-overrun', 'cell-overrun'):
            with self.subTest(fault=fault):
                self.clock = fake.Clock(); self.store = fake.Store(); self.provider = fake.Provider(self.store)
                result, probe, _ = self.run_case(fault)
                self.assertEqual('FAIL', result['status']); self.assertTrue(probe.stopped)
                self.assertFalse(self.provider.objects); self.assertEqual('PASS', result['cleanup']['status'])
                if fault != 'cancel': self.assertEqual('FAIL', result['budget']['status'])

    def test_generation_checks_prevent_stale_overwrite_and_release(self):
        first = self.store.put('x', dict(owner=1), 0)
        with self.assertRaises(ValueError): self.store.put('x', dict(owner=2), 0)
        second = self.store.put('x', dict(owner=1, revision=2), first)
        with self.assertRaises(ValueError): self.store.delete('x', first)
        self.assertEqual(second, self.store.get('x')[0])

    def test_no_real_adapter_or_paid_receipt_is_accepted(self):
        self.provider.execution = 'gcp-owned-runtime'
        with self.assertRaisesRegex(ValueError, 'paid execution disabled'):
            runner.Runner(self.store, self.provider, None, self.root/'not-created')
        self.assertFalse(self.store.events)

    def test_admission_failure_happens_before_lease_or_directory_creation(self):
        probe = fake.Probe(self.root/'guest', self.clock)
        req, pre, app = fake.fixture(); app['confirmed'] = False
        with self.assertRaisesRegex(ValueError, 'approval'):
            runner.Runner(self.store, self.provider, probe, self.root/'run', clock=self.clock.nanos,
                          wall=self.clock.wall).run(req, pre, app)
        self.assertFalse((self.root/'run').exists()); self.assertFalse(self.store.events)

    def test_failed_canonical_cannot_be_replaced_within_sequence(self):
        result, _, _ = self.run_case('startup-failure', member='canonical-1', order='canonical-first')
        self.assertEqual('FAIL', result['status'])
        count = len(self.provider.events)
        result, _, _ = self.run_case(member='canonical-1', order='canonical-first', attempt='2'*32, previous=1_000_000)
        self.assertEqual('FAIL', result['status']); self.assertEqual(count, len(self.provider.events))
        self.assertIn('failed canonical set', result['errors'][0]['message'])

    def test_reconnect_refreshes_only_queries_never_the_command(self):
        result, probe, _ = self.run_case('query-reconnect')
        self.assertEqual('PASS', result['status'])
        self.assertEqual((4, 4, 8), (probe.handlers, probe.submits, probe.queries))

    def test_stale_budget_conflict_after_lease_acquisition_prevents_all_creates(self):
        original = self.store.put
        def race(key, value, expected):
            if key == a.LEDGER and expected == 0:
                original(key, a.empty_ledger(), 0)
            return original(key, value, expected)
        self.store.put = race
        result, _, _ = self.run_case()
        self.assertEqual('FAIL', result['status']); self.assertFalse(self.provider.events)
        self.assertEqual(0, a.inspect_ledger(self.store.get(a.LEDGER)[1])[0])

    def test_lost_budget_ack_retains_reservation_and_never_creates(self):
        original = self.store.put; fired = []
        def lose_ack(key, value, expected):
            generation = original(key, value, expected)
            if key == a.LEDGER and not fired:
                fired.append(True); raise ConnectionError('lost budget ACK')
            return generation
        self.store.put = lose_ack
        result, _, _ = self.run_case()
        self.assertEqual('FAIL', result['status']); self.assertFalse(self.provider.events)
        self.assertEqual(1_000_000, a.inspect_ledger(self.store.get(a.LEDGER)[1])[0])

    def test_lost_intent_ack_is_unresolved_without_issuing_create(self):
        original = self.store.put; fired = []
        def lose_ack(key, value, expected):
            generation = original(key, value, expected)
            if key == a.LEASE and any(r['attempted'] for r in value['resources']) and not fired:
                fired.append(True); raise ConnectionError('lost intent ACK')
            return generation
        self.store.put = lose_ack
        result, _, _ = self.run_case()
        self.assertEqual('FAIL', result['status']); self.assertFalse(self.provider.events)
        self.assertIsNotNone(self.store.get(a.LEASE))

    def test_preflight_expiry_after_admitted_start_is_not_runtime_expiry(self):
        probe = fake.Probe(self.root/'guest', self.clock)
        req, pre, app = fake.fixture(); pre['expiresAt'] = pre['checkedAt']+1
        app['preflightSha256'] = m.sha(m.canonical(pre))
        original = probe.cell
        def measured(cell, deadline):
            self.clock.sleep(2); return original(cell, deadline)
        probe.cell = measured
        result = runner.Runner(self.store, self.provider, probe, self.root/'run', clock=self.clock.nanos,
                               wall=self.clock.wall).run(req, pre, app)
        self.assertGreater(self.clock.wall(), pre['expiresAt']); self.assertEqual('PASS', result['status'])
