"""Unattended cleanup trust, effective privileges and preflight failure regressions."""
from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote
from . import cloud_cleanup as cleanup
from .cloud_cleanup_setup import write_proposal
from .cloud_common import ROOT, canonical, plan, request
from .cloud_entry import main
from .cloud_gcp import Api
from .cloud_preflight import PROJECT_PERMISSIONS, check_observations, collect, condition_allows_only
from .cloud_runner import LEASE
from .test_cloud_runner import observations


class CloudCleanupTest(unittest.TestCase):
    def setUp(self):
        self.p = plan(); self.good = observations(self.p)
        self.env = dict(GITHUB_EVENT_NAME='schedule', GITHUB_REF=self.p['ref'],
                        GITHUB_WORKFLOW_REF=cleanup.claims(self.p)['workflow_ref'])

    def check(self, value): return check_observations(self.p, value, 'a' * 40, 1001)

    def test_cleanup_provider_allows_only_exact_schedule_and_has_disjoint_principal_mapping(self):
        c = cleanup.claims(self.p); strict = cleanup.condition(self.p)
        condition_allows_only(strict, c, exact_workflow=True)
        for key in c:
            pieces = strict.split(' && ')
            weakened = ' && '.join(piece for piece in pieces if not piece.startswith('assertion.' + key + ' =='))
            with self.subTest(key=key), self.assertRaises(ValueError):
                condition_allows_only(weakened, c, exact_workflow=True)
        self.assertNotIn('attribute.repository_id', cleanup.ATTRIBUTE_MAPPING)
        self.assertTrue(cleanup.ATTRIBUTE_MAPPING['google.subject'].startswith("'v50-cleanup:'"))
        self.assertIn('/attribute.gse_v50_cleanup/', cleanup.identity(self.p)['principal'])
        value = deepcopy(self.good)
        value['cleanupProvider']['attributeMapping']['attribute.repository_id'] = 'assertion.repository_id'
        self.assertTrue(any(v.startswith('cleanup WIF:') for v in self.check(value)['blockers']))

    def test_reviewers_timers_custom_rules_and_broad_branch_rules_block_preflight(self):
        for kind in ('required_reviewers', 'wait_timer', 'custom_deployment_protection_rule'):
            value = deepcopy(self.good); value['github']['cleanupEnvironment']['protection_rules'].append(dict(type=kind))
            with self.subTest(kind=kind): self.assertIn('must not wait', ' '.join(self.check(value)['blockers']))
        for policies in ([], [dict(name='*', type='branch')], [dict(name='master', type='tag')],
                         [dict(name='master', type='branch'), dict(name='other', type='branch')]):
            value = deepcopy(self.good); value['github']['cleanupBranches'] = dict(total_count=len(policies), branch_policies=policies)
            with self.subTest(policies=policies): self.assertIn('cleanup environment:', ' '.join(self.check(value)['blockers']))
        value = deepcopy(self.good); value['github']['cleanupEnvironment'] = dict(error='HTTP 403')
        self.assertIn('HTTP 403', ' '.join(self.check(value)['blockers']))
        for custom in ({}, dict(error='HTTP 403'), dict(total_count=1, custom_deployment_protection_rules=[dict(enabled=True)])):
            value = deepcopy(self.good); value['github']['cleanupCustomRules'] = custom
            self.assertIn('cleanup environment:', ' '.join(self.check(value)['blockers']))

    def test_old_or_manual_cleanup_receipts_and_missing_identity_step_are_rejected(self):
        for change in (dict(workflow=self.p['workflow']), dict(event='workflow_dispatch'), dict(identityConclusion='skipped')):
            value = deepcopy(self.good); value['github']['cleanup'].update(change)
            with self.subTest(change=change): self.assertIn('cleanup watchdog:', ' '.join(self.check(value)['blockers']))
        value = deepcopy(self.good); del value['github']['cleanup']['workflow']
        self.assertEqual(self.check(value)['status'], 'BLOCKED')

    def test_firewall_403_is_a_query_error_and_real_policy_is_still_rejected(self):
        for field, scope in [('effectiveFirewalls', 'global'), ('regionalFirewalls', 'regional')]:
            value = deepcopy(self.good); value[field] = dict(error='GCP GET failed (403): https://compute.googleapis.com/example')
            self.assertIn(scope + ' firewall query failed: GCP GET failed (403)', ' '.join(self.check(value)['blockers']))
            for invalid in (None, {'firewalls': None}, {'firewalls': [None]}, {'firewallPolicys': [{'name': 'unreviewed'}]}):
                value[field] = invalid
                with self.subTest(field=field, invalid=invalid): self.assertEqual(self.check(value)['status'], 'BLOCKED')

    def test_iap_disabled_missing_denied_or_wrong_project_blocks(self):
        for service in ({}, None, dict(error='HTTP 403'), dict(self.good['iapService'], state='DISABLED'),
                        dict(self.good['iapService'], name='projects/other/services/iap.googleapis.com')):
            value = deepcopy(self.good); value['iapService'] = service
            with self.subTest(service=service): self.assertIn('IAP API:', ' '.join(self.check(value)['blockers']))
        for permission in ('compute.networks.getRegionEffectiveFirewalls', 'serviceusage.services.get'):
            value = deepcopy(self.good); value['permissions']['permissions'] = [v for v in PROJECT_PERMISSIONS if v != permission]
            self.assertIn(permission, ' '.join(self.check(value)['blockers']))
        with patch('scripts.v50.cloud_gcp.subprocess.run', side_effect=AssertionError('must reject before auth')):
            with self.assertRaisesRegex(ValueError, 'paid admission'):
                Api().call('POST', 'https://serviceusage.googleapis.com/v1/projects/x/services/iap.googleapis.com:enable')

    def permission_api(self, *, extra_create=False, broad_delete=False, missing=False):
        def call(method, url, body=None):
            if method == 'POST':
                self.assertTrue(url.endswith(':testIamPermissions'))
                permissions = cleanup.PROJECT_PERMISSIONS[:-1] if missing else cleanup.PROJECT_PERMISSIONS[:]
                if extra_create: permissions.append('compute.instances.create')
                return dict(permissions=permissions)
            self.assertEqual(method, 'GET')
            if '/o/' not in url: return dict(permissions=['storage.objects.get', 'storage.objects.create'])
            return dict(permissions=['storage.objects.delete'] if broad_delete or '/o/' + LEASE + '/iam/' in unquote(url) else [])
        return Mock(call=Mock(side_effect=call))

    def test_cleanup_permissions_require_read_delete_but_forbid_topology_creation_and_other_deletes(self):
        auth = Mock(returncode=0, stdout=cleanup.identity(self.p)['serviceAccount'] + '\n')
        with patch.dict('os.environ', self.env, clear=True), patch('scripts.v50.cloud_cleanup.subprocess.run', return_value=auth):
            result = cleanup.verify(self.p, self.permission_api())
            self.assertEqual(result['status'], 'PASS'); self.assertFalse(result['topologyCreationAllowed'])
            for fault in ('extra_create', 'broad_delete', 'missing'):
                with self.subTest(fault=fault), self.assertRaises(ValueError): cleanup.verify(self.p, self.permission_api(**{fault: True}))
            auth.stdout = self.p['serviceAccount']
            api = self.permission_api()
            with self.assertRaisesRegex(ValueError, 'identity'): cleanup.verify(self.p, api)
            api.call.assert_not_called()

    def test_malformed_negative_permission_probe_is_not_treated_as_a_denial(self):
        auth = Mock(returncode=0, stdout=cleanup.identity(self.p)['serviceAccount'])
        with patch.dict('os.environ', self.env, clear=True), patch('scripts.v50.cloud_cleanup.subprocess.run', return_value=auth):
            for invalid in (dict(error='HTTP 403'), None, dict(permissions=None), dict(permissions='storage.objects.delete')):
                api = self.permission_api(); query = api.call.side_effect
                api.call.side_effect = lambda method, url, body=None: invalid if 'budget.json' in unquote(url) else query(method, url, body)
                with self.subTest(invalid=invalid), self.assertRaises(ValueError): cleanup.verify(self.p, api)

    def test_expired_entry_rejects_wrong_context_before_cloud_access(self):
        for field, value in [('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('GITHUB_REF', 'refs/heads/feature'),
                             ('GITHUB_WORKFLOW_REF', self.p['repository'] + '/' + self.p['workflow'] + '@' + self.p['ref'])]:
            with self.subTest(field=field), patch.dict('os.environ', dict(self.env, **{field: value}), clear=True), \
                 patch('sys.argv', ['cloud_entry', 'expired-cleanup', '--output', '/unused']), patch('scripts.v50.cloud_entry.Gcp') as gcp:
                with self.assertRaisesRegex(ValueError, 'dedicated scheduled'): main()
                gcp.assert_not_called()

    def test_no_lease_cleanup_uses_only_readonly_backend(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', self.env, clear=True), \
             patch('sys.argv', ['cloud_entry', 'expired-cleanup', '--output', temp]), patch('scripts.v50.cloud_entry.Gcp') as gcp:
            gcp.return_value.get_object.return_value = None
            self.assertEqual(main(), 0)
            self.assertEqual(json.loads((Path(temp) / 'cleanup.json').read_text()), dict(status='PASS', activeLease=False))
            self.assertFalse(gcp.call_args.kwargs['api'].paid)
            self.assertEqual(gcp.call_count, 1)
            self.assertEqual(gcp.return_value.method_calls, [unittest.mock.call.get_object(LEASE)])

    def test_active_lease_waits_without_creating_a_mutating_backend(self):
        req = request('a' * 40, 1, 1, 'b' * 64)
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', self.env, clear=True), \
             patch('sys.argv', ['cloud_entry', 'expired-cleanup', '--output', temp]), patch('scripts.v50.cloud_entry.Gcp') as gcp:
            gcp.return_value.get_object.return_value = ('1', canonical(dict(request=req, expiresAt=10**12)))
            self.assertEqual(main(), 0)
            self.assertEqual(json.loads((Path(temp) / 'cleanup.json').read_text()), dict(status='WAITING', activeLease=True))
            self.assertEqual(gcp.call_count, 1); self.assertFalse(gcp.call_args.kwargs['api'].paid)

    def test_collect_uses_dedicated_workflow_identity_step_and_separate_custom_rule_endpoint(self):
        scheduled = dict(id=101, head_sha='a' * 40, status='completed', conclusion='success', event='schedule',
                         path=cleanup.WORKFLOW, updated_at='1970-01-01T00:16:40Z')
        ci = dict(id=100, head_sha='a' * 40, status='completed', conclusion='success')
        identity_step = dict(name=cleanup.IDENTITY_STEP, conclusion='success')
        endpoints = {
            'branches/master': dict(commit=dict(sha='a' * 40)),
            'actions/workflows/ci.yml/runs?branch=master&per_page=10': dict(workflow_runs=[ci]),
            'actions/runs/100/jobs?per_page=100': dict(jobs=[dict(name='Cloud runner (no GCP)', conclusion='success', steps=[
                dict(name='Verify V5.0 Phase 6B runner failures and offline volume-layout probe', conclusion='success')])]),
            'actions/workflows/v50-expired-cleanup.yml/runs?event=schedule&per_page=10': dict(workflow_runs=[scheduled]),
            'actions/runs/101/jobs?per_page=100': dict(jobs=[dict(name='cleanup', steps=[identity_step,
                dict(name=cleanup.CLEANUP_STEP, conclusion='success')])]),
            'environments/' + cleanup.ENVIRONMENT: self.good['github']['cleanupEnvironment'],
            'environments/' + cleanup.ENVIRONMENT + '/deployment-branch-policies?per_page=100': self.good['github']['cleanupBranches'],
            'environments/' + cleanup.ENVIRONMENT + '/deployment_protection_rules': self.good['github']['cleanupCustomRules']}
        def command(args, **kwargs):
            if args[0] == 'gcloud': return Mock(returncode=0, stdout=self.p['serviceAccount'])
            self.assertEqual(args[:2], ['gh', 'api'])
            return Mock(returncode=0, stdout=json.dumps(endpoints[args[2].split(self.p['repository'] + '/', 1)[1]]).encode())
        api = Mock(); api.call.return_value = {}
        with patch('scripts.v50.cloud_preflight.subprocess.run', side_effect=command), patch('scripts.v50.cloud_preflight.time.time', return_value=1001):
            result = collect(self.p, 'a' * 40, api)
            actual = result['observations']['github']
            self.assertEqual(actual['cleanup']['workflow'], cleanup.WORKFLOW)
            self.assertEqual(actual['cleanup']['identityConclusion'], 'success')
            self.assertEqual(actual['cleanupCustomRules']['total_count'], 0)
            self.assertFalse(any(b.startswith(('cleanup watchdog:', 'cleanup environment:')) for b in result['blockers']))
            identity_step['conclusion'] = 'skipped'
            self.assertIn('did not execute', collect(self.p, 'a' * 40, api)['observations']['github']['cleanup']['error'])
            identity_step['conclusion'] = 'success'; scheduled['event'] = 'workflow_dispatch'
            self.assertIn('wrong cleanup workflow/event', collect(self.p, 'a' * 40, api)['observations']['github']['cleanup']['error'])
        queries = [c.args[:2] for c in api.call.call_args_list]
        self.assertIn(('GET', 'https://serviceusage.googleapis.com/v1/projects/' + self.p['projectNumber'] + '/services/iap.googleapis.com'), queries)

    def test_setup_is_offline_and_never_modifies_paid_environment_or_shared_provider(self):
        with tempfile.TemporaryDirectory() as temp, patch('subprocess.run', side_effect=AssertionError('offline only')):
            root = Path(temp) / 'proposal'; value = write_proposal(root, self.p)
            self.assertFalse(value['applied'])
            commands = json.loads((root / 'commands.json').read_text())
            for command in commands:
                self.assertNotIn('roles/owner', command)
                self.assertNotIn(self.p['wifProvider'], command)
                self.assertNotIn('repos/' + self.p['repository'] + '/environments/' + self.p['environment'], command)
            compute = value['roles'][cleanup.PROJECT_ROLE]['includedPermissions']
            self.assertFalse(set(compute) & set(cleanup.FORBIDDEN_PERMISSIONS))
            self.assertTrue(all(v.rsplit('.', 1)[1] in ('get', 'list', 'delete') for v in compute))
            self.assertIn("/objects/" + LEASE + "'", value['leaseCondition']['expression'])
            self.assertNotIn('startsWith', value['leaseCondition']['expression'])
            with self.assertRaises(FileExistsError): write_proposal(root, self.p)

    def test_workflow_has_no_manual_or_paid_entry_and_cannot_queue_behind_experiment_approval(self):
        text = (ROOT / cleanup.WORKFLOW).read_text()
        paid = (ROOT / self.p['workflow']).read_text()
        self.assertNotIn('workflow_dispatch:', text); self.assertNotIn('inputs.', text)
        self.assertNotIn('  schedule:', paid)
        self.assertIn('environment: ' + cleanup.ENVIRONMENT, text)
        self.assertIn('service_account: ' + cleanup.identity(self.p)['serviceAccount'], text)
        self.assertNotEqual(re.search(r'group: (.+)', text)[1], re.search(r'group: (.+)', paid)[1])
        self.assertLess(text.index(cleanup.IDENTITY_STEP), text.index(cleanup.CLEANUP_STEP))
        self.assertEqual(re.findall(r'python -m scripts.v50.cloud_entry (\S+)', text), ['expired-cleanup'])
        self.assertTrue(all(re.fullmatch('[0-9a-f]{40}', pin) for pin in re.findall(r'uses: \S+@(\S+)', text)))


if __name__ == '__main__': unittest.main()
