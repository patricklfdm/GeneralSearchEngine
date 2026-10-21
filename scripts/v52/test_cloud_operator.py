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
from .test_cloud_execution import chdir


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
    def execute(self,operation,value,output=None):
        self.env.update(V52_OPERATION=operation,V52_REQUEST=o.encoded(value).decode())
        output=output if output is not None else self.root/('operator-'+str(len(list(self.root.iterdir()))))
        self.output=Path(output).absolute()
        with patch.dict(os.environ,self.env,clear=True), patch.object(o.reads,'source_configuration',return_value=deepcopy(self.cfg)), \
             patch.object(o.preparation,'prepare_native',self.prepare),patch.object(o.downloaded,'collect_native',self.download), \
             patch.object(o.execution,'run_native',self.run),patch.object(o.acceptance,'verify_native',self.verify), \
             patch.object(o,'private_key',self.key),patch.object(o.access,'check_private_key'), \
             patch.object(o.time,'time',return_value=1200),patch.object(o.member.Progress,'report'):
            return o.execute_native('a'*40,output)
    def request(self):return dict(preparedRun=123456,preparedAttempt=2,confirmation=o.prepared.validate(self.plan,1200))
    def test_prepare_exports_only_exact_public_files_and_reviewable_unconfirmed_request(self):
        value=dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate'])
        result=self.execute('prepare',value); self.prepare.assert_called_once(); self.run.assert_not_called()
        self.assertEqual(set(o.downloaded.LIMITS),{p.name for p in (self.output/'result').iterdir()})
        self.assertEqual(dict(preparedRun=654321,preparedAttempt=2,confirmation=result['planSha256']),result['runRequest'])
        self.assertIn('artifactName=v52-prepared-654321-2',(self.root/'actions-output').read_text())
        self.assertNotIn('never-retain',str(result)); self.assertFalse(o.artifacts.read(self.output/'result/approval.json')['confirmed'])
    def test_original_build_failure_projects_nested_phase_status_attempts_and_check_site(self):
        def fail(source,request,public,output):
            (output/'build').mkdir(parents=True)
            o.artifacts.save(output/'failure.json',dict(code='V52_PREPARE_ORIGINAL_BUILD_REJECTED'))
            o.artifacts.save(output/'build/failure.json',dict(status='FAIL',phase='full-ci',
                code='V52_PROVENANCE_FULL_CI_REJECTED',reasonCode='V52_GITHUB_HTTP_REJECTED',httpStatus=503,
                checkSite=dict(module=o.artifacts.ci.__name__,line=123,secret='never-public'),
                request=dict(kind='jobs',ordinal=7,attempts=3,stop='attempt-limit',url='never-public'),
                stderr='never-public'))
            raise ValueError('never-public-original-error')
        self.prepare.side_effect=fail
        with self.assertRaises(ValueError):
            self.execute('prepare',dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate']))
        result=o.artifacts.read(self.output/'diagnostics/failure.json')
        self.assertEqual('V52_PREPARE_ORIGINAL_BUILD_REJECTED',result['causeCode'])
        detail=result['buildProvenance']; self.assertEqual('full-ci',detail['phase'])
        self.assertEqual(503,detail['httpStatus']); self.assertEqual(3,detail['request']['attempts'])
        self.assertEqual('jobs',detail['request']['kind']); self.assertEqual(123,detail['checkSite']['line'])
        self.assertNotIn('never-public',str(result));self.assertFalse((self.output/'result').exists())
        self.run.assert_not_called();self.prepare.assert_called_once()
        out=io.StringIO()
        with redirect_stdout(out):o.summary(self.output)
        self.assertIn('buildProvenance',out.getvalue());self.assertIn('503',out.getvalue())
        self.assertNotIn('never-public',out.getvalue())
    def test_run_confirms_only_downloaded_exact_plan_then_executes_once(self):
        result=self.execute('run',self.request());self.download.assert_called_once();self.run.assert_called_once()
        self.assertFalse(result['fullRemoteQualification']); self.assertEqual(1,self.key_calls)
        self.assertEqual({'member-seal.json'},{p.name for p in (self.output/'result').iterdir()})
        self.assertIn('artifactName=v52-runner-654321-2',(self.root/'actions-output').read_text())
    def test_workflow_relative_output_reaches_original_iap_path_boundary(self):
        from . import cloud_iap as iap
        class ReachedGuestAuthority(Exception): pass
        guest_session=object.__new__(o.native.Session);guest_session.api=object.__new__(o.native.NativeRunnerApi)
        guest_session.guests=None;guest_session.checkpoint=Mock(side_effect=ReachedGuestAuthority)
        closed=[];paths=[]
        class Session:
            def __enter__(self):return self
            def __exit__(self,*args):closed.append(True)
            def run_member(self,key,output):
                paths.append(output);return iap.open_native(guest_session,key,output/'guests')
        # Keep the original execution and IAP path checks. Only paid admission
        # and the authority checkpoint are modeled; no SDK/network is started.
        self.run.side_effect=o.execution.run_native
        with chdir(self.root),patch.object(o.native,'open_native',return_value=Session()) as admission, \
             patch.object(iap,'_gcloud') as sdk:
            with self.assertRaises(ReachedGuestAuthority):self.execute('run',self.request(),Path('target/v52-runner'))
        self.assertEqual([self.root/'target/v52-runner/run/member'],paths)
        self.assertTrue(admission.call_args.args[-1].is_absolute());self.assertEqual([True],closed)
        guest_session.checkpoint.assert_called_once();sdk.assert_not_called();self.run.assert_called_once()
        self.assertFalse((self.output/'result').exists())
    def test_relative_prepare_and_verify_outputs_are_absolute(self):
        selected={name:dict(requestSha256=f'{i:064x}',runId=1000+i,runAttempt=1) for i,name in enumerate(o.acceptance.suite.MEMBERS,1)}
        with chdir(self.root):
            self.execute('prepare',dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate']),Path('target/prepare'))
            self.assertEqual(self.root/'target/prepare/prepare',self.prepare.call_args.args[-1])
            self.execute('verify-set',selected,Path('target/verify'))
            self.assertEqual(self.root/'target/verify/verify-set',self.verify.call_args.args[-1])
    def test_unsafe_output_rejects_before_identity_or_paid_factory(self):
        self.env.update(V52_OPERATION='run',V52_REQUEST=o.encoded(self.request()).decode())
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'link').symlink_to(outside,target_is_directory=True)
            with chdir(self.root),patch.dict(os.environ,self.env,clear=True),patch.object(o.reads,'source_configuration') as source:
                for path in ('link/run','link/../run','../run'):
                    with self.subTest(path=path),self.assertRaises(ValueError):o.execute_native('a'*40,Path(path))
            source.assert_not_called();self.assertEqual([],list(Path(outside).iterdir()))
        self.run.assert_not_called();self.prepare.assert_not_called()
    def test_member_phase_and_cleanup_are_retained_without_private_details(self):
        def fail(*args):
            path=args[-1];(path/'native').mkdir(parents=True);(path/'member').mkdir()
            (path/'member/guests').mkdir()
            (path/'member/storage').mkdir()
            o.artifacts.save(path/'member/storage/diagnostic.json',storage_diagnostic())
            o.artifacts.save(path/'member/guests/connections.json',iap_diagnostic())
            o.artifacts.save(path/'member/failure.json',dict(status='FAIL',phase='guest-identity',
                code='V52_MEMBER_GUEST_IDENTITY_REJECTED',errorType='ValueError',secret='never-public'))
            o.artifacts.save(path/'native/cleanup.json',dict(status='PASS',resourceDeletesSubmitted=13,
                result=dict(status='PASS',leaseReleased=True,cleanup=dict(status='PASS',leftovers=[],errors=[])),
                secret='never-public'))
            raise ValueError('never-public-original-error')
        self.run.side_effect=fail
        with self.assertRaises(ValueError):self.execute('run',self.request())
        result=o.artifacts.read(self.output/'diagnostics/failure.json')
        self.assertEqual('V52_MEMBER_GUEST_IDENTITY_REJECTED',result['causeCode'])
        self.assertEqual('guest-identity',result['memberPhase'])
        self.assertEqual(dict(status='PASS',leaseReleased=True,resourceDeletesSubmitted=13),result['cleanup'])
        self.assertEqual(70,result['iap']['nodes']['node-1']['accepted'])
        self.assertEqual('SSH_DISCONNECTED',result['iap']['nodes']['node-1']['lastFailureCode'])
        self.assertNotIn('recent',str(result['iap']));self.assertNotIn('pid',str(result['iap']))
        self.assertEqual('python-install',result['storage']['operation'])
        self.assertEqual('node-2',result['storage']['node'])
        self.assertEqual('V52_STORAGE_EXCHANGE_TIMEOUT',result['storage']['reasonCode'])
        self.assertNotIn('never-public',str(result));self.assertFalse((self.output/'result').exists())
        self.run.assert_called_once()
        out=io.StringIO()
        with redirect_stdout(out):o.summary(self.output)
        self.assertIn('capacityRejections',out.getvalue());self.assertNotIn('never-public',out.getvalue())
        self.assertIn('python-install',out.getvalue())
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
        with self.assertRaises(o.access.PrivateKeyError) as error:self.execute('run',self.request())
        self.assertEqual('V52_SSH_KEY_MISMATCH',error.exception.code)
        self.assertEqual(error.exception.code,o.artifacts.read(self.output/'diagnostics/failure.json')['causeCode'])
        self.run.assert_not_called();self.assertFalse((self.output/'result').exists())
    def test_key_failure_has_safe_distinct_phase_before_prepare_or_paid_entry(self):
        @contextmanager
        def failed_key():
            raise ValueError('never-public-key-detail')
            yield
        self.key=failed_key
        for operation,request in (('prepare',dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate'])),
                                  ('run',self.request())):
            with self.subTest(operation=operation),self.assertRaises(ValueError):self.execute(operation,request)
            report=o.artifacts.read(self.output/'diagnostics/failure.json')
            self.assertEqual(operation+'-key',report['phase'])
            self.assertEqual('V52_OPERATOR_'+operation.upper()+'_KEY_REJECTED',report['code'])
            self.assertNotIn('causeCode',report)
            self.assertNotIn('never-public',str(report));self.assertFalse((self.output/'result').exists())
        self.prepare.assert_not_called();self.run.assert_not_called()
    def test_key_failure_reports_only_closed_reason_code_in_both_operations(self):
        for reason in o.access.KEY_FAILURES:
            @contextmanager
            def failed_key():
                raise o.access.PrivateKeyError(reason)
                yield
            self.key=failed_key
            for operation,request in (('prepare',dict(member='experiment',sequence='c'*32,estimate=self.plan['estimate'])),
                                      ('run',self.request())):
                with self.subTest(reason=reason,operation=operation),self.assertRaises(o.access.PrivateKeyError):
                    self.execute(operation,request)
                report=o.artifacts.read(self.output/'diagnostics/failure.json')
                self.assertEqual('V52_SSH_'+reason,report['causeCode'])
                self.assertEqual(operation+'-key',report['phase'])
                self.assertFalse((self.output/'result').exists())
                text=io.StringIO()
                with redirect_stdout(text):o.summary(self.output)
                self.assertIn(report['causeCode'],text.getvalue())
                self.assertNotIn('never-retain-secret',text.getvalue())
        self.prepare.assert_not_called();self.run.assert_not_called()
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


def storage_diagnostic():
    from . import cloud_storage_diagnostics as d
    return dict(schema=d.SCHEMA,status='FAIL',node='node-2',operation='python-install',stage='begin',kind=None,action=None,
        reasonCode='V52_STORAGE_EXCHANGE_TIMEOUT',errorType='TimeoutError',
        origin=dict(module='remote_python_ssh',line=22),initializedNodes=['node-1','node-2'],
        pythonInstalledNodes=['node-1'],javaInstalledNodes=[],secret='never-public')


class StorageDiagnosticTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def report(self,value):
        (self.root/'diagnostic.json').write_bytes(o.encoded(value))
        return o.storage_report(self.root)

    def test_only_closed_fields_are_projected(self):
        value=storage_diagnostic();report=self.report(value)
        self.assertIsNotNone(report);self.assertNotIn('never-public',str(report))
        self.assertEqual('remote_python_ssh',report['origin']['module'])

    def test_control_read_codes_survive_projection_without_exception_text(self):
        from . import cloud_provider as p, cloud_storage_diagnostics as d
        for code in p.READ_FAILURES:
            error=p.ControlReadError(code)
            # Public projection uses the closed code, never even a modified
            # exception's text or any additional private diagnostic fields.
            error.args=('never-public-provider-response',)
            value=storage_diagnostic()
            value.update(reasonCode=d.reason(error),errorType=d.error_type(error),
                         origin=dict(module='cloud_wire_policy',line=81))
            report=self.report(value)
            self.assertEqual(code,report['reasonCode'])
            self.assertEqual('ControlReadError',report['errorType'])
            self.assertNotIn('never-public',str(report))
        with self.assertRaises(ValueError):p.ControlReadError('never-public-unknown-code')

    def test_unknown_codes_nodes_operations_and_sites_are_omitted(self):
        for field in ('node','operation','stage','kind','action','reasonCode','errorType'):
            value=storage_diagnostic();value[field]='never-public'
            with self.subTest(field=field):self.assertIsNone(self.report(value))
        for site in (dict(module='private-key',line=1),dict(module='cloud_storage',line=True),
                     dict(module='cloud_storage',line=10001),dict(module='cloud_storage',line=1,secret='never-public')):
            value=storage_diagnostic();value['origin']=site
            self.assertIsNone(self.report(value))

    def test_invalid_node_progress_and_partial_exchange_are_omitted(self):
        for changes in (dict(initializedNodes=[]),dict(pythonInstalledNodes=['node-1','node-1']),
                        dict(javaInstalledNodes=['node-3']),dict(action='check')):
            value=storage_diagnostic();value.update(changes)
            self.assertIsNone(self.report(value))

    def test_missing_malformed_linked_oversized_diagnostic_is_not_published(self):
        self.assertIsNone(o.storage_report(self.root))
        path=self.root/'diagnostic.json'
        for raw in (b'not json',b'x'*16385,b'[]'):
            path.write_bytes(raw);self.assertIsNone(o.storage_report(self.root))
        path.unlink();(self.root/'private').write_bytes(o.encoded(storage_diagnostic()));path.symlink_to(self.root/'private')
        self.assertIsNone(o.storage_report(self.root))


def iap_diagnostic():
    return dict(schema='gse-v52-iap-connections-v2',status='CLOSED',failureCode=None,closeFailure=None,
        fullRemoteQualification=False,private='never-public',nodes={'node-1':dict(accepted=70,completed=70,
            failed=1,active=0,peakActive=4,capacityRejections=2,sentBytes=100,receivedBytes=200,historyDropped=6,
            lastFailureCode='SSH_DISCONNECTED',recent=[dict(pid=123,private='never-public')],activeRecords=[])})


class IapReportTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
    def report(self,value):
        (self.root/'connections.json').write_bytes(o.encoded(value));return o.iap_report(self.root)
    def test_only_closed_codes_and_counter_projection_are_public(self):
        value=iap_diagnostic();report=self.report(value)
        self.assertEqual('CLOSED',report['status']);self.assertFalse(report['closeFailed'])
        self.assertEqual(70,report['nodes']['node-1']['accepted'])
        self.assertNotIn('never-public',str(report));self.assertNotIn('recent',report['nodes']['node-1'])
        for code in ('IAP_PERMISSION','IAP_PROVIDER_HTTP_403','V52_CREDENTIAL_CLOSED','IAP_CLOSE_INCOMPLETE'):
            value['failureCode']=code;self.assertEqual(code,self.report(value)['failureCode'])
        for code in ('IAP_PERMISSION_secret','IAP_PROVIDER_HTTP_999','V52_CREDENTIAL_secret',{'private':'never-public'}):
            value['failureCode']=code;value['nodes']['node-1']['lastFailureCode']=code
            report=self.report(value);self.assertEqual('IAP_UNCLASSIFIED',report['failureCode'])
            self.assertEqual('IAP_UNCLASSIFIED',report['nodes']['node-1']['lastFailureCode'])
            self.assertNotIn('secret',str(report));self.assertNotIn('never-public',str(report))
        value['closeFailure']='never-public';self.assertTrue(self.report(value)['closeFailed'])
        self.assertNotIn('never-public',str(self.report(value)))
    def test_missing_malformed_unbounded_or_linked_diagnostic_is_ignored(self):
        self.assertIsNone(o.iap_report(self.root))
        value=iap_diagnostic()
        for field,bad in (('accepted',True),('completed',71),('active',5),('peakActive',5),('failed',71),
                          ('capacityRejections',-1),('sentBytes',2**63),('receivedBytes','secret'),('historyDropped',7)):
            changed=deepcopy(value);changed['nodes']['node-1'][field]=bad
            with self.subTest(field=field):self.assertIsNone(self.report(changed))
        for change in (dict(schema='old'),dict(status='secret'),dict(fullRemoteQualification=True),
                       dict(nodes={'private-host':value['nodes']['node-1']}),dict(nodes=[])):
            self.assertIsNone(self.report(dict(value,**change)))
        path=self.root/'connections.json'
        for raw in (b'not json',b'x'*131073):
            path.write_bytes(raw);self.assertIsNone(o.iap_report(self.root))
        path.unlink();(self.root/'original').write_bytes(o.encoded(value));path.symlink_to(self.root/'original')
        self.assertIsNone(o.iap_report(self.root))
    def test_partial_open_and_failed_close_remain_diagnostics(self):
        value=iap_diagnostic();value.update(status='FAIL',failureCode='IAP_CLOSE_INCOMPLETE',closeFailure='OSError')
        value['nodes']['node-1'].update(accepted=71,active=1)
        report=self.report(value);self.assertEqual(1,report['nodes']['node-1']['active'])
        self.assertTrue(report['closeFailed']);self.assertEqual('FAIL',report['status'])
        value['nodes']={};self.assertEqual({},self.report(value)['nodes'])

    def test_admission_failure_site_timing_and_retry_count_survive_projection(self):
        value=iap_diagnostic();row=value['nodes']['node-1']
        attempt=dict(attempt=1,status='FAIL',phase='owner-lock',elapsedMillis=25000,phaseMillis={'owner-lock':25000},
            reasonCode='IAP_ORIGINAL_CONNECT_TIMEOUT',errorType='TimeoutError',origin=dict(module='cloud_iap',line=123))
        row.update(admissionRetries=0,admissionMillis=25000,lastAdmission=[attempt])
        report=self.report(value)['nodes']['node-1']
        self.assertEqual([attempt],report['lastAdmission']);self.assertEqual(25000,report['admissionMillis'])
        self.assertNotIn('never-public',str(report))

    def test_private_or_invalid_admission_diagnostics_never_propagate(self):
        base=dict(attempt=1,status='FAIL',phase='credentials',elapsedMillis=3,phaseMillis={'credentials':3},
            reasonCode='V52_CREDENTIAL_DEADLINE',errorType='ContextError',origin=None)
        for change in (dict(phase='secret'),dict(reasonCode='secret'),dict(errorType='secret'),dict(attempt=True),
                       dict(elapsedMillis=-1),dict(phaseMillis={'secret':3}),dict(message='secret'),
                       dict(origin=dict(module='private-key',line=1)),dict(origin=dict(module='cloud_iap',line=True))):
            value=iap_diagnostic();value['nodes']['node-1'].update(admissionRetries=0,admissionMillis=3,
                lastAdmission=[dict(base,**change)])
            with self.subTest(change=change):self.assertIsNone(self.report(value))
        value=iap_diagnostic();value['nodes']['node-1'].update(admissionRetries=71,admissionMillis=3,lastAdmission=[base])
        self.assertIsNone(self.report(value))


class CleanupReportTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.clean=dict(status='PASS',resourceDeletesSubmitted=13,result=dict(status='PASS',leaseReleased=True,
            cleanup=dict(status='PASS',leftovers=[],errors=[])),private='never-public')
    def report(self,value):
        (self.root/'cleanup.json').write_bytes(o.encoded(value));return o.cleanup_report(self.root)
    def test_pass_failed_and_not_acquired_have_distinct_closed_fields(self):
        self.assertEqual(dict(status='PASS',leaseReleased=True,resourceDeletesSubmitted=13),self.report(self.clean))
        self.assertEqual(dict(status='FAIL',leaseReleased=False,resourceDeletesSubmitted=2),self.report(dict(
            status='FAIL',resourceDeletesSubmitted=2,result=dict(status='FAIL',leaseReleased=False),private='never-public')))
        self.assertEqual(dict(status='NOT_ACQUIRED',resourceDeletesSubmitted=0),self.report(dict(
            status='NOT_ACQUIRED',resourceDeletesSubmitted=0,result=None)))
    def test_incomplete_changed_or_linked_cleanup_cannot_claim_pass(self):
        self.assertIsNone(o.cleanup_report(self.root))
        changes=[lambda v:v.update(resourceDeletesSubmitted=True),lambda v:v.update(status='PRIVATE'),
                 lambda v:v.update(result=None),lambda v:v['result'].update(status='FAIL'),
                 lambda v:v['result'].update(leaseReleased=False),lambda v:v['result']['cleanup'].update(status='FAIL'),
                 lambda v:v['result']['cleanup'].update(leftovers=['resource']),
                 lambda v:v['result']['cleanup'].update(errors=['never-public'])]
        for change in changes:
            value=deepcopy(self.clean);change(value);self.assertIsNone(self.report(value))
        (self.root/'cleanup.json').write_text('not json');self.assertIsNone(o.cleanup_report(self.root))
        (self.root/'cleanup.json').unlink();(self.root/'cleanup.json').symlink_to(self.root/'elsewhere')
        o.artifacts.save(self.root/'elsewhere',self.clean);self.assertIsNone(o.cleanup_report(self.root))
    def test_late_cleanup_failure_overrides_an_earlier_pass(self):
        self.report(self.clean);o.artifacts.save(self.root/'cleanup-failure.json',dict(private='never-public'))
        self.assertEqual(dict(status='FAIL'),o.cleanup_report(self.root))


class SecretLifetimeTest(unittest.TestCase):
    def test_cli_trimmed_secret_keeps_same_key_for_prepare_and_run(self):
        # gh secret set v2.101.0 reads stdin then bytes.TrimRight(body, "\r\n").
        for comment in ('', 'gse-v52-experiment operator comment'):
            with self.subTest(comment=comment),tempfile.TemporaryDirectory() as directory:
                original=Path(directory)/'original'
                subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C',comment,'-f',str(original)],check=True,timeout=10)
                data=original.read_bytes();secret=data.rstrip(b'\r\n').decode('ascii')
                expected=' '.join(Path(str(original)+'.pub').read_text().split()[:2])
                descriptor=o.access.descriptor('a'*32,expected)
                for operation in ('prepare','run'):
                    with self.subTest(operation=operation),patch.dict(os.environ,{'V52_SSH_KEY':secret}):
                        with o.private_key() as (path,public):
                            self.assertEqual(data,path.read_bytes())
                            self.assertEqual(expected,public)
                            self.assertEqual(0,path.stat().st_mode&0o077)
                            self.assertEqual(0,path.parent.stat().st_mode&0o077)
                            self.assertNotIn('V52_SSH_KEY',os.environ)
                            o.access.check_private_key(path,descriptor)
                        self.assertFalse(path.exists());self.assertFalse(path.parent.exists())
    def test_invalid_secret_or_normalized_size_overflow_fails_before_keygen(self):
        header='-----BEGIN OPENSSH PRIVATE KEY-----\n'
        cases=(None,'',header+'x'*(4096-len(header)),header+'x'*4096,' '+header,
               header.replace('\n','\r\n'),header+'\udcff')
        for secret in cases:
            env={} if secret is None else {'V52_SSH_KEY':secret}
            with self.subTest(length=None if secret is None else len(secret)),patch.dict(os.environ,env,clear=True), \
                 patch.object(o.access,'private_public_key') as keygen:
                with self.assertRaises(o.access.PrivateKeyError) as error:
                    with o.private_key():self.fail('invalid secret accepted')
                self.assertEqual('V52_SSH_SECRET_INVALID',error.exception.code)
                keygen.assert_not_called();self.assertNotIn('V52_SSH_KEY',os.environ)
    def test_corrupt_or_truncated_secret_is_not_repaired_and_private_directory_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','','-f',str(original)],check=True,timeout=10)
            data=original.read_text();made=[];real_temp=tempfile.TemporaryDirectory
            def tracked_temp(**kwargs):
                temp=real_temp(**kwargs);made.append(Path(temp.name));return temp
            bad=(data.replace('-----END OPENSSH PRIVATE KEY-----',''),
                 data.replace(data.splitlines()[1],'!invalid-body!').rstrip('\n'))
            for secret in bad:
                with patch.dict(os.environ,{'V52_SSH_KEY':secret}),patch.object(o.tempfile,'TemporaryDirectory',tracked_temp):
                    with self.assertRaises(o.access.PrivateKeyError) as error:
                        with o.private_key():self.fail('damaged secret accepted')
                    self.assertEqual('V52_SSH_KEY_UNREADABLE',error.exception.code)
                    self.assertNotIn('V52_SSH_KEY',os.environ)
            self.assertEqual(2,len(made));self.assertTrue(all(not path.exists() for path in made))
    def test_actual_key_is_private_removed_and_not_inherited_by_children(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','','-f',str(original)],check=True,timeout=10)
            with patch.dict(os.environ,{'V52_SSH_KEY':original.read_text()}):
                with o.private_key() as (path,public):
                    self.assertEqual(0,path.stat().st_mode&0o077);self.assertNotIn('V52_SSH_KEY',os.environ)
                    o.access.check_private_key(path,o.access.descriptor('a'*32,public))
                self.assertFalse(path.exists())
    def test_commented_key_is_canonical_in_prepare_and_matches_again_for_run(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','gse-v52-experiment operator comment',
                            '-f',str(original)],check=True,timeout=10)
            expected=' '.join(Path(str(original)+'.pub').read_text().split()[:2])
            # Preparation derives the public key from the actual secret.
            with patch.dict(os.environ,{'V52_SSH_KEY':original.read_text()}):
                with o.private_key() as (path,public):
                    self.assertEqual(expected,public)
                    descriptor=o.access.descriptor('a'*32,public)
                    self.assertNotIn('operator comment',str(descriptor))
                    self.assertNotIn('V52_SSH_KEY',os.environ)
                self.assertFalse(path.exists())
            # A later run/IAP open checks the same commented private key again.
            o.access.check_private_key(original,descriptor)
    def test_encrypted_secret_fails_without_prompt_or_keygen_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','test-only-passphrase','-C','never-public-comment',
                            '-f',str(original)],check=True,timeout=10)
            for secret in (original.read_text(),original.read_text().rstrip('\r\n')):
                with patch.dict(os.environ,{'V52_SSH_KEY':secret}):
                    with self.assertRaisesRegex(ValueError,'private SSH key could not be read') as error:
                        with o.private_key():self.fail('encrypted secret accepted')
                    self.assertEqual('V52_SSH_KEY_UNREADABLE',error.exception.code)
                    self.assertNotIn('V52_SSH_KEY',os.environ)
                    self.assertNotIn('never-public',str(error.exception))
    def test_bad_secret_cannot_be_logged_or_left_in_environment(self):
        with patch.dict(os.environ,{'V52_SSH_KEY':'invalid-secret'}):
            with self.assertRaisesRegex(ValueError,'missing/invalid') as error:
                with o.private_key():self.fail('bad key accepted')
            self.assertNotIn('invalid-secret',str(error.exception));self.assertNotIn('V52_SSH_KEY',os.environ)


if __name__=='__main__':unittest.main()
