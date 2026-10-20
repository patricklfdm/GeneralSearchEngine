"""Deterministic scoped read/heartbeat interleavings; no live provider I/O."""
from copy import deepcopy
import threading
import unittest
from unittest.mock import patch, Mock
from scripts.v51 import cloud_http as http
from . import cloud_authority as a, cloud_control as c, cloud_provider as p, cloud_wire_policy as w
from . import cloud_identity as identity, cloud_storage_diagnostics as diagnostics
from .cloud_provider_offline import Server
from .test_cloud_identity import bound_request
from .test_cloud_provider import configuration
from .evidence import encoded


class ObservedLock:
    """Record whether the competing heartbeat can enter, without timing guesses."""
    def __init__(self, lock):
        self.lock = lock
        self.attempted = threading.Event()
        self.contended = None

    def acquire(self, blocking=True, timeout=-1):
        if threading.current_thread().name == 'test-heartbeat' and self.contended is None:
            acquired = self.lock.acquire(False)
            self.contended = not acquired
            self.attempted.set()
            if acquired:
                return True
        return self.lock.acquire(blocking, timeout)

    def release(self):
        self.lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class ControlReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = bound_request()
        server = Server(configuration())
        api = w.ScopedOfflineApi(server, cls.req, wall=lambda: 1000)
        store = p.Store(configuration(), api)
        provider = p.Provider(store, cls.req, wall=lambda: 1000, sleep=server.sleep)
        owner = c.OfflineOwner(store, provider, cls.req, wall=lambda: 1000)
        with patch.object(http.Network, 'send', side_effect=AssertionError('live network forbidden')):
            owner.prepare(previous_cost=0, cost=1)
        cls.snapshot = deepcopy((server.objects, server.resources, server.operations, server.serial,
                                 owner.lease, owner.generation))

    def setUp(self):
        self.now = 1000
        self.server = Server(configuration())
        (self.server.objects, self.server.resources, self.server.operations, self.server.serial,
         lease, generation) = deepcopy(self.snapshot)
        self.api = w.ScopedOfflineApi(self.server, self.req, wall=lambda: self.now)
        self.store = p.Store(configuration(), self.api)
        self.provider = p.Provider(self.store, self.req, wall=lambda: self.now, sleep=self.server.sleep)
        self.owner = c.OfflineOwner(self.store, self.provider, self.req, wall=lambda: self.now)
        self.owner.lease, self.owner.generation = lease, generation
        self.claim = a.resource_claim(lease)
        guard = patch.object(http.Network, 'send', side_effect=AssertionError('live network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def interleave(self, read):
        lock = ObservedLock(self.api.lock)
        self.api.lock = lock
        metadata = threading.Event()
        renewed = threading.Event()
        errors = []
        original = self.api.call
        reader = threading.current_thread()
        intercepted = []
        generation = self.owner.generation

        def heartbeat():
            try:
                if not metadata.wait(10):
                    raise AssertionError('reader never returned metadata')
                self.owner.renew()
            except BaseException as error:
                errors.append(error)
            finally:
                renewed.set()

        def call(method, endpoint, *args, **kwargs):
            result = original(method, endpoint, *args, **kwargs)
            if (threading.current_thread() is reader and not intercepted and method == 'GET' and
                    endpoint == self.store.endpoint(a.LEASE)):
                intercepted.append(True)
                metadata.set()
                self.assertTrue(lock.attempted.wait(10), 'heartbeat did not reach API lock')
                if not lock.contended:
                    # Original implementation lets renewal complete in the gap.
                    self.assertTrue(renewed.wait(10), 'heartbeat did not complete')
            return result

        worker = threading.Thread(target=heartbeat, name='test-heartbeat', daemon=True)
        worker.start()
        try:
            with patch.object(self.api, 'call', side_effect=call):
                result = read()
        finally:
            metadata.set()
            worker.join(15)
        self.assertFalse(worker.is_alive(), 'owner/API lock order deadlocked')
        self.assertEqual([], errors)
        self.assertTrue(intercepted)
        self.assertTrue(lock.contended)
        self.assertGreater(self.owner.generation, generation)
        self.assertEqual(self.claim, self.owner.resource_claim())
        self.assertEqual('ACTIVE', identity.current(self.provider, self.claim)['phase'])
        return result, generation

    def test_pinned_object_read_blocks_renewal_until_body_is_validated(self):
        result, generation = self.interleave(lambda: self.store.get(a.LEASE))
        self.assertEqual(generation, result[0])
        self.assertEqual(self.claim, a.resource_claim(result[1]))

    def test_identity_read_survives_heartbeat_without_retry_or_deadlock(self):
        result, _ = self.interleave(lambda: identity.current(self.provider, self.claim))
        self.assertEqual('ACTIVE', result['phase'])
        # The one heartbeat CAS and its nested policy reads must remain reentrant.
        writes = [e for e in self.server.events if e['method'] != 'GET']
        self.assertEqual(1, len(writes))

    def test_api_lock_wait_uses_original_deadline_and_sends_nothing_when_exhausted(self):
        original = self.api.lock
        waits = []
        server = self.server

        class DelayedLock:
            def acquire(self, blocking=True, timeout=-1):
                waits.append(timeout)
                acquired = original.acquire(blocking, timeout)
                server.seconds += 31
                return acquired

            def release(self):
                original.release()

            def __enter__(self):
                self.acquire()
                return self

            def __exit__(self, *args):
                self.release()

        self.api.lock = DelayedLock()
        with self.assertRaises(TimeoutError):
            self.store.get(a.LEASE)
        self.assertEqual([30], waits)
        self.assertEqual([], self.server.events)
        self.assert_lock_free(original)

    def assert_lock_free(self, lock=None):
        lock = self.api.lock if lock is None else lock
        result = []
        def other():
            acquired = lock.acquire(False)
            result.append(acquired)
            if acquired:
                lock.release()
        worker = threading.Thread(target=other, daemon=True)
        worker.start()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual([True], result)

    def test_failed_lock_acquisition_neither_dispatches_nor_releases_another_owner(self):
        lock = Mock()
        lock.acquire.return_value = False
        with patch.object(self.api, 'lock', lock), self.assertRaises(TimeoutError):
            self.store.get(a.LEASE)
        lock.acquire.assert_called_once_with(timeout=30)
        lock.release.assert_not_called()
        self.assertEqual([], self.server.events)
        self.assert_lock_free()

    def test_external_replacement_or_deletion_is_not_retried_or_reported_absent(self):
        for status in (404, 412):
            with self.subTest(status=status):
                self.server.events.clear()
                self.server.fault = lambda stage, event: (
                    (status, b'') if stage == 'before' and 'alt=media' in event['url'] else None)
                with self.assertRaises(http.ApiError) as raised:
                    self.store.get(a.LEASE)
                self.assertEqual(status, raised.exception.status)
                self.assertEqual(2, len(self.server.events))
                self.assertTrue(all(e['method'] == 'GET' for e in self.server.events))
                self.assert_lock_free()

    def test_truncated_media_releases_lock_and_retains_closed_cause(self):
        self.server.fault = lambda stage, event: (
            (200, b'{}') if stage == 'before' and 'alt=media' in event['url'] else None)
        with self.assertRaises(ValueError) as raised:
            self.store.get(a.LEASE)
        self.assertEqual('V52_CONTROL_READ_TRUNCATED', diagnostics.reason(raised.exception))
        self.assert_lock_free()

    def test_actual_absence_and_expiry_have_distinct_closed_codes(self):
        self.server.objects.pop(a.LEASE)
        with self.assertRaises(ValueError) as absent:
            identity.current(self.provider, self.claim)
        self.assertEqual('V52_CONTROL_LEASE_ABSENT', diagnostics.reason(absent.exception))
        self.assert_lock_free()
        self.server.objects[a.LEASE] = deepcopy(self.snapshot[0][a.LEASE])
        self.now = 1060
        with self.assertRaises(ValueError) as expired:
            identity.current(self.provider, self.claim)
        self.assertEqual('V52_CONTROL_LEASE_INACTIVE', diagnostics.reason(expired.exception))

    def test_external_claim_change_still_rejects_after_a_valid_pinned_read(self):
        changed = deepcopy(self.claim)
        changed['attempt'] = 'f'*32
        with self.assertRaisesRegex(ValueError, 'allocation changed'):
            identity.current(self.provider, changed)
        self.assertEqual([], [e for e in self.server.events if e['method'] != 'GET'])
        self.assert_lock_free()

    def test_malformed_metadata_remains_terminal_and_releases_lock(self):
        self.server.fault = lambda stage, event: (
            (200, encoded(dict(name='foreign'))) if stage == 'before' else None)
        with self.assertRaises(ValueError):
            self.store.get(a.LEASE)
        self.assertEqual(1, len(self.server.events))
        self.assert_lock_free()

    def test_generation_rejection_is_distinct_from_absent_lease(self):
        self.store.get(a.LEASE)
        endpoint = p.query(self.store.endpoint(a.LEASE), alt='media', generation=1, ifGenerationMatch=1)
        try:
            self.api.call('GET', endpoint, deadline=self.api.clock()+30)
        except ValueError as error:
            self.assertEqual('V52_CONTROL_READ_GENERATION', diagnostics.reason(error))
            self.assertEqual('cloud_wire_policy', diagnostics.origin(error)['module'])
        else:
            self.fail('unobserved generation accepted')


if __name__ == '__main__':
    unittest.main()
