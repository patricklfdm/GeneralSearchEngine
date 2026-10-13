"""Release preparation must reject missing/mixed artifacts and retain failures."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from . import release_preparation as r


class ReleasePreparationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.version = '5.1.0-SNAPSHOT'
        self.paths = []
        for artifact in r.ARTIFACTS:
            directory = self.root/('target' if artifact == r.ARTIFACTS[0] else artifact+'/target')
            directory.mkdir(parents=True)
            for suffix in ('', '-sources', '-javadoc'):
                path = directory/f'{artifact}-{self.version}{suffix}.jar'; self.paths.append(path)
                self.jar(path)

    def jar(self, path, version=None, extra=None):
        with zipfile.ZipFile(path, 'w') as jar:
            jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\r\nImplementation-Version: '+
                         (version or self.version)+'\r\n')
            if extra:jar.writestr(extra, b'fixture')

    def test_complete_inventory_binds_nine_original_bytes(self):
        result = r.artifact_inventory(self.root, self.version)
        self.assertEqual(9, len(result))
        original = result[self.paths[0].name]['sha256']
        self.jar(self.paths[0], extra='application/New.class')
        self.assertNotEqual(original, r.artifact_inventory(self.root, self.version)[self.paths[0].name]['sha256'])

    def test_missing_classifier_mixed_version_and_test_assets_fail(self):
        for path in self.paths:
            original = path.read_bytes(); path.unlink()
            with self.assertRaisesRegex(ValueError, 'missing preparation'):r.artifact_inventory(self.root, self.version)
            path.write_bytes(original)
        self.jar(self.paths[0], version='5.0.0')
        with self.assertRaisesRegex(ValueError, 'artifact version'):r.artifact_inventory(self.root, self.version)
        self.jar(self.paths[0])
        for extra in ('fixture/v51/Test.class', 'io/github/admission/Test.java', 'io/replication/v51/catalog.json'):
            self.jar(self.paths[1], extra=extra)
            with self.assertRaisesRegex(ValueError, 'asset leak'):r.artifact_inventory(self.root, self.version)

    def test_historical_other_versions_are_not_candidate_preparation(self):
        for version in ('5.1.0-SNAPSHOT', '5.1.0', '5.0.0', '5.2.0-SNAPSHOT'):
            (self.root/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><version>'+version+'</version></project>')
            if version.startswith('5.1.'):
                self.assertEqual(version, r.version(self.root))
            else:
                with self.assertRaisesRegex(ValueError, 'preparation version'):r.version(self.root)

    def test_failure_receipt_does_not_claim_candidate_freeze_or_overwrite(self):
        output = self.root/'audit'
        with patch.object(r, 'version', side_effect=ValueError('broken version')):
            with self.assertRaisesRegex(ValueError, 'broken version'):r.run(output, self.root/'controls')
        receipt = r.c.read(output/'receipt.json')
        self.assertEqual('FAIL', receipt['status'])
        self.assertFalse(receipt['candidateFrozen']); self.assertFalse(receipt['publication'])
        with self.assertRaises(FileExistsError):r.run(output, self.root/'controls')
        self.assertEqual(receipt, r.c.read(output/'receipt.json'))


if __name__ == '__main__': unittest.main()
