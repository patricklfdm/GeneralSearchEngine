"""Downloaded evidence must validate retained bytes, never files on the old runner."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from . import performance_evidence as e, performance_model as m, storage_inspector as s


class RelocatedArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'download';self.root.mkdir()
        self.mode='candidate-v5.1-automatic';self.classes=self.root/('classes-'+self.mode);self.classes.mkdir()
        (self.classes/'Adapter.class').write_bytes(b'adapter')
        (self.root/'artifacts').mkdir();self.original=Path('/unavailable-ci-run/evidence')
        artifacts=[]
        for name in ('general-search-engine','general-search-engine-replication'):
            path=self.root/'artifacts'/(name+'-5.1.0-SNAPSHOT.jar')
            with zipfile.ZipFile(path,'w') as archive:archive.writestr(name+'/Product.class',b'product')
            artifacts.append(dict(path=str(self.original/'artifacts'/path.name),sha256=m.sha(path.read_bytes())))
        self.adapter=dict(artifacts=artifacts,classes=s.inventory(self.classes),sources={'probe.java':'a'*64},
                          cp=os.pathsep.join([a['path'] for a in artifacts]+[str(self.original/self.classes.name)]))

    def validate(self):e.artifacts(self.root,self.mode,self.adapter,{}, {'probe.java':'a'*64})

    def test_downloaded_bundle_validates_without_original_runner_paths(self):self.validate()

    def test_tampered_or_missing_retained_bytes_fail(self):
        p=self.root/'artifacts'/Path(self.adapter['artifacts'][0]['path']).name
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'retained artifact'):self.validate()
        p.unlink()
        with self.assertRaisesRegex(ValueError,'retained artifact'):self.validate()

    def test_recorded_classpath_must_still_match_original_artifact_roots(self):
        original=copy.deepcopy(self.adapter)
        for cp in (self.adapter['cp']+':/injected/classes', self.adapter['cp'].replace(str(self.original),str(self.root))):
            self.adapter=copy.deepcopy(original);self.adapter['cp']=cp
            with self.assertRaisesRegex(ValueError,'classpath'):self.validate()
        self.adapter=copy.deepcopy(original);self.adapter['artifacts'][1]['path']='/other/artifacts/replication.jar'
        with self.assertRaisesRegex(ValueError,'classpath'):self.validate()

    def test_symlink_or_noncanonical_recorded_artifact_is_rejected(self):
        original=copy.deepcopy(self.adapter)
        for path in ('relative/artifacts/a.jar','/old/artifacts/../artifacts/a.jar','/old/classes/a.jar'):
            self.adapter=copy.deepcopy(original);self.adapter['artifacts'][0]['path']=path
            with self.assertRaises(ValueError):self.validate()
        self.adapter=original
        path=self.root/'artifacts'/Path(original['artifacts'][0]['path']).name
        actual=self.root/'elsewhere.jar';path.rename(actual);path.symlink_to(actual)
        with self.assertRaisesRegex(ValueError,'retained artifact'):self.validate()

    def test_classes_must_still_match_inventory_and_not_shadow_production(self):
        (self.classes/'Adapter.class').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'inventory'):self.validate()
        self.adapter['classes']=s.inventory(self.classes)
        path=self.root/'artifacts'/Path(self.adapter['artifacts'][0]['path']).name
        with zipfile.ZipFile(path,'a') as archive:archive.writestr('Adapter.class',b'forged')
        self.adapter['artifacts'][0]['sha256']=m.sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'shadows'):self.validate()


class RelocatedInventoryTest(unittest.TestCase):
    def test_relocated_evidence_requires_intact_complete_inventory(self):
        from .performance_artifacts import EvidenceLocation
        from .performance_bundle import members
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'data').write_bytes(b'authority')
            with self.assertRaisesRegex(ValueError,'inventory'):EvidenceLocation(root,Path('/old/run'))
            (root/'bundle-members.json').write_bytes(m.canonical(members(root)))
            EvidenceLocation(root,Path('/old/run'))
            (root/'data').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'inventory differs'):EvidenceLocation(root,Path('/old/run'))
