"""Transient failures through real V5.2 read/credential adapters, with no network."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import Mock, patch
from scripts.v51 import cloud_http as http
from . import cloud_read_retry as r, cloud_credentials as c, cloud_credentials_offline as auth
from . import test_cloud_provider as fixtures
from . import cloud_storage, cloud_iap, remote_voter_lifecycle
from . import cloud_guest_identity as probe
from . import cloud_control


class ReadRetryTest(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.output=io.StringIO();self.waits=[]
        self.addCleanup(patch.stopall)
        patch.object(r.time,'sleep',side_effect=self.sleep).start()
        self.redirect=redirect_stdout(self.output);self.redirect.__enter__();self.addCleanup(self.redirect.__exit__,None,None,None)
        self.transport=Mock(offline=True);self.tokens=Mock(return_value='test-token')
        self.api=r.Api(transport=self.transport,tokens=self.tokens,clock=lambda:self.now)

    def sleep(self,seconds):self.waits.append(seconds);self.now+=seconds
    def call(self,method='GET'):return self.api.call(method,'https://compute.googleapis.com/test',deadline=30)

    def test_transient_reads_recover_with_same_endpoint_and_shrinking_deadline(self):
        self.transport.send.side_effect=[ConnectionError('private-url'),(503,b'private-body'),(200,b'{"ok":true}')]
        self.assertEqual({'ok':True},self.call());self.assertEqual([.25,.5],self.waits)
        self.assertEqual([30,29.75,29.25],[x.args[4] for x in self.transport.send.call_args_list])
        self.assertEqual(1,self.tokens.call_count)
        self.assertEqual(1,len({x.args[1] for x in self.transport.send.call_args_list}))
        self.assertNotIn('private',self.output.getvalue())

    def test_every_transient_status_is_bounded(self):
        for status in r.STATUSES:
            with self.subTest(status=status):
                self.transport.reset_mock();self.now=0
                self.transport.send.side_effect=None;self.transport.send.return_value=(status,b'private')
                with self.assertRaises(r.ReadError) as caught:self.call()
                self.assertEqual(3,self.transport.send.call_count)
                self.assertEqual(dict(code='V52_READ_RETRIES_EXHAUSTED',scope='provider-read',attempts=3,
                    reason='http-'+str(status),stop='attempt-limit'),caught.exception.detail)

    def test_terminal_http_and_invalid_body_are_not_retried(self):
        for response in [(s,b'private') for s in (301,400,403,404,409,412,422,501,505)]+[(200,b'{'),(200,b'x'*65)]:
            self.transport.reset_mock();self.transport.send.return_value=response
            with self.subTest(response=response),self.assertRaises((ValueError,http.ApiError)):
                self.api.call('GET','https://storage.googleapis.com/test',deadline=30,maximum=64)
            self.assertEqual(1,self.transport.send.call_count)

    def test_auth_refresh_has_finite_wire_bound(self):
        self.transport.send.side_effect=[(401,b''),(503,b'')]*3
        with self.assertRaises(r.ReadError):self.call()
        self.assertEqual(6,self.transport.send.call_count);self.assertEqual(4,self.tokens.call_count)
        self.transport.reset_mock();self.transport.send.side_effect=[(401,b'')]*2
        with self.assertRaises(http.ApiError):self.call()
        self.assertEqual(2,self.transport.send.call_count)

    def test_mutations_never_replay_even_after_transport_or_http_failure(self):
        for method in ('POST','DELETE'):
            for error in (ConnectionError('lost'),TimeoutError('lost'),http.ApiError(503,method),http.ApiError(401,method)):
                self.transport.reset_mock();self.transport.send.side_effect=error
                with self.subTest(method=method,error=type(error)),self.assertRaises(type(error)):self.call(method)
                self.assertEqual(1,self.transport.send.call_count)
        self.assertEqual([],self.waits)

    def test_original_deadline_stops_before_sleep_and_further_exchange(self):
        def send(*args):self.now=29.8;raise TimeoutError('private')
        self.transport.send.side_effect=send
        with self.assertRaises(r.ReadError) as caught:self.call()
        self.assertEqual('deadline',caught.exception.detail['stop']);self.assertEqual([],self.waits)
        self.assertEqual(1,self.transport.send.call_count)

    def test_success_after_deadline_is_not_accepted_or_retried(self):
        def send(*args):self.now=31;return 200,b'{}'
        self.transport.send.side_effect=send
        with self.assertRaises(r.ReadError) as caught:self.call()
        self.assertEqual('deadline',caught.exception.detail['stop'])
        self.assertEqual(1,self.transport.send.call_count)

    def test_reauthorization_runs_before_another_wire_attempt(self):
        self.api.authorize=Mock(side_effect=[None,ValueError('authority changed')])
        self.transport.send.side_effect=ConnectionError('lost')
        with self.assertRaisesRegex(ValueError,'authority changed'):self.call()
        self.assertEqual(1,self.transport.send.call_count)

    def test_exhaustion_cannot_be_multiplied_by_outer_read_storage_iap_or_launch(self):
        exhausted=r.ReadError('provider-read',3,'connection','attempt-limit')
        self.transport.send.side_effect=exhausted
        with self.assertRaises(r.ReadError):self.call()
        self.assertEqual(1,self.transport.send.call_count);self.assertFalse(cloud_storage.transient(exhausted))
        self.assertFalse(cloud_iap._retry_admission(exhausted))
        query=Mock()
        with self.assertRaises(r.ReadError):remote_voter_lifecycle.original_launch(Mock(side_effect=exhausted),query)
        query.assert_not_called()

    def test_projection_drops_untrusted_text_and_invalid_fields(self):
        detail=r.ReadError('provider-read',3,'connection','attempt-limit').detail
        self.assertEqual({'readRetry':detail},r.public_failure(dict(readRetry=detail,secret='private')))
        for changed in (dict(detail,reason='private'),dict(detail,attempts=4),dict(detail,scope=[]),dict(detail,code='private')):
            self.assertEqual({},r.public_failure(dict(readRetry=changed)))

    def test_diagnostic_stream_failure_cannot_hide_exhaustion(self):
        self.transport.send.side_effect=ConnectionError('private')
        with patch('builtins.print',side_effect=BrokenPipeError('closed')):
            with self.assertRaises(r.ReadError) as caught:self.call()
        self.assertEqual(3,caught.exception.detail['attempts'])

    def test_control_cas_and_release_cannot_multiply_exhausted_read_retries(self):
        error=r.ReadError('provider-read',3,'connection','attempt-limit')
        # Failure before submission, after readback, or during uncertain-write
        # reconciliation must stop without a further write or read loop.
        for point in ('submission','readback','reconciliation'):
            store=Mock();store.put.return_value=2;store.get.side_effect=error
            if point!='readback':store.put.side_effect=error if point=='submission' else ConnectionError('lost write')
            with self.subTest(action='cas',point=point),self.assertRaises(r.ReadError):cloud_control.put(store,'key',{'v':1},0)
            store.put.assert_called_once();self.assertEqual(0 if point=='submission' else 1,store.get.call_count)
        for point in ('submission','reconciliation'):
            store=Mock();lease={'original':'lease'};store.get.side_effect=[(1,lease),error]
            store.delete.side_effect=error if point=='submission' else ConnectionError('lost delete')
            with self.subTest(action='release',point=point),self.assertRaises(r.ReadError):cloud_control.release(store,1,lease)
            store.delete.assert_called_once();self.assertEqual(1 if point=='submission' else 2,store.get.call_count)


class CredentialRetryTest(unittest.TestCase):
    def setUp(self):
        self.cfg=fixtures.configuration()
        project,env,value,self.invocation,self.issuer=auth.fixture(self.cfg)
        self.clock=self.invocation.clock
        self.tokens=c.OfflineCredentials(self.cfg,project,env,value,self.invocation,self.issuer,
            role='runner',source='a'*40,checkout_sha='a'*40)
        self.addCleanup(self.tokens.close);self.addCleanup(patch.stopall)
        patch.object(r.time,'sleep',side_effect=self.clock.sleep).start()
        patch.object(http.Network,'send',side_effect=AssertionError('network forbidden')).start()

    def test_late_provider_denial_is_not_reclassified_as_credential_transport_failure(self):
        for phase,method,url in (('oidc','GET','https://pipelines.actions.githubusercontent.com/fixed'),
                                  ('sts','POST',c.exchange.STS),
                                  ('impersonation','POST','https://iamcredentials.googleapis.com/fixed')):
            for raised in (False,True):
                with self.subTest(phase=phase,raised=raised):
                    def send(*args):
                        self.clock.sleep(31)
                        if raised:raise http.ApiError(403,method)
                        return 403,b'private-body'
                    # This is the real bounded credential retry wrapper, without a live issuer.
                    wire=self.tokens.exchange(self.clock.seconds()+30)
                    with patch.object(self.issuer,'send',side_effect=send) as sender:
                        with self.assertRaises(c.exchange.CredentialError) as caught:
                            wire.request(phase,method,url,{},None,self.clock.seconds()+30)
                    self.assertEqual('http',caught.exception.failure_kind)
                    self.assertEqual(403,caught.exception.http_status);sender.assert_called_once()
                    self.assertNotIn('private',str(caught.exception))

    def test_credential_transport_validation_is_not_retried(self):
        wire=self.tokens.exchange(self.clock.seconds()+30)
        with patch.object(self.issuer,'send',side_effect=ValueError('provider redirect forbidden')) as sender:
            with self.assertRaises(c.exchange.CredentialError) as caught:
                wire.request('oidc','GET','https://pipelines.actions.githubusercontent.com/fixed',{},None,
                             self.clock.seconds()+30)
        self.assertEqual('response',caught.exception.failure_kind);sender.assert_called_once()
        self.assertFalse(hasattr(caught.exception,'read_retry'))

    def test_each_stage_retries_only_its_fixed_exchange_and_keeps_identity_checks(self):
        original=self.issuer.send
        calls=[];failed=set()
        def send(method,url,*args):
            phase='oidc' if method=='GET' else 'sts' if url==c.exchange.STS else 'impersonation'
            calls.append((phase,method,url,args[1]))
            if phase not in failed:failed.add(phase);raise ConnectionError('private')
            return original(method,url,*args)
        with patch.object(self.issuer,'send',side_effect=send):token=self.tokens(30)
        self.assertIsInstance(token,http.AccessToken)
        self.assertEqual(['oidc','oidc','sts','sts','impersonation','impersonation'],[x[0] for x in calls])
        for index in (0,2,4):self.assertEqual(calls[index],calls[index+1])
        self.assertEqual(3,len(self.invocation.calls))

    def test_persistent_failure_preserves_closed_diagnostic_and_stops_chain(self):
        with patch.object(self.issuer,'send',return_value=(503,b'private-token')) as send:
            with self.assertRaises(c.exchange.CredentialError) as caught:self.tokens(30)
        self.assertEqual(3,send.call_count)
        detail=c.failure(caught.exception)
        self.assertEqual('OIDC_EXCHANGE_FAILED',detail['credentialCode'])
        self.assertEqual(3,detail['readRetry']['attempts']);self.assertNotIn('private',json.dumps(detail))

    def test_deadline_is_shared_across_credential_retries(self):
        def send(*args):self.clock.sleep(29.9);raise ConnectionError('lost')
        with patch.object(self.issuer,'send',side_effect=send) as sender:
            with self.assertRaises(c.exchange.CredentialError) as caught:self.tokens(30)
        self.assertEqual(1,sender.call_count);self.assertEqual('deadline',c.failure(caught.exception)['readRetry']['stop'])

    def test_denial_malformed_and_identity_drift_are_terminal(self):
        for response in ((403,b'private'),(200,b'{'),(400,b'private')):
            with patch.object(self.issuer,'send',return_value=response) as send:
                with self.assertRaises(c.exchange.CredentialError):self.tokens(30)
            self.assertEqual(1,send.call_count)
        self.issuer.claim_changes={'sha':'b'*40}
        with self.assertRaisesRegex(c.exchange.CredentialError,'OIDC_CLAIMS_REJECTED'):self.tokens(30)
        self.assertEqual(['oidc'],[row['stage'] for row in self.issuer.calls])


class MetadataRetryTest(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.opener=Mock();self.response=Mock(status=200,headers={'Metadata-Flavor':'Google'})
        self.response.read.return_value=b'original';self.response.__enter__=Mock(return_value=self.response)
        self.response.__exit__=Mock(return_value=False);self.request=object()
        self.addCleanup(patch.stopall)
        patch.object(probe.time,'monotonic',side_effect=lambda:self.now).start()
        patch.object(probe.time,'sleep',side_effect=self.sleep).start()
    def sleep(self,seconds):self.now+=seconds
    def read(self):return probe.metadata_read(self.opener,self.request)

    def test_transient_disconnect_and_503_keep_same_metadata_request_and_deadline(self):
        self.opener.open.side_effect=[ConnectionResetError(),probe.urllib.error.HTTPError('fixed',503,'',{},None),self.response]
        self.assertEqual('original',self.read())
        self.assertEqual([3,2.75,2.25],[c.kwargs['timeout'] for c in self.opener.open.call_args_list])
        self.assertTrue(all(c.args==(self.request,) for c in self.opener.open.call_args_list))

    def test_persistent_failure_and_expired_deadline_stop(self):
        self.opener.open.side_effect=ConnectionResetError()
        with self.assertRaises(ValueError):self.read()
        self.assertEqual(3,self.opener.open.call_count)
        self.opener.reset_mock()
        def late(*args,**kwargs):self.now+=3;raise TimeoutError()
        self.opener.open.side_effect=late
        with self.assertRaises(ValueError):self.read()
        self.assertEqual(1,self.opener.open.call_count)

    def test_denial_wrong_header_and_invalid_body_do_not_retry(self):
        for error in (probe.urllib.error.HTTPError('fixed',403,'',{},None),ValueError('redirect')):
            self.opener.reset_mock();self.opener.open.side_effect=error
            with self.assertRaises(type(error)):self.read()
            self.assertEqual(1,self.opener.open.call_count)
        self.opener.open.side_effect=None;self.opener.open.return_value=self.response
        for headers,body in (({},b'ok'),({'Metadata-Flavor':'Google'},b'x'*8193),({'Metadata-Flavor':'Google'},b'\xff')):
            self.opener.reset_mock();self.response.headers=headers;self.response.read.return_value=body
            with self.assertRaises(ValueError):self.read()
            self.assertEqual(1,self.opener.open.call_count)


if __name__=='__main__':unittest.main()
