from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import cloud_cleanup_credentials as c, cloud_cleanup_auth_fake as f
from . import cloud_cleanup_entry as e, cloud_cleanup_entry_qualification as q, cloud_cleanup_qualification as retained
from . import cloud_native_authority as n, cloud_fake
from .cloud_http import Api, ApiError, AccessToken
from .remote_command import read


class CleanupCredentialsTest(unittest.TestCase):
    def setUp(self):
        self.state, self.now, _ = retained.case_state('expired-manual', authority=n)
        self.invocation = q.fixture(self.state['configuration'], 'manual')
        v = self.invocation
        self.binding = e.identity(v['configuration'], v['env'], trigger='manual', source=v['source'], checkout=v['checkout'])
        self.env, self.descriptor = f.inputs(self.binding, v['env'])
        self.clock, self.http, _, _ = retained.restore(self.state)
        self.issuer = f.Issuer(self.binding, self.clock); self.provider = f.Provider(self.http)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def credentials(self, descriptor=None, env=None, transport=None):
        return c.Credentials(self.binding, env or self.env, descriptor if descriptor is not None else self.descriptor,
            transport=transport or self.issuer, clock=self.clock.seconds, wall=self.clock.wall)

    def integrated(self, name='run', **overrides):
        v = self.invocation
        arguments = dict(cfg=v['configuration'], env=self.env, observation=v['observation'],
            credentials=self.descriptor, transport=self.provider, auth_transport=self.issuer, output=self.root/name,
            trigger='manual', source=v['source'], checkout=v['checkout'], now=self.now, clock=self.clock.seconds, wall=self.clock.wall)
        arguments.update(overrides)
        return e.execute_integrated(**arguments)

    def test_bound_exchange_and_actual_expiry(self):
        value = self.credentials()(30)
        self.assertEqual(f.ACCOUNT_SECRET, value.value)
        self.assertEqual(self.clock.seconds()+3540, value.usable_until)
        self.assertEqual(['oidc','sts','impersonation'], [v['stage'] for v in self.issuer.calls])
        self.assertNotIn(f.ACCOUNT_SECRET, repr(value))

    def test_runtime_paths_are_opaque_and_preserved_through_exchange(self):
        # Synthetic routes: neither the toolkit nor pinned auth action requires
        # /idtoken to be the last segment. Do not infer a private service route.
        for path in ('/offline/idtoken',
                     '/42//idtoken/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222',
                     '/runtime/token/attempt-2', '/runtime/token/attempt-2/'):
            url='https://pipelines.actions.githubusercontent.com'+path+'?api-version=2.0'
            with self.subTest(path=path),patch.object(f,'OIDC',url):
                env,descriptor=f.inputs(self.binding,self.env)
                send=Mock(wraps=self.issuer.send)
                transport=Mock(offline=True,send=send)
                self.assertEqual(f.ACCOUNT_SECRET,self.credentials(descriptor,env,transport)(30).value)
                self.assertEqual(['GET','POST','POST'],[call.args[0] for call in send.call_args_list])
                self.assertEqual(descriptor['credential_source']['url'],send.call_args_list[0].args[1])

    def test_changed_runtime_path_is_rejected_before_exchange(self):
        url='https://pipelines.actions.githubusercontent.com/42//idtoken/runtime/job?api-version=2.0'
        with patch.object(f,'OIDC',url):env,descriptor=f.inputs(self.binding,self.env)
        for path in ('/offline/idtoken','/42/idtoken/runtime/job','/42//idtoken/runtime/other-job',
                     '/42//idtoken/runtime/job/'):
            bad=deepcopy(descriptor)
            bad['credential_source']['url']=bad['credential_source']['url'].replace('/42//idtoken/runtime/job',path)
            with self.subTest(path=path),self.assertRaises(c.CredentialError) as caught:
                self.credentials(bad,env)
            self.assertEqual('DESCRIPTOR_SOURCE_URL',caught.exception.reason_code)
        self.assertFalse(self.issuer.calls)

    def test_wrong_descriptor_fields_and_credential_kinds_fail_before_http(self):
        for field, value in [('type','service_account'),('audience','//iam.googleapis.com/wrong'),
                ('token_url','https://sts.googleapis.com.evil/token'),('subject_token_type',c.ACCESS),
                ('service_account_impersonation_url','https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/runner:generateAccessToken'),
                ('quota_project_id','foreign'),('private_key','secret')]:
            bad = deepcopy(self.descriptor);bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.credentials(bad)
        self.assertEqual([],self.issuer.calls)

    def test_cross_entry_descriptor_and_observer_cannot_be_used(self):
        v = q.fixture(self.state['configuration'], 'schedule')
        binding = e.identity(v['configuration'],v['env'],trigger='schedule',source=v['source'],checkout=v['checkout'])
        _, descriptor = f.inputs(binding,self.env)
        with self.assertRaises(ValueError):self.credentials(descriptor)
        bad=deepcopy(self.descriptor)
        bad['service_account_impersonation_url']=bad['service_account_impersonation_url'].replace('gse-v51-manual-cleanup','gse-v51-observer')
        with self.assertRaises(ValueError):self.credentials(bad)
        self.assertFalse(self.issuer.calls)

    def test_source_url_header_format_and_duplicate_query_are_closed(self):
        for change in (dict(url='https://evil/idtoken'),dict(headers={'Authorization':'Bearer wrong'}),
                       dict(format={'type':'text'}),dict(file='/tmp/token'),dict(executable={'command':'echo token'})):
            bad=deepcopy(self.descriptor);bad['credential_source'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):self.credentials(bad)
        bad=deepcopy(self.descriptor);bad['credential_source']['url']+='&audience=evil'
        with self.assertRaises(ValueError):self.credentials(bad)
        for url in ('http://pipelines.actions.githubusercontent.com/idtoken',
                    'https://pipelines.actions.githubusercontent.com.evil/idtoken',
                    'https://user@pipelines.actions.githubusercontent.com/idtoken',
                    f.OIDC+'&audience=foreign',f.OIDC+'&api-version=2.0',f.OIDC+'#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError):self.credentials(env=dict(self.env,ACTIONS_ID_TOKEN_REQUEST_URL=url))
        self.assertFalse(self.issuer.calls)

    def test_each_oidc_identity_claim_is_bound_before_sts(self):
        keys=('iss','aud','sub','repository','repository_id','repository_owner_id','ref','environment',
              'event_name','workflow_ref','workflow_sha','sha','run_id','run_attempt')
        for key in keys:
            self.issuer.calls.clear();self.issuer.claim_changes={key:'wrong'}
            with self.subTest(key=key),self.assertRaises(ValueError):self.credentials()(30)
            self.assertEqual(['oidc'],[v['stage'] for v in self.issuer.calls])

    def test_repository_immutable_subject_reaches_permission_queries_for_every_role(self):
        from . import cloud_permissions as permissions, cloud_permissions_qualification as fixtures
        # Repository OIDC API reports use_immutable_subject=true with this prefix.
        prefix='repo:patricklfdm@147357093/GeneralSearchEngine@1341513206:environment:'
        for role in permissions.ROLES:
            cfg,binding,env,descriptor,clock,issuer,provider,client,run=fixtures.fixture(role)
            issuer.claim_changes['sub']=prefix+binding['environment']
            with self.subTest(role=role):
                actual=client.probe('project',clock.seconds()+30)
                self.assertEqual(client.queries['project']['required'],actual)
                self.assertEqual(['oidc','sts','impersonation'],[v['stage'] for v in issuer.calls])
                self.assertEqual(1,len(provider.requests))

    def test_legacy_subject_and_changed_immutable_identity_stop_before_sts(self):
        suffix=':environment:'+self.binding['environment']
        for subject in (
            'repo:patricklfdm/GeneralSearchEngine'+suffix,
            'repo:patricklfdm@147357094/GeneralSearchEngine@1341513206'+suffix,
            'repo:patricklfdm@147357093/GeneralSearchEngine@1341513207'+suffix,
            'repo:other-owner@147357093/GeneralSearchEngine@1341513206'+suffix,
            'repo:patricklfdm@147357093/OtherRepository@1341513206'+suffix,
            'repo:patricklfdm@147357093/GeneralSearchEngine@1341513206:environment:other-environment'):
            self.issuer.calls.clear();self.issuer.claim_changes={'sub':subject}
            with self.subTest(subject=subject),self.assertRaises(ValueError):self.credentials()(30)
            self.assertEqual(['oidc'],[v['stage'] for v in self.issuer.calls])

    def test_expired_future_noninteger_and_unsigned_tokens_rejected(self):
        for changes in ({'exp':self.clock.wall()},{'nbf':self.clock.wall()+31},
                        {'iat':self.clock.wall()+31},{'exp':True},{'iat':'1'}):
            self.issuer.calls.clear();self.issuer.claim_changes=changes
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.credentials()(30)
            self.assertEqual(1,len(self.issuer.calls))
        self.issuer.claim_changes={}
        for token in ('invalid', 'e30.e30.', 'e30.e30.signature', '\nsecret'):
            self.issuer.response_changes={'oidc':dict(value=token)}
            with self.subTest(token=token),self.assertRaises(ValueError):self.credentials()(30)

    def test_sts_and_impersonation_rejection_never_reaches_provider(self):
        for stage in ('oidc','sts','impersonation'):
            self.issuer.calls.clear();self.issuer.fail=stage
            result=self.integrated(stage)
            self.assertEqual('FAIL',result['status']);self.assertEqual(0,self.provider.authorized_calls)
            self.assertEqual(['oidc','sts','impersonation'][:len(self.issuer.calls)],[v['stage'] for v in self.issuer.calls])
            for secret in (f.SUBJECT_SECRET,f.FEDERATED_SECRET,f.ACCOUNT_SECRET,'private issuer'):
                self.assertNotIn(secret,repr(result))
                self.assertNotIn(secret,(self.root/stage/'receipt.json').read_text())

    def test_malformed_issuer_responses_and_short_expiry_fail_closed(self):
        for stage,changes in [('sts',dict(token_type='Other')),('sts',dict(issued_token_type=c.JWT)),
                             ('sts',dict(expires_in=0)),('sts',dict(access_token='bad\nheader')),
                             ('impersonation',dict(accessToken='')),('impersonation',dict(expireTime='wrong'))]:
            self.issuer.response_changes={stage:changes}
            with self.subTest(stage=stage,changes=changes),self.assertRaises(ValueError):self.credentials()(30)
        self.issuer.response_changes={}
        for lifetime in (-1,60,3601):
            self.issuer.lifetime=lifetime
            with self.subTest(lifetime=lifetime),self.assertRaises(ValueError):self.credentials()(30)

    def test_provider_refreshes_at_returned_expiry_not_fixed_2400_seconds(self):
        self.issuer.lifetime=120
        api=Api(transport=self.provider,tokens=self.credentials(),clock=self.clock.seconds)
        url='https://storage.googleapis.com/storage/v1/b/'+self.state['configuration']['bucket']+'/o/'+n.LEASE.replace('/','%2F')
        api.call('GET',url,deadline=self.clock.seconds()+30)
        self.clock.sleep(61)
        api.call('GET',url,deadline=self.clock.seconds()+30)
        self.assertEqual(6,len(self.issuer.calls));self.assertEqual(2,self.provider.authorized_calls)

    def test_get_401_refreshes_once_and_mutation_401_does_not_replay(self):
        for method in ('GET','DELETE'):
            calls=[];self.issuer.calls.clear()
            def send(*args):
                calls.append(args);return (401,b'private') if len(calls)==1 else (200,b'{}')
            api=Api(transport=Mock(offline=True,send=send),tokens=self.credentials(),clock=self.clock.seconds)
            if method=='GET':api.call(method,'https://storage.googleapis.com/a',deadline=self.clock.seconds()+30)
            else:
                with self.assertRaises(ApiError):api.call(method,'https://storage.googleapis.com/a',deadline=self.clock.seconds()+30)
            self.assertEqual(2 if method=='GET' else 1,len(calls))
            self.assertEqual(6 if method=='GET' else 3,len(self.issuer.calls))

    def test_total_refresh_deadline_includes_all_stages(self):
        original=self.issuer.send
        def slow(*args):
            result=original(*args);self.clock.sleep(11);return result
        self.issuer.send=slow
        api=Api(transport=self.provider,tokens=self.credentials(),clock=self.clock.seconds)
        with self.assertRaises(ValueError):api.call('GET','https://storage.googleapis.com/a',deadline=self.clock.seconds()+30)
        self.assertEqual([30,19,8],[v['timeout'] for v in self.issuer.calls])
        self.assertEqual(0,self.provider.authorized_calls)

    def test_live_guards_precede_descriptor_tokens_http_and_output(self):
        for side in ('transport','auth_transport'):
            live=Mock(offline=False)
            with self.subTest(side=side),self.assertRaises(ValueError):self.integrated(**{side:live})
            live.send.assert_not_called();self.assertFalse((self.root/'run').exists())
        with self.assertRaises(ValueError):self.credentials(transport=Mock(offline=False))
        self.assertFalse(self.issuer.calls)

    def test_context_and_run_mismatch_precede_exchange(self):
        for changes in (dict(source='0'*40),dict(checkout='0'*40),dict(trigger='schedule'),
                        dict(observation=dict(self.invocation['observation'],run_attempt=3))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.integrated(**changes)
        self.assertFalse(self.issuer.calls);self.assertFalse((self.root/'run').exists())

    def test_closed_cleanup_policy_runs_before_credential_exchange(self):
        from .cloud_native_cleanup import CleanupApi
        policy=CleanupApi(self.state['configuration'],Api(transport=self.provider,tokens=self.credentials(),clock=self.clock.seconds))
        for method,url in [('POST','https://compute.googleapis.com/compute/v1/projects/offline-project/global/firewalls'),
                           ('DELETE','https://storage.googleapis.com/storage/v1/b/offline-evidence/o/'+n.LEDGER.replace('/','%2F'))]:
            with self.assertRaises(ValueError):policy.call(method,url,deadline=self.clock.seconds()+30)
        self.assertFalse(self.issuer.calls);self.assertEqual(0,self.provider.authorized_calls)

    def test_expired_native_reconciliation_preserves_charge_and_absence(self):
        result=self.integrated()
        self.assertEqual('PASS',result['status']);self.assertTrue(result['reconciliation']['leaseReleased'])
        self.assertFalse(result['identityAuthenticated']);self.assertFalse(result['cleanupReady'])
        self.assertFalse(self.http.resources);self.assertNotIn(n.LEASE,self.http.objects)
        total,attempts=n.inspect_ledger(c.m.strict_json(self.http.objects[n.LEDGER][1]))
        self.assertEqual(1_000_000,total);self.assertTrue(all(v['status']=='FAIL' for v in attempts.values()))

    def test_lost_delete_response_is_reconciled_without_blind_replay(self):
        original=self.http.send;lost=[]
        def send(method,url,*args):
            result=original(method,url,*args)
            if method=='DELETE' and 'compute.googleapis.com' in url and not lost:
                lost.append(url);raise ConnectionError('private provider error')
            return result
        self.http.send=send
        first=self.integrated('first');self.assertEqual('FAIL',first['status']);self.assertIn(n.LEASE,self.http.objects)
        count=len([v for v in self.http.requests if v['method']=='DELETE' and v['path']==c.urlsplit(lost[0]).path])
        second=self.integrated('second');self.assertEqual('PASS',second['status'])
        self.assertEqual(count,len([v for v in self.http.requests if v['method']=='DELETE' and v['path']==c.urlsplit(lost[0]).path]))

    def test_invalid_token_expiry_is_rejected_before_provider(self):
        for expiry in (True,float('nan'),float('inf'),self.clock.seconds()):
            api=Api(transport=self.provider,tokens=lambda timeout:AccessToken('secret',expiry),clock=self.clock.seconds)
            with self.subTest(expiry=expiry),self.assertRaises(ValueError):api.call('GET','https://storage.googleapis.com/a',deadline=self.clock.seconds()+30)
        self.assertEqual(0,self.provider.authorized_calls)


if __name__=='__main__':unittest.main()
