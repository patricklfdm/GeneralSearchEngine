"""Final coordinates, frozen toolchain and publication checks are release gates."""
import hashlib
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from . import candidate_artifacts as candidate, canonical_reproducibility as canonical
from .toolchain_manifest import validate
from scripts.build_coordinates import current as build_version

ROOT = Path(__file__).resolve().parents[2]
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_toolchain_and_complete_candidate_inventory(self):
        path=ROOT/'docs/v5x/v5.2/release-toolchain.json'
        self.assertEqual('e0e209b7e4f74d75cd61431aaa00c5e472940e8ab14ec100bb830af0f83702f0',hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(9,validate(path)['canonicalJarCount'])
        self.assertEqual('5.2.0',canonical.VERSION)
        self.assertEqual(canonical.ARTIFACTS,set(candidate.read_manifest(ROOT/candidate.MANIFEST)))

    def test_final_coordinates_are_aligned_in_all_applications(self):
        current=build_version()
        self.assertEqual('5.2.0', current)
        for name in ('pom.xml','general-search-engine-processor/pom.xml','general-search-engine-replication/pom.xml',
                     'reactor/pom.xml','examples/travel-search/pom.xml'):
            self.assertEqual(current,ET.parse(ROOT/name).getroot().findtext('m:version',namespaces=NS),name)
        consumers=list((ROOT/'compatibility').glob('*-style-consumer/pom.xml'))
        expected={'v1','v2','v3','v4','v5','v51','v52'}
        self.assertEqual({v+'-style-consumer' for v in expected},{p.parent.name for p in consumers})
        for path in consumers:self.assertEqual(current,ET.parse(path).getroot().findtext('m:properties/m:gse.version',namespaces=NS))

    def test_ci_and_release_require_exact_commit_canonical_receipt(self):
        for name in ('ci.yml','release.yml'):
            text=(ROOT/'.github/workflows'/name).read_text()
            self.assertIn('scripts/verify-v52-phase7-release.sh --skip-consumers',text)
            self.assertIn('scripts/verify-v52-canonical-build.sh',text)
            self.assertIn('scripts.v52.candidate_artifacts validate-evidence target/v52-canonical-reproducibility --source ',text)
            self.assertIn('scripts.v52.candidate_artifacts validate-build',text)
        text=(ROOT/'.github/workflows/release.yml').read_text()
        build=text.split('- name: Build, sign, and inspect release artifacts',1)[1].split('- name: Publish approved artifacts',1)[0]
        v52=build.split('elif [[ "$RELEASE_TAG" == "v5.2.0" ]]; then',1)[1].split('elif ',1)[0]
        self.assertEqual(2,v52.count('scripts.v52.candidate_artifacts validate-build'))
        deploy=text.split('- name: Publish approved artifacts to Maven Central',1)[1].split('- name: Verify remote artifacts',1)[0]
        before,after=deploy.split(' deploy ',1)
        for block in (before,after):self.assertIn('scripts.v52.candidate_artifacts validate-build',block)
        self.assertIn('environment: production-release',text)

    def test_remote_verifier_checks_poms_and_all_consumers_before_success(self):
        text=(ROOT/'scripts/verify-published-release.sh').read_text()
        self.assertIn('"$verification_root/candidate-artifacts/$artifact.pom"',text)
        self.assertIn('scripts.v52.candidate_artifacts validate-directory',text)
        self.assertIn('for consumer in v51 v52; do',text)
        self.assertIn('if [[ "$version" == 5.2.* ]]; then',text)
        self.assertLess(text.index('for consumer in v51 v52; do'),text.index('Published release verification: PASS'))

    def test_release_receipts_retained_for_ninety_days(self):
        from scripts import ci_suites as suites
        for workflow, names in (
            ('ci.yml', ('Retain V5.2 release preparation receipt', 'Upload V5.2 canonical reproducibility receipt')),
            ('release.yml', ('Retain V5.2 release receipts',)),
        ):
            jobs=suites.job_blocks((ROOT/'.github/workflows'/workflow).read_text())
            steps={}
            for job in jobs.values(): steps.update(suites.steps(suites.fields(job,4)['steps']))
            for name in names:
                self.assertGreaterEqual(int(suites.string_map(steps[name]['with'],10)['retention-days']),90)
                self.assertIn('always()',suites.scalar(steps[name]['if']))


if __name__ == '__main__':unittest.main()
