import base64
from copy import deepcopy
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from . import guest_delivery as d, guest_delivery_receiver as r, guest_setup as s, remote_command as c

ROOT = Path(__file__).resolve().parents[2]


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        access = s.generate(self.root/'private', 'c'*32)
        self.raw = d.pack(ROOT, 'a'*40)
        self.value = d.describe(self.raw, c.binding('a'*40,'b'*64,'c'*32,'node-1'),
                               dict(instanceId='123',diskId='456',node=1,attempt='c'*32),access)
        self.parent = self.root/'receive'; self.parent.mkdir(mode=0o700)
        self.path = r.location(self.parent,self.value,os.getuid())
    def install(self, raw=None):
        return r.install(self.parent,self.value,os.getuid(),io.BytesIO(self.raw if raw is None else raw),time.monotonic()+10)
    def test_complete_install_query_and_repeated_install_never_rewrite(self):
        answer=self.install(); self.assertEqual(answer['state'],'SUCCEEDED')
        before={p:p.stat().st_mtime_ns for p in self.path.rglob('*')}
        self.assertEqual(r.query(self.parent,self.value,os.getuid()),answer)
        self.assertEqual(self.install(b'not another upload'),answer)
        self.assertEqual(before,{p:p.stat().st_mtime_ns for p in self.path.rglob('*')})
    def test_every_payload_directory_is_private_independent_of_umask(self):
        for mask in (0, 0o002, 0o022, 0o077):
            with self.subTest(umask=oct(mask)):
                parent=self.parent/str(mask);parent.mkdir(mode=0o700)
                previous=os.umask(mask)
                try:
                    answer=r.install(parent,self.value,os.getuid(),io.BytesIO(self.raw),time.monotonic()+5)
                finally:os.umask(previous)
                self.assertEqual(answer['state'],'SUCCEEDED',answer)
                path=r.location(parent,self.value,os.getuid())
                self.assertEqual(r.query(parent,self.value,os.getuid()),answer)
                for directory in (path/'files',*(p for p in (path/'files').rglob('*') if p.is_dir())):
                    self.assertEqual(directory.stat().st_mode & 0o777,0o700,str(directory))
    def test_truncation_and_trailing_bytes_consume_without_executing(self):
        for raw in (self.raw[:-1],self.raw+b' '):
            with self.subTest(length=len(raw)):
                parent=self.parent/str(len(raw));parent.mkdir(mode=0o700)
                answer=r.install(parent,self.value,os.getuid(),io.BytesIO(raw),time.monotonic()+5)
                self.assertEqual(answer['state'],'FAILED')
                path=r.location(parent,self.value,os.getuid());self.assertFalse((path/'files').exists())
                self.assertEqual(r.install(parent,self.value,os.getuid(),io.BytesIO(self.raw),time.monotonic()+5),answer)
    def test_hash_failure_consumed_before_any_payload_import(self):
        answer=self.install(self.raw[:-1]+b' ')
        self.assertEqual(answer['state'],'FAILED');self.assertFalse((self.path/'files').exists())
    def test_source_and_closed_file_set_cannot_be_forged_by_rehashing(self):
        original=r.decode(self.raw)
        for change in (lambda v:v.update(source='b'*40),lambda v:v['files'].update({'../escape':'eA=='}),
                       lambda v:v['files'].pop('helper.py'),lambda v:v['files'].update({'helper.py':'%%%'})):
            value=deepcopy(original);change(value);raw=r.canonical(value)
            desc=dict(self.value,payloadSha256=r.sha(raw),payloadBytes=len(raw))
            with self.assertRaises((ValueError,TypeError)):r.payload(raw,desc)
    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):r.decode(raw)
    def test_owner_node_source_package_and_payload_are_bound_on_query(self):
        self.install()
        for key in ('instanceId','diskId','guestAccessSha256','payloadSha256'):
            bad=deepcopy(self.value);bad[key]='999' if key.endswith('Id') else 'f'*64
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'identity'):r.query(self.parent,bad,os.getuid())
        for key in ('source','bundleSha256','workloadSha256'):
            bad=deepcopy(self.value);bad['binding'][key]='f'*(40 if key=='source' else 64)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'identity'):r.query(self.parent,bad,os.getuid())
    def test_partial_claim_is_uncertain_and_cannot_reenter(self):
        self.path.mkdir(mode=0o700)
        self.assertEqual(self.install()['state'],'UNCERTAIN')
        r.publish(self.path/'request.json',self.value)
        self.assertEqual(self.install()['state'],'UNCERTAIN')
        self.assertFalse((self.path/'files').exists())
    def test_wrong_uid_and_unowned_mode_rejected_before_claim(self):
        with self.assertRaises(ValueError):r.install(self.parent,self.value,os.getuid()+1,io.BytesIO(self.raw),time.monotonic()+5)
        self.parent.chmod(0o777)
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.path.exists())
    def test_symlink_parent_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.parent)
        with self.assertRaises(ValueError):r.install(alias,self.value,os.getuid(),io.BytesIO(self.raw),time.monotonic()+5)
        self.assertFalse(self.path.exists())
    def test_installed_corruption_extra_files_links_and_missing_files_rejected(self):
        self.install(); helper=self.path/'files/helper.py'; original=helper.read_bytes()
        helper.write_bytes(b'changed')
        with self.assertRaises(ValueError):r.query(self.parent,self.value,os.getuid())
        helper.write_bytes(original)
        extra=self.path/'files/extra';extra.write_bytes(b'')
        with self.assertRaises(ValueError):r.query(self.parent,self.value,os.getuid())
        extra.unlink();helper.unlink()
        with self.assertRaises(ValueError):r.query(self.parent,self.value,os.getuid())
        helper.symlink_to(self.root/'private/identity')
        with self.assertRaises(ValueError):r.query(self.parent,self.value,os.getuid())
        helper.unlink();helper.write_bytes(original);os.link(helper,self.root/'hardlink')
        with self.assertRaises(ValueError):r.query(self.parent,self.value,os.getuid())
    def test_deadline_rejected_before_claim(self):
        with self.assertRaisesRegex(ValueError,'deadline'):
            r.install(self.parent,self.value,os.getuid(),io.BytesIO(self.raw),time.monotonic()-1)
        self.assertFalse(self.path.exists())
    def test_late_input_keeps_consumed_failed_receipt(self):
        raw=self.raw; now=[1.]
        class Stream:
            def read(self,*args):
                now[0]=3.;return raw
        with patch.object(r.time,'monotonic',side_effect=lambda:now[0]):
            answer=r.install(self.parent,self.value,os.getuid(),Stream(),2.)
        self.assertEqual(answer['state'],'FAILED');self.assertFalse((self.path/'files').exists())
    def test_relocated_helper_imports_without_repository_or_bytecode(self):
        self.install()
        result=subprocess.run([sys.executable,'-I',str(self.path/'files/helper.py')],cwd=self.root,
                              capture_output=True,check=True,timeout=10)
        self.assertEqual(r.decode(result.stdout),dict(status='PASS',nativeWritesEnabled=False))
        self.assertEqual(list(self.path.rglob('__pycache__')),[])
        self.assertEqual(r.query(self.parent,self.value,os.getuid())['state'],'SUCCEEDED')
    def test_helper_cannot_accept_write_commands(self):
        self.install()
        result=subprocess.run([sys.executable,'-I',str(self.path/'files/helper.py'),'mkfs.ext4'],capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
    def test_native_cloud_endpoint_stays_disabled(self):
        endpoint=d.Endpoint(dict(instanceId='123'),self.parent,os.getuid())
        with patch('scripts.v51.guest_delivery.process') as proc:
            with self.assertRaisesRegex(ValueError,'disabled'):endpoint.exchange('install',self.value,self.raw,time.monotonic()+5)
            proc.assert_not_called()
    def test_lost_reply_only_queries_original_request_and_deadline(self):
        calls=[];value=self.value;deadline=time.monotonic()+5
        files=r.payload(self.raw,value);inventory=dict(files=len(files),decodedBytes=sum(map(len,files.values())))
        class Endpoint:
            offline=True
            def exchange(inner,action,desc,data,until):
                calls.append((action,desc,data,until))
                if action=='install':raise ConnectionError('lost')
                return r.envelope(value,'SUCCEEDED',inventory=inventory)
        self.assertEqual(d.deliver(Endpoint(),value,self.raw,deadline)['state'],'SUCCEEDED')
        self.assertEqual([v[0] for v in calls],['install','query'])
        self.assertTrue(all(v[1]==value and v[3]==deadline for v in calls));self.assertEqual(calls[1][2],b'')
    def test_unknown_receipt_never_reinstalls_or_resets_deadline(self):
        calls=[];now=[0.];value=self.value
        class Endpoint:
            offline=True
            def exchange(inner,action,desc,data,until):
                calls.append(action);return r.envelope(value,'NOT_FOUND')
        with self.assertRaisesRegex(ValueError,'never reinstall'):
            d.deliver(Endpoint(),value,self.raw,.11,clock=lambda:now[0],sleep=lambda v:now.__setitem__(0,now[0]+v))
        self.assertEqual(calls.count('install'),1);self.assertGreater(calls.count('query'),0)
    def test_wrong_or_late_receipt_cannot_pass(self):
        value=self.value
        files=r.payload(self.raw,value);inventory=dict(files=len(files),decodedBytes=sum(map(len,files.values())))
        class Endpoint:
            offline=True
            def exchange(inner,*args):return dict(r.envelope(value,'SUCCEEDED'),requestSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'identity'):d.deliver(Endpoint(),value,self.raw,time.monotonic()+5)
        class Late:
            offline=True
            def exchange(inner,*args):now[0]=3.;return r.envelope(value,'SUCCEEDED',inventory=inventory)
        now=[1.]
        with self.assertRaisesRegex(ValueError,'late'):d.deliver(Late(),value,self.raw,2.,clock=lambda:now[0])
    def test_receipt_inventory_and_boolean_scope_are_independently_checked(self):
        value=self.value
        for change in ({'inventory':{}},{'paidCloud':0}):
            class Endpoint:
                offline=True
                def exchange(inner,*args):return dict(r.envelope(value,'SUCCEEDED'),**change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                d.deliver(Endpoint(),value,self.raw,time.monotonic()+5)
    def test_terminal_publication_window_remains_readable(self):
        answer=self.install()
        terminal=self.path/'receipt.json';temp=terminal.with_name('receipt.json.writing')
        os.link(terminal,temp)
        self.assertEqual(r.query(self.parent,self.value,os.getuid()),answer)
        temp.unlink()
    def test_foreign_workload_cannot_be_delivered(self):
        value=deepcopy(self.value);value['binding']['workloadSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'workload'):r.payload(self.raw,value)


if __name__=='__main__':unittest.main()
