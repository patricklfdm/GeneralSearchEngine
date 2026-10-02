from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote, urlsplit
from . import cloud_cleanup_entry as e, cloud_cleanup_entry_qualification as entries
from . import cloud_cleanup_network_fixture as tls
from . import cloud_cleanup_qualification as q, cloud_native_authority as n, cloud_native_cleanup as native
from . import cloud_http as http, cloud_gcp as g, cloud_runner as r, cloud_authority as a
from . import cloud_cleanup_credentials as credentials, cloud_cleanup_auth_fake as auth
from .remote_command import read


class CleanupNetworkTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.state,_,_=q.case_state('expired-manual',authority=n)
        self.v=entries.fixture(self.state['configuration'],'manual')
        self.binding=e.identity(self.v['configuration'],self.v['env'],trigger='manual',source=self.v['source'],checkout=self.v['checkout'])
        self.env,self.descriptor=auth.inputs(self.binding,self.v['env'])

    def network(self):
        return native.NetworkCleanupApi(self.state['configuration'],self.binding,self.env,self.descriptor)

    def test_generic_api_and_execution_labels_cannot_open_network_mutations_or_cleanup(self):
        transport=Mock(offline=False);tokens=Mock();api=http.Api(transport=transport,tokens=tokens)
        api.execution=n.CLEANUP_EXECUTION
        for method in ('POST','DELETE'):
            with self.assertRaisesRegex(ValueError,'live provider mutation'):
                api.call(method,'https://storage.googleapis.com/test',deadline=api.clock()+30)
        store=g.Store(self.state['configuration'],api,authority=n)
        store.execution=n.CLEANUP_EXECUTION
        with self.assertRaisesRegex(ValueError,'unqualified cleanup'):
            r.reconcile(store,None,self.root/'generic',trigger='manual',now=1,provider_factory=lambda lease:None,authority=n)
        tokens.assert_not_called();transport.send.assert_not_called();self.assertFalse((self.root/'generic').exists())

    def test_scoped_network_remains_ineligible_for_paid_runner_in_both_domains(self):
        api=self.network();store=g.Store(self.state['configuration'],api,authority=n)
        self.assertFalse(api.offline);self.assertEqual(n.CLEANUP_EXECUTION,store.execution)
        for authority in (a,n):
            with self.assertRaisesRegex(ValueError,'unqualified'):
                r.adapters(store,Mock(execution=store.execution),authority=authority)
        other=self.network();provider=Mock(execution=n.CLEANUP_EXECUTION,api=other)
        with self.assertRaises(ValueError):r.cleanup_adapters(store,provider,n)

    def test_closed_policy_precedes_tokens_even_through_base_api_call(self):
        api=self.network();api.tokens=Mock(side_effect=AssertionError('token requested'))
        api.transport=Mock(offline=False)
        requests=[('POST','https://compute.googleapis.com/compute/v1/projects/offline-project/global/firewalls'),
                  ('DELETE',api.objects+quote(n.LEDGER,safe='')),
                  ('GET','https://storage.googleapis.com/foreign')]
        for call in (api.call,lambda *args,**kw:http.Api.call(api,*args,**kw)):
            for method,url in requests:
                with self.subTest(method=method),self.assertRaises(ValueError):call(method,url,deadline=api.clock()+30)
        api.tokens.assert_not_called();api.transport.send.assert_not_called()

    def test_constructor_has_no_transport_token_identity_or_endpoint_bypass(self):
        for key in ('transport','tokens','clock','live','force','activationAllowed'):
            with self.subTest(key=key),self.assertRaises(TypeError):
                native.NetworkCleanupApi(self.state['configuration'],self.binding,self.env,self.descriptor,**{key:True})
        bad=deepcopy(self.descriptor);bad['token_url']='https://untrusted.invalid'
        with patch.object(http.Network,'send',side_effect=AssertionError('network before binding')):
            with self.assertRaises(ValueError):native.NetworkCleanupApi(self.state['configuration'],self.binding,self.env,bad)
            with self.assertRaises(ValueError):credentials.Credentials(self.binding,self.env,self.descriptor)

    def test_live_entry_revalidates_context_and_run_before_descriptor_or_network(self):
        with patch.object(e,'collect_run') as collect,patch.object(e,'credential_file') as descriptor,patch.object(http.Network,'send') as send:
            v=self.v
            with self.assertRaises(ValueError):
                e.execute_network(v['configuration'],self.env,self.root/'bad',trigger='manual',source='d'*40,checkout=v['checkout'])
            collect.assert_not_called();descriptor.assert_not_called();send.assert_not_called()
            collect.side_effect=ValueError('stale attempt')
            with self.assertRaises(ValueError):
                e.execute_network(v['configuration'],self.env,self.root/'bad',trigger='manual',source=v['source'],checkout=v['checkout'])
            collect.assert_called_once();descriptor.assert_not_called();send.assert_not_called();self.assertFalse((self.root/'bad').exists())

    def test_descriptor_file_is_bounded_regular_and_exact_without_ambient_fallback(self):
        path=self.root/'credentials';path.write_bytes(e.m.canonical(self.descriptor))
        self.assertEqual(self.descriptor,e.credential_file(dict(GOOGLE_GHA_CREDS_PATH=str(path))))
        link=self.root/'link';link.symlink_to(path)
        for value in (str(link),str(self.root),'relative',str(self.root/'missing')):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'file rejected'):
                e.credential_file(dict(GOOGLE_GHA_CREDS_PATH=value))
        with self.assertRaises(ValueError):e.credential_file(dict(GOOGLE_APPLICATION_CREDENTIALS=str(path)))
        for raw in (b'',b'{private-secret',b'x'*((128<<10)+1)):
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'file rejected'):e.credential_file(dict(GOOGLE_GHA_CREDS_PATH=str(path)))

    def test_runner_route_is_preserved_by_real_https_exchange(self):
        with tls.Fixture(self.state) as fixture,patch.object(fixture,'reply',wraps=fixture.reply) as reply:
            token=credentials.NetworkCredentials(fixture.binding,fixture.env,fixture.descriptor)(30)
            self.assertEqual(auth.ACCOUNT_SECRET,token.value)
            source=urlsplit(fixture.descriptor['credential_source']['url'])
            self.assertEqual(('GET',source.netloc,source.path+'?'+source.query),reply.call_args_list[0].args[:3])
            self.assertEqual(['oidc','sts','impersonation'],[request['stage'] for request in fixture.requests])
            self.assertFalse(fixture.errors)

    def test_cli_tls_reconciles_exact_ids_preserves_charge_and_rejects_output_reuse(self):
        with tls.Fixture(self.state) as fixture:
            root=self.root/'entry'
            self.assertEqual(0,fixture.run_cli(root))
            result=read(root/'receipt.json');self.assertEqual('PASS',result['status'])
            self.assertTrue(result['credentialExchangeCompleted']);self.assertFalse(result['identityAuthenticated'])
            self.assertFalse(result['cleanupReady']);self.assertEqual(n.CLEANUP_EXECUTION,result['reconciliation']['execution'])
            self.assertFalse(fixture.http.resources);self.assertNotIn(n.LEASE,fixture.http.objects)
            self.assertEqual(1_000_000,n.inspect_ledger(e.m.strict_json(fixture.http.objects[n.LEDGER][1]))[0])
            before=len(fixture.requests);receipt=(root/'receipt.json').read_bytes()
            self.assertEqual(2,fixture.run_cli(root));self.assertEqual(receipt,(root/'receipt.json').read_bytes())
            self.assertEqual(before,len(fixture.requests));self.assertFalse(fixture.errors)

    def test_cli_wrong_context_retains_sanitized_failure_with_nonzero_exit(self):
        with tls.Fixture(self.state) as fixture:
            fixture.env['GITHUB_SHA']='d'*40
            root=self.root/'bad';self.assertEqual(2,fixture.run_cli(root))
            self.assertEqual('entry',read(root/'receipt.json')['failure']['phase'])
            self.assertFalse(fixture.requests)

    def test_topology_profile_reconstructs_over_tls_without_opening_the_runner(self):
        from . import cloud_topology_qualification as topology, cloud_topology_fixture as driver
        value,clock,provider,reader,api=topology.fixture()
        prepared=driver.execute(value,api,self.root/'prepare-topology',now=clock.wall(),sleep=clock.sleep)
        self.assertEqual('PREPARED',prepared['status'])
        for resource in provider.resources.values():
            if 'machineType' in resource:
                self.assertEqual('STOP',resource['scheduling']['instanceTerminationAction'])
                resource['status']='TERMINATED'
        original_ids={resource['id'] for resource in provider.resources.values()}
        with tls.Fixture(q.snapshot(provider)) as fixture:
            root=self.root/'topology-cleanup';self.assertEqual(0,fixture.run_cli(root))
            result=read(root/'receipt.json');self.assertEqual('PASS',result['status'])
            self.assertFalse(result['cleanupReady']);self.assertFalse(fixture.http.resources)
            self.assertNotIn(n.LEASE,fixture.http.objects)
            calls=[r for r in fixture.http.requests if r['method']=='DELETE' and r['path'].startswith('/compute/')]
            self.assertEqual(original_ids,{r['path'].rsplit('/',1)[1] for r in calls})
            self.assertEqual(['instances']*3+['disks']*6+['firewalls']*4,[r['path'].split('/')[-2] for r in calls])
            ledger=e.m.strict_json(fixture.http.objects[n.LEDGER][1])
            self.assertEqual(topology.PRIOR_COST+driver.COST,n.inspect_ledger(ledger)[0])
            self.assertFalse(fixture.errors)

    def test_credential_expiry_and_original_deadline_remain_enforced_on_network_api(self):
        api=self.network();now=api.clock();api.tokens=Mock(return_value=http.AccessToken('private',now-1))
        api.transport=Mock(offline=False)
        with self.assertRaisesRegex(ValueError,'credential expired'):
            api.call('GET',api.objects+quote(n.LEASE,safe=''),deadline=now+30)
        api.transport.send.assert_not_called()
        api.tokens.reset_mock()
        with self.assertRaisesRegex(ValueError,'original deadline'):
            api.call('GET',api.objects+quote(n.LEASE,safe=''),deadline=now-1)
        api.tokens.assert_not_called()

    def test_malformed_resource_cannot_echo_provider_fields_into_retained_failures(self):
        with tls.Fixture(self.state,fault='malformed-resource') as fixture:
            root=self.root/'malformed';self.assertEqual(2,fixture.run_cli(root))
            receipt=read(root/'receipt.json')
            self.assertEqual('FAIL',receipt['reconciliation']['cleanup']['status'])
            self.assertTrue(receipt['reconciliation']['cleanup']['errors'])
            self.assertIn(n.LEASE,fixture.http.objects)
            for path in root.rglob('*'):
                if path.is_file():self.assertNotIn(auth.ACCOUNT_SECRET.encode(),path.read_bytes())
            for generation,raw,content in fixture.http.objects.values():self.assertNotIn(auth.ACCOUNT_SECRET.encode(),raw)

    def test_cancelled_reconciliation_keeps_failure_receipt_without_exception_text(self):
        with patch.object(e,'collect_run'),patch.object(e,'credential_file',return_value=self.descriptor),\
             patch.object(native,'reconcile',side_effect=KeyboardInterrupt('private-secret')):
            v=self.v
            value=e.execute_network(v['configuration'],self.env,self.root/'cancelled',trigger='manual',source=v['source'],checkout=v['checkout'])
            self.assertEqual('FAIL',value['status']);self.assertEqual('KeyboardInterrupt',value['failure']['type'])
            self.assertFalse(value['credentialExchangeCompleted']);self.assertNotIn('private-secret',repr(value))


if __name__=='__main__':unittest.main()
