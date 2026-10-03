from copy import deepcopy
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from . import cloud_permissions as p, cloud_permissions_qualification as q
from . import cloud_cleanup_auth_fake as auth, cloud_http as http, cloud_preflight as preflight
from .remote_command import write_once, read


class PermissionPrecheckTest(unittest.TestCase):
    def fixture(self, role='manual'):
        (self.cfg,self.binding,self.env,self.descriptor,self.clock,self.issuer,self.provider,self.client,self.run) = q.fixture(role)

    def collect(self): return p.collect(self.cfg,self.binding,self.client,wall=self.clock.wall)
    def evaluate(self, value): return p.evaluate(self.cfg,self.binding,value,now=self.clock.wall())

    def test_all_four_roles_use_bound_impersonated_token_and_remain_diagnostic(self):
        accounts = set()
        for role in p.ROLES:
            with self.subTest(role=role):
                self.fixture(role); value=self.collect(); receipt=self.evaluate(value)
                self.assertEqual('PRECHECK_PASS',receipt['status']); self.assertEqual('offline-permission-probes',receipt['execution'])
                self.assertEqual(['oidc','sts','impersonation'],[v['stage'] for v in self.issuer.calls])
                self.assertEqual(2,len(self.provider.requests)); accounts.add(self.binding['serviceAccount'])
                for key in p.BOUNDARY:self.assertIs(receipt[key],False)
        self.assertEqual(4,len(accounts))

    def test_context_drift_rejected_before_any_credentials_or_network(self):
        self.fixture()
        for key in self.env:
            if key.startswith('ACTIONS_'):continue
            for bad in (None, '', 'wrong', 1, True):
                env=deepcopy(self.env)
                if bad is None:env.pop(key)
                else:env[key]=bad
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                    p.identity(self.cfg,env,role='manual',source=self.binding['source'],checkout=self.binding['source'])
        for checkout in ('d'*40,'master'):
            with self.assertRaises(ValueError):p.identity(self.cfg,self.env,role='manual',source=self.binding['source'],checkout=checkout)
        self.assertEqual([],self.issuer.calls);self.assertEqual([],self.provider.requests)

    def test_other_role_or_descriptor_cannot_borrow_workflow_identity(self):
        for role in p.ROLES:
            self.fixture(role)
            for other in set(p.ROLES)-{role}:
                with self.subTest(role=role,other=other),self.assertRaises(ValueError):
                    p.identity(self.cfg,self.env,role=other,source=self.binding['source'],checkout=self.binding['source'])
            descriptor=deepcopy(self.descriptor);descriptor['service_account_impersonation_url']=descriptor['service_account_impersonation_url'].replace('gse-v51-','gse-v50-')
            with self.assertRaises(ValueError):
                p.OfflineClient(self.cfg,self.binding,self.env,descriptor,transport=self.provider,issuer=self.issuer,clock=self.clock.seconds,wall=self.clock.wall)

    def test_read_only_fixed_endpoints_and_existing_grants_are_preserved(self):
        for role in p.ROLES:
            self.fixture(role);plan=p.plan(self.cfg,role)
            self.assertEqual({'project','bucket'},set(plan))
            self.assertEqual('POST',plan['project']['method']);self.assertTrue(plan['project']['url'].endswith(':testIamPermissions'))
            self.assertEqual('GET',plan['bucket']['method']);self.assertIsNone(plan['bucket']['body'])
            self.assertNotIn('/o/',plan['bucket']['url']);self.assertNotIn('storage.objects.create',plan['bucket']['required'])
            if role in ('manual','schedule'):self.assertEqual(set(p.identities.CLEANUP_COMPUTE),set(plan['project']['required']))
            self.assertNotIn('iap.tunnelInstances.accessViaIAP',str(plan))
        self.assertIn('no object testIamPermissions',str(p.LIMITATIONS))

    def test_plan_drift_and_unknown_query_block_before_tokens(self):
        self.fixture();self.client.tokens=Mock(side_effect=AssertionError('credential acquired'))
        with self.assertRaises(ValueError):self.client.probe('foreign',10)
        self.client.queries['project']['url']='https://cloudresourcemanager.googleapis.com/v1/projects/foreign:setIamPolicy'
        with self.assertRaises(ValueError):self.client.probe('project',10)
        self.client.tokens.assert_not_called();self.assertEqual([],self.provider.requests)

    def test_offline_entry_cannot_accept_live_transport_or_issuer(self):
        self.fixture()
        for transport,issuer in ((Mock(offline=False),self.issuer),(self.provider,Mock(offline=False))):
            with self.assertRaises(ValueError):p.OfflineClient(self.cfg,self.binding,self.env,self.descriptor,transport=transport,issuer=issuer,clock=self.clock.seconds,wall=self.clock.wall)

    def test_required_denied_and_forbidden_returned_block(self):
        for role in p.ROLES:
            self.fixture(role);good=self.collect()
            for name,query in self.client.queries.items():
                for permission in query['required']+query['forbidden']:
                    bad=deepcopy(good);values=bad['observations'][name]['permissions']
                    if permission in query['required']:values.remove(permission)
                    else:values.append(permission)
                    with self.subTest(role=role,name=name,permission=permission):self.assertEqual('BLOCKED',self.evaluate(bad)['status'])

    def test_malformed_unrequested_duplicate_and_secret_responses_never_qualify(self):
        for response in (None,[],{'error':'secret'}, {'permissions':'secret'}, {'permissions':[1]},
                         {'permissions':['secret']}, {'permissions':['storage.buckets.get']*2}, {'kind':'wrong'}):
            with self.subTest(response=response):
                self.fixture();self.provider.responses['bucket']=response
                value=self.collect();self.assertEqual('BLOCKED',self.evaluate(value)['status'])
                self.assertNotIn('secret',repr(value))

    def test_403_404_429_503_are_unavailable_not_forbidden_action_success(self):
        for status in (403,404,429,503):
            self.fixture();self.provider.status=status;value=self.collect()
            self.assertEqual('BLOCKED',self.evaluate(value)['status'])
            self.assertEqual(status,value['observations']['bucket']['httpStatus']);self.assertEqual(2,len(self.provider.requests))

    def test_401_refresh_is_bounded_for_both_read_only_methods(self):
        self.fixture();self.provider.status=401;value=self.collect()
        self.assertEqual('BLOCKED',self.evaluate(value)['status']);self.assertEqual(4,len(self.provider.requests))
        self.assertEqual(4,self.client.tokens.exchanges)
        self.fixture();send=self.provider.send;seen=set()
        def once(method,url,*args):
            if method not in seen:seen.add(method);return 401,b''
            return send(method,url,*args)
        with patch.object(self.provider,'send',side_effect=once):self.assertEqual('PRECHECK_PASS',self.evaluate(self.collect())['status'])
        self.assertEqual(3,self.client.tokens.exchanges)

    def test_expiry_late_response_and_original_deadline_remain_bounded(self):
        self.fixture();self.issuer.delay=31
        value=self.collect();self.assertEqual('BLOCKED',self.evaluate(value)['status']);self.assertEqual([],self.provider.requests)
        self.fixture();send=self.provider.send
        def late(*args):self.clock.sleep(181);return send(*args)
        with patch.object(self.provider,'send',side_effect=late):value=self.collect()
        self.assertEqual('BLOCKED',self.evaluate(value)['status']);self.assertEqual(1,len(self.provider.requests))

    def test_wrong_oidc_claims_or_issuer_denial_never_reach_provider(self):
        for change in ({'sha':'d'*40},{'run_attempt':'3'},{'environment':'foreign'}):
            self.fixture();self.issuer.claim_changes=change;value=self.collect()
            self.assertEqual('BLOCKED',self.evaluate(value)['status']);self.assertEqual([],self.provider.requests)
        for stage in ('oidc','sts','impersonation'):
            self.fixture();self.issuer.fail=stage;value=self.collect()
            self.assertEqual('BLOCKED',self.evaluate(value)['status']);self.assertEqual([],self.provider.requests)
            for secret in (auth.SUBJECT_SECRET,auth.FEDERATED_SECRET,auth.ACCOUNT_SECRET):self.assertNotIn(secret,repr(value))

    def test_receipt_rejects_stale_future_incomplete_and_wrong_identity(self):
        self.fixture();good=self.collect()
        changes=[{'startedAt':self.clock.wall()-900},{'completedAt':self.clock.wall()+1},
                 {'source':'d'*40},{'runAttempt':3},{'role':'schedule'}, {'serviceAccount':'foreign'},
                 {'configurationSha256':'d'*64},{'planSha256':'d'*64},{'credentialExchangeCompleted':False},
                 {'observations':{}},{'execution':'GCP-PASS'}]
        for change in changes:
            with self.subTest(change=change):self.assertEqual('BLOCKED',self.evaluate(dict(good,**change))['status'])

    def test_local_receipts_cannot_substitute_for_live_same_run_precheck(self):
        self.fixture('observer');value=self.collect();receipt=self.evaluate(value)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,v in (('binding',self.binding),('observations',value),('receipt',receipt)):write_once(root/(name+'.json'),v)
            with self.assertRaisesRegex(ValueError,'offline'):p.check_saved(self.cfg,self.binding,root,now=self.clock.wall())
            # Fixture only: exercise the live-domain consistency validator, not a live-IAM claim.
            value['execution']='workflow-permission-probes';receipt=self.evaluate(value)
            (root/'observations.json').write_bytes(p.m.canonical(value));(root/'receipt.json').write_bytes(p.m.canonical(receipt))
            self.assertEqual('PASS',p.check_saved(self.cfg,self.binding,root,now=self.clock.wall())['status'])
            receipt['objectPermissionsQualified']=True;(root/'receipt.json').write_bytes(p.m.canonical(receipt))
            with self.assertRaisesRegex(ValueError,'differs'):p.check_saved(self.cfg,self.binding,root,now=self.clock.wall())

    def test_run_resamples_github_and_retains_no_credentials(self):
        self.fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(p.entry,'collect_run',return_value=self.run) as collect_run,\
             patch.object(p.entry,'credential_file',return_value=self.descriptor),patch.object(p,'NetworkClient',return_value=self.client),\
             patch.object(p.time,'time',side_effect=self.clock.wall):
            output=Path(tmp)/'run'
            result=p.run(self.cfg,self.env,output,role='manual',source=self.binding['source'],checkout=self.binding['source'])
            self.assertEqual('PRECHECK_PASS',result['status']);self.assertEqual(2,collect_run.call_count)
            for secret in (auth.SUBJECT_SECRET,auth.FEDERATED_SECRET,auth.ACCOUNT_SECRET):
                self.assertFalse(any(secret in file.read_text() for file in output.iterdir()))
            with self.assertRaises(FileExistsError):p.run(self.cfg,self.env,output,role='manual',source=self.binding['source'],checkout=self.binding['source'])

    def test_changed_run_after_collection_blocks_receipt(self):
        self.fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(p.entry,'collect_run',side_effect=[self.run,ValueError('private-secret')]),\
             patch.object(p.entry,'credential_file',return_value=self.descriptor),patch.object(p,'NetworkClient',return_value=self.client):
            result=p.run(self.cfg,self.env,Path(tmp)/'run',role='manual',source=self.binding['source'],checkout=self.binding['source'])
            self.assertEqual('BLOCKED',result['status']);self.assertEqual('github',result['failure']['phase']);self.assertNotIn('private-secret',repr(result))

    def test_generic_api_is_still_read_only_and_has_no_crm_endpoint(self):
        api=http.Api(transport=Mock(offline=False),tokens=Mock())
        self.fixture()
        for method,url in (('POST',p.plan(self.cfg,'manual')['project']['url']),('DELETE','https://storage.googleapis.com/test')):
            with self.assertRaises(ValueError):api.call(method,url,deadline=api.clock()+30)
        api.tokens.assert_not_called();api.transport.send.assert_not_called()

    def test_observer_report_requires_matching_fresh_network_precheck(self):
        from . import cloud_preflight_qualification as provider_fixture
        from . import cloud_recent_cleanup
        cfg,github,provider=provider_fixture.fixture()
        self.fixture('observer');observed=self.collect()
        source=self.binding['source'];now=self.clock.wall()
        # The preflight provider/source evaluator has its own full suite. Isolate
        # the same-run observer gate; recent cleanup is independently tested.
        baseline=preflight.evaluate(cfg,provider_fixture.SOURCE,github,provider,now=provider_fixture.NOW)
        for mode,expected in (('missing','BLOCKED'),('offline','BLOCKED'),('other-attempt','BLOCKED'),
                              ('stale','BLOCKED'),('network','OBSERVATIONS_READY')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                if mode!='missing':
                    target=root/'permissions';target.mkdir();value=deepcopy(observed)
                    if mode!='offline':value['execution']='workflow-permission-probes'
                    if mode=='other-attempt':value['runAttempt']+=1
                    if mode=='stale':value['startedAt']=now-900
                    for name,data in (('binding',self.binding),('observations',value),('receipt',self.evaluate(value))):
                        write_once(target/(name+'.json'),data)
                argv=['preflight','report','--source',source,'--output',str(root)]
                with patch('sys.argv',argv),patch.dict(preflight.os.environ,self.env,clear=True),\
                     patch.object(preflight.subprocess,'check_output',return_value=source+'\n'),\
                     patch.object(preflight,'evaluate',return_value=deepcopy(baseline)),\
                     patch.object(cloud_recent_cleanup,'check_saved',return_value=dict(status='PASS',detail=dict(expiresAt=now+100))),\
                     patch.object(preflight.time,'time',return_value=now),contextlib.redirect_stdout(io.StringIO()):
                    if expected=='BLOCKED':
                        with self.assertRaises(SystemExit) as error:preflight.main()
                        self.assertEqual(2,error.exception.code)
                    else:preflight.main()
                receipt=read(root/'preflight.json');self.assertEqual(expected,receipt['status'])
                self.assertFalse(receipt['paidAdmission']);self.assertFalse(receipt['fullRemoteQualification'])


if __name__=='__main__':unittest.main()
