"""Exercise the shared HTTP transport through V5.2 retries, without cloud I/O."""
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import MagicMock, Mock, patch
from scripts.v51 import cloud_http as h
from scripts.v51.test_cloud_http_pool import Connection, Response
from . import cloud_read_retry as retry, cloud_iap


class TransportDeadlineTest(unittest.TestCase):
    def setUp(self):
        self.now=100.;self.connections=[];self.responses=[];self.waits=[]
        self.enterContext(patch.object(h.time,'monotonic',side_effect=lambda:self.now))
        self.enterContext(patch.object(h.time,'sleep',side_effect=self.sleep))
        self.enterContext(patch.object(h.urllib.request,'getproxies',return_value={}))
        self.enterContext(patch.object(h,'HTTPSConnection',side_effect=self.connect))
        self.output=io.StringIO();self.enterContext(redirect_stdout(self.output))
        self.network=h.Network();self.addCleanup(self.network.close)
        self.api=retry.Api(transport=self.network,tokens=lambda _:h.AccessToken('private-token',1000),clock=lambda:self.now)

    def sleep(self,seconds):self.waits.append(seconds);self.now+=seconds
    def connect(self,host,timeout):
        connection=Connection(host,timeout);self.connections.append(connection)
        if self.responses:connection.response=self.responses.pop(0)
        return connection
    def response(self,status=200,delay=0,data=b'{}',error=None):
        response=Response(data,status)
        def read(maximum):
            self.now+=delay
            if error is not None:raise error
            return data[:maximum]
        response.read=read;return response
    def send(self,method='GET',timeout=30,maximum=4096):
        return self.network.send(method,'https://compute.googleapis.com/fixed',{},None,timeout,maximum)

    def test_late_success_has_typed_timeout_and_closed_socket(self):
        self.responses=[self.response(delay=30.001)]
        with self.assertRaises(TimeoutError) as caught:self.send()
        self.assertIs(type(caught.exception),TimeoutError)
        self.assertEqual('timeout',retry.reason(caught.exception))
        self.assertEqual('IAP_ORIGINAL_CONNECT_TIMEOUT',cloud_iap._safe(caught.exception))
        self.assertTrue(self.connections[0].closed);self.assertFalse(self.network.connections)

    def test_waiting_for_transport_lock_is_bounded_before_any_request(self):
        lock=MagicMock();lock.acquire.return_value=False
        with patch.object(self.network,'lock',lock):
            with self.assertRaises(TimeoutError):self.send()
        lock.acquire.assert_called_once_with(timeout=30)
        lock.release.assert_not_called();self.assertEqual([],self.connections)

    def test_expired_clock_after_lock_never_opens_connection(self):
        lock=MagicMock()
        def acquire(**kwargs):self.now=131;return True
        lock.acquire.side_effect=acquire
        with patch.object(self.network,'lock',lock):
            with self.assertRaises(TimeoutError):self.send()
        lock.release.assert_called_once();self.assertEqual([],self.connections)

    def test_socket_timeout_is_not_demoted_to_generic_connection_error(self):
        self.responses=[self.response(error=TimeoutError('private-provider-detail'))]
        with self.assertRaises(TimeoutError) as caught:self.send()
        self.assertNotIn('private',str(caught.exception));self.assertTrue(self.connections[0].closed)

    def test_late_http_denial_keeps_status_and_cannot_enter_iap_retry(self):
        for status in (400,401,403,404,409,412,422):
            with self.subTest(status=status):
                self.responses=[self.response(status,30.001,b'private-body')]
                with self.assertRaises(h.ApiError) as caught:self.send()
                self.assertEqual(status,caught.exception.status)
                self.assertIsNone(retry.reason(caught.exception))
                self.assertFalse(cloud_iap._retry_admission(caught.exception,attempt_deadline=self.now))
                self.assertTrue(self.connections[-1].closed)
                self.assertNotIn('private',str(caught.exception))

    def test_denial_headers_survive_body_read_timeout(self):
        for status in (401,403):
            self.responses=[self.response(status,error=TimeoutError('private-body'))]
            with self.assertRaises(h.ApiError) as caught:self.send()
            self.assertEqual(status,caught.exception.status)
            self.assertTrue(self.connections[-1].closed)

    def test_truncated_denial_keeps_status_instead_of_becoming_connection_failure(self):
        response=self.response(403);response.length=10;self.responses=[response]
        with self.assertRaises(h.ApiError) as caught:self.send()
        self.assertEqual(403,caught.exception.status);self.assertIsNone(retry.reason(caught.exception))
        self.assertTrue(self.connections[0].closed)

    def test_late_redirect_is_terminal(self):
        self.responses=[self.response(302,30.001)]
        with self.assertRaisesRegex(ValueError,'redirect'):self.send()
        self.assertEqual(1,len(self.connections));self.assertTrue(self.connections[0].closed)

    def test_oversized_late_body_stays_validation_failure(self):
        self.responses=[self.response(delay=30.001,data=b'x'*65)]
        with self.assertRaisesRegex(ValueError,'response size/type'):
            self.api.call('GET','https://compute.googleapis.com/fixed',deadline=130,maximum=64)
        self.assertEqual(1,len(self.connections));self.assertEqual([],self.waits)

    def test_transport_timeout_can_retry_get_inside_original_deadline(self):
        self.responses=[self.response(delay=30.001),self.response(data=b'{"ok":true}')]
        self.assertEqual({'ok':True},self.api.call('GET','https://compute.googleapis.com/fixed',deadline=160))
        self.assertEqual([.25],self.waits);self.assertEqual(2,len(self.connections))
        self.assertLess(self.connections[1].timeout,30)
        self.assertEqual([1,1],[len(c.calls) for c in self.connections])

    def test_admission_deadline_exhaustion_reaches_existing_iap_retry(self):
        self.responses=[self.response(delay=30.001)]
        with self.assertRaises(retry.ReadError) as caught:
            self.api.call('GET','https://compute.googleapis.com/fixed',deadline=130)
        self.assertEqual(dict(code='V52_READ_DEADLINE',scope='provider-read',attempts=1,reason='timeout',stop='deadline'),caught.exception.detail)
        self.assertTrue(cloud_iap._retry_admission(caught.exception,attempt_deadline=130))
        self.assertEqual([],self.waits);self.assertEqual(1,len(self.connections))

    def test_mutation_late_success_or_denial_never_replays(self):
        # The fixture owns mutation authorization; production still requires its scoped adapter.
        self.api.authorize=lambda *args:None
        for method in ('POST','DELETE'):
            for status in (200,401,403,503):
                before=len(self.connections);self.responses=[self.response(status,30.001)]
                with self.subTest(method=method,status=status),self.assertRaises(TimeoutError if status==200 else h.ApiError):
                    self.api.call(method,'https://compute.googleapis.com/fixed',deadline=self.now+30)
                self.assertEqual(before+1,len(self.connections));self.assertEqual(1,len(self.connections[-1].calls))
        self.assertEqual([],self.waits)

    def test_generic_api_expiry_before_and_after_credentials_has_no_wire_call(self):
        transport=Mock();tokens=Mock(return_value='private-token')
        api=h.Api(transport=transport,tokens=tokens,clock=lambda:self.now)
        with self.assertRaises(TimeoutError):api.call('GET','https://compute.googleapis.com/fixed',deadline=100)
        tokens.assert_not_called();transport.send.assert_not_called()
        def delayed(_):self.now=131;return 'private-token'
        tokens.side_effect=delayed
        with self.assertRaises(TimeoutError):api.call('GET','https://compute.googleapis.com/fixed',deadline=130)
        transport.send.assert_not_called()

    def test_generic_api_late_denial_retains_status_without_auth_refresh(self):
        transport=Mock();api=h.Api(transport=transport,tokens=lambda _:'private-token',clock=lambda:self.now)
        for status in (401,403,503):
            transport.reset_mock()
            def send(*args):self.now+=31;return status,b''
            transport.send.side_effect=send
            with self.subTest(status=status),self.assertRaises(h.ApiError) as caught:
                api.call('GET','https://compute.googleapis.com/fixed',deadline=self.now+30)
            self.assertEqual(status,caught.exception.status);transport.send.assert_called_once()

    def test_invalid_timeout_configuration_is_terminal_before_io(self):
        for value in (True,0,-1,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):self.send(timeout=value)
        transport=Mock();api=h.Api(transport=transport,tokens=lambda _:self.fail('invalid deadline reached credentials'))
        for value in (True,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):
                api.call('GET','https://compute.googleapis.com/fixed',deadline=value)
        self.assertEqual([],self.connections);transport.send.assert_not_called()

    def test_unpooled_late_success_and_denial_have_same_classification(self):
        opener=Mock()
        with patch.object(h.urllib.request,'getproxies',return_value={'https':'http://test-proxy'}), \
             patch.object(h.urllib.request,'proxy_bypass',return_value=False), \
             patch.object(h.urllib.request,'build_opener',return_value=opener):
            for status in (200,401,403):
                opener.reset_mock();opener.open.return_value=self.response(status,30.001)
                with self.subTest(status=status),self.assertRaises(TimeoutError if status==200 else h.ApiError):self.send()
                opener.open.assert_called_once()
            opener.open.side_effect=h.urllib.error.URLError(TimeoutError('private-url'))
            with self.assertRaises(TimeoutError) as caught:self.send()
            self.assertNotIn('private',str(caught.exception))

    def test_unpooled_http_error_keeps_denial_without_reading_body(self):
        opener=Mock()
        with patch.object(h.urllib.request,'getproxies',return_value={'https':'http://test-proxy'}), \
             patch.object(h.urllib.request,'proxy_bypass',return_value=False), \
             patch.object(h.urllib.request,'build_opener',return_value=opener):
            for status in (401,403,503):
                body=Mock()
                def reject(*args,**kwargs):
                    self.now+=30.001
                    raise h.urllib.error.HTTPError('https://private',status,'private',{},body)
                opener.open.side_effect=reject
                with self.subTest(status=status),self.assertRaises(h.ApiError) as caught:self.send()
                self.assertEqual(status,caught.exception.status);body.read.assert_not_called()
                body.close.assert_called_once();self.assertNotIn('private',str(caught.exception))


if __name__=='__main__':unittest.main()
