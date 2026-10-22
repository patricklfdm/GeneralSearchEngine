"""Deterministic delayed connection/upload and original-result recovery."""
from contextlib import ExitStack
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remote_python_ssh as p,remote_python_package as package
from . import remote_java_ssh as j
from .test_remote_python import SOURCE
from .test_remote_java import fixture


class InstallationDeadlineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload,cls.descriptor,_=package.compose(package.ROOT,SOURCE)

    def setUp(self):
        self.now=100.;self.grants=[];self.sent=0;self.finished=0;self.closed=0
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(p.time,'monotonic',side_effect=lambda:self.now))
        self.stack.enter_context(patch.object(p.ssh.Endpoint,'__init__',return_value=None))
        self.endpoint=p.Installer({},self.descriptor)
        self.endpoint.args=['ssh'];self.endpoint.target={};self.endpoint.pins={}
        self.endpoint.closed=False;self.endpoint.master=None;self.endpoint.connections=0
        self.endpoint.private=SimpleNamespace(name='/unused')
        self.stack.enter_context(patch.object(p.ssh,'ssh_args',return_value=['ssh']))
        self.stack.enter_context(patch.object(self.endpoint,'disconnect',side_effect=self.disconnect))
        self.receipt=dict(schema=p.receiver.RECEIPT,descriptorSha256=self.endpoint.sha,
            filesSha256=p.receiver.digest(p.receiver.encoded(self.descriptor)),root='/unused')
        self.receipt.update(filesSha256=p.receiver.digest(p.receiver.encoded(self.descriptor['files'])),
            root='/unit/python-'+self.descriptor['sha256'],
            host=dict(bootId='00000000-0000-4000-8000-000000000001',uid=1000,parentDevice=1,parentInode=1))
        self.stack.enter_context(patch.object(p.ssh.master,'Master',side_effect=self.master))
        self.stack.enter_context(patch.object(p,'Stream',side_effect=self.channel))

    def disconnect(self):
        self.closed+=1;self.endpoint.master=None

    def master(self,*args,connect_deadline=None,**kwargs):
        self.now+=25
        self.grants.append(connect_deadline)
        def check(deadline):
            if self.now>=deadline:raise TimeoutError('original connect deadline')
        check(connect_deadline)
        return SimpleNamespace(args=['ssh'],check=check)

    def channel(self,*args):
        outer=self
        class Channel:
            def __init__(self):
                self.proc=SimpleNamespace(stdin=io.BytesIO())
                self.reader=io.BytesIO(p.receiver.encoded(outer.receipt)+b'\n')
            def sendall(self,raw,*,deadline):
                outer.now+=.4;outer.sent+=len(raw)
                if outer.now>=deadline:raise TimeoutError('original send deadline')
            def check_exit(self):pass
            def finish(self):outer.finished+=1
        return Channel()

    def test_iap_connect_and_capsule_write_can_exceed_thirty_seconds(self):
        self.assertEqual(self.receipt,self.endpoint.install('/unit',self.payload))
        self.assertGreater(self.now,130);self.assertEqual(400,self.endpoint.end)
        self.assertEqual([400],self.grants);self.assertEqual(['install'],self.endpoint.calls)
        self.assertEqual(1,self.finished)

    def test_lost_reply_queries_once_using_same_absolute_grant(self):
        self.assertEqual(self.receipt,self.endpoint.install('/unit',self.payload,discard_reply=True))
        self.assertTrue(self.endpoint.reply_lost);self.assertEqual(['install','verify'],self.endpoint.calls)
        self.assertEqual([400,400],self.grants)
        with self.assertRaisesRegex(ValueError,'already consumed'):self.endpoint.install('/unit',self.payload)

    def test_exhausted_grant_cannot_be_renewed_by_result_query(self):
        def exhausted(*args,**kwargs):self.now=401;raise TimeoutError('install reply lost')
        with patch.object(p,'transfer',side_effect=exhausted) as transfer,self.assertRaises(TimeoutError):
            self.endpoint.install('/unit',self.payload)
        self.assertEqual(1,transfer.call_count);self.assertEqual(['install'],self.endpoint.calls)
        self.assertEqual([400],self.grants)

    def test_native_python_install_keeps_upload_time_and_one_grant_after_lost_reply(self):
        self.endpoint.target={'connectSeconds':240};ends=[]
        def transfer(channel,request,deadline):
            try:
                ends.append(deadline)
                if len(ends)==1:
                    self.now=500;raise ConnectionError('original reply lost after cold upload')
                p.remaining(deadline,'query deadline');return p.receiver.encoded(self.receipt)
            finally:channel.finish()
        with patch.object(p,'transfer',side_effect=transfer):
            self.assertEqual(self.receipt,self.endpoint.install('/unit',self.payload))
        self.assertEqual([640,640],ends);self.assertEqual([640,640],self.grants)
        self.assertEqual(['install','verify'],self.endpoint.calls)

    def test_native_java_install_query_keeps_original_grant_and_never_resubmits(self):
        value,_=fixture();endpoint=j.Installer({},value);endpoint.target={'connectSeconds':240}
        ends=[]
        def exchange(action,*args):
            p.remaining(endpoint.end,'original grant');ends.append(endpoint.end);endpoint.calls.append(action)
            if action=='install':self.now=500;raise ConnectionError('original reply lost after cold upload')
            return {'verified':True}
        with patch.object(endpoint,'exchange',side_effect=exchange):
            self.assertEqual({'verified':True},endpoint.install('/unit','unused'))
        self.assertEqual([640,640],ends);self.assertEqual(['install','verify'],endpoint.calls)

    def test_native_install_expiry_cannot_restart_the_540_second_grant(self):
        self.endpoint.target={'connectSeconds':240}
        def exhausted(*args,**kwargs):self.now=641;raise TimeoutError('original reply lost')
        with patch.object(p,'transfer',side_effect=exhausted) as transfer,self.assertRaises(TimeoutError):
            self.endpoint.install('/unit',self.payload)
        self.assertEqual(640,self.endpoint.end);self.assertEqual([640],self.grants)
        self.assertEqual(['install'],self.endpoint.calls);transfer.assert_called_once()

    def test_terminal_validation_does_not_query_or_resubmit(self):
        with patch.object(p,'transfer',side_effect=ValueError('altered bytes')) as transfer,self.assertRaises(ValueError):
            self.endpoint.install('/unit',self.payload)
        self.assertEqual(1,transfer.call_count);self.assertEqual(['install'],self.endpoint.calls)
        self.assertFalse(self.endpoint.reply_lost)

    def test_buffered_late_python_success_is_not_accepted(self):
        channel=self.channel()
        def late():self.now=201
        channel.check_exit=late
        with self.assertRaises(TimeoutError):p.transfer(channel,b'original',200)
        self.assertEqual(1,self.finished)

    def test_java_late_response_is_uncertainty_not_validation_failure(self):
        value,_=fixture();channel=self.channel()
        channel.reader=io.BytesIO(b'{}\n')
        def late():self.now=201
        channel.check_exit=late
        with self.assertRaises(TimeoutError):j.transfer(channel,value,None,200)
        self.assertEqual(1,self.finished)


if __name__=='__main__':unittest.main()
