"""Registration rejects incomplete evidence, changed reviews and duplicate baselines."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .cloud_baseline import BASELINE, REGISTRY_SCHEMA, check_registry, percentiles, register, review_entry
from .cloud_common import ROOT, read, save

REVIEW = ROOT / 'docs/v5x/v5.0/phase6-cloud-review.json'
REGISTRY = ROOT / 'docs/v5x/v5.0/cloud-benchmark-baselines.json'


class CloudBaselineTests(unittest.TestCase):
    def setUp(self):
        self.review = read(REVIEW, 16 << 20)

    def test_checked_in_registry_binds_the_reviewed_source_and_all_five_members(self):
        registry = check_registry(read(REGISTRY), self.review)
        self.assertEqual(len(registry['baselines']), 1)
        self.assertEqual(registry['baselines'][0]['name'], BASELINE)
        self.assertEqual(registry['baselines'][0]['reviewSha256'],
                         '864552f0fa669738fd059d4739c5d78b2411c448274eb9af5265b3beade6c685')
        self.assertEqual(self.review['source'], '340df06148bc7d5a25a29a55c3ee928c9472dd09')
        self.assertEqual(sum(m['validation']['cells'] for m in self.review['members']), 49)

    def test_nearest_rank_percentiles_do_not_average_window_percentiles(self):
        values = [1] * 99 + [1000]
        self.assertEqual(percentiles(values), dict(samples=100, p50Nanos=1, p95Nanos=1, p99Nanos=1))
        with self.assertRaisesRegex(ValueError, 'empty measurement'):
            percentiles([])

    def test_incomplete_reordered_or_repeated_topologies_fail(self):
        for kind in ('missing', 'order', 'duplicate'):
            value = copy.deepcopy(self.review)
            if kind == 'missing': value['members'].pop()
            elif kind == 'order': value['members'][-2:] = reversed(value['members'][-2:])
            else: value['members'][1] = copy.deepcopy(value['members'][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                review_entry(value)

    def test_failed_dirty_mixed_or_unretained_members_fail(self):
        changes = [('status', 'FAIL'), ('cleanup', 'FAIL'), ('retention', 'PENDING'),
                   ('sourceDirty', True), ('sourceHead', 'a' * 40), ('execution', 'local-remote-workload-only')]
        for key, replacement in changes:
            value = copy.deepcopy(self.review)
            value['members'][0]['validation'][key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'member identity/status'):
                review_entry(value)

    def test_missing_cells_overlapping_times_and_bad_digests_fail(self):
        for kind in ('cells', 'time', 'digest', 'cost', 'plan'):
            value = copy.deepcopy(self.review)
            if kind == 'cells': value['members'][0]['cells'].pop()
            elif kind == 'time': value['members'][1]['startedAt'] = value['members'][0]['startedAt']
            elif kind == 'digest': value['members'][0]['completionSha256'] = 'invalid'
            elif kind == 'cost': value['reservedMicrousd'] = 100_000_001
            else: value['workloadPlanSha256'] = 'a' * 64
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                review_entry(value)

    def test_renamed_modified_and_duplicate_registry_entries_fail(self):
        for kind in ('rename', 'digest', 'duplicate'):
            registry = copy.deepcopy(read(REGISTRY))
            if kind == 'rename': registry['baselines'][0]['name'] = 'renamed'
            elif kind == 'digest': registry['baselines'][0]['reviewSha256'] = 'a' * 64
            else: registry['baselines'].append(copy.deepcopy(registry['baselines'][0]))
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'registry identity'):
                check_registry(registry, self.review)

    def test_registration_revalidates_raw_evidence_and_is_append_only(self):
        # Isolate registration behavior; real raw validation runs in the offline
        # five-topology review, not in CI using synthetic cloud evidence.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'registry.json'
            save(path, dict(schema=REGISTRY_SCHEMA, baselines=[]))
            before = path.read_bytes()
            with patch('scripts.v50.cloud_baseline.build_review', side_effect=ValueError('invalid raw proof')):
                with self.assertRaisesRegex(ValueError, 'invalid raw proof'):
                    register([], REVIEW, path)
            self.assertEqual(path.read_bytes(), before)
            changed = copy.deepcopy(self.review)
            changed['members'][0]['baselineOperations']['candidate']['ADD']['p99Nanos'] += 1
            with patch('scripts.v50.cloud_baseline.build_review', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'differs from reviewed'):
                    register([], REVIEW, path)
            self.assertEqual(path.read_bytes(), before)
            with patch('scripts.v50.cloud_baseline.build_review', return_value=self.review) as validate:
                register([], REVIEW, path)
                validate.assert_called_once()
            registered = path.read_bytes()
            with patch('scripts.v50.cloud_baseline.build_review') as validate:
                with self.assertRaisesRegex(ValueError, 'already registered'):
                    register([], REVIEW, path)
                validate.assert_not_called()
            self.assertEqual(path.read_bytes(), registered)


if __name__ == '__main__':
    unittest.main()
