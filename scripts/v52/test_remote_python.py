from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from . import remote_python_package as package, remote_python_receiver as receiver

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(source='a'*40, checkoutSha256='b'*64,
              java={'java.runtime.version':'test-only', 'java.vendor':'test-only'})
from . import remote_python_qualification as qualification



class PythonCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.value, cls.graph = package.compose(ROOT, SOURCE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v52-python-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def install(self):
        receipt = receiver.install(self.root, self.value, self.raw)
        return Path(receipt['root'])

    def test_exact_static_closure_no_tests_secrets_or_generated_build_outputs(self):
        files = self.value['files']
        self.assertGreater(len(self.graph), 100)
        self.assertEqual(set(self.graph), {n[:-3].replace('/', '.') if not n.endswith('/__init__.py') else
                                         n[:-12].replace('/', '.') for n in files if n.endswith('.py')})
        self.assertFalse(any(part in ('target', '.git', '__pycache__') or part.startswith('test_')
                             for n in files for part in n.split('/')))
        self.assertEqual(receiver.DATA, {n for n in files if not n.endswith('.py')})
        self.assertEqual((self.raw, self.value, self.graph), package.compose(ROOT, SOURCE))

    def test_real_isolated_imports_resolve_from_installed_capsule_without_git_or_site(self):
        own = self.install(); receipt = receiver.installed(own, self.value)
        observed = qualification.probe(own, self.value)
        self.assertGreater(len(observed['loaded']), 80)
        self.assertFalse(observed['gitPresent'])
        self.assertEqual(set(observed['loaded'].values()) - set(self.value['files']), set())
        self.assertEqual(receipt, receiver.installed(own, self.value))
        self.assertFalse(list(own.rglob('__pycache__')))

    def test_missing_entry_and_added_unknown_path_reject_before_install(self):
        for name in (receiver.ENTRIES[0].replace('.', '/')+'.py', 'pom.xml'):
            value = deepcopy(self.value); value['files'].pop(name)
            with self.assertRaisesRegex(ValueError, 'inventory|missing entry'):
                receiver.install(self.root, value, self.raw)
        for name in ('../escape.py','/absolute','scripts/../bad.py','scripts/test_guest.py','credentials.json'):
            value = deepcopy(self.value); value['files'][name] = dict(bytes=0,sha256=receiver.digest(b''))
            with self.assertRaisesRegex(ValueError, 'undeclared path'):
                receiver.install(self.root, value, self.raw)
        self.assertEqual([],list(self.root.iterdir()))

    def test_payload_hash_and_each_member_are_checked_before_destination_consumed(self):
        with self.assertRaisesRegex(ValueError, 'payload changed'):
            receiver.install(self.root, self.value, self.raw+b' ')
        value = deepcopy(self.value); item = next(iter(value['files'].values())); item['sha256']='0'*64
        with self.assertRaisesRegex(ValueError, 'member changed'):
            receiver.install(self.root, value, self.raw)
        self.assertEqual([],list(self.root.iterdir()))

    def test_bounds_and_boolean_sizes_reject(self):
        for replacement in (True,0,receiver.MAX_PAYLOAD+1):
            value = deepcopy(self.value); value['bytes'] = replacement
            with self.assertRaisesRegex(ValueError,'payload bound'):receiver.descriptor(value)
        for replacement in (True,-1,receiver.MAX_FILE+1):
            value=deepcopy(self.value);next(iter(value['files'].values()))['bytes']=replacement
            with self.assertRaisesRegex(ValueError,'member bound'):receiver.descriptor(value)
        with patch.object(receiver,'MAX_EXPANDED',1):
            with self.assertRaisesRegex(ValueError,'expansion'):receiver.descriptor(self.value)
        with patch.object(receiver,'MAX_FILES',1):
            with self.assertRaisesRegex(ValueError,'inventory'):receiver.descriptor(self.value)

    def test_duplicate_json_and_unexpected_entries_reject(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            receiver.decode(b'{"files":{},"files":{}}')
        value=deepcopy(self.value);value['entries'].append('scripts.v52.cloud_entry')
        with self.assertRaisesRegex(ValueError,'descriptor'):receiver.descriptor(value)

    def test_partial_install_remains_consumed_and_cannot_be_verified(self):
        original=receiver.write;calls=[]
        def fail(path,raw):
            calls.append(path)
            if len(calls)==3:raise OSError('injected interrupted write')
            original(path,raw)
        with patch.object(receiver,'write',side_effect=fail):
            with self.assertRaisesRegex(OSError,'interrupted'):self.install()
        own=receiver.location(self.root,self.value)
        self.assertTrue(own.is_dir());self.assertFalse((own/'receipt.json').exists())
        with self.assertRaises(ValueError):receiver.installed(own,self.value)
        with self.assertRaises(FileExistsError):self.install()

    def test_changed_missing_and_extra_installed_files_reject(self):
        own=self.install();path=own/'files/pom.xml';raw=path.read_bytes();path.chmod(0o600)
        path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(ValueError,'read bound|installed bytes'):receiver.installed(own,self.value)
        path.write_bytes(raw);path.unlink()
        with self.assertRaisesRegex(ValueError,'incomplete installation'):receiver.installed(own,self.value)
        path.write_bytes(raw);path.chmod(0o400);extra=own/'files/credentials.json';extra.write_text('{}')
        with self.assertRaisesRegex(ValueError,'extra file'):receiver.installed(own,self.value)

    def test_linked_paths_hardlinks_and_writable_directory_reject(self):
        own=self.install();path=own/'files/pom.xml';other=self.root/'saved';path.rename(other);path.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'owned path'):receiver.installed(own,self.value)
        path.unlink();os.link(other,path)
        with self.assertRaisesRegex(ValueError,'owned path'):receiver.installed(own,self.value)
        path.unlink();other.rename(path);(own/'files/scripts').chmod(0o755)
        with self.assertRaisesRegex(ValueError,'owned path'):receiver.installed(own,self.value)

    def test_changed_source_and_receipt_reject(self):
        own=self.install();value=deepcopy(self.value);value['source']['source']='c'*40
        with self.assertRaisesRegex(ValueError,'descriptor changed'):receiver.installed(own,value)
        path=own/'receipt.json';receipt=json.loads(path.read_bytes());receipt['host']['parentInode']+=1
        path.chmod(0o600);path.write_bytes(receiver.encoded(receipt))
        with self.assertRaisesRegex(ValueError,'receipt changed'):receiver.installed(own,self.value)

    def test_trusted_standalone_receiver_accepts_only_exact_descriptor(self):
        trusted=Path(receiver.__file__).read_text();request=receiver.encoded(dict(descriptor=self.value,payload=self.raw.decode('ascii')))
        args=[sys.executable,'-I','-S','-c',trusted,'install',str(self.root)]
        rejected=subprocess.run([*args,'0'*64],input=request,capture_output=True,timeout=30)
        self.assertNotEqual(0,rejected.returncode);self.assertEqual([],list(self.root.iterdir()))
        accepted=subprocess.run([*args,receiver.digest(receiver.encoded(self.value))],input=request,capture_output=True,timeout=30)
        self.assertEqual(0,accepted.returncode,accepted.stderr.decode());own=Path(json.loads(accepted.stdout)['root'])
        self.assertEqual(json.loads(accepted.stdout),receiver.installed(own,self.value))

    def test_undeclared_dynamic_and_external_imports_fail_static_audit(self):
        for source in ('import numpy','from evil_library import api',"__import__(name)","__import__('scripts.v52.hidden')",
                       "importlib.import_module('scripts.v52.hidden')",'from scripts.v52 import *'):
            with self.assertRaises(ValueError):package.imports('scripts.v52.guest','scripts/v52/guest.py',source.encode(),lambda _:True)
        self.assertEqual([],package.imports('scripts.guest','scripts/guest.py',b"__import__('base64')",lambda _:False))

    def test_missing_static_dependency_is_not_silently_omitted(self):
        with self.assertRaisesRegex(ValueError,'dependency missing'):
            package.imports('scripts.v52.guest','scripts/v52/guest.py',b'from .missing import run',lambda _:False)


if __name__ == '__main__':unittest.main()
