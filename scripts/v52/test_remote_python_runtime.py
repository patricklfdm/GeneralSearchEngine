from copy import deepcopy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remote_python_package as package, remote_python_receiver as receiver
from . import remote_python_context as context, remote_python_ssh as ssh

ROOT=Path(__file__).resolve().parents[2]


class PythonRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        java=subprocess.run(['java','-XshowSettings:properties','-version'],check=True,capture_output=True,text=True).stderr
        cls.source=dict(source='a'*40,checkoutSha256='b'*64,
            java=dict(re.findall(r'^\s*(java\.(?:runtime.version|vendor)) = (.+)$',java,re.MULTILINE)))
        cls.raw,cls.descriptor,_=package.compose(ROOT,cls.source)

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='v52-python-runtime-unit-');self.addCleanup(temp.cleanup)
        self.parent=Path(temp.name);self.root=Path(receiver.install(self.parent,self.descriptor,self.raw)['root'])
        self.value=dict(root=str(self.root),descriptorSha256=receiver.digest(receiver.encoded(self.descriptor)))

    def probe(self,value=None):
        return subprocess.run(context.command(value or self.value,'delivery',['probe',self.parent],python=sys.executable),
            input=b'',capture_output=True,timeout=30,cwd=self.parent)

    def isolated(self,body):
        setup='import sys,json,pathlib\nsys.dont_write_bytecode=True\nroot=pathlib.Path(sys.argv[1])\nsys.path.insert(0,str(root/"files"))\nsys._gse_v52_installed_python=(str(root),sys.argv[2])\nfrom scripts.v52 import remote_python_context as context\n'
        return subprocess.run([sys.executable,'-I','-S','-c',setup+body,str(self.root),self.value['descriptorSha256']],
            capture_output=True,text=True,timeout=30,cwd=self.parent)

    def test_real_fixed_entry_launch_from_installed_root_without_git_or_site(self):
        result=self.probe();self.assertEqual(0,result.returncode,result.stderr.decode())
        self.assertEqual({'host'},set(json.loads(result.stdout)))
        self.assertFalse((self.root/'files/.git').exists());self.assertFalse(list(self.root.rglob('__pycache__')))
        receiver.installed(self.root,self.descriptor)

    def test_wrong_external_pin_rejects_before_guest_probe(self):
        value=dict(self.value,descriptorSha256='0'*64);result=self.probe(value)
        self.assertNotEqual(0,result.returncode);self.assertEqual(b'',result.stdout)
        self.assertIn(b'trusted descriptor changed',result.stderr)

    def test_installed_descriptor_does_not_silently_enable_source_context(self):
        code='import sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,sys.argv[1])\nfrom scripts.v52.remote_history import source\nsource()'
        result=subprocess.run([sys.executable,'-I','-S','-c',code,str(self.root/'files')],capture_output=True,timeout=30,cwd=self.parent)
        self.assertNotEqual(0,result.returncode);self.assertIn(b'git',result.stderr)
        self.assertIsNone(context.source())

    def test_spawned_child_keeps_descriptor_pin_and_isolated_source(self):
        body="import subprocess\nargs=context.child('delivery','unsafe legacy',['probe',root.parent])\nassert args[1:3]==['-I','-S'] and args[-5:-3]==[str(root),sys.argv[2]]\nr=subprocess.run(args,input=b'',capture_output=True,timeout=20)\nassert r.returncode==0,r.stderr\nprint(json.dumps(dict(source=context.source(),child=json.loads(r.stdout))))"
        result=self.isolated(body);self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(self.source,json.loads(result.stdout)['source'])

    def test_java_drift_is_rejected_before_guest_work(self):
        value=deepcopy(self.descriptor);value['source']['java']['java.vendor']='foreign'
        # A different descriptor can only be installed in a fresh private root.
        other=self.parent/'other';other.mkdir(mode=0o700)
        root=Path(receiver.install(other,value,self.raw)['root'])
        result=self.probe(dict(root=str(root),descriptorSha256=receiver.digest(receiver.encoded(value))))
        self.assertNotEqual(0,result.returncode);self.assertIn(b'Python capsule Java changed',result.stderr)
        self.assertEqual(b'',result.stdout)

    def test_source_mutation_after_import_rejects_child_launch(self):
        result=self.isolated("path=root/'files/pom.xml'\npath.chmod(0o600)\npath.write_bytes(path.read_bytes()+b' ')\ncontext.child('delivery','unsafe legacy',['probe',root.parent])")
        self.assertNotEqual(0,result.returncode);self.assertIn('Python capsule read bound',result.stderr)

    def test_endpoint_keeps_original_source_pin_after_caller_dictionary_changes(self):
        from . import remote_voter_ssh as stream
        value=dict(self.value)
        with patch.object(stream.ssh.Endpoint,'__init__',return_value=None):
            endpoint=stream.Endpoint({},ROOT,python_context=value)
        value['descriptorSha256']='0'*64
        args=endpoint.launch(['control','c'*64])
        self.assertEqual(self.value['descriptorSha256'],args[-4])

    def test_unknown_entry_and_malformed_context_reject(self):
        with self.assertRaisesRegex(ValueError,'launch entry'):context.command(self.value,'arbitrary-command',[])
        for value in (None,{},[],('a',),('a',1)):
            with patch.object(sys,context.ATTRIBUTE,value,create=True):
                with self.assertRaisesRegex(ValueError,'explicit launch context'):context.verify()
        for value in (dict(self.value,root=1),dict(self.value,root='../files'),dict(self.value,extra=True)):
            with self.assertRaises(ValueError):context.command(value,'delivery',[])

    def test_foreign_preloaded_module_rejects_recheck(self):
        result=self.isolated("from types import SimpleNamespace\nsys.modules['scripts.foreign']=SimpleNamespace(__file__='/tmp/foreign.py')\ncontext.source()")
        self.assertNotEqual(0,result.returncode);self.assertIn('ValueError',result.stderr)

    def test_capsule_binding_is_mandatory_for_installed_voter(self):
        result=self.isolated("context.require_binding({},'node-1')")
        self.assertNotEqual(0,result.returncode);self.assertIn('Python capsule receiver binding',result.stderr)
        with self.assertRaisesRegex(ValueError,'requires explicit launch'):context.require_binding({'remotePython':{}},'node-1')

    def test_explicit_java_cannot_fall_back_to_ambient_java_or_unbound_context(self):
        value=dict(self.value,java=dict(root='/does-not-exist/java',descriptorSha256='f'*64))
        result=self.probe(value);self.assertNotEqual(0,result.returncode);self.assertEqual(b'',result.stdout)
        with patch.object(sys,context.JAVA_ATTRIBUTE,('/missing/java','f'*64),create=True):
            with self.assertRaisesRegex(ValueError,'requires installed Python'):context.java()
        with self.assertRaisesRegex(ValueError,'requires explicit launch'):context.require_binding({'remoteJava':{}},'node-1')

    def test_legacy_java_keeps_original_toolchain_path_but_installed_java_uses_closed_environment(self):
        self.assertIsNone(context.environment());self.assertEqual('java',context.java())
        with patch.object(sys,context.JAVA_ATTRIBUTE,('/unit/java','f'*64),create=True):
            self.assertEqual({'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'},context.environment())


class CapsuleStreamTest(unittest.TestCase):
    def channel(self,reply=b'{}\n',tail=b''):
        class Channel:
            def __init__(self):
                self.parts=[];self.finished=False;self.checked=False;self.proc=SimpleNamespace(stdin=io.BytesIO())
                self.reader=SimpleNamespace(readline=lambda limit:self.replies.pop(0));self.replies=[reply,tail]
            def sendall(self,part,*,deadline):self.parts.append(part)
            def check_exit(self):self.checked=True
            def finish(self):self.finished=True
        return Channel()

    def test_capsule_larger_than_control_envelope_is_sent_once_in_bounded_pieces(self):
        request=b'x'*(2<<20);channel=self.channel()
        self.assertEqual(b'{}\n',ssh.transfer(channel,request,time.monotonic()+30))
        self.assertEqual(request,b''.join(channel.parts));self.assertEqual(32,len(channel.parts))
        self.assertTrue(channel.finished and channel.checked and channel.proc.stdin.closed)

    def test_oversized_request_and_deadline_fail_before_writing(self):
        for request,deadline,error in ((b'x'*(receiver.MAX_REQUEST+1),time.monotonic()+30,ValueError),(b'x',time.monotonic()-1,TimeoutError)):
            channel=self.channel()
            with self.assertRaises(error):ssh.transfer(channel,request,deadline)
            self.assertEqual([],channel.parts);self.assertTrue(channel.finished)

    def test_stream_writer_preserves_absolute_deadline(self):
        from .remote_voter_ssh import Stream
        channel=Stream.__new__(Stream);channel.closed=False;channel.proc=SimpleNamespace(stdin=object())
        with patch('scripts.v52.remote_voter_ssh.time.monotonic',return_value=100), patch('scripts.v52.remote_voter_ssh.select.select',return_value=([],[],[])) as select:
            with self.assertRaises(TimeoutError):channel.sendall(b'original',deadline=101)
            self.assertEqual(1,select.call_args.args[-1])
            with self.assertRaises(TimeoutError):channel.sendall(b'original',deadline=200)
            self.assertEqual(10,select.call_args.args[-1])

    def test_truncated_oversized_or_extra_response_rejects_and_closes(self):
        for reply,tail in ((b'{}',b''),(b'x'*8193,b''),(b'{}\n',b'x')):
            channel=self.channel(reply,tail)
            with self.assertRaisesRegex(ValueError,'response'):ssh.transfer(channel,b'one original request',time.monotonic()+30)
            self.assertEqual([b'one original request'],channel.parts);self.assertTrue(channel.finished)


if __name__=='__main__':unittest.main()
