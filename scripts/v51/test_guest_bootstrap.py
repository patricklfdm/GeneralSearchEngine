from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import guest_bootstrap as b, cloud_package as p, remote_command as c, performance_model as m
from .test_guest_service import config


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cell=self.root/'cell';self.cell.mkdir();self.cfg=config(self.cell)
        self.prepare()
    def prepare(self):
        for n in b.expected_files(self.cfg):
            path=self.cell/n;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(n.encode())
        for n,text in zip(b.TOPOLOGY, ('\n'.join(self.cfg['hosts'])+'\n','\n'.join(map(str,self.cfg['ports']))+'\n',self.cfg['groupId']+'\n')):
            (self.cell/n).write_text(text)
    def exported(self):
        folder=self.root/'export';result=b.export(self.cell,folder,self.cfg)
        # Keep sealed root unchanged and preserve the producing bytes elsewhere.
        self.cell.rename(self.root/'original');self.cell.mkdir()
        return folder,result['descriptorSha256']
    def test_install_keeps_exact_bytes_and_rejects_second_install(self):
        folder,digest=self.exported();self.assertEqual(b.install(folder,digest,self.cfg)['status'],'PASS')
        b.check_ready(self.cell,self.cfg)
        for n in b.expected_files(self.cfg):self.assertEqual((self.cell/n).read_bytes(),(self.root/'original'/n).read_bytes())
        with self.assertRaisesRegex(ValueError,'consumed'):b.install(folder,digest,self.cfg)
    def test_identity_path_topology_mode_and_package_must_match(self):
        folder,digest=self.exported()
        changes=[('root',str(self.root/'other')),('mode',p.MODES[1]),('packageManifestSha256','e'*64),('groupId','00000000-0000-0000-0000-000000000001')]
        for key,value in changes:
            with self.subTest(key=key),self.assertRaises(ValueError):b.install(folder,digest,dict(self.cfg,**{key:value}))
        for key,value in [('node','node-2'),('source','f'*40),('attempt','f'*32),('bundleSha256','f'*64)]:
            cfg=deepcopy(self.cfg);cfg['binding'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):b.install(folder,digest,cfg)
        self.assertEqual(list(self.cell.iterdir()),[])
    def test_corrupt_blob_leaves_consumed_claim_no_ready(self):
        folder,digest=self.exported();part=folder/'parts/part-0000.bin';part.write_bytes(part.read_bytes()[:-1])
        with self.assertRaises(ValueError):b.install(folder,digest,self.cfg)
        self.assertTrue((self.cell/b.CLAIM).exists());self.assertFalse((self.cell/b.READY).exists())
        with self.assertRaisesRegex(ValueError,'consumed'):b.install(folder,digest,self.cfg)
    def test_interrupted_publication_never_becomes_ready(self):
        folder,digest=self.exported()
        with patch.object(b.os,'rename',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):b.install(folder,digest,self.cfg)
        with self.assertRaises(FileNotFoundError):b.check_ready(self.cell,self.cfg)
        with self.assertRaisesRegex(ValueError,'consumed'):b.install(folder,digest,self.cfg)
    def test_wrong_digest_and_extra_peer_scope(self):
        folder,digest=self.exported()
        with self.assertRaisesRegex(ValueError,'digest'):b.install(folder,'0'*64,self.cfg)
        value=c.read(folder/'bootstrap.json');value['files']['node-2/current.gsr']=dict(bytes=0,sha256=m.sha(b''))
        (folder/'bootstrap.json').write_bytes(m.canonical(value))
        with self.assertRaisesRegex(ValueError,'member scope'):b.install(folder,m.sha(m.canonical(value)),self.cfg)
    def test_runtime_state_and_links_not_exportable(self):
        (self.cell/'node-1').mkdir();path=self.cell/'node-1/current.gsr';path.write_bytes(b'started')
        with self.assertRaisesRegex(ValueError,'authority cannot'):b.export(self.cell,self.root/'bad1',self.cfg)
        path.unlink();(self.cell/'node-1').rmdir();path=self.cell/'source/gse-backup-checkpoint';path.unlink();path.symlink_to(self.cell/'hosts.txt')
        with self.assertRaisesRegex(ValueError,'type'):b.export(self.cell,self.root/'bad2',self.cfg)
    def test_started_local_control_not_exportable(self):
        (self.cell/'node-1-jvm.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'already used'):b.export(self.cell,self.root/'bad',self.cfg)
    def test_modified_missing_and_foreign_initial_storage_prevents_launch(self):
        folder,digest=self.exported();b.install(folder,digest,self.cfg)
        path=self.cell/'source/gse-backup-checkpoint';original=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaises(ValueError):b.check_ready(self.cell,self.cfg)
        path.write_bytes(original);(self.cell/'node-2').mkdir()
        with self.assertRaisesRegex(ValueError,'unexpected'):b.check_ready(self.cell,self.cfg)
        (self.cell/'node-2').rmdir();path.unlink()
        with self.assertRaises(ValueError):b.check_ready(self.cell,self.cfg)
    def test_all_three_modes_have_closed_bootstrap_sets(self):
        for mode in p.MODES:
            cfg=dict(self.cfg,mode=mode);wanted=b.expected_files(cfg)
            self.assertTrue(set(b.TOPOLOGY)<=wanted)
            self.assertFalse(any(n.startswith('node-1/') for n in wanted))
            self.assertEqual(bool(b.authority_files(cfg)),mode!=p.MODES[0])
    def test_local_bootstrap_required_before_imported_seed_can_start(self):
        folder,digest=self.exported();b.install(folder,digest,self.cfg)
        with self.assertRaises(FileNotFoundError):b.check_ready(self.cell,self.cfg,sealed=True)
    def test_manifest_genesis_and_backup_disagreement_rejected_before_start(self):
        configs=[deepcopy(self.cfg) for _ in range(3)]
        for n,cfg in enumerate(configs,1):cfg['binding']['node']='node-'+str(n)
        identity=dict(sourceSha256='a'*64,manifestSha256='b'*64,genesisSha256='c'*64)
        rows=[dict(node=cfg['binding']['node'],status='PASS',identity=deepcopy(identity)) for cfg in configs]
        self.assertEqual(b.group_identity(rows,configs),identity)
        for key in identity:
            changed=deepcopy(rows);changed[1]['identity'][key]='0'*64
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'disagree'):b.group_identity(changed,configs)
        with self.assertRaisesRegex(ValueError,'member set'):b.group_identity(rows[:-1],configs)
    def test_topology_symlink_rejected(self):
        path=self.cell/'hosts.txt';data=path.read_bytes();path.unlink();other=self.root/'hosts';other.write_bytes(data);path.symlink_to(other)
        with self.assertRaises(ValueError):b.export(self.cell,self.root/'bad',self.cfg)

if __name__=='__main__':unittest.main()
