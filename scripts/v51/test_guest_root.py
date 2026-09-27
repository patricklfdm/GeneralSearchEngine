"""Root transport binding and metadata boundary tests; no privilege or network."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from . import guest_root as root, guest_root_receiver as receiver
from . import performance_model as m
from .test_guest_root_admission import fixture


class RootTransportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.plan = fixture(Path(self.temp.name))[5]
        self.desc = self.plan['delivery']
        self.target = dict(instanceId=self.desc['instanceId'], user=self.plan['access']['user'])

    def test_native_endpoint_stays_closed_before_clock_or_elevation(self):
        with patch.object(root.guest_transport, 'process') as process:
            with self.assertRaisesRegex(ValueError, 'live helper delivery disabled'):
                root.Endpoint(self.target, self.plan).exchange('install', self.desc, b'', time.monotonic()+10)
            process.assert_not_called()

    def test_remote_command_is_closed_root_group_and_isolated_python(self):
        endpoint = root.Endpoint(self.target, self.plan)
        argv = endpoint.remote('query', 'ticket')
        self.assertEqual(argv[:10], ['sudo', '-n', '-u', 'root', '-g', 'root', '--', 'python3', '-I', '-c'])
        self.assertEqual(len(argv), 14)
        compile(argv[10], '<trusted-bootstrap>', 'exec')
        self.assertNotIn('/tmp/', argv[10])

    def test_wrong_pinned_instance_or_user_rejected(self):
        for delta in ({'instanceId':'999'}, {'user':'root'}):
            with self.assertRaisesRegex(ValueError, 'SSH target'):
                root.Endpoint(dict(self.target, **delta), self.plan)

    def test_endpoint_freezes_the_original_root_plan(self):
        endpoint = root.Endpoint(self.target, self.plan)
        self.plan['requestSha256'] = 'f'*64
        self.plan['access']['user'] = 'root'
        self.assertNotEqual(endpoint.plan['requestSha256'], self.plan['requestSha256'])
        self.assertEqual(endpoint.plan['access']['user'], self.target['user'])

    def test_root_receipt_cannot_be_substituted_or_claim_boolean_root(self):
        endpoint = root.Endpoint(self.target, self.plan); endpoint.argv = lambda remote:remote
        good = dict(schema='gse-v51-root-transport-v1', planSha256=m.sha(m.canonical(self.plan)), rootUid=0, answer={'observed':1})
        for delta in ({'planSha256':'f'*64}, {'rootUid':False}, {'rootUid':1001}, {'extra':True}):
            with patch.object(root.guest_transport, 'process', return_value=m.canonical(dict(good, **delta))):
                with self.assertRaisesRegex(ValueError, 'root transport identity'):
                    endpoint._call('query', self.desc, b'', 123, 'ticket')

    def test_bounded_diagnostics_retain_original_transport_failure(self):
        endpoint = root.Endpoint(self.target, self.plan); endpoint.argv = lambda remote:remote
        with patch.object(root.guest_transport, 'process', side_effect=ConnectionError('lost')):
            for _ in range(12):
                with self.assertRaises(ConnectionError): endpoint._call('query', self.desc, b'', 123, 'ticket')
        self.assertEqual(len(endpoint.failures), 8)
        self.assertEqual(endpoint.failures[0]['message'], 'lost')

    def test_nonroot_rejected_before_account_metadata_or_paths(self):
        with patch.object(receiver.os, 'getuid', return_value=1001), patch.object(receiver, 'metadata') as metadata:
            with self.assertRaisesRegex(ValueError, 'root effective identity'):
                receiver.observe(self.plan, {}, 123)
            metadata.assert_not_called()

    def test_changed_invoker_rejected_before_metadata(self):
        with patch.multiple(receiver.os, getuid=lambda:0, geteuid=lambda:0, getgid=lambda:0, getegid=lambda:0), \
             patch.object(receiver.pwd, 'getpwnam', return_value=Mock(pw_uid=1001, pw_gid=1001)), \
             patch.dict(receiver.os.environ, {'SUDO_USER':self.plan['access']['user'], 'SUDO_UID':'1002', 'SUDO_GID':'1001'}), \
             patch.object(receiver, 'metadata') as metadata:
            with self.assertRaisesRegex(ValueError, 'root invoking account'): receiver.observe(self.plan, {}, 123)
            metadata.assert_not_called()

    def test_fixed_metadata_urls_disable_proxy_and_require_flavor(self):
        responses = []
        for value in ('123', 'key', 'TRUE', 'FALSE'):
            response = Mock(status=200, headers={'Metadata-Flavor':'Google'})
            response.read.return_value = value.encode(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
            responses.append(response)
        opener = Mock(); opener.open.side_effect = responses
        with patch.object(receiver.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual(receiver.metadata(time.monotonic()+10)['instanceId'], '123')
        self.assertEqual(build.call_args.args[0].proxies, {})
        for call, suffix in zip(opener.open.call_args_list, ('id', 'attributes/ssh-keys', 'attributes/block-project-ssh-keys', 'attributes/enable-oslogin')):
            request = call.args[0]
            self.assertEqual(request.full_url, 'http://169.254.169.254/computeMetadata/v1/instance/'+suffix)
            self.assertEqual(request.get_header('Metadata-flavor'), 'Google')
            self.assertLessEqual(call.kwargs['timeout'], 2)

    def test_redirect_wrong_flavor_oversize_and_expired_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, 'redirect'): receiver.NoRedirect().redirect_request(None)
        for headers, data, reason in (({}, b'123', 'response'), ({'Metadata-Flavor':'Google'}, b'x'*4097, 'bound')):
            response = Mock(status=200, headers=headers); response.read.return_value = data
            response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
            opener = Mock(); opener.open.return_value = response
            with patch.object(receiver.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaisesRegex(ValueError, reason): receiver.metadata(time.monotonic()+10)
        with patch.object(receiver.urllib.request, 'build_opener') as build:
            with self.assertRaisesRegex(ValueError, 'deadline'): receiver.metadata(time.monotonic()-1)
            build.return_value.open.assert_not_called()


if __name__ == '__main__': unittest.main()
