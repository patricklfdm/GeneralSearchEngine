from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import remote_java_evidence as j,remote_python_runtime_evidence as evidence
from .test_remote_java import fixture
from . import test_remote_python_runtime_evidence as py_fixture


class JavaEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):py_fixture.PythonRuntimeEvidenceTest.setUpClass()
    def setUp(self):
        self.base=py_fixture.PythonRuntimeEvidenceTest('test_portable_source_chain_does_not_require_original_installation_paths')
        self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.root=self.base.root;self.binding=self.base.binding;self.write=self.base.write;self.mutate=self.base.mutate
        self.value,self.raw=fixture(self.base.source);self.pin=j.r.p.digest(j.r.p.encoded(self.value));self.nodes={}
        for i,node in enumerate(self.binding['remotePython']['nodes'],1):
            py=self.binding['remotePython']['nodes'][node]
            own=dict(schema=j.r.RECEIPT,descriptorSha256=self.pin,root='/original/'+node+'/java-'+self.value['sha256'],
                filesSha256=j.r.p.digest(j.r.p.encoded(self.value['files'])),java=self.value['source']['java'],host=deepcopy(py['host']))
            self.nodes[node]=own
            for name in (node+'-python-bootstrap.json',node+'-control/python-runtime.json'):
                self.mutate(name,lambda v:v.update(java=dict(selection=j.selection(own),installation=own)))
            process=dict(pid=300+i,startTicks=123,bootId=own['host']['bootId'])
            self.mutate(node+'-control/identity.json',lambda v:v.update(jvm=process))
            self.write(node+'-control/java-process.json',dict(schema='gse-v52-java-process-v1',process=process,selection=j.selection(own),
                executable=own['root']+'/files/bin/java',executableSha256=self.value['files']['bin/java']['sha256']))
        self.binding['remoteJava']=dict(schema=j.SCHEMA,descriptorSha256=self.pin,nodes=self.nodes)
        self.write(j.FILE,self.value);(self.root/j.ARCHIVE).write_bytes(self.raw)
    def check(self):return evidence.validate(self.root,self.binding)

    def test_portable_bytes_host_python_and_actual_process_chain_passes_without_original_paths_or_execution(self):
        with patch.object(j.r.subprocess,'run',side_effect=AssertionError('retained evidence executed')):
            self.assertEqual('PASS',self.check()['status'])
        self.assertFalse(Path(self.nodes['node-1']['root']).exists())

    def test_missing_or_changed_original_image_does_not_accept_runtime_receipt(self):
        path=self.root/j.ARCHIVE;path.unlink()
        with self.assertRaises(FileNotFoundError):self.check()
        path.write_bytes(self.raw[:-1]+bytes([self.raw[-1]^1]))
        with self.assertRaisesRegex(ValueError,'archive hash'):self.check()

    def test_source_or_descriptor_pin_changes_reject(self):
        self.mutate(j.FILE,lambda v:v['source'].update(source='f'*40))
        with self.assertRaisesRegex(ValueError,'original source'):self.check()

    def test_runtime_fallback_to_path_java_rejects(self):
        self.mutate('node-1-python-bootstrap.json',lambda v:v['java']['selection'].update(root='/usr'))
        with self.assertRaisesRegex(ValueError,'runtime selection'):self.check()

    def test_unbound_java_is_not_authorized_by_its_local_files(self):
        self.binding.pop('remoteJava')
        with self.assertRaisesRegex(ValueError,'runtime identity'):self.check()

    def test_missing_process_record_cannot_be_replaced_with_runtime_selection(self):
        (self.root/'node-2-control/java-process.json').unlink()
        with self.assertRaises(FileNotFoundError):self.check()

    def test_same_pid_new_start_or_another_binary_is_rejected(self):
        for change in (lambda v:v['process'].update(startTicks=124),lambda v:v.update(executable='/usr/bin/java'),
                       lambda v:v.update(executableSha256='a'*64)):
            path=self.root/'node-1-control/java-process.json';raw=path.read_bytes();self.mutate(str(path.relative_to(self.root)),change)
            with self.assertRaisesRegex(ValueError,'process executable'):self.check()
            path.write_bytes(raw)

    def test_receipt_boot_uid_and_directory_substitution_reject(self):
        for change in (lambda v:v['host'].update(uid=1001),lambda v:v['host'].update(bootId='00000000-0000-0000-0000-000000000002'),
                       lambda v:v.update(root='/other/java-'+self.value['sha256'])):
            old=deepcopy(self.nodes['node-1']);change(self.nodes['node-1'])
            with self.assertRaises(ValueError):self.check()
            self.nodes['node-1']=old

    def test_missing_node_and_extra_runtime_field_reject(self):
        saved=self.nodes.pop('node-3')
        with self.assertRaisesRegex(ValueError,'receiver binding'):self.check()
        self.nodes['node-3']=saved
        self.mutate('node-3-control/python-runtime.json',lambda v:v['java'].update(ambientJava=True))
        with self.assertRaisesRegex(ValueError,'runtime selection'):self.check()


if __name__=='__main__':unittest.main()
