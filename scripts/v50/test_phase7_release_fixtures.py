"""Freeze release inputs and keep replication publishable alongside core/processor."""
import hashlib
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from .canonical_reproducibility import ARTIFACTS, JARS, VERSION
from .candidate_artifacts import MANIFEST, read_manifest
from .toolchain_manifest import validate

ROOT = Path(__file__).resolve().parents[2]
NS = {"m": "http://maven.apache.org/POM/4.0.0"}


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_toolchain_and_nine_jar_inventory_are_frozen(self):
        path = ROOT / "docs/v5x/v5.0/release-toolchain.json"
        self.assertEqual("3433c725214836f80412ca86f3a0abbc448f6a47f4bfe88a4a23aed45d9a3390",
                         hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(9, validate(path)["canonicalJarCount"])
        self.assertEqual("5.0.0", VERSION)
        self.assertEqual(12, len(ARTIFACTS))
        self.assertEqual(JARS, set(read_manifest(ROOT / MANIFEST)))

    def test_all_three_artifacts_keep_aligned_coordinates_and_release_plugins(self):
        current = ET.parse(ROOT / "pom.xml").getroot().findtext("m:version", namespaces=NS)
        for module in (".", "general-search-engine-processor", "general-search-engine-replication"):
            with self.subTest(module=module):
                pom = ET.parse(ROOT / module / "pom.xml").getroot()
                self.assertEqual(current, pom.findtext("m:version", namespaces=NS))
                profile = pom.find("m:profiles/m:profile[m:id='release']", NS)
                plugins = {p.findtext("m:artifactId", namespaces=NS): p
                           for p in profile.findall("m:build/m:plugins/m:plugin", NS)}
                central = plugins["central-publishing-maven-plugin"]
                self.assertEqual("true", central.findtext("m:extensions", namespaces=NS))
                self.assertEqual("central", central.findtext(
                    "m:configuration/m:publishingServerId", namespaces=NS))
                for required in ("maven-source-plugin", "maven-javadoc-plugin", "maven-gpg-plugin"):
                    self.assertIn(required, plugins)
        replication = ET.parse(ROOT / "general-search-engine-replication/pom.xml").getroot()
        dependency = replication.find("m:dependencies/m:dependency[m:artifactId='general-search-engine']", NS)
        self.assertEqual("${project.version}", dependency.findtext("m:version", namespaces=NS))


if __name__ == "__main__":
    unittest.main()
