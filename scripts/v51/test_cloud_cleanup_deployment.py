"""Proposals cannot apply changes or turn configuration matching into admission."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_cleanup_deployment as d, cloud_identity_audit as audit
from . import cloud_identity_qualification as q, cloud_preflight as p
from . import cloud_cleanup_workflows as inactive, performance_model as m, remote_command as c


class CleanupDeploymentTest(unittest.TestCase):
    def setUp(self): self.cfg = c.read(p.CONFIG); self.source = 'a'*40

    @staticmethod
    def objects(value, key):
        o = value['observations']
        return o[key+':account'], o[key+':pool'], o[key+':providers'][0]

    def fixture(self, state):
        value = q.fixture(self.cfg)
        for key in d.STATES[state]:
            for obj in self.objects(value, key): obj['disabled'] = False
        return value

    def test_configuration_states_never_establish_admission(self):
        for state in d.STATES:
            value = self.fixture(state); original = deepcopy(value)
            result = d.evaluate(self.cfg, state, value, now=q.NOW)
            self.assertEqual('CONFIGURATION_MATCH', result['status']); self.assertEqual(original, value)
            for key in d.BOUNDARY:
                if key in result: self.assertIs(result[key], False)
            self.assertEqual([True]*3, result['observedDisabled']['runner'])
            self.assertEqual('STAGED_MATCH' if state=='staged' else 'BLOCKED',
                             audit.evaluate(self.cfg, 'staged', value, now=q.NOW)['status'])

    def test_each_partial_or_unexpected_enable_bit_is_blocked(self):
        for state in d.STATES:
            for index in range(9):
                with self.subTest(state=state, bit=index):
                    value = self.fixture(state)
                    rows = [obj for key in ('runner', 'manual', 'schedule') for obj in self.objects(value, key)]
                    rows[index]['disabled'] = not rows[index]['disabled']
                    self.assertEqual('BLOCKED', d.evaluate(self.cfg, state, value, now=q.NOW)['status'])

    def test_enabled_default_boolean_may_be_omitted_but_disabled_must_be_explicit(self):
        value = self.fixture('cleanup')
        for key in d.STATES['cleanup']:
            for obj in self.objects(value, key): obj.pop('disabled')
        self.assertEqual('CONFIGURATION_MATCH', d.evaluate(self.cfg, 'cleanup', value, now=q.NOW)['status'])
        self.objects(value, 'runner')[0].pop('disabled')
        self.assertEqual('BLOCKED', d.evaluate(self.cfg, 'cleanup', value, now=q.NOW)['status'])

    def test_malformed_bits_extra_provider_and_unavailable_reads_fail_closed(self):
        for bad in (0, 1, 'false', None):
            value = self.fixture('manual'); self.objects(value, 'manual')[0]['disabled'] = bad
            self.assertEqual('BLOCKED', d.evaluate(self.cfg, 'manual', value, now=q.NOW)['status'])
        for providers in ([], [{}, {}], {'error': 'PermissionError'}):
            value = self.fixture('manual'); value['observations']['manual:providers'] = providers
            self.assertEqual('BLOCKED', d.evaluate(self.cfg, 'manual', value, now=q.NOW)['status'])

    def test_enabled_audit_preserves_existing_policy_drift_rejections(self):
        for state in ('manual', 'cleanup'):
            for name, mutation in list(q.mutations().items())[3:]:
                with self.subTest(state=state, mutation=name):
                    value = self.fixture(state); mutation(value['observations'])
                    self.assertEqual('BLOCKED', d.evaluate(self.cfg, state, value, now=q.NOW)['status'])

    def test_stale_wrong_configuration_and_missing_query_cannot_pass_readback(self):
        for mutation in (lambda v:v.update(startedAt=q.NOW-901), lambda v:v.update(configurationSha256='b'*64),
                         lambda v:v['observations'].pop('manual:keys')):
            value = self.fixture('manual'); mutation(value)
            self.assertEqual('BLOCKED', d.evaluate(self.cfg, 'manual', value, now=q.NOW)['status'])

    def test_workflows_bind_before_auth_and_share_reviewed_reconciliation(self):
        for trigger in ('manual', 'schedule'):
            text = d.render(self.cfg, trigger)
            self.assertLess(text.index('cloud_cleanup_entry identity'), text.index('google-github-actions/auth@'))
            self.assertLess(text.index('google-github-actions/auth@'), text.index('cloud_permissions --role '+trigger))
            self.assertLess(text.index('cloud_permissions --role '+trigger), text.index('cloud_cleanup_entry reconcile'))
            self.assertIn('--output target/v51-cleanup/permissions', text)
            self.assertEqual(2, text.count('--trigger '+trigger))
            self.assertIn('id-token: write', text.split('jobs:\n')[1]); self.assertNotIn('id-token:', text.split('jobs:\n')[0])
            for part in ('cleanup_credentials: true', 'target/v51-cleanup/identity', 'target/v51-cleanup/reconciliation',
                         'group: v51-native-cleanup\n  cancel-in-progress: false', 'if: ${{ always() }}', '          path: target/v51-cleanup\n'):
                self.assertIn(part, text)
            self.assertEqual('schedule'==trigger, '    - cron:' in text)
            self.assertEqual('manual'==trigger, '  workflow_dispatch:' in text)
            for forbidden in ('workflow_call:', 'inputs:', 'activation-check', 'continue-on-error', 'token_format:',
                              'credentials_json:', 'setup-gcloud', 'cloud_runner', 'needs:'):
                self.assertNotIn(forbidden, text)

    def test_installed_manual_entry_matches_reviewed_auth_and_reconciliation(self):
        # Guard the actual runnable entry as well as the proposal: a workflow-only
        # edit must not silently bypass the reviewed identity or permission gates.
        workflow = d.ci.ROOT/'.github/workflows/v51-manual-cleanup.yml'
        self.assertEqual(d.render(self.cfg, 'manual').encode(), workflow.read_bytes())

    def test_commands_only_toggle_two_cleanup_identities_in_safe_order(self):
        plans = d.commands(self.cfg); self.assertEqual({'manual', 'schedule'}, set(plans))
        for key, rows in plans.items():
            identity = d.setup.proposal(self.cfg)['identities'][key]
            self.assertEqual(3, len(rows['enable'])); self.assertEqual(3, len(rows['disable']))
            self.assertIn('update-oidc', rows['enable'][0]); self.assertIn('enable', rows['enable'][2])
            self.assertIn('disable', rows['disable'][0]); self.assertIn('update-oidc', rows['disable'][1])
            for command in rows['enable']+rows['disable']:
                self.assertIn('--project=gse-benchmark', command)
                self.assertTrue(any(identity['name'] in word for word in command))
                self.assertFalse(any('runner' in word or 'delete'==word or 'add-iam' in word for word in command))

    def test_generation_and_validation_never_call_cloud_or_git(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(d.subprocess, 'run') as run, patch.object(d.subprocess, 'check_output') as output:
            root = Path(temp)/'package'; result = d.write(root, self.cfg, self.source)
            self.assertEqual(result, d.validate(root, self.cfg, self.source)); run.assert_not_called(); output.assert_not_called()
            self.assertEqual('REVIEW_ONLY', result['status']); self.assertFalse(result['deployed']); self.assertFalse(result['applied'])
            for key in d.BOUNDARY: self.assertIs(result[key], False)
            with self.assertRaises(FileExistsError): d.write(root, self.cfg, self.source)

    def test_payload_drift_fails_even_with_rehashed_manifest(self):
        for name in ('v51-manual-cleanup.yml', 'commands.json', 'REVIEW.md'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)/'package'; d.write(root, self.cfg, self.source)
                (root/name).write_bytes((root/name).read_bytes()+b'\n')
                receipt = c.read(root/'review.json'); receipt['files'][name] = m.sha((root/name).read_bytes())
                (root/'review.json').write_bytes(m.canonical(receipt))
                with self.assertRaisesRegex(ValueError, 'payload drift'): d.validate(root, self.cfg, self.source)

    def test_manifest_cannot_claim_approval_or_different_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'package'; d.write(root, self.cfg, self.source)
            with self.assertRaises(ValueError): d.validate(root, self.cfg, 'b'*40)
            receipt = c.read(root/'review.json'); receipt['activationAllowed'] = True
            (root/'review.json').write_bytes(m.canonical(receipt))
            with self.assertRaisesRegex(ValueError, 'manifest drift'): d.validate(root, self.cfg, self.source)

    def test_extra_missing_and_symlinked_payloads_are_rejected(self):
        for kind in ('extra', 'missing', 'symlink'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)/'package'; d.write(root, self.cfg, self.source)
                if kind=='extra': (root/'unreviewed').write_text('extra')
                else:
                    path = root/'commands.json'; data = path.read_bytes(); path.unlink()
                    if kind=='symlink':
                        other = Path(temp)/'other'; other.write_bytes(data); path.symlink_to(other)
                with self.assertRaises(ValueError): d.validate(root, self.cfg, self.source)

    def test_generator_cannot_target_github_even_through_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            github = Path(temp)/'.github'; github.mkdir(); alias = Path(temp)/'alias'; alias.symlink_to(github)
            for root in (github/'workflows', alias/'workflows'):
                with self.assertRaisesRegex(ValueError, 'cannot target .github'): d.write(root, self.cfg, self.source)
            self.assertEqual([], list(github.iterdir()))

    def test_existing_inactive_proposals_still_stop_before_credentials(self):
        for trigger in ('manual', 'schedule'):
            text = inactive.render(self.cfg, trigger); self.assertIn('activation-check', text)
            for part in ('id-token: write', 'google-github-actions/auth@', 'cloud_cleanup_entry reconcile'):
                self.assertNotIn(part, text)


if __name__ == '__main__': unittest.main()
