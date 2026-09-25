import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
import uuid
from . import cloud_guest as g, guest_transport as t, remote_command as c


def config(root):
    return dict(schema='gse-v51-guest-service-v1', execution=g.EXECUTION,
        binding=c.binding('a'*40,'b'*64,'c'*32,'node-1'), packageManifestSha256='d'*64,
        root=str(root), mode='candidate-v5.1-automatic', hosts=['127.0.0.2','127.0.0.3','127.0.0.4'],
        ports=[19151]*3, groupId=str(uuid.uuid4()))


class GuestServiceTest(unittest.TestCase):
    def setUp(self): self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
    def test_configuration_rejects_public_hosts_duplicate_endpoints_and_scope(self):
        good = config(self.root); g.validate(good)
        for key, value in [('hosts',[2130706433]*3), ('hosts',['8.8.8.8']*3), ('hosts',['127.0.0.1']*3), ('ports',[True,19151,19151]),
                           ('execution','paid'), ('root','../escape'), ('groupId','unknown')]:
            with self.subTest(key=key), self.assertRaises(ValueError): g.validate(dict(good, **{key:value}))
    def test_socket_identity_short_and_per_guest(self):
        first = g.socket_path(self.root/('long-'*100)/'node-1'); second = g.socket_path(self.root/('long-'*100)/'node-2')
        self.assertLess(len(str(first)), 108); self.assertNotEqual(first, second)
    def service(self):
        obj = g.Service.__new__(g.Service); obj.config = config(self.root)
        obj.store = c.CommandStore(self.root/'commands', obj.config['binding'], create=True)
        obj.active, obj.answer, obj.ack = None, None, threading.Event(); obj.shutting_down = False
        return obj
    def test_duplicate_and_busy_never_enter_handler_twice(self):
        obj=self.service(); release=threading.Event(); calls=[]
        def handler(name,payload,checkpoint): obj.ack.set(); calls.append(name); release.wait(5); return {'done':True}
        obj.handler=handler
        value=c.request(obj.config['binding'],'1'*32,'window',{})
        other=c.request(obj.config['binding'],'2'*32,'window',{})
        try:
            self.assertEqual(obj.submit(value)['state'],'RUNNING')
            self.assertEqual(obj.submit(value)['state'],'RUNNING')
            self.assertEqual(obj.submit(other)['state'],'BUSY')
            self.assertEqual(calls,['window'])
        finally: release.set();obj.active.join(5)
        self.assertEqual(obj.submit(value)['state'],'SUCCEEDED');self.assertEqual(calls,['window'])
    def test_cancel_receipt_cannot_become_success(self):
        obj=self.service();release=threading.Event()
        def handler(name,payload,checkpoint): obj.ack.set();release.wait(5);checkpoint();return {}
        obj.handler=handler;value=c.request(obj.config['binding'],'3'*32,'window',{})
        try:
            obj.submit(value);obj.store.cancel(value)
        finally: release.set();obj.active.join(5)
        self.assertEqual(obj.store.query(value)['state'],'CANCELLED')
    def test_claim_before_handler_survives_lost_client(self):
        obj=self.service(); calls=[]
        def handler(name,payload,checkpoint):
            self.assertEqual(obj.store.query(value)['state'],'RUNNING')
            obj.ack.set();calls.append(name);return {}
        obj.handler=handler;value=c.request(obj.config['binding'],'4'*32,'window',{})
        obj.submit(value);obj.active.join(5)
        restarted=c.CommandStore(obj.store.root,obj.config['binding'])
        self.assertEqual(restarted.query(value)['state'],'SUCCEEDED');self.assertEqual(calls,['window'])
    def test_child_transport_limits_and_deadline(self):
        result=t.process([sys.executable,'-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],b'hello',time.monotonic()+5)
        self.assertEqual(result,b'hello')
        with self.assertRaisesRegex(ValueError,'bound'):
            t.process([sys.executable,'-c','print("x"*1000)'],b'',time.monotonic()+5,maximum=100)
        with self.assertRaises(TimeoutError):
            t.process([sys.executable,'-c','import time;time.sleep(5)'],b'',time.monotonic()+.1)
    def target(self):
        key=self.root/'key';key.write_text('fixture');key.chmod(0o600)
        known=self.root/'known';known.write_text('gse-v51-123 ssh-ed25519 AQID\n');known.chmod(0o600)
        return dict(project='test-project',zone='us-west4-a',instance='gse-v51-fixture',instanceId='123',user='gse',key=str(key),knownHosts=str(known))
    def test_ssh_pins_identity_and_never_uses_tofu_or_unquoted_shell(self):
        target=self.target(); args=t.ssh_args(target,['python3','/tmp/name with space/guest.py','service','query'])
        self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('HostKeyAlias=gse-v51-123',args)
        self.assertIn('IdentitiesOnly=yes',args);self.assertIn("'/tmp/name with space/guest.py'",args[-1])
        self.assertTrue(any('--listen-on-stdin' in v for v in args));self.assertFalse(any('StrictHostKeyChecking=no' in v for v in args))
    def test_ssh_rejects_name_injection_bad_permissions_or_host_alias(self):
        target=self.target()
        with self.assertRaises(ValueError):t.ssh_args(dict(target,instance='x;bad'),['true'])
        Path(target['key']).chmod(0o644)
        with self.assertRaises(ValueError):t.ssh_args(target,['true'])
        Path(target['key']).chmod(0o600);Path(target['knownHosts']).write_text('other ssh-ed25519 AQID\n')
        with self.assertRaises(ValueError):t.ssh_args(target,['true'])
    def test_live_ssh_not_enabled_by_offline_configuration(self):
        transport=t.Ssh(self.root,config(self.root),self.target())
        with self.assertRaisesRegex(ValueError,'disabled'):transport.start(time.monotonic()+5)

if __name__=='__main__':unittest.main()
