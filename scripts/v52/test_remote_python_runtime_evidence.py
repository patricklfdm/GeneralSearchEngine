from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from . import remote_python_package as package, remote_python_receiver as r
from . import remote_python_runtime_evidence as evidence


class PythonRuntimeEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=dict(source='a'*40,checkoutSha256='b'*64,java={'java.runtime.version':'unit','java.vendor':'unit'})
        cls.raw,cls.descriptor,_=package.compose(Path(__file__).resolve().parents[2],cls.source)

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='v52-python-evidence-unit-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.sha=r.digest(r.encoded(self.descriptor));nodes={}
        for i in range(1,4):
            node='node-'+str(i);host=dict(bootId='00000000-0000-0000-0000-000000000001',uid=1000,parentDevice=1,parentInode=i)
            receipt=dict(schema=r.RECEIPT,descriptorSha256=self.sha,root='/unit/'+node+'/python-'+self.descriptor['sha256'],
                         host=host,filesSha256=r.digest(r.encoded(self.descriptor['files'])))
            nodes[node]=receipt
            runtime=dict(schema='gse-v52-python-runtime-v1',selection=dict(root=receipt['root'],descriptorSha256=self.sha),
                         source=self.source,installation=receipt,process=dict(pid=100+i,entry='gse-v52-delivery'),isolated=True,noSite=True)
            self.write(node+'-python-bootstrap.json',runtime)
            self.write(node+'-delivery.json',dict(receiverHost=dict(host,parentInode=100+i),process=dict(pid=100+i)))
            runtime=deepcopy(runtime);runtime['process']=dict(pid=200+i,entry='gse-v52-voter')
            self.write(node+'-control/python-runtime.json',runtime)
            self.write(node+'-control/identity.json',dict(service=dict(pid=200+i)))
        self.binding=dict(self.source,remotePython=dict(schema=evidence.SCHEMA,descriptorSha256=self.sha,nodes=nodes))
        self.write(evidence.FILE,self.descriptor);(self.root/evidence.PAYLOAD).write_bytes(self.raw)

    def write(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.encoded(value))

    def mutate(self,name,change):
        path=self.root/name;value=r.decode(path.read_bytes());change(value);self.write(name,value)

    def test_portable_source_chain_does_not_require_original_installation_paths(self):
        self.assertEqual('PASS',evidence.validate(self.root,self.binding)['status'])
        self.assertFalse(evidence.validate(self.root,self.binding)['fullRemoteQualification'])

    def test_missing_source_binding_is_not_inferred_from_retained_files(self):
        binding=dict(self.binding);binding.pop('remotePython')
        with self.assertRaisesRegex(ValueError,'receiver binding'):evidence.validate(self.root,binding)

    def test_changed_raw_source_payload_rejects_even_with_intact_runtime_receipts(self):
        (self.root/evidence.PAYLOAD).write_bytes(bytes([self.raw[0]^1])+self.raw[1:])
        with self.assertRaisesRegex(ValueError,'payload changed'):evidence.validate(self.root,self.binding)

    def test_changed_descriptor_source_rejects(self):
        self.mutate(evidence.FILE,lambda v:v['source'].update(source='c'*40))
        with self.assertRaisesRegex(ValueError,'retained source changed'):evidence.validate(self.root,self.binding)

    def test_missing_all_runtime_records_for_a_node_does_not_count_as_empty_success(self):
        root=self.root/'node-1-control'
        for path in root.iterdir():path.unlink()
        root.rmdir()
        with self.assertRaisesRegex(ValueError,'control generations'):evidence.validate(self.root,self.binding)

    def test_substituted_process_or_enabled_site_rejects(self):
        self.mutate('node-2-control/python-runtime.json',lambda v:v.update(noSite=False))
        with self.assertRaisesRegex(ValueError,'runtime identity'):evidence.validate(self.root,self.binding)
        self.mutate('node-2-control/python-runtime.json',lambda v:v.update(noSite=True,process=dict(pid=999,entry='gse-v52-voter')))
        with self.assertRaisesRegex(ValueError,'runtime identity'):evidence.validate(self.root,self.binding)

    def test_source_selection_is_not_self_authorizing(self):
        self.binding['remotePython']['descriptorSha256']='c'*64
        with self.assertRaisesRegex(ValueError,'source changed'):evidence.validate(self.root,self.binding)

    def test_arbitrary_restart_marker_does_not_authorize_extra_generations(self):
        self.binding['remoteRestart']='not-an-admitted-restart'
        with self.assertRaisesRegex(ValueError,'restart scope'):evidence.validate(self.root,self.binding)

    def test_second_generation_is_only_accepted_when_the_history_declares_restart(self):
        self.write('node-1-control-g2/python-runtime.json',{})
        with self.assertRaisesRegex(ValueError,'control generations'):evidence.validate(self.root,self.binding)


if __name__=='__main__':unittest.main()
