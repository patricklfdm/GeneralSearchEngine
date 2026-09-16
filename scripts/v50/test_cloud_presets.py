"""Preset gates, replacement failures, and serial-set counterexamples; no credentials."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
from .cloud_common import canonical, plan, replacement_resource, request, resources, save, sha, validate_inventory
from .cloud_preset_fake import PresetFake, PresetProbe, cells, run_one
from .cloud_presets import ORDER, SEQUENCES, preset, reserve_sequence, workload_request
from .cloud_runner import BUDGET, LEASE, Runner, reconcile


class PresetTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.objects = {}; self.number = 0

    def run_case(self, profile='experiment', repetition=1, fault=None, sequence='c' * 32):
        self.number += 1
        return run_one(self.root / str(self.number), profile, repetition, sequence, self.number,
                       objects=self.objects, fault=fault)

    def test_presets_bind_frozen_windows_resource_and_evidence_bounds(self):
        for name, seconds, maximum in [('experiment', 300, 2340), ('failure-drill', 900, 3360), ('canonical', 1800, 5400)]:
            p = preset(name)
            self.assertEqual(sum(c['seconds'] for c in p['cells']), seconds)
            self.assertEqual(p['plannedMaximumSeconds'], maximum)
            self.assertEqual(p['resources']['peakDiskGiB'], 450)
            self.assertEqual(p['evidenceBounds']['maxBundleBytes'], 4 << 30)
            self.assertFalse(p['paidEnabled'])
        with self.assertRaises(ValueError): preset('admission-probe')

    def test_invalid_set_identity_and_repetitions_rejected(self):
        for profile, repetition, sequence in [('experiment', 2, 'c'*32), ('canonical', True, 'c'*32),
                ('canonical', 4, 'c'*32), ('canonical', 1, '../other')]:
            with self.subTest(profile=profile, repetition=repetition), self.assertRaises(ValueError):
                workload_request('a'*40, 1, 1, 'b'*64, profile, sequence, repetition)

    def test_all_five_topologies_are_serial_and_costs_accumulate(self):
        for name, repetition in ORDER:
            backend, state = self.run_case(name, repetition)
            self.assertEqual(state['status'], 'PASS', state['errors'])
            self.assertTrue(state['leaseReleased']); self.assertNotIn(LEASE, self.objects)
            self.assertFalse(backend.resources); self.assertEqual(backend.peak_disk_gib, 450)
        ledger = json.loads(self.objects[SEQUENCES][1])
        self.assertEqual([v['status'] for v in ledger['attempts']], ['PASS']*5)
        self.assertEqual(sum(v['maximumCostMicrousd'] for v in json.loads(self.objects[BUDGET][1])['reservations']), 5_000_000)
        backend, repeat = self.run_case('canonical', 3)
        self.assertEqual(repeat['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))

    def test_skip_or_reorder_cannot_create_resources(self):
        backend, state = self.run_case('canonical')
        self.assertEqual(state['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))
        self.run_case()
        backend, state = self.run_case('canonical', 2)
        self.assertEqual(state['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))

    def test_failed_member_poisoned_even_after_successful_cleanup(self):
        self.run_case()
        _, state = self.run_case('failure-drill', fault='replacement-bootstrap')
        self.assertEqual(state['cleanup']['status'], 'PASS'); self.assertEqual(state['retention'], 'VERIFIED')
        for profile in ('failure-drill', 'canonical'):
            backend, result = self.run_case(profile)
            self.assertEqual(result['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))
        self.assertEqual(len(json.loads(self.objects[BUDGET][1])['reservations']), 2)
        _, fresh = self.run_case(sequence='d'*32)
        self.assertEqual(fresh['status'], 'PASS')
        self.assertEqual(len(json.loads(self.objects[BUDGET][1])['reservations']), 3)

    def test_ledger_pass_requires_retained_completion_and_exact_source(self):
        backend, _ = self.run_case()
        req = workload_request('a'*40, 2, 1, 'b'*64, 'failure-drill', 'c'*32)
        backend.request = req
        key = json.loads(self.objects[SEQUENCES][1])['attempts'][0]['completionObject']
        original = self.objects.pop(key)
        with self.assertRaisesRegex(ValueError, 'completion'): reserve_sequence(backend)
        self.objects[key] = (original[0], original[1] + b' ')
        with self.assertRaisesRegex(ValueError, 'completion'): reserve_sequence(backend)
        self.objects[key] = original
        backend.request = workload_request('d'*40, 2, 1, 'b'*64, 'failure-drill', 'c'*32)
        with self.assertRaisesRegex(ValueError, 'different-source'): reserve_sequence(backend)

    def test_ledger_cannot_borrow_another_profile_completion(self):
        backend, _ = self.run_case(); version, raw = self.objects[SEQUENCES]; ledger = json.loads(raw)
        borrowed = dict(ledger['attempts'][0], profile='failure-drill')
        ledger['attempts'].append(borrowed); self.objects[SEQUENCES] = (version, canonical(ledger))
        backend.request = workload_request('a'*40, 3, 1, 'b'*64, 'canonical', 'c'*32)
        with self.assertRaisesRegex(ValueError, 'topology identity'): reserve_sequence(backend)

    def test_budget_exhaustion_stops_before_compute(self):
        self.run_case()
        version, raw = self.objects[BUDGET]; ledger = json.loads(raw)
        ledger['reservations'][0]['maximumCostMicrousd'] = 40_000_000
        self.objects[BUDGET] = (version, canonical(ledger))
        backend, state = self.run_case('failure-drill')
        self.assertEqual(state['status'], 'FAIL'); self.assertFalse(any(c[0] == 'create' for c in backend.calls))

    def test_replacement_deletes_old_before_creating_and_keeps_both_generations(self):
        self.run_case(); backend, state = self.run_case('failure-drill')
        self.assertEqual(state['status'], 'PASS', state['errors'])
        self.assertEqual(len(state['resources']), 15)
        requests = [r['requestId'] for r in state['resources']]
        self.assertEqual(len(requests), len(set(requests)))
        for node in (3, 1):
            old = next(r for r in state['resources'] if r['name'].endswith(f'n{node}-data'))
            new = next(r for r in state['resources'] if r['name'].endswith(f'n{node}-data-g2'))
            self.assertTrue(old['retired']['absent']); self.assertNotEqual(old['id'], new['id'])
            self.assertLess(backend.calls.index(('delete', old['name'])), backend.calls.index(('create', new['name'])))
            self.assertEqual(new['replacementReceipt']['diskId'], new['id'])
        # Auto-delete removes attached generations with their VM. Cleanup still
        # independently reads back every intent, including the retired disks.
        self.assertEqual(state['cleanup']['status'], 'PASS')
        self.assertEqual({v['name'] for v in state['cleanup']['checks']}, {v['name'] for v in state['resources']})
        self.assertTrue(all(v['absent'] for v in state['cleanup']['checks']))

    def test_old_disk_deletion_failures_never_allocate_new_disk(self):
        for fault in ('old-delete-failure', 'old-delete-lies', 'old-foreign', 'old-reused-id'):
            with self.subTest(fault=fault):
                self.objects = {}; self.run_case()
                backend, state = self.run_case('failure-drill', fault=fault)
                self.assertEqual(state['status'], 'FAIL'); self.assertIn(LEASE, self.objects)
                self.assertFalse(any(c[0] == 'create' and c[1].endswith('-g2') for c in backend.calls))

    def test_partial_replacement_and_cancellation_cleanup_are_complete(self):
        for fault in ('replacement-lost-ack', 'replacement-bootstrap', 'replacement-cancel'):
            with self.subTest(fault=fault):
                self.objects = {}; self.run_case()
                backend, state = self.run_case('failure-drill', fault=fault)
                self.assertEqual(state['status'], 'FAIL'); self.assertEqual(state['cleanup']['status'], 'PASS')
                self.assertFalse(backend.resources); self.assertNotIn(LEASE, self.objects)

    def test_unresolved_insert_reconciles_all_generations_after_expiry(self):
        self.run_case(); backend, state = self.run_case('failure-drill', fault='replacement-unresolved')
        self.assertEqual(state['cleanup']['status'], 'FAIL'); self.assertIn(LEASE, self.objects)
        before = len([c for c in backend.calls if c[0] == 'create'])
        blocked = Runner(backend, PresetProbe(backend), self.root/'blocked', approval={}).run()
        self.assertEqual(blocked['status'], 'FAIL')
        self.assertEqual(before, len([c for c in backend.calls if c[0] == 'create']))
        backend.fault = None
        with patch('scripts.v50.cloud_runner.time.time', return_value=time.time()+6000):
            result = reconcile(backend, self.root/'reconciled')
        self.assertEqual(result['status'], 'PASS'); self.assertNotIn(LEASE, self.objects)
        # Reconciliation releases ownership, but does not promote an incomplete set.
        entry = json.loads(self.objects[SEQUENCES][1])['attempts'][-1]
        self.assertEqual(entry['status'], 'FAIL')

    def test_retention_failure_holds_lease_after_complete_deletion(self):
        self.run_case(); backend, state = self.run_case('failure-drill', fault='upload-failure')
        self.assertEqual(state['retention'], 'INCOMPLETE'); self.assertIn(LEASE, self.objects)
        self.assertFalse(backend.resources)
        self.assertEqual(json.loads(self.objects[SEQUENCES][1])['attempts'][-1]['status'], 'RUNNING')

    def test_cleanup_rejects_injected_or_reordered_generation_names(self):
        p = plan(); r = workload_request('a'*40, 1, 1, 'b'*64, 'canonical', 'c'*32)
        rows = resources(p, r); third = replacement_resource(p, r, 3); leader = replacement_resource(p, r, 1)
        validate_inventory(p, r, [*rows, third, leader])
        for added in ([leader], [third, third], [third, dict(leader, name='foreign')], [third, leader, third]):
            with self.subTest(added=added), self.assertRaises(ValueError): validate_inventory(p, r, [*rows, *added])

    def test_real_backend_is_blocked_before_creating_workspace_or_resources(self):
        r = workload_request('a'*40, 1, 1, 'b'*64, 'experiment', 'c'*32)
        backend = PresetFake(plan(), r); backend.execution = 'gcp-owned-runtime'
        with self.assertRaisesRegex(ValueError, 'not enabled'):
            Runner(backend, PresetProbe(backend), self.root/'forbidden', approval={})
        self.assertFalse((self.root/'forbidden').exists()); self.assertFalse(backend.calls)

    def test_offline_bundle_cannot_enter_paid_adapter(self):
        from .cloud_entry import execute
        prepared = self.root/'prepared'; (prepared/'artifacts').mkdir(parents=True)
        archive = prepared/'artifacts/bundle.tar.gz'
        raw = canonical(dict(schema='gse-v50-cloud-workload-bundle-v1', execution='offline-workload-bundle-only'))
        with tarfile.open(archive, 'w:gz') as stream:
            member = tarfile.TarInfo('bundle.json'); member.size = len(raw); stream.addfile(member, io.BytesIO(raw))
        req = request('a'*40, 1, 1, sha(archive.read_bytes()))
        save(prepared/'request.json', req); save(prepared/'preflight.json', {}); save(self.root/'approval.json', {})
        with patch('scripts.v50.cloud_entry.exact_checkout'), patch('scripts.v50.cloud_entry.admission'), \
                patch('scripts.v50.cloud_entry.Gcp') as backend, self.assertRaisesRegex(ValueError, 'bundle schema'):
            execute(prepared, self.root/'paid', self.root/'approval.json', sha(canonical(req)))
        backend.assert_not_called(); self.assertFalse((self.root/'paid').exists())

    def test_cells_wait_to_deadline_and_fail_on_overrun(self):
        stamp = [0.0]
        def sleep(seconds): stamp[0] += seconds
        def action(name, deadline): stamp[0] += 1
        rows = cells('experiment', action, lambda: stamp[0], sleep)
        self.assertEqual(stamp[0], 300)
        self.assertEqual([r['finishedSeconds']-r['startedSeconds'] for r in rows], [120,30,30,30,45,15,15,15])
        def late(name, deadline): stamp[0] = deadline+1
        with self.assertRaisesRegex(ValueError, 'deadline'): cells('experiment', late, lambda: stamp[0], sleep)


if __name__ == '__main__': unittest.main()
