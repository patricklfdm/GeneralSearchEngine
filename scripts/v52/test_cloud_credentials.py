from copy import deepcopy
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import traceback
import unittest
from unittest.mock import Mock, patch
from scripts.v51 import cloud_cleanup_auth_fake as fake, cloud_cleanup_credentials as exchange, cloud_http as http
from . import cloud_credentials as c, cloud_credentials_offline as offline, cloud_provider as provider
from .test_cloud_provider import configuration


class CredentialTest(unittest.TestCase):
    def setUp(self):
        self.cfg=configuration();self.source='a'*40
        self.project,self.env,self.value,self.invocation,self.issuer=offline.fixture(self.cfg)
        self.clock=self.invocation.clock
        # Every test fails if an unpatched path tries real network IO.
        self.no_network=patch.object(http.Network,'send',side_effect=AssertionError('network forbidden'))
        self.no_network.start();self.addCleanup(self.no_network.stop)

    def tokens(self,role='runner'):
        return c.OfflineCredentials(self.cfg,self.project,self.env,self.value,self.invocation,self.issuer,
            role=role,source=self.source,checkout_sha=self.source)

    def identity(self,**kwargs):
        return c.identity(self.cfg,self.project,self.env,role=kwargs.get('role','runner'),
            source=kwargs.get('source',self.source),checkout=kwargs.get('checkout',self.source))

    def assert_sanitized(self,value):
        for secret in (fake.SUBJECT_SECRET,fake.FEDERATED_SECRET,fake.ACCOUNT_SECRET,fake.OIDC,
                       getattr(self.issuer,'subject','secret-subject-not-created'), 'secret-exception'):
            self.assertNotIn(secret,value)

    def test_roles_select_dedicated_v52_workflows_identities_and_environment(self):
        identities=[]
        for role in c.ROLES:
            project,env,value,invocation,issuer=offline.fixture(self.cfg,role)
            token=c.OfflineCredentials(self.cfg,project,env,value,invocation,issuer,role=role,
                source=self.source,checkout_sha=self.source)
            result=token(30);self.assertIs(type(result),http.AccessToken)
            self.assertEqual(['oidc','sts','impersonation'],[x['stage'] for x in issuer.calls])
            identities.append((token.binding['provider'],token.binding['serviceAccount'],token.binding['environment']))
            self.assertIn('/gse-v52-',token.binding['provider']);self.assertNotIn('v51',json.dumps(token.receipt()))
            self.assertEqual('PASS',token.receipt()['status']);self.assertFalse(token.receipt()['paidAdmission'])
            self.assertFalse(token.receipt()['fullRemoteQualification'])
            self.assertEqual('offline-v52-credential-exchange',token.receipt()['execution'])
        self.assertEqual(3,len(set(identities)))

    def test_every_runtime_identity_field_is_required_and_exact(self):
        for field in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REPOSITORY_ID','GITHUB_REPOSITORY_OWNER_ID',
                      'GITHUB_EVENT_NAME','GITHUB_REF','GITHUB_WORKFLOW_REF','GITHUB_WORKFLOW_SHA',
                      'GITHUB_SHA','GITHUB_JOB','V52_CLOUD_ENVIRONMENT'):
            original=self.env[field]
            for value in (None,'foreign',True):
                with self.subTest(field=field,value=value):
                    self.env[field]=value
                    with self.assertRaisesRegex(c.ContextError,'RUNTIME_CONTEXT'):self.identity()
            self.env[field]=original
        self.assertEqual([],self.invocation.calls);self.assertEqual([],self.issuer.calls)

    def test_source_role_project_number_and_configuration_are_closed(self):
        for source in ('a'*39,'A'*40,False):
            with self.assertRaisesRegex(c.ContextError,'SOURCE'):self.identity(source=source)
        with self.assertRaisesRegex(c.ContextError,'SOURCE'):self.identity(checkout='b'*40)
        for role in ('cleanup','v51',None,[]):
            with self.assertRaisesRegex(c.ContextError,'ROLE'):self.identity(role=role)
        for number in ('0','01',12,True,'1/2'):
            with self.assertRaisesRegex(c.ContextError,'CONFIGURATION'):c.selection(self.cfg,number,'runner')
        changed=dict(self.cfg,serviceAccount='foreign')
        with self.assertRaisesRegex(c.ContextError,'CONFIGURATION'):c.selection(changed,self.project,'runner')

    def test_run_identity_is_positive_bounded_decimal(self):
        for field in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'):
            original=self.env[field]
            for value in ('0','01','-1','1/attempts/2','1'*21,1,True,None):
                with self.subTest(field=field,value=value):
                    self.env[field]=value
                    with self.assertRaisesRegex(c.ContextError,'RUN_IDENTITY'):self.identity()
            self.env[field]=original

    def test_run_reads_latest_exact_attempt_latest_and_binds_digest(self):
        tokens=self.tokens();tokens(30)
        self.assertEqual(['actions/runs/123456','actions/runs/123456/attempts/2','actions/runs/123456'],self.invocation.calls)
        receipt=tokens.receipt()['runObservation']
        self.assertEqual(64,len(receipt['observationSha256']));self.assertEqual(2,receipt['runAttempt'])
        self.assertEqual(self.source,receipt['source'])

    def test_each_observation_rejects_late_rerun_cancel_and_source_drift(self):
        for nth in (1,2,3):
            for change in (dict(run_attempt=3),dict(head_sha='b'*40),dict(status='completed',conclusion='cancelled')):
                with self.subTest(nth=nth,change=change):
                    self.invocation.calls.clear()
                    self.invocation.change=lambda number,value:dict(value,**change) if number==nth else value
                    tokens=self.tokens()
                    with self.assertRaisesRegex(c.ContextError,'RUN_OBSERVATION'):tokens(30)
                    self.assertEqual(nth,len(self.invocation.calls));self.assertEqual([],self.issuer.calls)
                    self.assertEqual(0,tokens.receipt()['completedExchanges'])

    def test_run_repository_event_workflow_and_numeric_identity_cannot_drift(self):
        original=deepcopy(self.invocation.value)
        for change in (dict(id=True),dict(run_attempt=True),dict(id=42),dict(head_branch='feature'),
                       dict(event='pull_request'),dict(path=c.ROLES['manual'][1]),dict(conclusion='success'),
                       dict(repository=None),dict(head_repository=dict(original['head_repository'],id=1)),
                       dict(repository=dict(original['repository'],owner=dict(id=True))),
                       dict(repository=dict(original['repository'],full_name='other/GeneralSearchEngine'))):
            with self.subTest(change=change):
                with self.assertRaisesRegex(c.ContextError,'RUN_OBSERVATION'):
                    c.check_run(self.identity(),dict(original,**change))

    def test_github_errors_are_sanitized_without_exchange_or_retry(self):
        def reject(*args):raise RuntimeError('secret-exception')
        self.invocation.change=reject;tokens=self.tokens()
        with self.assertRaisesRegex(c.ContextError,'RUN_OBSERVATION') as error:tokens(30)
        self.assert_sanitized(''.join(traceback.format_exception(error.exception)))
        self.assert_sanitized(json.dumps(tokens.receipt()));self.assertEqual(1,len(self.invocation.calls))
        self.assertEqual([],self.issuer.calls)

    def test_context_and_latest_attempt_are_rechecked_before_refresh(self):
        for drift in ('checkout','attempt','environment'):
            with self.subTest(drift=drift):
                project,env,value,invocation,issuer=offline.fixture(self.cfg)
                tokens=c.OfflineCredentials(self.cfg,project,env,value,invocation,issuer,role='runner',
                    source=self.source,checkout_sha=self.source)
                tokens(30)
                if drift=='checkout':invocation.source='b'*40
                elif drift=='attempt':invocation.value['run_attempt']=3
                else:tokens.env['V52_CLOUD_ENVIRONMENT']='other'
                with self.assertRaises(c.ContextError):tokens(30)
                self.assertEqual(3,len(issuer.calls));self.assertEqual(1,tokens.receipt()['completedExchanges'])

    def test_every_oidc_identity_claim_rejects_before_sts(self):
        for field in ('iss','aud','sub','repository','repository_id','repository_owner_id','ref','environment',
                      'event_name','workflow_ref','workflow_sha','sha','run_id','run_attempt'):
            with self.subTest(field=field):
                self.issuer.calls.clear();self.issuer.claim_changes={field:'foreign'};tokens=self.tokens()
                with self.assertRaisesRegex(exchange.CredentialError,'OIDC_CLAIMS_REJECTED'):tokens(30)
                self.assertEqual(['oidc'],[v['stage'] for v in self.issuer.calls])

    def test_oidc_lifetime_and_immutable_subject_reject(self):
        now=self.clock.wall()
        for changes in (dict(exp=now),dict(iat=now+31),dict(nbf=now+31),dict(exp=True),
                        dict(sub='repo:patricklfdm/GeneralSearchEngine:environment:v52-cloud-benchmark')):
            self.issuer.calls.clear();self.issuer.claim_changes=changes
            with self.assertRaisesRegex(exchange.CredentialError,'OIDC_CLAIMS_REJECTED'):self.tokens()(30)
            self.assertEqual(1,len(self.issuer.calls))

    def test_descriptor_cannot_select_v51_identity_adc_or_redirect_endpoint(self):
        original=deepcopy(self.value)
        changes=(('audience','//iam.googleapis.com/projects/1/locations/global/workloadIdentityPools/gse-v51-runner/providers/github'),
                 ('service_account_impersonation_url','https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/other:generateAccessToken'),
                 ('token_url','https://other/token'),('type','service_account'),('extra','secret-exception'))
        for key,value in changes:
            self.value=dict(original,**{key:value})
            with self.assertRaises(exchange.CredentialError) as error:self.tokens()
            self.assert_sanitized(str(error.exception))
        self.assertEqual([],self.issuer.calls);self.assertEqual([],self.invocation.calls)

    def test_opaque_runtime_route_preserved_and_source_header_query_rejected(self):
        original=deepcopy(self.value);tokens=self.tokens();tokens(30)
        self.assertIn('//idtoken/',original['credential_source']['url'])
        for field,value in (('url',original['credential_source']['url'].replace('/42//','/43//')),
                            ('url',original['credential_source']['url']+'&audience=extra'),
                            ('headers',{'Authorization':'Bearer foreign'}),('format',{'type':'text'})):
            self.value=deepcopy(original);self.value['credential_source'][field]=value
            with self.assertRaises(exchange.CredentialError):self.tokens()

    def test_exchange_stage_failure_has_closed_reason_no_retry_no_secret(self):
        for n,phase in enumerate(('oidc','sts','impersonation')):
            self.issuer.calls.clear();self.issuer.fail=phase;tokens=self.tokens()
            with self.assertRaises(exchange.CredentialError) as error:tokens(30)
            self.assertEqual(n+1,len(self.issuer.calls));self.assertEqual('FAIL',tokens.receipt()['status'])
            self.assertEqual(phase.upper()+'_EXCHANGE_FAILED',tokens.receipt()['reasonCode'])
            self.assert_sanitized(''.join(traceback.format_exception(error.exception))+json.dumps(tokens.receipt()))

    def test_native_exchange_failure_distinguishes_http_timeout_and_invalid_response(self):
        from contextlib import ExitStack
        cases=((403,b'private issuer error','http',403),
               (503,b'private issuer error','http',503),
               (200,b'private invalid JSON','response',None))
        for status,raw,kind,http_status in cases:
            with self.subTest(status=status),ExitStack() as stack:
                tokens=self.native(stack)[0]
                stack.enter_context(patch.object(tokens.transport,'send',return_value=(status,raw)))
                with self.assertRaises(exchange.CredentialError) as caught:tokens(30)
                report=c.failure(caught.exception)
                self.assertEqual('OIDC_EXCHANGE_FAILED',report['credentialCode'])
                self.assertEqual(kind,report['credentialFailureKind'])
                self.assertEqual(http_status,report.get('credentialHttpStatus'));self.assert_sanitized(str(report))
        with ExitStack() as stack:
            tokens=self.native(stack)[0]
            stack.enter_context(patch.object(tokens.transport,'send',side_effect=TimeoutError('private issuer timeout')))
            with self.assertRaises(exchange.CredentialError) as caught:tokens(30)
            self.assertEqual('timeout',c.failure(caught.exception)['credentialFailureKind'])

    def test_forged_or_mutated_credential_errors_cannot_export_private_fields(self):
        error=ValueError('private issuer');error.reason_code='STS_EXCHANGE_FAILED'
        self.assertEqual({},c.failure(error))
        error=exchange.CredentialError('STS_EXCHANGE_FAILED')
        error.failure_kind='private issuer';error.http_status=True
        self.assertEqual({'credentialCode':'STS_EXCHANGE_FAILED'},c.failure(error))
        error.reason_code='private issuer';self.assertEqual({},c.failure(error))

    def test_malformed_sts_or_impersonation_response_never_returns_token(self):
        for phase,change,code in (
            ('sts',dict(token_type='Basic'),'STS_RESPONSE_INVALID'),
            ('sts',dict(expires_in=True),'STS_RESPONSE_INVALID'),
            ('sts',dict(access_token='contains whitespace'),'STS_RESPONSE_INVALID'),
            ('impersonation',dict(accessToken=''),'IMPERSONATION_RESPONSE_INVALID'),
            ('impersonation',dict(expireTime='tomorrow'),'IMPERSONATION_RESPONSE_INVALID')):
            self.issuer.response_changes={phase:change};tokens=self.tokens()
            with self.assertRaisesRegex(exchange.CredentialError,code):tokens(30)
            self.assertEqual(0,tokens.receipt()['completedExchanges'])

    def test_token_lifetime_safety_margin_and_no_token_in_repr_or_receipt(self):
        tokens=self.tokens();token=tokens(30)
        self.assertEqual(self.clock.seconds()+3540,token.usable_until)
        self.assert_sanitized(repr(token)+json.dumps(tokens.receipt()))
        for lifetime in (0,60,3605.001):
            self.issuer.lifetime=lifetime
            with self.assertRaisesRegex(exchange.CredentialError,'IMPERSONATION_RESPONSE_INVALID'):tokens(30)

    def test_small_issuer_clock_skew_is_clamped_without_extending_usable_lifetime(self):
        tokens=self.tokens()
        for lifetime in (3600.001,3601.465,3605):
            self.issuer.lifetime=lifetime
            with self.subTest(lifetime=lifetime):
                token=tokens(30)
                self.assertEqual(self.clock.seconds()+3540,token.usable_until)
        self.issuer.lifetime=3605.001
        with self.assertRaises(exchange.CredentialError) as caught:tokens(30)
        self.assertEqual('lifetime',c.failure(caught.exception)['credentialFailureKind'])

    def test_original_deadline_covers_run_observation_and_entire_exchange(self):
        def delayed(number,value):self.clock.sleep(2);return value
        self.invocation.change=delayed;self.issuer.delay=2
        tokens=self.tokens();tokens(20)
        self.assertEqual([14,12,10],[x['timeout'] for x in self.issuer.calls])
        self.issuer.calls.clear();self.issuer.delay=8
        with self.assertRaisesRegex(exchange.CredentialError,'STS_EXCHANGE_FAILED'):tokens(20)
        self.assertEqual(['oidc','sts'],[x['stage'] for x in self.issuer.calls])
        self.assertEqual(2,tokens.receipt()['attempts']);self.assertEqual(1,tokens.receipt()['completedExchanges'])

    def test_observation_timeout_does_not_start_exchange_or_extend_budget(self):
        def delayed(number,value):self.clock.sleep(11);return value
        self.invocation.change=delayed;tokens=self.tokens()
        with self.assertRaisesRegex(c.ContextError,'DEADLINE'):tokens(30)
        self.assertEqual(3,len(self.invocation.calls));self.assertEqual([],self.issuer.calls)
        for timeout in (0,-1,31,True,float('nan'),float('inf'),'30'):
            with self.assertRaisesRegex(c.ContextError,'DEADLINE'):tokens(timeout)

    def test_lock_wait_counts_against_original_deadline(self):
        tokens=self.tokens()
        class DelayedLock:
            def acquire(inner,timeout):self.clock.sleep(29);return True
            def release(inner):pass
        tokens.lock=DelayedLock();self.issuer.delay=2
        with self.assertRaisesRegex(exchange.CredentialError,'OIDC_EXCHANGE_FAILED'):tokens(30)
        self.assertEqual(1,self.issuer.calls[0]['timeout'])
        self.assertLessEqual(len(self.issuer.calls),1)

    def test_refresh_revalidates_while_api_caches_and_only_get_401_retries(self):
        tokens=self.tokens()
        class Transport:
            offline=True
            def __init__(inner):inner.calls=0;inner.status=200
            def send(inner,method,url,headers,body,timeout,maximum):
                self.assertEqual('Bearer '+fake.ACCOUNT_SECRET,headers['Authorization'])
                inner.calls+=1;return inner.status,b'{}'
        transport=Transport();api=http.Api(transport=transport,tokens=tokens,clock=self.clock.seconds)
        def call(method='GET'):return api.call(method,'https://storage.googleapis.com/storage/v1/b/offline-evidence',deadline=self.clock.seconds()+30)
        call();call();self.assertEqual(1,tokens.exchanges)
        self.clock.sleep(2400);call();self.assertEqual(2,tokens.exchanges)
        transport.status=401
        before=transport.calls
        with self.assertRaises(http.ApiError):call()
        self.assertEqual(2,transport.calls-before);self.assertEqual(3,tokens.exchanges)
        before=transport.calls
        with self.assertRaises(http.ApiError):call('POST')
        self.assertEqual(1,transport.calls-before);self.assertEqual(4,tokens.exchanges)

    def test_fixture_adapters_and_clocks_cannot_be_promoted_or_mixed(self):
        class Pretend:offline=True
        for invocation,issuer in ((Pretend(),self.issuer),(self.invocation,Pretend())):
            with self.assertRaisesRegex(ValueError,'offline credential adapters'):
                c.OfflineCredentials(self.cfg,self.project,self.env,self.value,invocation,issuer,role='runner',
                    source=self.source,checkout_sha=self.source)
        self.issuer.clock=offline.Clock()
        with self.assertRaisesRegex(ValueError,'offline credential clock'):self.tokens()
        self.issuer.clock=self.clock
        with self.assertRaisesRegex(ValueError,'native credential factory'):
            c.NetworkCredentials(self.cfg,self.project,self.env,self.identity(),object())
        with self.assertRaisesRegex(ValueError,'not admitted'):provider.api_guard(self.tokens())

    def test_close_cannot_reopen_or_exchange_and_public_receipt_is_copy(self):
        tokens=self.tokens();tokens(30);receipt=tokens.receipt();receipt['context']['source']='b'*40
        self.assertEqual(self.source,tokens.receipt()['context']['source'])
        tokens.close();tokens.close()
        with self.assertRaisesRegex(c.ContextError,'CLOSED'):tokens(30)
        self.assertEqual({},tokens.env);self.assertEqual(3,len(self.issuer.calls))

    def test_unexpected_exception_and_forged_reason_are_sanitized(self):
        tokens=self.tokens();error=RuntimeError('secret-exception')
        error.reason_code='OIDC_CLAIMS_REJECTED'
        with patch.object(tokens,'recheck',side_effect=error):
            with self.assertRaisesRegex(c.ContextError,'UNCLASSIFIED') as raised:tokens(30)
        self.assert_sanitized(''.join(traceback.format_exception(raised.exception)))
        self.assertEqual('V52_CREDENTIAL_UNCLASSIFIED',tokens.receipt()['reasonCode'])

    def native(self,stack):
        stack.enter_context(patch.object(c.time,'monotonic',self.clock.seconds))
        stack.enter_context(patch.object(c.time,'time',self.clock.wall))
        source=stack.enter_context(patch.object(c,'checkout',return_value=self.source))
        get=stack.enter_context(patch.object(c,'github',side_effect=lambda path,end,clock:self.invocation.get(path,end)))
        descriptor=stack.enter_context(patch.object(c,'credential_file',return_value=deepcopy(self.value)))
        transport=Mock(send=self.issuer.send)
        network=stack.enter_context(patch.object(c.http,'Network',return_value=transport))
        tokens=c.open_network(self.cfg,self.project,self.env,role='runner',source=self.source)
        return tokens,source,get,descriptor,network,transport

    def test_native_factory_observes_without_tokens_then_rechecks_every_exchange(self):
        with ExitStack() as stack:
            tokens,source,get,descriptor,network,transport=self.native(stack)
            self.assertEqual(3,get.call_count);self.assertEqual(1,source.call_count)
            self.assertEqual([],self.issuer.calls);network.assert_called_once_with()
            tokens(30);tokens(30)
            self.assertEqual(9,get.call_count);self.assertEqual(3,source.call_count);self.assertEqual(3,descriptor.call_count)
            self.assertEqual('native-v52-credential-exchange',tokens.receipt()['execution'])
            self.assertFalse(tokens.receipt()['paidAdmission'])
            with self.assertRaisesRegex(ValueError,'not admitted'):provider.api_guard(tokens)
            # Advancing master is separate from this original run's identity.
            self.assertTrue(all('/commits/' not in call.args[0] for call in get.call_args_list))
            tokens.close();transport.close.assert_called_once_with()

    def test_native_refresh_cannot_reuse_stale_context_or_descriptor(self):
        for drift in ('source','attempt','descriptor'):
            with self.subTest(drift=drift),ExitStack() as stack:
                self.issuer.calls.clear();self.invocation.value['run_attempt']=2
                tokens,source,get,descriptor,network,transport=self.native(stack);tokens(30)
                if drift=='source':source.return_value='b'*40
                elif drift=='attempt':self.invocation.value['run_attempt']=3
                else:descriptor.return_value=dict(self.value,token_url='https://foreign/token')
                with self.assertRaises((c.ContextError,exchange.CredentialError)):tokens(30)
                self.assertEqual(3,len(self.issuer.calls));tokens.close()

    def test_native_factory_rejects_context_before_transport_creation(self):
        with patch.object(c,'checkout',return_value='b'*40),patch.object(c,'github') as get,patch.object(c.http,'Network') as network:
            with self.assertRaisesRegex(c.ContextError,'SOURCE'):
                c.open_network(self.cfg,self.project,self.env,role='runner',source=self.source)
            get.assert_not_called();network.assert_not_called()

    def test_native_factory_rejects_run_and_descriptor_before_transport_creation(self):
        for drift in ('attempt','descriptor'):
            with self.subTest(drift=drift):
                value=deepcopy(self.value)
                self.invocation.value['run_attempt']=3 if drift=='attempt' else 2
                if drift=='descriptor':value['token_url']='https://foreign/token'
                with patch.object(c,'checkout',return_value=self.source),patch.object(c,'github',
                    side_effect=lambda path,end,clock:self.invocation.get(path,end)),patch.object(c,'credential_file',
                    return_value=value),patch.object(c.http,'Network') as network:
                    with self.assertRaises((c.ContextError,exchange.CredentialError)):
                        c.open_network(self.cfg,self.project,self.env,role='runner',source=self.source)
                    network.assert_not_called()
        self.assertEqual([],self.issuer.calls)

    def test_inputs_are_copied_and_receipts_do_not_confer_mutation_authority(self):
        tokens=self.tokens();self.env['GITHUB_SHA']='b'*40;self.cfg['project']='foreign'
        self.value['token_url']='https://foreign/token'
        tokens(30);self.assertEqual(self.source,tokens.binding['source'])
        with self.assertRaisesRegex(ValueError,'not admitted'):provider.api_guard(tokens.receipt())
        with patch.object(http.Network,'send') as send:
            api=http.Api(tokens=tokens)
            with self.assertRaisesRegex(ValueError,'live provider mutation disabled'):
                api.call('POST','https://compute.googleapis.com/compute/v1/projects/offline-project/zones/us-west4-a/instances',
                         {},deadline=self.clock.seconds()+30)
            send.assert_not_called()

    def test_failed_lock_acquisition_does_not_start_observation_or_exchange(self):
        tokens=self.tokens();lock=Mock();lock.acquire.return_value=False;tokens.lock=lock
        with self.assertRaisesRegex(c.ContextError,'DEADLINE'):tokens(30)
        lock.acquire.assert_called_once_with(timeout=30);lock.release.assert_not_called()
        self.assertEqual([],self.invocation.calls);self.assertEqual([],self.issuer.calls)

    def test_fixed_checkout_commands_reject_dirty_wrong_root_and_timeout(self):
        result=lambda value:subprocess.CompletedProcess([],0,value,b'')
        for outputs in ((str(c.ROOT).encode(),self.source.encode(),b''),
                        (str(c.ROOT).encode(),self.source.encode(),b' M scripts/example.py'),
                        (b'/foreign',), (str(c.ROOT).encode(),b'bad-sha')):
            with patch.object(c.subprocess,'run',side_effect=[result(v) for v in outputs]) as run:
                if len(outputs)==3 and outputs[-1]==b'':self.assertEqual(self.source,c.checkout(40,self.clock.seconds))
                else:
                    with self.assertRaisesRegex(c.ContextError,'SOURCE'):c.checkout(40,self.clock.seconds)
                for call in run.call_args_list:
                    self.assertEqual('git',call.args[0][0]);self.assertEqual(c.ROOT,call.kwargs['cwd'])
                    self.assertLessEqual(call.kwargs['timeout'],30)
        with patch.object(c.subprocess,'run',side_effect=subprocess.TimeoutExpired('secret-exception',30)):
            with self.assertRaisesRegex(c.ContextError,'SOURCE') as error:c.checkout(40,self.clock.seconds)
        self.assert_sanitized(''.join(traceback.format_exception(error.exception)))

    def test_github_read_commands_are_fixed_and_errors_do_not_leak_output(self):
        from . import cloud_artifacts
        value=json.dumps(self.invocation.value).encode()
        def write(command,path,maximum,timeout):Path(path).write_bytes(value)
        with patch.object(cloud_artifacts,'bounded_command',side_effect=write) as run:
            self.assertEqual(self.invocation.value,c.github('actions/runs/123456/attempts/2',40,self.clock.seconds))
            self.assertEqual(cloud_artifacts.Network.command('actions/runs/123456/attempts/2'),run.call_args.args[0])
        def reject(*args):raise cloud_artifacts.GitHubReadError('HTTP_REJECTED',403)
        def invalid(command,path,maximum,timeout):Path(path).write_bytes(b'{"a":1,"a":2}')
        for effect in (reject,invalid):
            with patch.object(cloud_artifacts,'bounded_command',side_effect=effect) as run:
                with self.assertRaisesRegex(c.ContextError,'RUN_OBSERVATION') as error:c.github('actions/runs/123456',40,self.clock.seconds)
                self.assert_sanitized(''.join(traceback.format_exception(error.exception)))
                self.assertEqual(1,run.call_count)
        with patch.object(cloud_artifacts,'bounded_command') as run:
            for path in ('actions/workflows/x/dispatches','actions/runs/1/rerun','actions/runs/1?x=2','../x'):
                with self.assertRaises(ValueError):c.github(path,40,self.clock.seconds)
            run.assert_not_called()

    def test_credential_run_read_recovers_without_changing_exact_attempt(self):
        from . import cloud_artifacts
        calls=[]
        def reply(command,path,maximum,timeout):
            calls.append(command)
            if len(calls)<3:raise cloud_artifacts.GitHubReadError('TRANSPORT')
            Path(path).write_bytes(json.dumps(self.invocation.value).encode())
        with patch.object(cloud_artifacts,'bounded_command',side_effect=reply),patch.object(cloud_artifacts.time,'sleep'):
            self.assertEqual(self.invocation.value,c.github('actions/runs/123456/attempts/2',40,self.clock.seconds))
        self.assertEqual(3,len(calls));self.assertEqual(calls[0],calls[1]);self.assertEqual(calls[1],calls[2])

    def test_only_auth_action_regular_bounded_descriptor_file_is_read(self):
        with tempfile.TemporaryDirectory(prefix='v52-credentials-') as temp:
            path=Path(temp)/'credentials.json';path.write_text(json.dumps(self.value))
            self.assertEqual(self.value,c.credential_file({'GOOGLE_GHA_CREDS_PATH':str(path)}))
            link=Path(temp)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(exchange.CredentialError,'CREDENTIAL_FILE_OPEN'):c.credential_file({'GOOGLE_GHA_CREDS_PATH':str(link)})
            with self.assertRaisesRegex(exchange.CredentialError,'CREDENTIAL_FILE_PATH'):c.credential_file({'GOOGLE_APPLICATION_CREDENTIALS':str(path)})
            path.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(exchange.CredentialError,'CREDENTIAL_FILE_JSON'):c.credential_file({'GOOGLE_GHA_CREDS_PATH':str(path)})


if __name__=='__main__':unittest.main()
