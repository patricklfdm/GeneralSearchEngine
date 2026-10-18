"""Real filesystem/archive boundaries; JVM observation alone is modeled here."""
from copy import deepcopy
import gzip
import io
from pathlib import Path
import tempfile
import tarfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remote_java_receiver as r,remote_java_ssh as ssh

SOURCE=dict(source='a'*40,checkoutSha256='b'*64,java={'java.runtime.version':'unit','java.vendor':'unit'})


def fixture(source=None,*,entries=None):
    files={'bin/java':b'unit executable','lib/modules':b'unit modules','release':b'unit release'}
    inventory={n:dict(bytes=len(v),sha256=r.p.digest(v),executable=n=='bin/java') for n,v in files.items()}
    out=io.BytesIO()
    with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            for name in entries if entries is not None else files:
                info=tarfile.TarInfo(name);info.size=len(files[name]);info.mode=0o755 if name=='bin/java' else 0o644
                tar.addfile(info,io.BytesIO(files[name]))
    raw=out.getvalue()
    value=dict(schema=r.SCHEMA,source=deepcopy(source or SOURCE),modules=list(r.MODULES),files=inventory,bytes=len(raw),sha256=r.p.digest(raw))
    return value,raw


class JavaImageTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='v52-java-unit-');self.addCleanup(tmp.cleanup);self.parent=Path(tmp.name)
        self.value,self.raw=fixture()
        self.observe=patch.object(r.subprocess,'run',return_value=SimpleNamespace(stdout='\n'.join(r.MODULES),stderr=''))
        self.observe.start();self.addCleanup(self.observe.stop)
        self.properties=patch.object(r,'properties',return_value=SOURCE['java']);self.properties.start();self.addCleanup(self.properties.stop)

    def install(self,raw=None,value=None):return r.install(self.parent,value or self.value,io.BytesIO(self.raw if raw is None else raw))

    def test_exact_installation_replays_original_receipt_and_private_modes(self):
        result=self.install();root=Path(result['root']);self.assertEqual(result,r.installed(root,self.value))
        for n,row in self.value['files'].items():self.assertEqual(0o500 if row['executable'] else 0o400,(root/'files'/n).stat().st_mode&0o777)
        self.assertEqual(self.raw,(root/'archive.tar.gz').read_bytes())
        with self.assertRaises(FileExistsError):self.install()

    def test_partial_upload_consumes_destination_and_cannot_retry(self):
        with self.assertRaisesRegex(ValueError,'truncated upload'):self.install(self.raw[:10])
        with self.assertRaises(FileExistsError):self.install()
        self.assertFalse((r.location(self.parent,self.value)/'receipt.json').exists())

    def test_changed_or_trailing_upload_has_no_success_receipt(self):
        for raw in (self.raw[:-1]+bytes([self.raw[-1]^1]),self.raw+b'x'):
            with tempfile.TemporaryDirectory() as parent,self.assertRaisesRegex(ValueError,'hash/trailing'):
                r.install(parent,self.value,io.BytesIO(raw))

    def test_closed_descriptor_bounds_and_collision(self):
        changes=[lambda v:v.update(extra=True),lambda v:v.update(bytes=True),lambda v:v.update(bytes=r.MAX_BYTES+1),
            lambda v:v['source'].update(source='x'),lambda v:v['modules'].append('java.desktop'),
            lambda v:v['files']['bin/java'].update(executable=False),lambda v:v['files']['lib/modules'].update(bytes=r.MAX_FILE+1),
            lambda v:v['files'].update({'../outside':v['files']['release']}),lambda v:v['files'].update({'bin':v['files']['release']})]
        for change in changes:
            value=deepcopy(self.value);change(value)
            with self.subTest(value=value),self.assertRaises(ValueError):r.descriptor(value)
        for value in ({'root':'../java','descriptorSha256':'a'*64},{'root':'/x//java','descriptorSha256':'a'*64}):
            with self.assertRaises(ValueError):r.selection(value)

    def archive(self,raw,value=None):
        value=deepcopy(value or self.value);value.update(bytes=len(raw),sha256=r.p.digest(raw));path=self.parent/'test.tar.gz'
        path.write_bytes(raw);r.verify_archive(path,value)

    def test_missing_duplicate_link_and_wrong_mode_archive_reject(self):
        for entries in (['bin/java','release'],['bin/java','bin/java','lib/modules','release']):
            value,raw=fixture(entries=entries)
            with self.subTest(entries=entries),self.assertRaisesRegex(ValueError,'missing member|archive entry'):self.archive(raw,value)
        for kind in ('symlink','hardlink','mode','size','unknown'):
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as tar:
                entry=tarfile.TarInfo('unknown' if kind=='unknown' else 'bin/java');entry.mode=0o700
                if kind in ('symlink','hardlink'):
                    entry.type=tarfile.SYMTYPE if kind=='symlink' else tarfile.LNKTYPE;entry.linkname='/tmp/foreign'
                elif kind=='size':entry.mode=0o755;entry.size=1
                tar.addfile(entry,io.BytesIO(b'x'))
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'archive entry|size/mode'):self.archive(gzip.compress(out.getvalue()))

    def test_member_hash_and_hidden_trailing_bytes_reject(self):
        plain=gzip.decompress(self.raw)
        changed=plain.replace(b'unit executable',b'evil executable')
        with self.assertRaisesRegex(ValueError,'member hash'):self.archive(gzip.compress(changed))
        with self.assertRaisesRegex(ValueError,'trailing payload'):self.archive(gzip.compress(plain+b'hidden'))
        with patch.object(r,'MAX_BYTES',512),patch.object(r,'MAX_FILES',3):
            with self.assertRaisesRegex(ValueError,'expanded bound'):self.archive(gzip.compress(plain+b'\x00'*8192))

    def test_pax_and_gnu_extended_metadata_reject(self):
        for fmt in (tarfile.PAX_FORMAT,tarfile.GNU_FORMAT):
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w',format=fmt) as tar:
                entry=tarfile.TarInfo('a'*200);entry.size=1;tar.addfile(entry,io.BytesIO(b'x'))
            with self.subTest(fmt=fmt),self.assertRaisesRegex(ValueError,'extended archive'):self.archive(gzip.compress(out.getvalue()))

    def test_retained_archive_bytes_are_checked_without_executing_binary(self):
        path=self.parent/'retained.tar.gz';path.write_bytes(self.raw)
        with patch.object(r.subprocess,'run',side_effect=AssertionError('executed retained binary')):r.verify_archive(path,self.value)
        path.write_bytes(self.raw+b'x')
        with self.assertRaisesRegex(ValueError,'size/type'):r.verify_archive(path,self.value)

    def test_wrong_module_set_or_version_never_records_success(self):
        self.properties.stop()
        with patch.object(r,'properties',return_value={'java.vendor':'other'}),self.assertRaisesRegex(ValueError,'runtime differs'):self.install()
        with tempfile.TemporaryDirectory() as parent,patch.object(r,'properties',return_value=SOURCE['java']),\
             patch.object(r.subprocess,'run',return_value=SimpleNamespace(stdout='java.base\njava.desktop',stderr='')):
            with self.assertRaisesRegex(ValueError,'module set'):r.install(parent,self.value,io.BytesIO(self.raw))
            self.assertFalse((r.location(parent,self.value)/'receipt.json').exists())

    def test_installed_byte_mode_extra_file_and_symlink_changes_reject(self):
        receipt=self.install();root=Path(receipt['root']);path=root/'files/release'
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'mode/size'):r.installed(root,self.value)
        path.write_bytes(b'changed');path.chmod(0o400)
        with self.assertRaises(ValueError):r.installed(root,self.value)
        path.unlink();path.symlink_to(root/'files/lib/modules')
        with self.assertRaisesRegex(ValueError,'owned path'):r.installed(root,self.value)

    def test_unsafe_parent_and_symlink_destination_reject(self):
        unsafe=self.parent/'unsafe';unsafe.mkdir(mode=0o777);unsafe.chmod(0o777)
        with self.assertRaisesRegex(ValueError,'writable ancestor'):r.install(unsafe,self.value,io.BytesIO(self.raw))
        root=r.location(self.parent,self.value);root.symlink_to(unsafe)
        with self.assertRaises(FileExistsError):self.install()


class JavaStreamTest(unittest.TestCase):
    def test_stream_is_chunked_and_has_one_original_header(self):
        value,raw=fixture();parts=[];finished=[];stdin=io.BytesIO()
        class Reader:
            def __init__(self):self.rows=[b'{}\n',b'']
            def readline(self,n):return self.rows.pop(0)
        def send(part,**kw):self.assertLessEqual(len(part),64);parts.append(part)
        channel=SimpleNamespace(sendall=send,proc=SimpleNamespace(stdin=stdin),reader=Reader(),
            check_exit=lambda:None,finish=lambda:finished.append(True))
        with tempfile.TemporaryDirectory() as parent,patch.object(r,'PIECE',64):
            path=Path(parent)/'image';path.write_bytes(raw)
            self.assertEqual({},ssh.transfer(channel,value,path,time.monotonic()+10))
        self.assertEqual(r.p.encoded(value)+b'\n'+raw,b''.join(parts));self.assertEqual([True],finished)
        self.assertTrue(stdin.closed)

    def test_install_is_submitted_once_and_lost_reply_only_queries(self):
        value,raw=fixture()
        with patch.object(ssh.ssh.Endpoint,'__init__',return_value=None):endpoint=ssh.Installer({},value)
        def exchange(action,*args):endpoint.calls.append(action);return {'original':True}
        with patch.object(endpoint,'exchange',side_effect=exchange),patch.object(endpoint,'disconnect'):
            self.assertEqual({'original':True},endpoint.install('/unit','unused',discard_reply=True))
            self.assertEqual(['install','verify'],endpoint.calls);self.assertTrue(endpoint.reply_lost)
            with self.assertRaisesRegex(ValueError,'already consumed'):endpoint.install('/unit','unused')

    def test_failed_original_verification_does_not_resubmit_install(self):
        value,_=fixture()
        with patch.object(ssh.ssh.Endpoint,'__init__',return_value=None):endpoint=ssh.Installer({},value)
        def exchange(action,*args):
            endpoint.calls.append(action)
            if action=='install':raise ConnectionError('lost')
            raise ValueError('partial original installation')
        with patch.object(endpoint,'exchange',side_effect=exchange):
            with self.assertRaisesRegex(ValueError,'partial original'):endpoint.install('/unit','unused')
        self.assertEqual(['install','verify'],endpoint.calls)


if __name__=='__main__':unittest.main()
