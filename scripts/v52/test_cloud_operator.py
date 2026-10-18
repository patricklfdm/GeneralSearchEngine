"""Operator routing models and actual local SSH-secret lifetime checks."""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from . import cloud_operator as o, cloud_credentials_offline as auth
from .test_cloud_prepared_artifact import fixture
from .test_cloud_member_seal import fixture as sealed_fixture


class OperatorTest(unittest.TestCase):
    def setUp(self):
        self.cfg, self.source, self.files = fixture(); self.plan = o.strict(self.files['plan.json'])
        _, self.env, _, _, _ = auth.fixture(self.cfg['provider'], 'runner', 'a'*40)
        self.env['GITHUB_RUN_ID'] = '654321'; self.env['V52_SSH_KEY'] = 'never-retain-secret'
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.env['GITHUB_OUTPUT'] = str(self.root/'actions-output'); (self.root/'actions-output').touch()
        self.prepare = Mock(side_effect=self.preparing); self.download = Mock(side_effect=self.downloading)
        self.run = Mock(side_effect=self.running); self.verify = Mock(side_effect=self.verifying); self.key_calls = 0
        self.preparation = o.strict(self.files['preparation.json']); self.preparation['credentialContext'].update(runId=654321)
        self.seal = o.execution.seal.create(**sealed_fixture()); self.seal['credentialContext'].update(runId=654321)
    def preparing(self, source, request, public, output):
        output.mkdir(); (output/'public').mkdir()
        for name, raw in self.files.items(): (output/'public'/name).write_bytes(raw)
        (output/'private-key').write_text('never-upload')
        return deepcopy(self.preparation)
    def downloading(self, source, chosen, output):
        self.assertEqual(dict(runId=123456,runAttempt=2),chosen)
        (output/'files').mkdir(parents=True)
        for name, raw in self.files.items(): (output/'files'/name).write_bytes(raw)
        return dict(status='PREPARED_ARTIFACT_VERIFIED_NOT_ADMITTED')
    def running(self, source, plan, approval, confirmation, package, key, output):
        self.assertEqual(self.plan,o.artifacts.read(plan)); approved=o.artifacts.read(approval)
        self.assertTrue(approved['confirmed']); self.assertEqual(approved['planSha256'],confirmation)
        (output/'public').mkdir(parents=True); o.artifacts.save(output/'public/member-seal.json',self.seal)
        return deepcopy(self.seal)
    def verifying(self, source, selected, output):
        return dict(status='PASS',fullRemoteQualification=True,totals=dict(histories=33),selected=selected,
                    selectedReservedCostMicrousd=20_000_000,ledgerReservedCostMicrousd=30_000_000)
    @contextmanager
    def key(self):
        self.key_calls+=1; yield self.root/'private-key',self.plan['request']['guestAccess']['publicKey']
    def execute(self,operation,value):
        self.env.update(V52_OPERATION=operation,V52_REQUEST=o.encoded(value).decode())
        self.output=self.root/('operator-'+str(len(list(self.root.iterdir()))))
        with patch.dict(os.environ,self.env,clear=True), patch.object(o.reads,'source_configuration',return_value=deepcopy(self.cfg)), \
             patch.object(o.preparation,'prepare_native',self.prepare),patch.object(o.downloaded,'collect_native',self.download), \
             patch.object(o.execution,'run_native',self.run),patch.object(o.acceptance,'verify_native',self.verify), \
             patch.object(o,'private_key',self.key),patch.object(o.access,'check_private_key'), \
             patch.object(o.time,'time',return_value=1200),patch.object(o.member.Progress,'report'):
            return o.execute_native('a'*40,self.output)
    def request(self):return dict(preparedRun=123456,preparedAttempt=2,confirmation=o.prepared.validate(self.plan,1200))
    def test_prepare_exports_only_exact_public_files_and_reviewable_unconfirmed_request(self):
        value=dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate'])
        result=self.execute('prepare',value); self.prepare.assert_called_once(); self.run.assert_not_called()
        self.assertEqual(set(o.downloaded.LIMITS),{p.name for p in (self.output/'result').iterdir()})
        self.assertEqual(dict(preparedRun=654321,preparedAttempt=2,confirmation=result['planSha256']),result['runRequest'])
        self.assertIn('artifactName=v52-prepared-654321-2',(self.root/'actions-output').read_text())
        self.assertNotIn('never-retain',str(result)); self.assertFalse(o.artifacts.read(self.output/'result/approval.json')['confirmed'])
    def test_run_confirms_only_downloaded_exact_plan_then_executes_once(self):
        result=self.execute('run',self.request());self.download.assert_called_once();self.run.assert_called_once()
        self.assertFalse(result['fullRemoteQualification']); self.assertEqual(1,self.key_calls)
        self.assertEqual({'member-seal.json'},{p.name for p in (self.output/'result').iterdir()})
        self.assertIn('artifactName=v52-runner-654321-2',(self.root/'actions-output').read_text())
    def test_changed_confirmation_or_failed_download_never_opens_paid_entry(self):
        request=self.request();request['confirmation']='f'*64
        with self.assertRaisesRegex(ValueError,'confirmation changed'):self.execute('run',request)
        self.run.assert_not_called();self.assertEqual(0,self.key_calls)
        self.download.side_effect=ValueError('synthetic original failed')
        with self.assertRaisesRegex(ValueError,'original failed'):self.execute('run',self.request())
        self.run.assert_not_called();self.assertFalse((self.output/'result').exists())
    def test_failed_original_run_exports_only_safe_diagnostic_code_and_never_retries(self):
        def fail(*args):
            path=args[-1];(path/'native').mkdir(parents=True)
            o.artifacts.save(path/'native/failure.json',dict(code='V52_RUNNER_PROVIDER_REJECTED',httpStatus=403,secret='never-public'))
            raise ValueError('never-public-secret')
        self.run.side_effect=fail
        with self.assertRaises(ValueError):self.execute('run',self.request())
        self.run.assert_called_once();report=o.artifacts.read(self.output/'diagnostics/failure.json')
        self.assertEqual('V52_RUNNER_PROVIDER_REJECTED',report['causeCode']);self.assertEqual(403,report['httpStatus'])
        self.assertNotIn('never-public',str(report));self.assertFalse((self.output/'result').exists())
    def test_rotated_ssh_key_rejects_before_original_native_entry(self):
        from .test_cloud_identity import public_key
        @contextmanager
        def changed(): yield self.root/'private-key',public_key(9)
        self.key=changed
        with self.assertRaisesRegex(ValueError,'SSH key changed'):self.execute('run',self.request())
        self.run.assert_not_called();self.assertFalse((self.output/'result').exists())
    def test_verify_set_has_no_key_or_paid_entry_and_keeps_all_original_selections(self):
        chosen={name:dict(requestSha256=f'{i:064x}',runId=1000+i,runAttempt=1) for i,name in enumerate(o.acceptance.suite.MEMBERS,1)}
        result=self.execute('verify-set',chosen);self.assertTrue(result['fullRemoteQualification']);self.assertEqual(0,self.key_calls)
        self.prepare.assert_not_called();self.run.assert_not_called();self.verify.assert_called_once()
        self.assertEqual({'cloud-set.json'},{p.name for p in (self.output/'result').iterdir()})
        self.assertIn('artifactName=v52-cloud-set-654321-2',(self.root/'actions-output').read_text())
    def test_invalid_input_or_unprotected_context_fails_before_factories(self):
        for operation,request in (('force-delete',{}),('run',dict(preparedRun=True,preparedAttempt=1,confirmation='a'*64)),('verify-set',{})):
            with self.assertRaises(ValueError):self.execute(operation,request)
        self.env['GITHUB_REF']='refs/heads/topic'
        with self.assertRaises(ValueError):self.execute('run',self.request())
        self.download.assert_not_called();self.prepare.assert_not_called();self.run.assert_not_called()
    def test_summary_shows_request_costs_identity_and_escapes_diagnostics(self):
        self.execute('prepare',dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate']))
        out=io.StringIO()
        with redirect_stdout(out):o.summary(self.output)
        text=out.getvalue();self.assertIn('Exact run request',text);self.assertIn('previousCostMicrousd',text);self.assertIn('source',text)
        o.artifacts.save(self.output/'diagnostics/failure.json',dict(status='FAIL',code='<script>|bad\nline'))
        out=io.StringIO()
        with redirect_stdout(out):o.summary(self.output)
        self.assertNotIn('<script>',out.getvalue());self.assertIn('&#124;',out.getvalue());self.assertNotIn('Exact run request',out.getvalue())
    def test_draft_uses_explicit_cost_and_claims_no_live_price_verification(self):
        with patch.object(o.reads,'source_configuration',return_value=self.cfg),patch.object(o.time,'time',return_value=1000):
            result=o.prepare_request('a'*40,'canonical-3','c'*32,12_000_000,21600,14400,self.root/'draft')
        self.assertEqual(12_000_000,result['estimate']['costMicrousd']);self.assertEqual(15400,result['estimate']['expiresAt'])
        self.assertFalse(o.artifacts.read(self.root/'draft/receipt.json')['livePricesVerified'])


class SecretLifetimeTest(unittest.TestCase):
    def test_actual_key_is_private_removed_and_not_inherited_by_children(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','','-f',str(original)],check=True,timeout=10)
            with patch.dict(os.environ,{'V52_SSH_KEY':original.read_text()}):
                with o.private_key() as (path,public):
                    self.assertEqual(0,path.stat().st_mode&0o077);self.assertNotIn('V52_SSH_KEY',os.environ)
                    o.access.check_private_key(path,o.access.descriptor('a'*32,public))
                self.assertFalse(path.exists())
    def test_bad_secret_cannot_be_logged_or_left_in_environment(self):
        with patch.dict(os.environ,{'V52_SSH_KEY':'invalid-secret'}):
            with self.assertRaisesRegex(ValueError,'missing/invalid') as error:
                with o.private_key():self.fail('bad key accepted')
            self.assertNotIn('invalid-secret',str(error.exception));self.assertNotIn('V52_SSH_KEY',os.environ)


if __name__=='__main__':unittest.main()
