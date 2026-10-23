"""Actual native factory with external source, GitHub and provider I/O mocked.

Synthetic archive/JAR bytes are parsed, never executed or called cloud evidence.
"""
from copy import deepcopy
from pathlib import Path
import threading
import unittest
from unittest.mock import patch, Mock
import tempfile
from . import cloud_native_runner as n, cloud_prepared as prepared, cloud_access as access
from . import cloud_artifacts as artifacts, cloud_recent_cleanup as recent, cloud_inputs as inputs
from . import cloud_credentials as credentials, cloud_credentials_offline as auth
from . import test_cloud_native_cleanup as native_test
from .test_cloud_artifacts import ArtifactFixture
from .test_cloud_recent_cleanup import FixtureCleanup,evidence,NOW
from .test_cloud_inputs import binding,roots
from .test_cloud_identity import public_key
from .evidence import encoded,strict,digest

SOURCE='a'*40


class NativeRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cleanup_cfg,cls.cleanup_files=evidence()

    def setUp(self):
        self.case=native_test.NativeCleanupTest('test_empty_control_pass_is_observation_only_and_does_not_certify_delete_path')
        self.case.setUp();self.addCleanup(self.case.doCleanups);self.root=self.case.root;self.cfg=self.case.cfg
        self.case.role='runner';self.case.make();self.case.clock.now=100
        self.case.env['GITHUB_RUN_ID']='654321'
        bound=credentials.identity(self.cfg['provider'],self.cfg['projectNumber'],self.case.env,role='runner',source=SOURCE,checkout=SOURCE)
        self.case.env,self.case.descriptor=auth.issuer.inputs(bound,self.case.env)
        self.case.invocation=auth.Invocation(bound,self.case.clock);self.case.issuer=auth.issuer.Issuer(bound,self.case.clock)
        n.os.environ.clear();n.os.environ.update(self.case.env)
        self.shape=n.ci.contract();self.git=ArtifactFixture(self.shape,self.root);self.clean=FixtureCleanup(self.cleanup_files)
        self.stack=self.case.stack
        self.sdk=self.stack.enter_context(patch.object(n.cloud_sdk_runtime,'check',return_value=dict(
            schema='gse-v52-sdk-runtime-v1',status='PASS',pythonVersion='3.11.17',sdkVersion='1.0.0',
            credentialEnvironmentInherited=False,cloudOperationExecuted=False)))
        self.stack.enter_context(patch.object(inputs,'checkout',return_value=binding()))
        self.stack.enter_context(patch.object(artifacts.Network,'get',new=lambda client,path:self.github(path)))
        self.network_download=artifacts.Network.download
        self.stack.enter_context(patch.object(artifacts.Network,'download',new=lambda client,identity,out,size:self.download(identity,out,size)))
        raw,candidate=inputs.build_files(self.root/'shared',binding(),roots())
        controls=(inputs.suite.PLAN.parent/'published-controls.json').read_bytes()
        published={name:('synthetic-'+name).encode() for name in inputs.CONTROL_NAMES};pins={name:digest(raw) for name,raw in published.items()}
        self.stack.enter_context(patch.object(inputs,'controls',return_value=(controls,pins)))
        payload=inputs.payload(binding(),raw,controls,candidate,published);meta=inputs.manifest(binding(),raw,controls,payload)
        self.package=self.root/'input.tar.gz';inputs.pack(self.package,meta,payload)
        proof=inputs.verify_archive(self.package,binding(),raw,controls,candidate,pins)
        quote=dict(schema='gse-v52-operator-estimate-v1',currency='USD',configurationSha256=n.p.config(self.cfg['provider']),
            layoutSha256=digest(encoded(self.cfg['layout'])),createdAt=NOW-100,expiresAt=NOW+10000,coverageSeconds=14400,
            costMicrousd=4_000_000,includes=list(prepared.INCLUDES),priceSources=['https://cloud.google.com/compute/all-pricing'])
        self.arguments=dict(configuration=self.cfg['provider'],project_number=self.cfg['projectNumber'],proof=proof,
            guest_access=access.descriptor('b'*32,public_key()),resource_layout=self.cfg['layout'],ownership_policy=self.cfg['policy'],
            original_ledger=None,quote=quote,source=SOURCE,sequence='c'*32,member='canonical-3-legacy',now=NOW,domain='native')
        self.prepare();self.count=0;self.clients=[];original=n.NativeRunnerApi.__init__
        def capture(api,*args):original(api,*args);self.clients.append(api)
        self.stack.enter_context(patch.object(n.NativeRunnerApi,'__init__',new=capture))
        self.on_download=lambda identity:None;self.on_github=lambda path:None

    def prepare(self):
        self.plan=prepared.prepare(**self.arguments);self.approval=prepared.approval_template(self.plan);self.approval['confirmed']=True
        self.confirmation=prepared.validate(self.plan,NOW);self.write_plan()

    def write_plan(self):
        self.plan_path=self.root/'prepared.json';self.plan_path.write_bytes(encoded(self.plan))
        self.approval_path=self.root/'approval.json';self.approval_path.write_bytes(encoded(self.approval))

    def github(self,path):
        self.on_github(path)
        if 'v52-manual-cleanup' in path or '/123456' in path or '/901' in path:return self.clean.get(path)
        return self.git.get(path)

    def download(self,identity,out,size):
        self.on_download(identity);return (self.git if identity==501 else self.clean).download(identity,out,size)

    def open(self,**kwargs):
        self.count+=1;self.output=self.root/f'run-{self.count}'
        result=n.open_native(SOURCE,self.plan_path,self.approval_path,self.confirmation,self.package,self.output,**kwargs)
        self.addCleanup(result.close);return result

    def state(self):return n.a.inspect_ledger(self.case.get(n.a.LEDGER),domain='native')
    def mutations(self):return self.case.mutations()

    def test_valid_preflight_token_is_reused_without_a_second_exchange(self):
        def fail_second_exchange(method,url,body):
            if self.clients:self.case.issuer.fail='oidc'
        self.case.change=fail_second_exchange
        with self.open() as session:
            self.assertEqual(1,session.reader.tokens.exchanges)
            self.assertLessEqual(session.api.expires,session.reader.token.usable_until)
            self.assertLessEqual(session.api.expires,self.case.clock.seconds()+2400)
        self.assertEqual({},self.case.server.resources)

    def test_successful_build_admits_resources_without_waiting_for_full_ci(self):
        self.git.run.update(status='in_progress',conclusion=None);self.git.install()
        with self.open() as session:
            self.assertTrue(session.result['resourceAdmission'])
            self.assertEqual(13,len(self.case.server.resources))
            self.assertFalse(session.api.admission.build['ci']['fullCiRequired'])
        self.assertEqual({},self.case.server.resources);self.assertIsNone(self.case.get(n.a.LEASE))

    def test_standalone_build_admits_and_cleans_mock_resources_without_ci(self):
        self.git.use_standalone()
        with self.open() as session:
            self.assertTrue(session.result['resourceAdmission'])
            self.assertEqual(13,len(self.case.server.resources))
            self.assertEqual(n.ci.standalone.WORKFLOW,session.api.admission.build['ci']['workflow'])
        self.assertEqual({},self.case.server.resources);self.assertIsNone(self.case.get(n.a.LEASE))

    def test_real_download_publication_and_native_provenance_pass_retention_framing(self):
        from . import cloud_retention as retention,cloud_evidence_parts as parts
        def download(command,path,maximum,timeout):
            identity=int(command[-1].split('/')[-2]); self.download(identity,path,maximum)
        with patch.object(artifacts.Network,'download',new=self.network_download), \
             patch.object(artifacts,'bounded_command',side_effect=download):
            with self.open() as session:
                files=retention.provenance_files(session.output,session.package)
                manifest=parts.scan(files,session.owner.request)
                chunks=dict(parts.chunks(files,manifest))
                restored=parts.restore(manifest,session.owner.request,chunks.__getitem__,self.root/'restored')
                self.assertEqual(18,len(files))
                for name,path in files.items():self.assertEqual(path.read_bytes(),(restored/name).read_bytes())
                for folder in ('build-provenance','recent-cleanup'):
                    response=session.output/folder/'requests/001.zip'
                    self.assertEqual(1,response.stat().st_nlink)
        self.assertEqual({},self.case.server.resources); self.assertIsNone(self.case.get(n.a.LEASE))

    def test_hardlinked_build_or_cleanup_fails_before_provider_lease_ledger_and_resources(self):
        for linked in (501,901):
            def download(client,identity,path,size):
                self.download(identity,path,size)
                if identity==linked:n.os.link(path,Path(path).with_suffix('.alias'))
            with self.subTest(identity=linked),patch.object(artifacts.Network,'download',new=download):
                with self.assertRaisesRegex(ValueError,'original regular file'):self.open()
                report=strict((self.output/'failure.json').read_bytes())
                self.assertEqual('retention-readiness',report['phase'])
                self.assertEqual('V52_RUNNER_RETENTION_READINESS_REJECTED',report['code'])
                self.assertFalse(report['fullRemoteQualification'])
                self.assertEqual([],self.case.calls); self.assertEqual([],self.clients)
                self.assertEqual({},self.case.server.resources); self.assertEqual([],self.mutations())
                self.assertIsNone(self.case.get(n.a.LEASE)); self.assertIsNone(self.case.get(n.a.LEDGER))

    def test_provider_credential_failure_retains_closed_diagnostics_before_any_write(self):
        self.case.issuer.fail='sts'
        with self.assertRaises(credentials.exchange.CredentialError):self.open()
        report=strict((self.output/'failure.json').read_bytes())
        self.assertEqual('provider',report['phase'])
        self.assertEqual('STS_EXCHANGE_FAILED',report['credentialCode'])
        self.assertEqual('http',report['credentialFailureKind'])
        self.assertEqual(403,report['credentialHttpStatus'])
        self.assertEqual([],self.mutations());self.assertIsNone(self.case.get(n.a.LEDGER))
        self.assertNotIn(auth.issuer.SUBJECT_SECRET,str(report))

    def test_expired_preflight_token_refresh_failure_is_retained_without_acquisition(self):
        original=n.NativeRunnerApi.__init__
        def expire(api,reader,*args):
            reader.token=n.h.AccessToken(reader.token.value,self.case.clock.seconds())
            self.case.issuer.fail='impersonation'
            original(api,reader,*args)
        with patch.object(n.NativeRunnerApi,'__init__',new=expire),self.assertRaises(credentials.exchange.CredentialError):self.open()
        report=strict((self.output/'failure.json').read_bytes())
        self.assertEqual('resources',report['phase'])
        self.assertEqual('IMPERSONATION_EXCHANGE_FAILED',report['credentialCode'])
        self.assertEqual(403,report['credentialHttpStatus'])
        self.assertEqual('NOT_ACQUIRED',strict((self.output/'cleanup.json').read_bytes())['status'])
        self.assertEqual([],self.mutations());self.assertIsNone(self.case.get(n.a.LEDGER))

    def test_cached_token_get_401_refreshes_once_before_acquisition(self):
        rejected=False
        def reject(stage,row):
            nonlocal rejected
            if stage=='before' and row['method']=='GET' and not rejected:
                rejected=True;return 401,b'private-provider-body'
        self.case.server.fault=reject
        with self.open() as session:self.assertEqual(2,session.reader.tokens.exchanges)
        self.assertTrue(rejected);self.assertEqual({},self.case.server.resources)

    def test_complete_native_factory_original_inputs_resources_and_final_cleanup(self):
        with self.open() as session:
            self.sdk.assert_called_once_with()
            self.assertEqual('RESOURCES_PREPARED_NOT_QUALIFIED',session.result['status'])
            self.assertFalse(session.result['fullRemoteQualification']);self.assertFalse(session.result['engineWorkloadExecuted'])
            self.assertTrue(session.result['resourceAdmission']);self.assertEqual(13,len(self.case.server.resources))
            self.assertEqual('canonical-3-legacy',session.owner.request['selection']['member']['name'])
            self.assertEqual(self.package.read_bytes(),session.package.read_bytes());session.checkpoint()
        self.assertEqual({},self.case.server.resources);self.assertIsNone(self.case.get(n.a.LEASE))
        self.assertEqual(4_000_000,self.state()['reservedCostMicrousd'])
        self.assertEqual({'FAIL'},{row['status'] for row in self.state()['attempts'].values()})
        self.assertTrue(session.reader.closed);self.assertTrue(session.api.closed);self.assertTrue(session.reader.tokens.closed)
        self.assertFalse(session.heartbeat.thread.is_alive());self.assertTrue(session.log.closed)
        self.assertEqual(13,strict((self.output/'cleanup.json').read_bytes())['resourceDeletesSubmitted'])

    def test_sdk_startup_failure_precedes_build_provider_lease_and_ledger(self):
        self.sdk.side_effect=n.cloud_sdk_runtime.SdkError('PYTHON_START_FAILED')
        with self.assertRaises(n.cloud_sdk_runtime.SdkError):self.open()
        self.sdk.assert_called_once_with()
        self.assertEqual([],self.git.calls);self.assertEqual([],self.case.calls)
        self.assertEqual([],self.mutations());self.assertEqual({},self.case.server.resources)
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertIsNone(self.case.get(n.a.LEDGER))
        report=strict((self.output/'failure.json').read_bytes())
        self.assertEqual('sdk-runtime',report['phase']);self.assertEqual('V52_SDK_PYTHON_START_FAILED',report['sdkCode'])
        self.assertFalse((self.output/'sdk-runtime.json').exists())

    def test_wrong_operator_approval_and_package_bytes_cannot_write(self):
        self.approval['confirmed']=False;self.write_plan()
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations());self.assertFalse((self.output/'resources.json').exists())
        self.approval['confirmed']=True;self.write_plan();self.package.write_bytes(b'not an input archive')
        with self.assertRaises(Exception):self.open()
        self.assertEqual([],self.mutations())

    def test_failed_build_or_latest_cleanup_cannot_write(self):
        self.git.current['conclusion']='failure';self.git.install()
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations());self.assertEqual([],self.case.calls)
        self.git.current['conclusion']='success';self.git.install();self.clean.data['actions/runs/123456']['conclusion']='failure'
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations());self.assertEqual([],self.case.calls)

    def test_missing_permission_or_active_lease_cannot_acquire(self):
        key='projectPermissions';original=self.case.observations.rows[key]
        self.case.observations.rows[key]={'permissions':[]}
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations());self.case.observations.rows[key]=original
        self.case.put(n.a.LEASE,n.a.lease(self.plan['request'],NOW))
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations())

    def test_source_policy_and_layout_are_bound_even_if_operator_approves_other_values(self):
        self.arguments['resource_layout']=dict(self.cfg['layout'],dataDiskGiB=101)
        self.arguments['quote']=dict(self.arguments['quote'],layoutSha256=digest(encoded(self.arguments['resource_layout'])))
        self.prepare()
        with self.assertRaisesRegex(ValueError,'layout/policy'):self.open()
        self.assertEqual([],self.mutations())

    def test_same_ledger_value_in_new_generation_is_not_the_approved_baseline(self):
        self.case.put(n.a.LEDGER,n.a.empty_ledger(domain='native'))
        with self.assertRaisesRegex(ValueError,'lease/ledger changed'):self.open()
        self.assertEqual([],self.mutations())

    def test_ledger_generation_change_during_context_token_refresh_stops_first_write(self):
        changed=False
        def change(method,url,body):
            nonlocal changed
            if self.clients and not changed and 'iamcredentials.googleapis.com' in url:
                changed=True;self.case.put(n.a.LEDGER,n.a.empty_ledger(domain='native'))
        self.case.change=change
        original=n.NativeRunnerApi.__init__
        def expire(api,*args):original(api,*args);api.expires=0
        with patch.object(n.NativeRunnerApi,'__init__',new=expire),self.assertRaisesRegex(ValueError,'ledger generation'):self.open()
        self.assertTrue(changed)
        self.assertEqual([],self.mutations());self.assertIsNone(self.case.get(n.a.LEASE))

    def test_expired_approval_after_lease_acquisition_cleans_without_rechecking_admission(self):
        self.arguments['quote']['expiresAt']=NOW+1;self.prepare()
        def change(stage,row):
            if stage=='after' and row['method']=='POST' and strict(row['body']).get('phase')=='ACQUIRING':
                self.case.clock.now+=1
        self.case.server.fault=change
        with self.assertRaises(ValueError):self.open()
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)
        self.assertIsNone(self.case.get(n.a.LEDGER));self.assertEqual('PASS',strict((self.output/'cleanup.json').read_bytes())['status'])

    def test_submission_retention_failure_records_charge_and_cleans_partial_resources(self):
        def change(stage,row):
            if stage=='before' and row['method']=='POST':
                value=strict(row['body'])
                if value.get('schema')=='gse-v52-provider-submission-v2' and value['spec']['purpose']=='iap':
                    return 403,b'never print this provider secret'
        self.case.server.fault=change
        with self.assertRaises(n.h.ApiError):self.open()
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)
        self.assertEqual(4_000_000,self.state()['reservedCostMicrousd'])
        self.assertNotIn('never print',str(list(self.output.glob('*.json')))+''.join(p.read_text() for p in self.output.glob('*.json')))
        self.assertEqual('V52_RUNNER_RESOURCES_REJECTED',strict((self.output/'failure.json').read_bytes())['code'])

    def test_workload_exception_is_preserved_and_cleanup_runs(self):
        with self.assertRaisesRegex(RuntimeError,'original failure'):
            with self.open():raise RuntimeError('original failure')
        self.assertEqual({},self.case.server.resources);self.assertIsNone(self.case.get(n.a.LEASE))
        self.assertEqual('PASS',strict((self.output/'cleanup.json').read_bytes())['status'])

    def test_failed_context_entry_cleans_and_double_close_cannot_reacquire(self):
        session=self.open()
        with patch.object(session,'checkpoint',side_effect=ValueError('entry fenced')):
            with self.assertRaisesRegex(ValueError,'entry fenced'):
                with session:self.fail('body must not run')
        self.assertTrue(session.closed);self.assertFalse(session.heartbeat.thread.is_alive())
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)
        count=len(self.mutations());session.close()
        self.assertEqual(count,len(self.mutations()))
        with self.assertRaises(ValueError):session.checkpoint()
        with self.assertRaises(ValueError):session.owner.acquire(previous_cost=4_000_000,cost=4_000_000)

    def test_native_adapters_and_request_cannot_enter_offline_or_cleanup_owner(self):
        with self.open() as session:
            with self.assertRaises(ValueError):n.c.OfflineOwner(session.owner.store,session.owner.provider,session.owner.request)
            with self.assertRaises(ValueError):n.NativeOwner(session.owner.store,session.owner.provider,session.owner.request,object())
            with self.assertRaises(ValueError):n.cleanup.NativeCleanupApi(session.reader,{},session.log,n.cleanup._CAPABILITY)
            session.api.policy.role='cleanup'
            try:
                with self.assertRaises(ValueError):session.owner.store.get(n.a.LEASE)
            finally:session.api.policy.role='runner'

    def test_factory_requires_original_confirmation_before_any_remote_observation(self):
        self.confirmation='f'*64
        with self.assertRaisesRegex(ValueError,'operator approval'):self.open()
        self.assertEqual([],self.git.calls);self.assertEqual([],self.clean.calls);self.assertEqual([],self.case.calls)

    def test_control_baseline_is_checked_again_between_context_and_lease(self):
        def change(stage,row):
            if stage=='after' and row['method']=='POST' and strict(row['body']).get('schema')=='gse-v52-provider-context-v1':
                self.case.put(n.a.LEDGER,n.a.empty_ledger(domain='native'))
        self.case.server.fault=change
        with self.assertRaisesRegex(ValueError,'ledger generation'):self.open()
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)
        self.assertEqual(1,len(self.mutations()))

    def test_approval_and_cost_are_not_reapplied_during_an_existing_resource_lifetime(self):
        with self.open() as session:
            self.case.clock.now+=800;session.owner.renew();original=session.checkpoint()
            self.case.clock.now+=800;session.owner.renew()
            self.assertEqual(original,session.checkpoint())
            self.assertEqual(4_000_000,self.state()['reservedCostMicrousd'])
            self.assertEqual('ACTIVE',session.api.admission.state)
            with self.assertRaises(ValueError):session.api.admission.check()  # Admission is stale, owner is not.

    def test_renewal_failure_fails_next_checkpoint_and_stops_the_thread(self):
        with self.open() as session:
            session.heartbeat.close();session.owner.heartbeat=None
            beat=n._Heartbeat(session.owner);beat.interval=.001;session.owner.heartbeat=beat
            session.heartbeat=beat
            with patch.object(session.owner,'renew',side_effect=RuntimeError('sensitive failure')):
                beat.start();self.assertTrue(beat.stop.wait(2));beat.close()
            self.assertEqual('RuntimeError',beat.failure)
            with self.assertRaisesRegex(ValueError,'renewal failed'):session.checkpoint()
        self.assertIsNone(self.case.get(n.a.LEASE))

    def test_live_renewal_is_owned_and_stopped_before_cleanup(self):
        with self.open() as session:
            session.heartbeat.close();session.owner.heartbeat=None;beat=n._Heartbeat(session.owner);beat.interval=.001
            session.heartbeat=beat;session.owner.heartbeat=beat;done=threading.Event();original=session.owner.renew
            self.case.clock.now+=1
            def renew():
                result=original();done.set();beat.stop.set();return result
            with patch.object(session.owner,'renew',side_effect=renew):
                beat.start();self.assertTrue(done.wait(10));beat.close()
            self.assertEqual(NOW+1,session.owner.lease['renewedAt']);self.assertIsNone(beat.failure)
        self.assertFalse(beat.thread.is_alive());self.assertIsNone(self.case.get(n.a.LEASE))

    def test_native_api_cannot_rebind_its_validated_request_to_another_member(self):
        with self.open() as session:
            saved=deepcopy(session.api.policy.req);session.api.policy.req['createdAt']+=1
            try:
                with self.assertRaisesRegex(ValueError,'adapter changed'):session.owner.store.get(n.a.LEASE)
            finally:session.api.policy.req=saved

    def test_resource_failure_and_cleanup_failure_retain_original_lease_and_diagnostics(self):
        def change(stage,row):
            if stage!='before' or 'compute.googleapis.com' not in row['url']:return
            if row['method']=='DELETE' or row['method']=='POST' and strict(row['body'])['name'].endswith('-iap'):
                return 403,b'do not retain provider detail'
        self.case.server.fault=change
        with self.assertRaises(n.h.ApiError):self.open()
        self.assertIsNotNone(self.case.get(n.a.LEASE));self.assertTrue(self.case.server.resources)
        self.assertEqual('FAIL',strict((self.output/'cleanup.json').read_bytes())['status'])
        self.assertTrue((self.output/'cleanup-failure.json').exists());self.assertEqual(4_000_000,self.state()['reservedCostMicrousd'])

    def test_lost_original_acquisition_ack_is_observed_without_resubmission(self):
        lost=False
        def change(stage,row):
            nonlocal lost
            if row['method']!='POST':return
            value=strict(row['body'])
            if stage=='after' and not lost and value.get('phase')=='ACQUIRING':
                lost=True;raise ConnectionError('lost acquisition reply')
            if stage=='before' and value.get('schema')=='gse-v52-provider-submission-v2':return 403,b''
        self.case.server.fault=change
        with self.assertRaises(n.h.ApiError):self.open()
        self.assertTrue(lost);self.assertIsNone(self.case.get(n.a.LEASE))
        acquisition=[row for row in self.mutations() if row['method']=='POST' and strict(row['body']).get('phase')=='ACQUIRING']
        self.assertEqual(1,len(acquisition));self.assertEqual(4_000_000,self.state()['reservedCostMicrousd'])

    def test_source_or_exact_workflow_run_change_cannot_reach_native_write(self):
        self.case.invocation.change=lambda count,row:dict(row,run_attempt=3) if count>3 else row
        with self.assertRaises(Exception):self.open()
        self.assertEqual([],self.mutations());self.assertFalse((self.output/'resources.json').exists())

    def test_cleanup_observation_is_fresh_again_after_build_download_delay(self):
        def delay(identity):
            if identity==901:self.case.clock.now+=901
        self.on_download=delay
        with self.assertRaises(ValueError):self.open()
        self.assertEqual([],self.mutations());self.assertIsNone(self.case.get(n.a.LEASE))

    def test_approved_cost_above_soft_budget_is_recorded_and_not_silently_blocked(self):
        self.arguments['quote']['costMicrousd']=300_000_000;self.prepare()
        self.assertTrue(self.plan['warnings']['exceeded'])
        def deny_marker(stage,row):
            if stage=='before' and row['method']=='POST' and strict(row['body']).get('schema')=='gse-v52-provider-submission-v2':
                return 403,b''
        self.case.server.fault=deny_marker
        with self.assertRaises(n.h.ApiError):self.open()
        self.assertEqual(300_000_000,self.state()['reservedCostMicrousd'])
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)

    def test_result_and_failure_diagnostic_write_failures_do_not_bypass_cleanup(self):
        original=artifacts.save
        def save(path,value):
            if Path(path).name in ('resources.json','failure.json'):raise OSError('synthetic disk full')
            return original(path,value)
        with patch.object(artifacts,'save',side_effect=save):
            with self.assertRaises(OSError):self.open()
        self.assertIsNone(self.case.get(n.a.LEASE));self.assertEqual({},self.case.server.resources)
        self.assertEqual('PASS',strict((self.output/'cleanup.json').read_bytes())['status'])
        self.assertTrue(self.clients[-1].closed);self.assertTrue(self.clients[-1].reader.tokens.closed)


class SessionLifecycleTest(unittest.TestCase):
    def test_failed_entry_closes_before_propagating_original_error(self):
        session=object.__new__(n.Session);error=ValueError('original entry failure')
        session.checkpoint=Mock(side_effect=error);session.close=Mock()
        with self.assertRaises(ValueError) as raised:
            with session:self.fail('body must not run')
        self.assertIs(error,raised.exception);session.close.assert_called_once_with()

    def test_failed_entry_preserves_original_error_if_cleanup_also_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            session=object.__new__(n.Session);session.output=Path(directory);error=ValueError('original entry failure')
            session.checkpoint=Mock(side_effect=error);session.close=Mock(side_effect=RuntimeError('sensitive cleanup detail'))
            with self.assertRaises(ValueError) as raised:
                with session:self.fail('body must not run')
            self.assertIs(error,raised.exception)
            self.assertEqual(dict(status='FAIL',errorType='RuntimeError'),strict((session.output/'cleanup-failure.json').read_bytes()))

    def test_missing_diagnostic_storage_does_not_mask_original_error(self):
        session=object.__new__(n.Session);session.output=Path('/unused');error=ValueError('original entry failure')
        session.checkpoint=Mock(side_effect=error);session.close=Mock(side_effect=RuntimeError('cleanup failed'))
        with patch.object(artifacts,'save',side_effect=OSError('disk full')):
            with self.assertRaises(ValueError) as raised:
                with session:self.fail('body must not run')
        self.assertIs(error,raised.exception);session.close.assert_called_once_with()


if __name__=='__main__':unittest.main()
