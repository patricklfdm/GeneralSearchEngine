"""Summaries distinguish reviewed plans, observed results and retained failures."""
from pathlib import Path
import tempfile
import unittest
from .cloud_common import save
from .cloud_summary import render


class CloudSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(GITHUB_SHA='a' * 40, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2')

    def summary(self, mode='run', **kwargs):
        return render(self.root, mode=mode, env=self.env, now=1000, **kwargs)

    def test_ready_preparation_shows_plan_without_claiming_execution_or_spend(self):
        save(self.root / 'prepared/request.json', dict(profile='experiment', sequence='b' * 32, source='a' * 40))
        save(self.root / 'prepared/preflight.json', dict(status='READY', observedAt=900, expiresAt=1800,
            observations=dict(budget=dict(reservations=[]))))
        text = self.summary('prepare', job_status='success')
        for value in ('Result: READY', '800 s', '4096 documents', 'n2-standard-8', 'Not executed',
                      'USD 0.00', 'USD 40.00', 'reservations are not billing', 'manual run'):
            self.assertIn(value, text)
        self.assertNotIn('Reservation written by this run | Yes', text)

    def test_failure_keeps_budget_cleanup_and_resource_uncertainty_visible(self):
        save(self.root / 'evidence/lifecycle.json', dict(status='FAIL', request=dict(profile='experiment'),
            budgetReservation=dict(reservations=[dict(maximumCostMicrousd=6000000)]),
            sequenceReservation=dict(status='FAIL'), retention='VERIFIED', cleanup=dict(status='FAIL'),
            resources=[dict(name='peer', kind='firewalls', attempted=True)],
            errors=[dict(phase='execution', type='ApiError', message='403: compute.networks.updatePolicy')]))
        text = self.summary(job_status='failure')
        for value in ('Result: FAILURE', 'USD 6.00', 'USD 34.00', 'Cleanup result | FAIL', 'Unresolved',
                      'compute.networks.updatePolicy', 'prepare a new sequence'):
            self.assertIn(value, text)
        self.assertNotIn('Lease released by this runner | Yes', text)

    def test_entry_failure_overrides_old_ready_preflight(self):
        save(self.root / 'prepared/preflight.json', dict(status='READY', expiresAt=500))
        save(self.root / 'evidence/entry-error.json', dict(phase='run', type='ValueError', message='admission expired'))
        text = self.summary(job_status='failure')
        self.assertIn('Result: FAILURE', text); self.assertIn('admission expired', text)
        self.assertIn('Receipt status when collected | READY', text)
        self.assertIn('summary generation | 0 s', text)

    def test_observed_cells_show_duration_and_separate_control_overhead(self):
        save(self.root / 'evidence/lifecycle.json', dict(status='FAIL', request=dict(profile='experiment')))
        save(self.root / 'evidence/runtime/cells.json', [
            dict(name='healthy', status='PASS', startedNanos=1000000000, finishedNanos=4000000000,
                 controlOverheadNanos=500000000), dict(name='unavailable', status='RUNNING')])
        text = self.summary()
        self.assertIn('PASS | 3.000 | 0.500', text); self.assertIn('Interrupted', text)

    def test_cleanup_waiting_and_fake_outcomes_are_explicit(self):
        save(self.root / 'reconciliation/cleanup.json', dict(status='WAITING', activeLease=True, expiresAt=1100))
        save(self.root / 'identity.json', dict(principal='cleanup@example.com', status='PASS'))
        text = self.summary('expired-cleanup')
        self.assertIn('Result: WAITING', text); self.assertIn('cleanup@example.com / PASS', text)
        self.assertIn('Active lease reported by cleanup | True', text)
        save(self.root / 'evidence/matrix.json', dict(status='PASS'))
        text = self.summary('fake')
        self.assertIn('Result: PASS', text); self.assertIn('No real-cloud performance claim', text)

    def test_missing_or_corrupt_receipts_do_not_hide_job_failure(self):
        text = self.summary(job_status='cancelled')
        self.assertIn('Result: CANCELLED', text); self.assertIn('Not recorded', text)
        (self.root / 'evidence').mkdir()
        (self.root / 'evidence/lifecycle.json').write_text('{incomplete')
        save(self.root / 'prepared/preflight.json', [])
        text = self.summary(job_status='failure')
        self.assertIn('Result: FAILURE', text)
        self.assertIn('Unreadable receipt: evidence/lifecycle.json', text)
        self.assertIn('Unreadable receipt: prepared/preflight.json', text)

    def test_receipt_text_cannot_inject_summary_markup_or_expose_environment(self):
        self.env['ADMISSION_JSON'] = 'PRIVATE-ADMISSION'; self.env['GH_TOKEN'] = 'PRIVATE-TOKEN'
        save(self.root / 'evidence/entry-error.json', dict(phase='run', type='Error',
            message='<script> | fake\n## header [link](url)'))
        text = self.summary(job_status='failure')
        for value in ('<script>', '| fake', '\n## header', '[link]', 'PRIVATE-ADMISSION', 'PRIVATE-TOKEN'):
            self.assertNotIn(value, text)
        self.assertIn('&lt;script&gt;', text); self.assertIn('&#124;', text)


if __name__ == '__main__': unittest.main()
