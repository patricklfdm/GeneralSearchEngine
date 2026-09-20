"""Regression coverage for inherited gates after opening a new reactor version."""
from pathlib import Path
import tempfile
import unittest

from .offline_harness import current_jars


class CurrentJarsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def pom(self, version):
        (self.root / 'pom.xml').write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0">'
            '<modelVersion>4.0.0</modelVersion>'
            '<parent><version>99.0.0</version></parent>'
            f'<version>{version}</version></project>')

    def jars(self, version, contents):
        paths = (self.root / f'target/general-search-engine-{version}.jar',
                 self.root / 'general-search-engine-replication/target' /
                 f'general-search-engine-replication-{version}.jar')
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        return paths

    def test_clean_build_uses_current_version_without_a_previous_release(self):
        for version in ('5.0.0', '5.1.0-SNAPSHOT', '5.2.0-SNAPSHOT'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                self.pom(version)
                expected = self.jars(version, b'current build')
                self.assertEqual(expected, current_jars(self.root))
                self.assertEqual([b'current build'] * 2, [p.read_bytes() for p in current_jars(self.root)])

    def test_stale_release_and_classifier_jars_cannot_substitute_for_current_build(self):
        self.pom('5.1.0-SNAPSHOT')
        for version in ('5.0.0', '5.1.0-SNAPSHOT-sources', '5.1.0-SNAPSHOT-javadoc'):
            self.jars(version, b'not the current production jar')
        for path in current_jars(self.root):
            with self.subTest(path=path), self.assertRaises(FileNotFoundError):
                path.read_bytes()
        self.jars('5.1.0-SNAPSHOT', b'current build')
        self.assertEqual([b'current build'] * 2, [p.read_bytes() for p in current_jars(self.root)])

    def test_missing_project_version_does_not_fall_back_to_parent(self):
        self.pom('')
        with self.assertRaisesRegex(ValueError, 'root POM'):
            current_jars(self.root)


if __name__ == '__main__':
    unittest.main()
