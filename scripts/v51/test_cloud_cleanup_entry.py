import base64
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import cloud_cleanup_entry as e, cloud_cleanup_entry_qualification as q, cloud_cleanup_workflows as workflows
from . import cloud_cleanup_qualification as retained, cloud_native_authority as n
from . import cloud_preflight as preflight, cloud_identity_setup as identities, cloud_authority as a, cloud_fake
from .cloud_http import Api
from .remote_command import read


class CleanupEntryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.state, self.now, _ = retained.case_state('expired-manual', authority=n)
        self.v = q.fixture(self.state['configuration'], 'manual')

    def binding(self, v=None):
        v = v or self.v
        return e.identity(v['configuration'], v['env'], trigger=v['trigger'], source=v['source'], checkout=v['checkout'])

    def execute(self, v=None, api=None, name='run'):
        v = v or self.v
        if api is None: _, _, api, _ = retained.restore(self.state)
        return e.execute(v['configuration'], v['env'], v['observation'], api, self.root/name,
                         trigger=v['trigger'], source=v['source'], checkout=v['checkout'], now=self.now)

    def test_entries_bind_separate_workflows_environments_accounts_and_pools(self):
        values = [self.binding(q.fixture(self.state['configuration'], trigger)) for trigger in e.TRIGGERS]
        proposal = identities.proposal(self.v['configuration'])
        for value in values:
            selected = proposal['identities'][value['trigger']]
            for field in ('workflow', 'environment', 'serviceAccount', 'provider'): self.assertEqual(value[field], selected[field])
            self.assertFalse(value['identityAuthenticated']); self.assertFalse(value['activationAllowed'])
        for field in ('workflow', 'environment', 'serviceAccount', 'provider', 'event'):
            self.assertNotEqual(values[0][field], values[1][field])

    def test_context_drift_missing_and_non_string_values_fail_before_http(self):
        for field in self.v['env']:
            for bad in (None, '', 'wrong', 1, True):
                with self.subTest(field=field, bad=bad):
                    v = deepcopy(self.v)
                    if bad is None: del v['env'][field]
                    else: v['env'][field] = bad
                    transport = Mock(offline=True); tokens = Mock(); api = Api(transport=transport, tokens=tokens)
                    with self.assertRaises(ValueError): self.execute(v, api)
                    tokens.assert_not_called(); transport.send.assert_not_called(); self.assertFalse((self.root/'run').exists())

    def test_run_ids_are_positive_bounded_canonical_decimals(self):
        for field in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
            for bad in ('0', '-1', '01', '+1', '1\n', '1e2', '1'*21):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    v = deepcopy(self.v); v['env'][field] = bad; self.binding(v)

    def test_no_runner_observer_v50_or_cross_trigger_can_enter(self):
        for trigger in ('runner', 'observer', 'workflow_dispatch', 'force', ''):
            with self.subTest(trigger=trigger), self.assertRaises(ValueError): self.binding(dict(self.v, trigger=trigger))
        with self.assertRaises(ValueError): self.binding(dict(self.v, trigger='schedule'))
        for workflow in (a.RUNNER_WORKFLOW, '.github/workflows/v50-manual-cleanup.yml', '.github/workflows/ci.yml'):
            v = deepcopy(self.v); v['env']['GITHUB_WORKFLOW_REF'] = e.ci.REPOSITORY+'/'+workflow+'@refs/heads/master'
            with self.assertRaises(ValueError): self.binding(v)

    def test_checkout_workflow_and_run_must_use_same_source(self):
        for field in ('source', 'checkout'):
            with self.subTest(field=field), self.assertRaises(ValueError): self.binding(dict(self.v, **{field:'d'*40}))
        for field in ('GITHUB_SHA', 'GITHUB_WORKFLOW_SHA', 'GITHUB_REF'):
            v = deepcopy(self.v); v['env'][field] = 'd'*40
            with self.assertRaises(ValueError): self.binding(v)

    def test_api_observation_rejects_wrong_source_attempt_event_path_and_forks(self):
        for field, bad in (('id', 12346), ('run_attempt', 1), ('run_attempt', True), ('head_sha', 'd'*40),
                           ('head_branch', 'feature'), ('path', a.RUNNER_WORKFLOW), ('event', 'schedule'),
                           ('status', 'completed'), ('conclusion', 'success')):
            with self.subTest(field=field):
                v = deepcopy(self.v); v['observation'][field] = bad
                api = Mock(offline=True)
                with self.assertRaises(ValueError): self.execute(v, api)
                api.call.assert_not_called(); self.assertFalse((self.root/'run').exists())
        for field in ('repository', 'head_repository'):
            for key, bad in (('id', 123), ('full_name', 'fork/GeneralSearchEngine'), ('owner', dict(id=123))):
                v = deepcopy(self.v); v['observation'][field][key] = bad
                with self.assertRaises(ValueError): e.validate_run(self.binding(), v['observation'])

    def test_missing_run_fields_fail_closed(self):
        for key in self.v['observation']:
            v = deepcopy(self.v['observation']); del v[key]
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)): e.validate_run(self.binding(), v)

    def test_collection_detects_rerun_before_or_during_sampling(self):
        binding = self.binding(); original = self.v['observation']
        get = Mock(return_value=original)
        self.assertEqual(e.collect_run(binding, get), original)
        self.assertEqual([c.args[0] for c in get.call_args_list],
                         ['actions/runs/12345', 'actions/runs/12345/attempts/2', 'actions/runs/12345'])
        for index in range(3):
            values = [deepcopy(original) for _ in range(3)]; values[index]['run_attempt'] = 3
            with self.subTest(index=index), self.assertRaises(ValueError): e.collect_run(binding, Mock(side_effect=values))

    def test_cleanup_does_not_depend_on_green_ci_or_current_master_tip(self):
        # A current cleanup source can reclaim an abandoned older-source request;
        # CI failure or a subsequent commit must not disable that reconciliation.
        request = e.m.strict_json(base64.b64decode(self.state['objects'][n.LEASE]['data']))['request']
        self.assertNotEqual(self.v['source'], request['source'])
        with patch.object(e.ci, 'collect', side_effect=AssertionError('cleanup must not require CI')):
            result = self.execute()
        self.assertEqual(result['status'], 'PASS'); self.assertTrue(result['reconciliation']['leaseReleased'])
        self.assertFalse(result['paidCloud']); self.assertFalse(result['cleanupReady'])

    def test_live_api_rejected_before_credentials_network_and_output(self):
        tokens = Mock(); transport = Mock(offline=False)
        with self.assertRaisesRegex(ValueError, 'activation unavailable'):
            self.execute(api=Api(transport=transport, tokens=tokens))
        tokens.assert_not_called(); transport.send.assert_not_called(); self.assertFalse((self.root/'run').exists())

    def test_caller_cannot_select_cloud_identity_or_resource_scope_via_environment(self):
        v = deepcopy(self.v)
        v['env'].update(SERVICE_ACCOUNT='attacker@example.com', WIF_PROVIDER='other', BUCKET='other', FORCE='true')
        self.assertEqual(self.binding(v), self.binding())

    def test_configuration_drift_does_not_delete_old_resources(self):
        v = deepcopy(self.v); v['configuration']['provider']['network'] = 'wrong-network'
        _, http, api, _ = retained.restore(self.state)
        result = self.execute(v, api)
        self.assertEqual(result['status'], 'FAIL'); self.assertEqual(retained.snapshot(http), self.state)
        self.assertTrue(all(row['method'] == 'GET' for row in http.requests))

    def test_fake_authority_is_not_relabelled_into_native_readiness(self):
        state, _, _ = retained.case_state('expired-manual')
        _, http, api, _ = retained.restore(state)
        result = self.execute(api=api)
        self.assertEqual(result['status'], 'FAIL'); self.assertEqual(retained.snapshot(http), state)
        self.assertEqual(result['failure'], dict(phase='reconciliation', type='ValueError'))
        req, _, approval = cloud_fake.fixture()
        with self.assertRaises(ValueError): a.admit(req, result, approval, self.now)

    def test_provider_error_text_and_credential_environment_not_retained(self):
        secret = 'sentinel-secret-not-for-evidence'
        v = deepcopy(self.v); v['env']['GH_TOKEN'] = secret
        api = Mock(offline=True); api.clock = lambda: 0; api.call.side_effect = ConnectionError(secret)
        result = self.execute(v, api)
        self.assertEqual(result['status'], 'FAIL'); api.call.assert_called_once()
        self.assertEqual(result['failure']['type'], 'ConnectionError')
        for file in (self.root/'run').rglob('*'):
            if file.is_file(): self.assertNotIn(secret, file.read_text())

    def test_activation_command_blocks_with_nonzero_exit_without_cloud_tools(self):
        root = self.root/'closed'
        result = subprocess.run([sys.executable, '-m', 'scripts.v51.cloud_cleanup_entry', 'activation-check', '--output', str(root)],
                                capture_output=True, text=True, timeout=10, env={'PATH':str(self.root)})
        self.assertEqual(result.returncode, 2, result.stderr)
        receipt = read(root/'receipt.json'); self.assertEqual(receipt['status'], 'BLOCKED')
        for key in ('activationAllowed', 'identityAuthenticated', 'cleanupReady', 'paidCloud'): self.assertIs(receipt[key], False)
        self.assertIn('BLOCKED', (root/'summary.md').read_text())

    def test_summary_cannot_inject_html_or_table_rows(self):
        value = dict(status='FAIL', execution='<script>|\nfake', reason='<secret>')
        text = e.summary(value)
        self.assertNotIn('<script>', text); self.assertIn('&lt;script&gt;&#124; fake', text)


class CleanupWorkflowTest(unittest.TestCase):
    def test_proposals_are_separate_inactive_entries_with_retained_diagnostics(self):
        cfg = read(preflight.CONFIG)
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.run', side_effect=AssertionError('unexpected apply')):
            root = Path(tmp)/'proposal'; receipt = workflows.write(root, cfg)
            self.assertEqual(receipt['status'], 'PROPOSAL_ONLY'); self.assertFalse(receipt['deployed'])
            for row in receipt['entries']:
                text = (root/row['file']).read_text()
                event = text.split('\non:\n')[1].split('\npermissions:')[0]
                self.assertIn('schedule:' if row['trigger']=='schedule' else 'workflow_dispatch:', event)
                self.assertNotIn('workflow_dispatch:' if row['trigger']=='schedule' else 'schedule:', event)
                self.assertNotIn('inputs:', text); self.assertNotIn('id-token:', text); self.assertNotIn('google-github-actions/auth@', text)
                self.assertIn('group: v51-native-cleanup', text); self.assertIn('cancel-in-progress: false', text)
                self.assertIn('environment: '+row['environment'], text)
                self.assertIn('activation-check', text); self.assertIn('if: ${{ always() }}', text)
                self.assertIn('--trigger '+row['trigger'], text)
                self.assertEqual(row['sha256'], e.m.sha(text.encode()))
            with self.assertRaises(FileExistsError): workflows.write(root, cfg)

    def test_generator_cannot_deploy_into_github_or_symlink_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'.github').mkdir(); (root/'alias').symlink_to(root/'.github', target_is_directory=True)
            for output in (root/'.github/workflows', root/'alias/workflows'):
                with self.assertRaises(ValueError): workflows.write(output, read(preflight.CONFIG))
                self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
