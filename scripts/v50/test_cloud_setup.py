"""Offline setup proposals preserve existing trust and keep delete grants scoped."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from .cloud_common import plan
from .cloud_preflight import PROJECT_PERMISSIONS, check_observations, claims, condition_allows_only
from .cloud_setup import BASE_ROLE, DELETE_ROLE, METADATA_ROLE, SUPPLEMENT_ROLE, proposal, write_proposal
from .test_cloud_runner import observations


class CloudSetupTest(unittest.TestCase):
    def setUp(self):
        self.p = plan()
        self.provider = dict(observations(self.p)['provider'], name=self.p['wifProvider'])
        self.provider['attributeCondition'] = self.provider['attributeCondition'].replace(
            'v50-replication-evidence.yml', 'v44-final-durable-evidence.yml')
        self.role = dict(name='projects/' + self.p['project'] + '/roles/' + BASE_ROLE,
                         includedPermissions=['compute.instances.get'], stage='GA')
        self.policy = dict(bindings=[dict(role=self.role['name'], members=['serviceAccount:' + self.p['serviceAccount']])])

    def make(self): return proposal(self.p, self.provider, self.role, self.policy)

    def test_adds_exact_workflow_preserves_old_guarded_workflow_and_is_idempotent(self):
        result = self.make(); c = claims(self.p)
        condition_allows_only(result['wifAfter'], c)
        c['workflow_ref'] = c['workflow_ref'].replace('v50-replication-evidence.yml', 'v44-final-durable-evidence.yml')
        condition_allows_only(result['wifAfter'], c)
        self.assertIn(self.provider['attributeCondition'], result['wifAfter'])
        self.provider['attributeCondition'] = result['wifAfter']
        self.assertEqual(self.make()['wifAfter'], result['wifAfter'])

    def test_unsafe_or_unsupported_existing_wif_conditions_are_not_extended(self):
        strict = self.provider['attributeCondition']
        for condition in (strict + " || assertion.ref == 'refs/heads/master'", 'true',
                          strict.replace("assertion.environment == 'cloud-benchmark'", "assertion.environment != 'untrusted'")):
            self.provider['attributeCondition'] = condition
            with self.subTest(condition=condition), self.assertRaises(ValueError): self.make()

    def test_supplement_is_only_missing_project_permissions_and_storage_stays_separate(self):
        result = self.make(); roles = result['roles']
        self.assertEqual(set(roles[SUPPLEMENT_ROLE]['includedPermissions']), set(PROJECT_PERMISSIONS) - {'compute.instances.get'})
        self.assertIn('compute.disks.setLabels', roles[SUPPLEMENT_ROLE]['includedPermissions'])
        self.assertEqual(roles[METADATA_ROLE]['includedPermissions'], ['storage.buckets.get'])
        self.assertEqual(roles[DELETE_ROLE]['includedPermissions'], ['storage.objects.delete'])
        self.assertEqual(result['deleteCondition']['expression'],
            "resource.type == 'storage.googleapis.com/Object' && resource.name.startsWith('projects/_/buckets/" +
            self.p['bucket'] + "/objects/v5.0-replicated-single-shard/control/')")
        self.role['includedPermissions'] = PROJECT_PERMISSIONS
        self.assertNotIn(SUPPLEMENT_ROLE, self.make()['roles'])

    def test_wrong_disabled_provider_or_role_is_rejected(self):
        for key, value in [('name', 'projects/other/provider'), ('state', 'DELETED'), ('disabled', True),
                           ('oidc', dict(issuerUri='https://untrusted.example'))]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                proposal(self.p, dict(self.provider, **{key: value}), self.role, self.policy)
        for value in (dict(name='projects/other/roles/runner'), dict(deleted=True), dict(stage='DISABLED')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                proposal(self.p, self.provider, dict(self.role, **value), self.policy)

    def test_role_delta_requires_actual_unconditional_binding_to_workflow_account(self):
        for bindings in ([], [dict(role=self.role['name'], members=['user:someone@example.com'])],
                         [dict(self.policy['bindings'][0], condition={'expression': 'true'})]):
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                proposal(self.p, self.provider, self.role, dict(bindings=bindings))

    def test_generator_writes_review_files_without_running_commands_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as temp, patch('subprocess.run', side_effect=AssertionError('must stay offline')):
            output = Path(temp) / 'review'
            value = write_proposal(output, self.p, self.provider, self.role, self.policy)
            self.assertFalse(value['applied'])
            self.assertEqual(json.loads((output / 'proposal.json').read_text()), value)
            commands = (output / 'APPLY.md').read_text()
            self.assertIn('--condition-from-file=control-delete-condition.json', commands)
            self.assertIn('cloud setup input changed; regenerate and review', commands)
            self.assertNotIn('roles/storage.objectAdmin', commands)
            self.assertNotIn('roles/owner', commands)
            self.assertNotIn('gh variable set', commands)
            self.assertLess(commands.index('project-policy-current.json'), commands.index('update-oidc'))
            with self.assertRaises(FileExistsError): write_proposal(output, self.p, self.provider, self.role, self.policy)

    def test_permission_blockers_name_exact_missing_project_and_bucket_access(self):
        value = observations(self.p)
        value['permissions'] = dict(permissions=['compute.instances.get'])
        value['storagePermissions'] = dict(permissions=['storage.objects.get'])
        result = check_observations(self.p, value, 'a' * 40, 1001)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIn('iam.workloadIdentityPoolProviders.get', result['blockers'][0])
        self.assertIn('storage.buckets.get', result['blockers'][1])
        self.assertIn('storage.objects.create', result['blockers'][1])

    def test_generated_drift_checks_fail_even_when_python_assertions_are_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            # Run the generated commands unchanged with only the current
            # interpreter exposed as python3, as on CI without python3.11.
            bin_dir = Path(temp) / 'bin'; bin_dir.mkdir()
            (bin_dir / 'python3').symlink_to(sys.executable)
            environment = dict(os.environ, PATH=str(bin_dir), PYTHONOPTIMIZE='1')
            output = Path(temp) / 'review'
            write_proposal(output, self.p, self.provider, self.role, self.policy)
            checks = [shlex.split(line) for line in (output / 'APPLY.md').read_text().splitlines()
                      if line.startswith('python3 -c ')]
            self.assertEqual(len(checks), 3)
            for name, command in zip(('provider', 'runner-role', 'project-policy'), checks):
                current = output / (name + '-current.json')
                current.write_bytes((output / (name + '-before.json')).read_bytes())
                result = subprocess.run(command, cwd=output, env=environment, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                current.write_text('{}')
                result = subprocess.run(command, cwd=output, env=environment, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'cloud setup input changed', result.stderr)

    def test_permission_query_errors_and_empty_responses_stay_explanatory_and_closed(self):
        for response in ({'error': 'HTTP 403'}, {}, {'permissions': None}, {'permissions': ['ok', {}]}):
            value = observations(self.p); value['permissions'] = response
            with self.subTest(response=response):
                result = check_observations(self.p, value, 'a' * 40, 1001)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertTrue(result['blockers'][0].startswith('project permissions:'))
                if 'error' in response: self.assertIn('HTTP 403', result['blockers'][0])

    def test_cleanup_diagnostic_retains_cause_and_disabled_provider_blocks(self):
        value = observations(self.p)
        value['github']['cleanup'] = dict(error='no completed scheduled cleanup for the exact source')
        value['provider']['disabled'] = True
        result = check_observations(self.p, value, 'a' * 40, 1001)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIn('no completed scheduled cleanup for the exact source', result['blockers'][0])
        self.assertTrue(any(v.startswith('provider:') for v in result['blockers']))


if __name__ == '__main__': unittest.main()
