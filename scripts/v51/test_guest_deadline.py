"""Independent clock epochs, conservative mapping and durable non-renewal."""
import base64
from copy import deepcopy
import io
import os
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import guest_delivery as d, guest_delivery_receiver as r
from . import test_guest_delivery as fixtures

BOOT = '12345678-1234-1234-1234-123456789abc'


class DeadlineTest(unittest.TestCase):
    setUp = fixtures.DeliveryTest.setUp

    def endpoint(self, now, *, outbound=2., inbound=3., offset=10**6):
        outer = self
        class Fixture(d.Endpoint):
            offline = True
            def _call(self, action, value, data, deadline, token):
                self.calls.append((action, deepcopy(value), data, deadline, token))
                if action == 'clock':
                    now[0] += outbound
                    sample = dict(schema='gse-v51-helper-clock-v1', requestSha256=r.sha(r.canonical(value)),
                                  nonce=token, bootId=BOOT, sampledNanos=int((now[0]+offset)*10**9))
                    now[0] += inbound
                    return sample
                ticket = r.decode(base64.b64decode(token))
                return dict(schema='gse-v51-helper-transport-v1', deadlineSha256=r.sha(r.canonical(ticket)),
                            receipt=r.envelope(value, 'SUCCEEDED', inventory=dict(
                                files=len(r.NAMES), decodedBytes=sum(map(len, r.payload(outer.raw, value).values())))))
        result = Fixture(dict(instanceId='123'), self.parent, os.getuid()); result.calls = []
        return result

    def test_unrelated_epochs_and_asymmetric_latency_never_add_budget(self):
        for offset in (-900, 0, 10**6):
            for outbound, inbound in ((2, 3), (4, 1), (0, 5)):
                with self.subTest(offset=offset, outbound=outbound):
                    now = [1000.]; endpoint = self.endpoint(now, outbound=outbound, inbound=inbound, offset=offset)
                    with patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])):
                        endpoint.exchange('install', self.value, self.raw, 1010.)
                        # Independent reference timeline: remote real deadline is 1010+offset.
                        expiry = endpoint.budget['expiresNanos']/10**9
                        self.assertEqual(expiry, 1010+offset-inbound)
                        self.assertLessEqual(expiry, 1010+offset)
                        now[0] += 1
                        endpoint.exchange('query', self.value, b'', 1010.)
                    self.assertEqual([v[0] for v in endpoint.calls], ['clock', 'install', 'query'])
                    self.assertEqual(endpoint.calls[1][4], endpoint.calls[2][4])
                    self.assertTrue(all(v[3] == 1010. for v in endpoint.calls))

    def test_original_deadline_and_request_cannot_change(self):
        now = [1000.]; endpoint = self.endpoint(now)
        with patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])):
            endpoint.exchange('install', self.value, self.raw, 1010.)
            for deadline in (1009., 1011.):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    endpoint.exchange('query', self.value, b'', deadline)
            value = dict(self.value, diskId='789')
            with self.assertRaisesRegex(ValueError, 'changed'): endpoint.exchange('query', value, b'', 1010.)
        self.assertEqual(len(endpoint.calls), 2)

    def test_failed_clock_connection_never_sends_payload_or_renews(self):
        now = [1000.]; endpoint = self.endpoint(now)
        with patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])), \
             patch.object(endpoint, '_call', side_effect=ConnectionError('clock reply lost')) as call:
            with self.assertRaises(ConnectionError): endpoint.exchange('install', self.value, self.raw, 1010.)
            with self.assertRaisesRegex(ValueError, 'never renew'): endpoint.exchange('query', self.value, b'', 1010.)
        self.assertEqual(call.call_count, 1); self.assertEqual(call.call_args.args[0], 'clock')
        self.assertEqual(call.call_args.args[2], b''); self.assertFalse(self.path.exists())

    def test_expired_or_backwards_controller_sample_does_not_install(self):
        for outbound, inbound in ((4., 7.), (-2., 0.)):
            now = [1000.]; endpoint = self.endpoint(now, outbound=outbound, inbound=inbound)
            with patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])):
                with self.assertRaisesRegex(ValueError, 'round-trip'): endpoint.exchange('install', self.value, self.raw, 1010.)
                now[0] = 1005.
                with self.assertRaisesRegex(ValueError, 'never renew'): endpoint.exchange('query', self.value, b'', 1010.)
            self.assertEqual([v[0] for v in endpoint.calls], ['clock'])

    def test_foreign_nonce_request_and_malformed_clock_are_rejected(self):
        for change in ({'nonce':'0'*32}, {'requestSha256':'0'*64}, {'bootId':'unknown'},
                       {'sampledNanos':True}, {'sampledNanos':-1}, {'sampledNanos':1.5},
                       {'sampledNanos':float('inf')}, {'extra':1}):
            now = [1000.]; endpoint = self.endpoint(now); original = endpoint._call
            def changed(*args): return dict(original(*args), **change)
            with self.subTest(change=change), patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])), \
                 patch.object(endpoint, '_call', side_effect=changed):
                with self.assertRaises(ValueError): endpoint.exchange('install', self.value, self.raw, 1010.)
            self.assertEqual(len(endpoint.calls), 1)

    def test_late_or_wrong_transport_envelope_cannot_pass(self):
        for change in ({'deadlineSha256':'0'*64}, {'schema':'other'}, {'receipt':[]}, {'extra':1}, None):
            now = [1000.]; endpoint = self.endpoint(now); original = endpoint._call
            def changed(action, *args):
                result = original(action, *args)
                if action != 'clock':
                    if change is None: now[0] = 1011.
                    else: result.update(change)
                return result
            with self.subTest(change=change), patch.object(d, 'time', SimpleNamespace(monotonic=lambda:now[0])), \
                 patch.object(endpoint, '_call', side_effect=changed):
                with self.assertRaises(ValueError): endpoint.exchange('install', self.value, self.raw, 1010.)

    def ticket(self):
        with patch.object(r, 'boot_identity', return_value=BOOT): sample = r.clock_sample(self.value, 'f'*32)
        return dict(schema='gse-v51-helper-deadline-v1', sample=sample, expiresNanos=sample['sampledNanos']+10**10)

    def test_durable_ticket_rejects_renewal_after_process_reconnect(self):
        ticket = self.ticket(); deadline = ticket['expiresNanos']/10**9
        with patch.object(r, 'boot_identity', return_value=BOOT):
            answer = r.install(self.parent, self.value, os.getuid(), io.BytesIO(self.raw), deadline, budget=ticket)
            self.assertEqual(answer['state'], 'SUCCEEDED')
            self.assertEqual(r.decode((self.path/'deadline.json').read_bytes()), ticket)
            self.assertEqual(r.query(self.parent, self.value, os.getuid(), budget=deepcopy(ticket)), answer)
            renewed = dict(ticket, expiresNanos=ticket['expiresNanos']+10**9)
            with self.assertRaisesRegex(ValueError, 'changed'): r.query(self.parent, self.value, os.getuid(), budget=renewed)
            with self.assertRaisesRegex(ValueError, 'changed'):
                r.install(self.parent, self.value, os.getuid(), io.BytesIO(self.raw), renewed['expiresNanos']/10**9, budget=renewed)

    def test_missing_ticket_is_uncertain_and_never_adopted(self):
        ticket = self.ticket(); self.path.mkdir(mode=0o700)
        with patch.object(r, 'boot_identity', return_value=BOOT):
            answer = r.install(self.parent, self.value, os.getuid(), io.BytesIO(self.raw),
                               ticket['expiresNanos']/10**9, budget=ticket)
        self.assertEqual(answer['state'], 'UNCERTAIN'); self.assertEqual(list(self.path.iterdir()), [])

    def test_consumed_ticket_without_request_is_uncertain(self):
        ticket = self.ticket(); self.path.mkdir(mode=0o700); r.publish(self.path/'deadline.json', ticket)
        with patch.object(r, 'boot_identity', return_value=BOOT):
            self.assertEqual(r.query(self.parent, self.value, os.getuid(), budget=ticket)['state'], 'UNCERTAIN')

    def test_reboot_expiry_and_backwards_guest_clock_fail_before_claim(self):
        ticket = self.ticket()
        for boot, now in (('ffffffff-ffff-ffff-ffff-ffffffffffff', ticket['sample']['sampledNanos']),
                          (BOOT, ticket['expiresNanos']), (BOOT, ticket['sample']['sampledNanos']-1)):
            with self.subTest(boot=boot, now=now), patch.object(r, 'boot_identity', return_value=boot), \
                 patch.object(r, 'time', SimpleNamespace(monotonic_ns=lambda:now)):
                with self.assertRaises(ValueError):
                    r.install(self.parent, self.value, os.getuid(), io.BytesIO(self.raw),
                              ticket['expiresNanos']/10**9, budget=ticket)
            self.assertFalse(self.path.exists())

    def test_invalid_budget_and_unbounded_durations_rejected(self):
        ticket = self.ticket()
        for change in ({'expiresNanos':True}, {'expiresNanos':float('nan')}, {'extra':1},
                       {'expiresNanos':ticket['sample']['sampledNanos']},
                       {'expiresNanos':ticket['sample']['sampledNanos']+r.MAX_DEADLINE_NANOS+1}):
            with self.subTest(change=change), self.assertRaises(ValueError): r.validate_budget(dict(ticket, **change), self.value)

    def test_actual_receiver_processes_with_offset_and_lost_reply(self):
        class ProcessEndpoint(d.Endpoint):
            offline = True
            def argv(inner, remote):
                # Fixture-only clock/boot producer; no claim of native Linux or SSH.
                source = remote[3].rsplit("if __name__ == '__main__':", 1)[0]
                source += ("\nfrom types import SimpleNamespace\n"
                           "_clock = time\n"
                           "time = SimpleNamespace(monotonic=lambda: _clock.monotonic()+1000000, "
                           "monotonic_ns=lambda: _clock.monotonic_ns()+1000000000000000)\n"
                           "boot_identity = lambda: '"+BOOT+"'\nmain()\n")
                return [sys.executable, *remote[1:3], source, *remote[4:]]
            def _call(inner, action, *args):
                calls.append(action); answer = super()._call(action, *args)
                if action == 'install': raise ConnectionError('lost completed install response')
                return answer
        calls = []; endpoint = ProcessEndpoint(dict(instanceId='123'), self.parent, os.getuid())
        deadline = time.monotonic()+10
        answer = d.deliver(endpoint, self.value, self.raw, deadline)
        self.assertEqual(answer['state'], 'SUCCEEDED'); self.assertEqual(calls, ['clock', 'install', 'query'])
        self.assertEqual(endpoint.exchange('check', self.value, b'', deadline), answer)
        self.assertEqual(r.decode((self.path/'deadline.json').read_bytes()), endpoint.budget)
        self.assertEqual(list(self.path.rglob('__pycache__')), [])


if __name__ == '__main__': unittest.main()
