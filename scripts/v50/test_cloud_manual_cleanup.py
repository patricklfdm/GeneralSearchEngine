"""Manual cleanup changes the entry point, never expiry/ownership or spending authority."""
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote

from . import cloud_cleanup as cleanup
from .cloud_common import ROOT, canonical, plan, request, resources
from .cloud_entry import main
from .cloud_fake import Fake
from .cloud_manual_cleanup_setup import write_proposal
from .cloud_preflight import check_observations, collect_cleanup_receipt, condition_allows_only
from .cloud_runner import BUDGET, LEASE, reconcile
from .cloud_presets import SEQUENCES
from .test_cloud_runner import observations


class ManualCleanupTest(unittest.TestCase):
    def setUp(self):
        self.p = plan(); self.who = cleanup.identity(self.p, trigger='manual')
        self.env = dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REF=self.p['ref'],
                        GITHUB_WORKFLOW_REF=cleanup.claims(self.p, trigger='manual')['workflow_ref'])
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        self.req = request('a' * 40, 1, 1, 'b' * 64)

    def test_manual_trust_is_exact_and_disjoint_from_scheduled_and_paid_principals(self):
        expected = cleanup.claims(self.p, trigger='manual'); strict = cleanup.condition(self.p, trigger='manual')
        condition_allows_only(strict, expected, exact_workflow=True)
        for key in expected:
            weakened = ' && '.join(v for v in strict.split(' && ') if not v.startswith('assertion.' + key + ' =='))
            with self.subTest(key=key), self.assertRaises(ValueError):
                condition_allows_only(weakened, expected, exact_workflow=True)
        self.assertEqual(expected['environment'], cleanup.ENVIRONMENT)
        self.assertNotEqual(self.who['serviceAccount'], cleanup.identity(self.p)['serviceAccount'])
        self.assertNotEqual(self.who['serviceAccount'], self.p['serviceAccount'])
        self.assertEqual(set(cleanup.attribute_mapping('manual')), {'google.subject', 'attribute.gse_v50_manual_cleanup'})
        cleanup.require_context(self.p, self.env, trigger='manual')
        with self.assertRaises(ValueError): cleanup.require_context(self.p, self.env)
        for field, wrong in [('GITHUB_EVENT_NAME', 'schedule'), ('GITHUB_REF', 'refs/heads/feature'),
                             ('GITHUB_WORKFLOW_REF', cleanup.claims(self.p)['workflow_ref'])]:
            with self.subTest(field=field), patch.dict('os.environ', dict(self.env, **{field: wrong}), clear=True), \
                 patch('sys.argv', ['cleanup', 'expired-cleanup', '--cleanup-trigger', 'manual', '--output', str(self.root)]), \
                 patch('scripts.v50.cloud_entry.Gcp') as backend:
                with self.assertRaisesRegex(ValueError, 'dedicated manual'): main()
                backend.assert_not_called()

    def invoke(self, backend, now):
        with patch.dict('os.environ', self.env, clear=True), \
             patch('sys.argv', ['cleanup', 'expired-cleanup', '--cleanup-trigger', 'manual', '--output', str(self.root)]), \
             patch('scripts.v50.cloud_entry.Gcp', return_value=backend) as factory, \
             patch('scripts.v50.cloud_entry.time.time', return_value=now), \
             patch('scripts.v50.cloud_entry.reconcile', wraps=reconcile) as shared:
            code = main()
            return code, factory, shared

    def test_no_lease_is_readonly_and_repeated_invocations_are_safe(self):
        backend = Fake(self.p, self.req)
        for _ in range(2):
            code, factory, shared = self.invoke(backend, 1000)
            self.assertEqual(code, 0); self.assertEqual(factory.call_count, 1)
            self.assertFalse(factory.call_args.kwargs['api'].paid); shared.assert_not_called()
            self.assertEqual(json.loads((self.root / 'cleanup.json').read_text()), dict(status='PASS', activeLease=False))
        self.assertFalse(any(c[0] in ('create', 'delete') for c in backend.calls))

    def test_active_lease_and_inclusive_grace_never_create_mutating_backend(self):
        backend = Fake(self.p, self.req)
        backend.objects[LEASE] = ('1', canonical(dict(request=self.req, expiresAt=1000)))
        original = deepcopy(backend.objects)
        for now in (999, 1000, 1001, 1000 + self.p['commandTimeoutSeconds']):
            code, factory, shared = self.invoke(backend, now)
            self.assertEqual(code, 0); self.assertEqual(factory.call_count, 1)
            self.assertFalse(factory.call_args.kwargs['api'].paid); shared.assert_not_called()
            self.assertEqual(json.loads((self.root / 'cleanup.json').read_text())['status'], 'WAITING')
            self.assertEqual(backend.objects, original)

    def test_expired_lease_uses_shared_reconciliation_and_preserves_budget_and_sequence(self):
        backend = Fake(self.p, self.req)
        rows = [dict(r, attempted=False) for r in resources(self.p, self.req)]
        backend.objects[LEASE] = ('1', canonical(dict(schema='gse-v50-cloud-lease-v1', request=self.req,
            plan=self.p, resources=rows, expiresAt=1000)))
        ledgers = {BUDGET: ('2', b'budget unchanged'), SEQUENCES: ('3', b'failed sequence unchanged')}
        backend.objects.update(ledgers)
        code, factory, shared = self.invoke(backend, 1001 + self.p['commandTimeoutSeconds'])
        self.assertEqual(code, 0); self.assertEqual(factory.call_count, 2); shared.assert_called_once()
        self.assertNotIn(LEASE, backend.objects)
        self.assertEqual({k: backend.objects[k] for k in ledgers}, ledgers)
        self.assertFalse(any(c[0] == 'create' for c in backend.calls))
        self.assertEqual(json.loads((self.root / 'reconciliation.json').read_text())['status'], 'PASS')

    def test_manual_identity_must_have_only_cleanup_privileges(self):
        def call(method, url, body=None):
            if method == 'POST': return dict(permissions=cleanup.PROJECT_PERMISSIONS)
            if '/o/' not in url: return dict(permissions=['storage.objects.get', 'storage.objects.create'])
            return dict(permissions=['storage.objects.delete'] if '/o/' + LEASE + '/iam/' in unquote(url) else [])
        auth = Mock(returncode=0, stdout=self.who['serviceAccount'])
        with patch.dict('os.environ', self.env, clear=True), patch('scripts.v50.cloud_cleanup.subprocess.run', return_value=auth):
            api = Mock(call=Mock(side_effect=call)); result = cleanup.verify(self.p, api, trigger='manual')
            self.assertEqual(result['trigger'], 'manual'); self.assertFalse(result['topologyCreationAllowed'])
            for extra in cleanup.FORBIDDEN_PERMISSIONS:
                api.call.side_effect = lambda method, url, body=None: dict(permissions=cleanup.PROJECT_PERMISSIONS + [extra]) if method == 'POST' else call(method, url, body)
                with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'create or modify'):
                    cleanup.verify(self.p, api, trigger='manual')
            auth.stdout = cleanup.identity(self.p)['serviceAccount']
            with self.assertRaisesRegex(ValueError, 'identity'): cleanup.verify(self.p, api, trigger='manual')

    def test_proposal_reuses_exact_roles_without_modifying_existing_trust_or_environments(self):
        with patch('subprocess.run', side_effect=AssertionError('offline only')):
            result = write_proposal(self.root / 'proposal', self.p)
        self.assertFalse(result['applied'])
        commands = json.loads((self.root / 'proposal/commands.json').read_text())
        self.assertTrue(all(c[0] == 'python3' for c in commands[:3]))
        self.assertNotIn('compute.disks.setLabels', result['reusedRoles'][cleanup.PROJECT_ROLE])
        self.assertEqual(result['reusedRoles']['gseV50ControlDeleter'], ['storage.objects.delete'])
        self.assertEqual(result['leaseCondition'], cleanup.lease_condition(self.p))
        for command in commands:
            self.assertNotIn('gh', command); self.assertNotIn('update-oidc', command)
            self.assertNotIn('roles/owner', command); self.assertNotIn('roles/editor', command)
        with self.assertRaises(FileExistsError): write_proposal(self.root / 'proposal', self.p)

    def test_workflow_approval_precedes_shared_cleanup_slot_and_has_no_force_inputs(self):
        manual = (ROOT / cleanup.MANUAL_WORKFLOW).read_text(); scheduled = (ROOT / cleanup.WORKFLOW).read_text()
        self.assertIn('  workflow_dispatch:', manual); self.assertNotIn('  schedule:', manual)
        self.assertNotIn('inputs:', manual); self.assertNotIn('workflow_dispatch:', scheduled)
        self.assertIn('    needs: authorize', manual)
        approval, execution = manual.split('  cleanup:', 1)
        self.assertIn('environment: ' + self.p['environment'], approval)
        self.assertNotIn('concurrency:', approval); self.assertNotIn('id-token:', approval)
        self.assertIn('environment: ' + cleanup.ENVIRONMENT, execution)
        self.assertIn('      group: v50-expired-cleanup-gse-benchmark', execution)
        self.assertIn('  group: v50-expired-cleanup-gse-benchmark', scheduled)
        self.assertIn('cancel-in-progress: false', execution)
        self.assertIn('cloud_entry expired-cleanup --cleanup-trigger manual', execution)
        self.assertLess(execution.index(cleanup.IDENTITY_STEP), execution.index(cleanup.CLEANUP_STEP))
        self.assertTrue(all(re.fullmatch('[0-9a-f]{40}', pin) for pin in re.findall(r'uses: \S+@(\S+)', manual)))


class CleanupAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.p = plan(); self.source = 'a' * 40; self.now = 10000

    def fixture(self, trigger, run_id, completed=9900):
        from datetime import datetime, timezone
        stamp = datetime.fromtimestamp(completed, timezone.utc).isoformat()
        event = 'schedule' if trigger == 'schedule' else 'workflow_dispatch'
        run = dict(id=run_id, head_sha=self.source, head_branch='master', status='completed', conclusion='success',
                   event=event, path=cleanup.workflow(trigger), updated_at=stamp)
        jobs = [dict(name='cleanup', conclusion='success', steps=[dict(name=cleanup.IDENTITY_STEP, conclusion='success'),
            dict(name=cleanup.CLEANUP_STEP, conclusion='success', completed_at=stamp)])]
        if trigger == 'manual': jobs.append(dict(name=cleanup.MANUAL_APPROVAL_JOB, conclusion='success'))
        return run, jobs

    def collect(self, schedule, manual):
        fixtures = schedule + manual
        def github(path):
            if path.startswith('actions/workflows/'):
                return dict(workflow_runs=[v[0] for v in (manual if 'v50-manual-cleanup.yml' in path else schedule)])
            return dict(jobs=next(j for r, j in fixtures if path == 'actions/runs/' + str(r['id']) + '/jobs?per_page=100'))
        return collect_cleanup_receipt(github, self.source, self.now)

    def test_either_entry_qualifies_and_newest_valid_success_wins(self):
        scheduled = self.fixture('schedule', 1, 9800); manual = self.fixture('manual', 2)
        self.assertEqual(self.collect([scheduled], [])['run'], 1)
        self.assertEqual(self.collect([], [manual])['run'], 2)
        self.assertEqual(self.collect([scheduled], [manual])['run'], 2)
        failed = self.fixture('manual', 3, 9950); failed[0]['conclusion'] = 'failure'
        self.assertEqual(self.collect([], [failed, manual])['run'], 2)

    def test_wrong_source_branch_event_workflow_stale_or_skipped_never_qualifies(self):
        for trigger in ('schedule', 'manual'):
            for change in (dict(head_sha='b'*40), dict(head_branch='other'), dict(event='push'),
                           dict(path=self.p['workflow']), dict(status='in_progress'), dict(conclusion='cancelled')):
                fixture = self.fixture(trigger, 1); fixture[0].update(change)
                self.assertIn('error', self.collect([fixture] if trigger == 'schedule' else [], [fixture] if trigger == 'manual' else []))
            for completed in (self.now - 7201, self.now + 1):
                fixture = self.fixture(trigger, 1, completed)
                self.assertIn('error', self.collect([fixture] if trigger == 'schedule' else [], [fixture] if trigger == 'manual' else []))
            for step in (0, 1):
                fixture = self.fixture(trigger, 1); fixture[1][0]['steps'][step]['conclusion'] = 'skipped'
                self.assertIn('error', self.collect([fixture] if trigger == 'schedule' else [], [fixture] if trigger == 'manual' else []))
        manual = self.fixture('manual', 1); manual[1][1]['conclusion'] = 'skipped'
        self.assertIn('error', self.collect([], [manual]))

    def test_run_metadata_refresh_cannot_freshen_an_old_cleanup_step(self):
        old = self.fixture('manual', 1, self.now - 7201)
        old[0]['updated_at'] = self.fixture('manual', 2)[0]['updated_at']
        self.assertIn('error', self.collect([], [old]))

    def test_unavailable_schedule_api_does_not_block_valid_manual_receipt(self):
        manual = self.fixture('manual', 2)
        def github(path):
            if 'v50-expired-cleanup.yml' in path: raise ValueError('schedule API unavailable')
            return dict(workflow_runs=[manual[0]]) if 'workflows/' in path else dict(jobs=manual[1])
        self.assertEqual(collect_cleanup_receipt(github, self.source, self.now)['run'], 2)

    def test_manual_receipt_requires_its_exact_provider_and_passes_full_preflight(self):
        value = deepcopy(observations(self.p)); value['github']['cleanup'] = self.collect([], [self.fixture('manual', 2)])
        who = cleanup.identity(self.p, trigger='manual')
        value['manualCleanupProvider'] = dict(name=who['provider'], state='ACTIVE',
            oidc=dict(issuerUri='https://token.actions.githubusercontent.com'),
            attributeMapping=cleanup.attribute_mapping('manual'), attributeCondition=cleanup.condition(self.p, trigger='manual'))
        result = check_observations(self.p, value, self.source, self.now)
        self.assertEqual(result['status'], 'READY_FOR_PAID_REVIEW', result['blockers'])
        for bad in ({}, value['cleanupProvider'], dict(value['manualCleanupProvider'], disabled=True)):
            invalid = deepcopy(value); invalid['manualCleanupProvider'] = bad
            self.assertEqual(check_observations(self.p, invalid, self.source, self.now)['status'], 'BLOCKED')


if __name__ == '__main__': unittest.main()
