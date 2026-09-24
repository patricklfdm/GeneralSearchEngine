import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from . import remote_command as c, performance_model as m


class RemoteCommandTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.owner = c.binding('a'*40, 'b'*64, 'c'*32, 'node-1')
        self.store = c.CommandStore(Path(self.temp.name)/'guest', self.owner, create=True)
        self.req = c.request(self.owner, 'd'*32, 'window', {'name': 'baseline-a'})

    def test_reopen_returns_durable_result_without_reexecuting_handler(self):
        calls = []
        result = self.store.execute(self.req, lambda *args: calls.append(1) or {'outcome': 'SUCCESS'})
        reopened = c.CommandStore(self.store.root, self.owner)
        self.assertEqual(result, reopened.execute(self.req, lambda *args: self.fail('replayed')))
        self.assertEqual([1], calls)
        self.assertEqual('SUCCEEDED', result['state'])

    def test_changed_payload_or_identity_cannot_reuse_claim(self):
        self.store.execute(self.req, lambda *args: {})
        for changed in (dict(self.req, payload={'name':'baseline-b'}), dict(self.req, command='fault'),
                        dict(self.req, bindingSha256='0'*64), dict(self.req, commandId='../bad')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.store.execute(changed, lambda *args: self.fail('executed'))
        with self.assertRaises(ValueError):
            c.CommandStore(self.store.root, dict(self.owner, attempt='0'*32))

    def test_crash_between_claim_and_request_never_reexecutes(self):
        self.store.command_path(self.req).mkdir()
        self.assertEqual('UNCERTAIN', self.store.execute(self.req, lambda *args: self.fail('replayed'))['state'])

    def test_crash_after_forced_request_never_reexecutes(self):
        path = self.store.command_path(self.req)
        path.mkdir()
        c.write_once(path/'request.json', self.req)
        self.assertEqual('UNCERTAIN', self.store.execute(self.req, lambda *args: self.fail('replayed'))['state'])

    def test_torn_receipt_rejected_not_repaired(self):
        self.store.execute(self.req, lambda *args: {})
        path = self.store.command_path(self.req)/'terminal.json'
        path.write_text('{"state":')
        with self.assertRaises(json.JSONDecodeError):
            self.store.execute(self.req, lambda *args: self.fail('replayed'))
        self.assertEqual('{"state":', path.read_text())

    def test_parallel_executor_rejects_second_command_before_claim(self):
        entered, release = threading.Event(), threading.Event()
        def handler(*args):
            entered.set()
            self.assertTrue(release.wait(3))
            return {}
        errors = []
        def execute():
            try: self.store.execute(self.req, handler)
            except BaseException as e: errors.append(e)
        thread = threading.Thread(target=execute)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            other = dict(self.req, commandId='e'*32)
            self.assertEqual('BUSY', self.store.execute(other, lambda *a:self.fail('second handler'))['state'])
            self.assertEqual('NOT_FOUND', self.store.query(other)['state'])
            self.assertEqual('RUNNING', self.store.execute(self.req, lambda *a:self.fail('duplicate handler'))['state'])
        finally:
            release.set()
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual([], errors)

    def test_cancellation_preserves_completed_side_effect_result(self):
        def handler(*args):
            self.store.cancel(self.req)
            return {'outcome': 'INDETERMINATE', 'raw': 'retained'}
        result = self.store.execute(self.req, handler)
        self.assertEqual('CANCELLED', result['state'])
        self.assertEqual('INDETERMINATE', result['result']['outcome'])
        self.assertEqual(result, self.store.cancel(self.req))

    def test_cooperative_cancellation_and_exception_are_terminal(self):
        def handler(kind, data, checkpoint):
            self.store.cancel(self.req)
            checkpoint()
            self.fail('ignored cancellation')
        result = self.store.execute(self.req, handler)
        self.assertEqual('CANCELLED', result['state'])
        self.assertEqual(result, self.store.execute(self.req, lambda *a:self.fail('retry')))
        with self.assertRaises(ValueError):
            self.store.cancel(dict(self.req, commandId='e'*32))

    def test_oversized_request_and_result_fail_closed(self):
        with self.assertRaises(ValueError):
            self.store.execute(dict(self.req, payload={'large':'x'*(64<<10)}), lambda *a:self.fail('entry'))
        result = self.store.execute(self.req, lambda *a: {'large':'x'*(4<<20)})
        self.assertEqual('FAILED', result['state'])
        self.assertIn('byte limit', result['error']['message'])

    def test_symlinked_store_claim_or_receipt_rejected(self):
        alias = Path(self.temp.name)/'alias'
        alias.symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(ValueError): c.CommandStore(alias, self.owner)
        path = self.store.command_path(self.req)
        path.symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(ValueError): self.store.query(self.req)
        path.unlink()
        self.store.execute(self.req, lambda *a: {})
        receipt = path/'terminal.json'
        receipt.unlink()
        receipt.symlink_to(self.store.root/'binding.json')
        with self.assertRaises(OSError): self.store.query(self.req)

    def test_lost_submit_reply_only_queries_same_request(self):
        store = self.store
        class Transport:
            submits = 0
            queries = 0
            def submit(self, value, deadline):
                self.submits += 1
                store.execute(value, lambda *a: {'outcome':'SUCCESS'})
                raise ConnectionError('lost SSH reply')
            def query(self, value, deadline):
                self.queries += 1
                if self.queries == 1: raise ConnectionError('renew credentials')
                return store.query(value)
        transport = Transport()
        import time
        result = c.submit_and_observe(transport, self.req, time.monotonic()+2)
        self.assertEqual('SUCCEEDED', result['state'])
        self.assertEqual((1,2), (transport.submits,transport.queries))

    def test_unobserved_acceptance_times_out_without_resubmit(self):
        now = [0.]
        store = self.store
        class Transport:
            submits = 0
            def submit(self, value, deadline):
                self.submits += 1
                raise ConnectionError('lost before acceptance')
            def query(self, value, deadline): return store.query(value)
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            c.submit_and_observe(transport, self.req, .2, clock=lambda:now[0], sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(1, transport.submits)

    def test_response_mismatch_or_unknown_state_rejected(self):
        good = self.store.execute(self.req, lambda *a: {})
        for patch in ({'commandId':'0'*32}, {'bindingSha256':'0'*64}, {'requestSha256':'0'*64}, {'state':'RETRY'}):
            class Transport:
                def submit(self, value, deadline): return dict(good, **patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                c.submit_and_observe(Transport(), self.req, 10, clock=lambda:0)

    def test_late_success_is_not_a_deadline_extension(self):
        now = [0]
        store = self.store
        class Transport:
            def submit(self, value, deadline):
                result = store.execute(value, lambda *a: {})
                now[0] = 11
                return result
        with self.assertRaisesRegex(ValueError, 'late'):
            c.submit_and_observe(Transport(), self.req, 10, clock=lambda:now[0])

    def test_polling_cannot_see_partial_json_during_receipt_publication(self):
        original = c.os.link
        observations = []
        def before_publish(source, target, **kwargs):
            if Path(target).name == 'request.json':
                observations.append(self.store.query(self.req)['state'])
                self.assertFalse(Path(target).exists())
                self.assertEqual(self.req, c.read(source))
            return original(source,target,**kwargs)
        with patch.object(c.os,'link',side_effect=before_publish):
            result = self.store.execute(self.req,lambda *a:{})
        self.assertEqual(['UNCERTAIN'],observations)
        self.assertEqual('SUCCEEDED',result['state'])

    def test_interrupted_atomic_publish_consumes_claim_without_replay(self):
        with patch.object(c.os,'link',side_effect=OSError('crash before publish')):
            with self.assertRaises(OSError):self.store.execute(self.req,lambda *a:self.fail('entered'))
        self.assertEqual('UNCERTAIN',self.store.execute(self.req,lambda *a:self.fail('replayed'))['state'])
        self.assertTrue((self.store.command_path(self.req)/'request.json.writing').is_file())

    def test_receipt_fifo_is_rejected_without_blocking(self):
        self.store.execute(self.req,lambda *a:{})
        path = self.store.command_path(self.req)/'terminal.json'
        path.unlink()
        c.os.mkfifo(path)
        with self.assertRaises(ValueError):self.store.query(self.req)

    def test_terminal_receipt_failure_cannot_repeat_completed_handler(self):
        original = c.write_once
        entered = []
        def fail_terminal(path, value, *args):
            if Path(path).name == 'terminal.json':raise OSError('terminal force failed')
            return original(path,value,*args)
        with patch.object(c,'write_once',side_effect=fail_terminal):
            with self.assertRaises(OSError):self.store.execute(self.req,lambda *a:entered.append(1) or {})
        self.assertEqual('RUNNING',self.store.execute(self.req,lambda *a:self.fail('replayed'))['state'])
        self.assertEqual([1],entered)

    def test_partial_cancel_marker_cannot_be_reported_as_accepted(self):
        path = self.store.command_path(self.req)
        path.mkdir()
        c.write_once(path/'request.json',self.req)
        (path/'cancel.json.writing').write_bytes(b'{')
        with self.assertRaisesRegex(ValueError,'incomplete cancellation'):self.store.cancel(self.req)
