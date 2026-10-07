"""No credentials or network: exercise response/socket lifecycle and no replay."""
import http.client
import unittest
from unittest.mock import Mock, patch
from . import cloud_http as h


class Response:
    def __init__(self, data=b'{}', status=200, close=False):
        self.data,self.status,self.will_close=data,status,close
        self.reads=[];self.length=0
    def read(self, maximum):
        self.reads.append(maximum);return self.data[:maximum]
    def __enter__(self):return self
    def __exit__(self,*args):pass


class Connection:
    def __init__(self, host, timeout):
        self.host,self.timeout=host,timeout;self.sock=Mock();self.calls=[]
        self.response=Response();self.error=None;self.closed=False
    def request(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        if self.error:raise self.error
    def getresponse(self):return self.response
    def close(self):self.closed=True;self.sock=None


class PoolTest(unittest.TestCase):
    def setUp(self):
        self.connections=[];self.now=100
        def connect(host,timeout):
            conn=Connection(host,timeout);self.connections.append(conn);return conn
        self.factory=self.enterContext(patch.object(h,'HTTPSConnection',side_effect=connect))
        self.enterContext(patch.object(h.urllib.request,'getproxies',return_value={}))
        self.enterContext(patch.object(h.time,'monotonic',side_effect=lambda:self.now))
        self.network=h.Network();self.addCleanup(self.network.close)
    def send(self,method='GET',host='storage.googleapis.com',token='first',maximum=4096):
        return self.network.send(method,'https://'+host+'/object?generation=1',
                                 {'Authorization':'Bearer '+token},b'{}' if method=='POST' else None,5,maximum)
    def test_same_origin_reuses_socket_with_fresh_headers_and_timeout(self):
        self.send();self.now+=1;self.send(token='renewed')
        self.assertEqual(1,len(self.connections));conn=self.connections[0]
        self.assertEqual(2,len(conn.calls));self.assertEqual('Bearer renewed',conn.calls[1][1]['headers']['Authorization'])
        self.assertEqual('/object?generation=1',conn.calls[1][0][1]);conn.sock.settimeout.assert_called_once_with(5)
    def test_two_origins_have_separate_connections(self):
        self.send();self.send(host='compute.googleapis.com');self.send()
        self.assertEqual(['storage.googleapis.com','compute.googleapis.com'],[c.host for c in self.connections])
        self.assertEqual([2,1],[len(c.calls) for c in self.connections])
    def test_idle_socket_retired_before_sending(self):
        self.send();self.now+=10;self.send()
        self.assertTrue(self.connections[0].closed);self.assertEqual(2,len(self.connections))
    def test_mutation_uses_fresh_connection_and_lost_reply_is_never_replayed(self):
        self.send();original=self.factory.side_effect
        def connect(*args,**kwargs):
            conn=original(*args,**kwargs);conn.error=OSError('private credential');return conn
        self.factory.side_effect=connect
        with self.assertRaisesRegex(ConnectionError,'original operation remains unresolved') as caught:self.send('POST')
        self.assertNotIn('private',str(caught.exception));self.assertEqual(2,len(self.connections))
        self.assertEqual([1,1],[len(c.calls) for c in self.connections]);self.assertTrue(all(c.closed for c in self.connections))
    def test_reused_get_failure_discards_socket_without_replay(self):
        self.send();self.connections[0].error=http.client.RemoteDisconnected('closed')
        with self.assertRaises(ConnectionError):self.send()
        self.assertEqual(1,len(self.connections));self.assertFalse(self.network.connections)
        self.send();self.assertEqual(2,len(self.connections))
    def test_http_error_body_is_redacted_but_bounded_drained_connection_reusable(self):
        self.send();self.connections[0].response=Response(b'sensitive',401)
        self.assertEqual((401,b''),self.send());self.assertEqual([4097],self.connections[0].response.reads)
        self.send();self.assertEqual(1,len(self.connections))
    def test_oversized_response_and_server_close_discard_connection(self):
        for data,close in ((b'123456',False),(b'{}',True)):
            self.send();conn=self.connections[-1];conn.response=Response(data,close=close)
            self.send(maximum=4);self.assertTrue(conn.closed);self.assertFalse(self.network.connections)
    def test_redirect_never_followed_and_socket_is_closed(self):
        self.send();self.connections[0].response=Response(status=302)
        with self.assertRaisesRegex(ValueError,'redirect'):self.send()
        self.assertEqual(1,len(self.connections));self.assertFalse(self.network.connections)
    def test_truncated_content_length_is_rejected_even_if_json_looks_complete(self):
        self.send();self.connections[0].response.length=100
        with self.assertRaises(ConnectionError):self.send()
        self.assertFalse(self.network.connections)
    def test_late_response_cannot_be_accepted_or_reused(self):
        self.send();response=self.connections[0].response
        def late(maximum):self.now+=6;return b'{}'
        response.read=late
        with self.assertRaisesRegex(ValueError,'late response'):self.send()
        self.assertFalse(self.network.connections)
    def test_close_releases_all_origins_and_later_owner_can_open_fresh(self):
        self.send();self.send(host='compute.googleapis.com');self.network.close()
        self.assertTrue(all(c.closed for c in self.connections));self.assertFalse(self.network.connections)
        self.send();self.assertEqual(3,len(self.connections))
    def test_proxy_keeps_existing_transport_without_direct_connection(self):
        with patch.object(h.urllib.request,'getproxies',return_value={'https':'http://proxy'}),\
             patch.object(h.urllib.request,'proxy_bypass',return_value=False),\
             patch.object(self.network,'_unpooled',return_value=(200,b'{}')) as legacy:
            self.assertEqual((200,b'{}'),self.send());legacy.assert_called_once()
        self.assertFalse(self.connections)
    def test_foreign_host_and_port_rejected_before_transport(self):
        api=h.Api(transport=self.network,tokens=Mock(side_effect=AssertionError('unexpected credential')))
        for host in ('storage.googleapis.com.evil','storage.googleapis.com:443','user@storage.googleapis.com'):
            with self.subTest(host=host),self.assertRaises(ValueError):
                api.call('GET','https://'+host+'/object',deadline=105)
        self.assertFalse(self.connections)
    def test_credential_hosts_keep_unpooled_network_after_their_own_admission(self):
        with patch.object(self.network,'_unpooled',return_value=(200,b'{}')) as legacy:
            for host in ('pipelines.actions.githubusercontent.com','sts.googleapis.com','iamcredentials.googleapis.com'):
                self.assertEqual((200,b'{}'),self.send(host=host))
            self.assertEqual(3,legacy.call_count)
        self.assertFalse(self.connections)


if __name__=='__main__':unittest.main()
