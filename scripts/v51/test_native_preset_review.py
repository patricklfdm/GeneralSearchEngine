from copy import deepcopy
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from . import native_preset_review as r, cloud_runner_admission_qualification as q
from . import cloud_native_authority as n, cloud_authority as a, performance_model as m


class NativePresetReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Parse/audit the unchanged frozen workload once, as in Runner admission
        # tests. Each caller gets a fresh copy; timing-plan bytes are still read
        # and hash-checked by the real review loader on every allocation.
        frozen = r.workload.load()
        loader = patch.object(r.workload, 'load', side_effect=lambda:deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.fixture = q.fixture(Path(cls.temp.name)/'fixture')
        cls.now = cls.fixture['clock'].wall()

    def inputs(self, member='experiment', order='experiment-first'):
        original = self.fixture['value']; remaining = a.ORDERS[order][a.ORDERS[order].index(member):]
        quotes = {v: dict(deepcopy(original['prices']), pricedThroughSeconds=r.allocation(v)['priceCoverageSeconds']) for v in remaining}
        return dict(configuration=deepcopy(original['configuration']), artifacts=deepcopy(original['artifacts']),
                    guestAccess=deepcopy(original['resourcePlan']['guestAccess']), prices=quotes, baseline=None,
                    sequence='d'*32, member=member, order=order, maximumCostsMicrousd={v:20_000_000 for v in remaining})

    def request(self, inputs, member, *, attempt='e'*32):
        return n.request(inputs['artifacts']['source'], inputs['artifacts']['archiveSha256'],
            r.admission.g.config(inputs['configuration']['provider']), inputs['sequence'], attempt, member,
            now=self.now-10, order=inputs['order'], guest_access_sha256='f'*64,
            timing_profile=r.allocation(member)['profile'],timing_plan_sha256=r.PLAN_SHA256)

    def finished(self, ledger, req, status='PASS', cost=1_000_000):
        total, _ = n.inspect_ledger(ledger)
        result = n.reserve(ledger, req, dict(previousCostMicrousd=total, maximumCostMicrousd=cost))
        return n.finish(result, req, dict(requestSha256=n.validate_request(req), status=status))

    def make(self, inputs=None): return r.review(inputs or self.inputs(), now=self.now)

    def test_all_five_members_bind_remaining_quotes_without_changing_inputs_or_ledger(self):
        inputs = self.inputs(); original = deepcopy(inputs); value = self.make(inputs)
        self.assertEqual(original, inputs)
        self.assertEqual(list(a.ORDERS['experiment-first']), [v['member'] for v in value['members']])
        self.assertEqual(100_000_000, value['projectedMaximumCostMicrousd'])
        self.assertEqual(100_000_000, value['remainingHeadroomMicrousd'])
        self.assertEqual('REVIEW_ONLY', value['status'])
        self.assertFalse(value['observationsAuthenticated'])
        for key in r.FLAGS: self.assertIs(value[key], False)
        self.assertEqual(m.sha(m.canonical(value)), r.validate(value, now=self.now))
        self.assertNotIn('request', value); self.assertNotIn('approval', value)

    def test_allocations_cover_all_maxima_and_enclosing_runner_guards(self):
        for member in a.ORDERS['experiment-first']:
            value = r.allocation(member); limits = value['limitsSeconds']
            self.assertLessEqual(sum(limits.values()), value['leaseSeconds'])
            self.assertEqual(sum(limits.values()), value['allocatedSeconds'])
            self.assertGreaterEqual(value['jobOverheadReserveSeconds'], 1140)
            self.assertLessEqual(value['jobMinutes'], 360)
            self.assertEqual(limits['preparation']+value['leaseSeconds']+1800, value['priceCoverageSeconds'])
        self.assertEqual(19800, r.allocation('canonical-1')['leaseSeconds'])
        self.assertEqual(5400, r.allocation('canonical-1')['limitsSeconds']['preparation'])
        self.assertEqual(27000, r.allocation('canonical-3')['priceCoverageSeconds'])
        self.assertEqual(21600, r.allocation('failure-drill')['priceCoverageSeconds'])

    def test_rotated_control_is_exact_and_unknown_or_boolean_members_fail(self):
        for i in (1, 2, 3):
            t = r.allocation('canonical-'+str(i))
            self.assertEqual((i, 'node-'+str(i)), (t['repetition'], t['controlNode']))
        for member in ('canonical', 'canonical-0', 'canonical-4', True, 1, None, []):
            with self.subTest(member=member), self.assertRaises(ValueError): r.allocation(member)

    def test_timing_file_and_workload_are_digest_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'timing.json'; value = r.load(); value['profiles']['canonical']['leaseSeconds'] += 1
            path.write_bytes(m.canonical(value))
            with patch.object(r, 'PLAN', path), self.assertRaisesRegex(ValueError, 'plan drift'): r.allocation('canonical-1')

    def test_each_quote_must_cover_its_entire_proposed_provider_lifetime(self):
        for member in a.ORDERS['experiment-first']:
            inputs = self.inputs(); inputs['prices'][member]['pricedThroughSeconds'] -= 1
            with self.subTest(member=member), self.assertRaisesRegex(ValueError, 'lifetime coverage'): self.make(inputs)

    def test_missing_extra_and_expired_future_quotes_fail(self):
        for change in (lambda v:v['prices'].pop('canonical-3'),
                       lambda v:v['prices'].update(extra=v['prices']['experiment']),
                       lambda v:v['maximumCostsMicrousd'].pop('failure-drill'),
                       lambda v:v['prices']['canonical-3'].update(expiresAt=self.now),
                       lambda v:v['prices']['canonical-2']['sources'].update(compute='https://cloud.google.com@evil.test/price'),
                       lambda v:v['prices']['canonical-1'].update(vmMicrousdPerHour=True)):
            inputs = self.inputs(); change(inputs)
            with self.assertRaises(ValueError): self.make(inputs)

    def test_member_maximum_and_full_remaining_reservations_must_fit(self):
        inputs = self.inputs(); inputs['maximumCostsMicrousd']['canonical-3'] = 1
        with self.assertRaisesRegex(ValueError, 'estimate exceeds'): self.make(inputs)
        inputs = self.inputs(); inputs['maximumCostsMicrousd'] = {k:41_000_000 for k in inputs['prices']}
        with self.assertRaisesRegex(ValueError, 'remaining sequence'): self.make(inputs)

    def test_failed_attempt_charges_and_exact_cumulative_boundary_are_preserved(self):
        inputs = self.inputs(); old = self.request(inputs, 'experiment')
        ledger = self.finished(n.empty_ledger(), old, status='FAIL', cost=100_000_000)
        inputs['baseline'] = [7, ledger]; original = deepcopy(ledger)
        value = self.make(inputs)
        self.assertEqual(200_000_000, value['projectedMaximumCostMicrousd'])
        self.assertEqual(0, value['remainingHeadroomMicrousd']); self.assertEqual(original, ledger)
        inputs['maximumCostsMicrousd']['canonical-3'] += 1
        with self.assertRaisesRegex(ValueError, 'remaining sequence'): self.make(inputs)

    def test_global_pending_attempt_and_consumed_attempt_cannot_be_reviewed_as_fresh(self):
        inputs = self.inputs(); req = self.request(inputs, 'experiment')
        pending = n.reserve(n.empty_ledger(), req, dict(previousCostMicrousd=0, maximumCostMicrousd=1_000_000))
        inputs['baseline'] = [7, pending]
        with self.assertRaisesRegex(ValueError, 'unresolved prior attempt'): self.make(inputs)
        consumed = self.request(inputs, 'experiment', attempt=inputs['guestAccess']['attempt'])
        inputs['baseline'] = [8, self.finished(n.empty_ledger(), consumed, 'FAIL')]
        with self.assertRaisesRegex(ValueError, 'duplicate/changed request'): self.make(inputs)

    def test_remaining_sequence_and_repetition_require_original_successful_prefix(self):
        inputs = self.inputs('failure-drill')
        with self.assertRaisesRegex(ValueError, 'sequence order'): self.make(inputs)
        ledger = self.finished(n.empty_ledger(), self.request(inputs, 'experiment'))
        inputs['baseline'] = [4, ledger]
        self.assertEqual('failure-drill', self.make(inputs)['members'][0]['member'])
        inputs = self.inputs('canonical-2', 'canonical-first')
        with self.assertRaisesRegex(ValueError, 'sequence order'): self.make(inputs)
        inputs['baseline'] = [5, self.finished(n.empty_ledger(), self.request(inputs, 'canonical-1'))]
        value = self.make(inputs)
        self.assertEqual(['canonical-2','canonical-3','experiment','failure-drill'], [v['member'] for v in value['members']])

    def test_failed_canonical_blocks_same_sequence_but_retains_charge_for_new_sequence(self):
        inputs = self.inputs('canonical-1', 'canonical-first')
        inputs['baseline'] = [5, self.finished(n.empty_ledger(), self.request(inputs, 'canonical-1'), 'FAIL')]
        with self.assertRaisesRegex(ValueError, 'sequence changed/failed'): self.make(inputs)
        inputs['sequence'] = 'c'*32
        value = self.make(inputs); self.assertEqual(1_000_000, value['previousCostMicrousd'])

    def test_changed_source_bundle_configuration_or_order_cannot_reuse_sequence(self):
        inputs = self.inputs('failure-drill')
        inputs['baseline'] = [4, self.finished(n.empty_ledger(), self.request(inputs, 'experiment'))]
        for key in ('source','bundleSha256','configurationSha256','order'):
            changed = deepcopy(inputs); req = changed['baseline'][1]['entries'][0]['request']
            req[key] = 'canonical-first' if key=='order' else ('c' if req[key][0]!='c' else 'a')*(40 if key=='source' else 64)
            # Build a valid prior ledger with a different identity/order.
            if key=='order':req.update(member='canonical-1',timingProfile=r.allocation('canonical-1')['profile'])
            changed['baseline'][1] = self.finished(n.empty_ledger(), req)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'sequence changed/failed'): self.make(changed)

    def test_synthetic_fake_ledger_and_invalid_generation_fail(self):
        for baseline in ([1, a.empty_ledger()], [True, n.empty_ledger()], [0, n.empty_ledger()]):
            inputs = self.inputs(); inputs['baseline'] = baseline
            with self.assertRaises(ValueError): self.make(inputs)

    def test_review_recomputes_all_fields_and_expires_without_extending_deadlines(self):
        original = self.make()
        for mutate in (lambda v:v.update(dispatchEnabled=True), lambda v:v.update(paidAdmission=0),
                       lambda v:v.update(remainingHeadroomMicrousd=1), lambda v:v.update(expiresAt=v['expiresAt']+1),
                       lambda v:v['members'][2]['timing']['limitsSeconds'].update(cleanup=1),
                       lambda v:v['members'].reverse(), lambda v:v.update(timingPlanSha256='0'*64)):
            changed = deepcopy(original); mutate(changed)
            with self.assertRaises(ValueError): r.validate(changed, now=self.now)
        r.validate(original, now=original['expiresAt']-1)
        for now in (self.now-1, original['expiresAt']):
            with self.assertRaises(ValueError): r.validate(original, now=now)

    def test_review_is_rejected_by_current_request_and_paid_plan_validators(self):
        value = self.make()
        with self.assertRaises(ValueError): n.validate_request(value)
        with self.assertRaises((KeyError, ValueError)): r.admission.validate_plan(value, self.now)
        original = deepcopy(self.fixture['value'])
        original['resourcePlan']['request']['member'] = 'canonical-1'
        with self.assertRaises(ValueError): r.admission.validate_plan(original, self.now)
        from . import remote_budget
        with self.assertRaisesRegex(ValueError, 'unreviewed budget profile'):
            remote_budget.Budget(profile='caller-selected-duration')

    def test_summary_exposes_unverified_review_and_remaining_reservations(self):
        text = r.summary(self.make())
        for expected in ('Review only', 'not been authenticated', 'not a dispatch request',
                         'canonical-3', '27000 s', '100.000000', 'Failed-attempt charges'):
            self.assertIn(expected, text)

    def test_existing_experiment_quote_and_allocation_are_unchanged(self):
        original = self.fixture['value']
        self.assertEqual(8_885_000, r.admission.prices(original['prices'], self.now))
        self.assertEqual(r.experiment.allocation(), original['timing'])
        self.assertEqual(19800, r.allocation('experiment')['priceCoverageSeconds'])
        self.assertIsNone(r.allocation('experiment')['retentionReserveSeconds'])
        self.assertIsNone(r.allocation('failure-drill')['controlNode'])

    def test_cli_round_trip_is_review_only_and_cannot_overwrite_prior_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); inputs = self.inputs(); now = int(time.time())
            for quote in inputs['prices'].values(): quote.update(observedAt=now, expiresAt=now+3600)
            source = root/'inputs.json'; source.write_bytes(m.canonical(inputs)); output = root/'review'
            command = [sys.executable, '-m', 'scripts.v51.native_preset_review', 'prepare',
                       '--inputs', str(source), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = m.strict_json(result.stdout.encode()); self.assertFalse(receipt['dispatchEnabled'])
            self.assertEqual('REVIEW_ONLY', receipt['status'])
            result = subprocess.run([sys.executable, '-m', 'scripts.v51.native_preset_review',
                                     'validate', str(output/'review.json')], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(receipt, m.strict_json(result.stdout.encode()))
            before = (output/'review.json').read_bytes()
            self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)
            self.assertEqual(before, (output/'review.json').read_bytes())

    def test_shared_price_rounds_up_without_accepting_invalid_lifetime_policy(self):
        quote = deepcopy(self.fixture['value']['prices'])
        quote.update(vmMicrousdPerHour=1, diskMicrousdPerGiBHour=1, pricedThroughSeconds=27001)
        expected = (453*27001+3599)//3600+sum(quote['otherCostsMicrousd'].values())
        self.assertEqual(expected, r.cloud_prices.estimate(quote, self.now, minimum_coverage_seconds=27000))
        for seconds in (True, 0, 86401):
            with self.assertRaises(ValueError):
                r.cloud_prices.estimate(quote, self.now, minimum_coverage_seconds=seconds)


if __name__ == '__main__': unittest.main()
