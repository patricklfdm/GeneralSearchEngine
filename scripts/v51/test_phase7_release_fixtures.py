"""Final coordinates, frozen toolchain and publication checks are release gates."""
import hashlib
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from . import artifact_version as version, candidate_artifacts as candidate, canonical_reproducibility as canonical
from .toolchain_manifest import validate
from scripts.build_coordinates import current as build_version

ROOT = Path(__file__).resolve().parents[2]
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}


class Phase7ReleaseFixtureTest(unittest.TestCase):
    def test_frozen_toolchain_and_complete_candidate_inventory(self):
        path=ROOT/'docs/v5x/v5.1/release-toolchain.json'
        self.assertEqual('4b6a57bb767b7e6f4b323f7b0566038bd04eebd94074b03013b25d27a4e118bf',hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(9,validate(path)['canonicalJarCount'])
        self.assertEqual('5.1.0',canonical.VERSION)
        self.assertEqual(canonical.ARTIFACTS,set(candidate.read_manifest(ROOT/candidate.MANIFEST)))

    def test_final_coordinates_are_aligned_in_all_applications(self):
        current=build_version()
        self.assertEqual(('5.1.0-SNAPSHOT','5.1.0'),version.VERSIONS)
        for name in ('pom.xml','general-search-engine-processor/pom.xml','general-search-engine-replication/pom.xml',
                     'reactor/pom.xml','examples/travel-search/pom.xml'):
            self.assertEqual(current,ET.parse(ROOT/name).getroot().findtext('m:version',namespaces=NS),name)
        consumers=list((ROOT/'compatibility').glob('*-style-consumer/pom.xml'))
        expected={'v1','v2','v3','v4','v5','v51'}
        if current=='5.2.0-SNAPSHOT':expected.add('v52')
        self.assertEqual({v+'-style-consumer' for v in expected},{p.parent.name for p in consumers})
        for path in consumers:self.assertEqual(current,ET.parse(path).getroot().findtext('m:properties/m:gse.version',namespaces=NS))

    def test_ci_and_release_require_exact_commit_canonical_receipt(self):
        for name in ('ci.yml','release.yml'):
            text=(ROOT/'.github/workflows'/name).read_text()
            self.assertIn('scripts/verify-v51-phase7-release.sh --skip-consumers',text)
            self.assertIn('scripts/verify-v51-canonical-build.sh',text)
            self.assertIn('scripts.v51.candidate_artifacts validate-evidence target/v51-canonical-reproducibility --source ',text)
            self.assertIn('scripts.v51.candidate_artifacts validate-build',text)
        text=(ROOT/'.github/workflows/release.yml').read_text()
        build=text.split('- name: Build, sign, and inspect release artifacts',1)[1].split('- name: Publish approved artifacts',1)[0]
        v51=build.split('elif [[ "$RELEASE_TAG" == "v5.1.0" ]]; then',1)[1].split('elif ',1)[0]
        self.assertEqual(2,v51.count('scripts.v51.candidate_artifacts validate-build'))
        deploy=text.split('- name: Publish approved artifacts to Maven Central',1)[1].split('- name: Verify remote artifacts',1)[0]
        before,after=deploy.split(' deploy ',1)
        for block in (before,after):self.assertIn('scripts.v51.candidate_artifacts validate-build',block)
        self.assertIn('environment: production-release',text)

    def test_remote_verifier_checks_poms_and_all_consumers_before_success(self):
        text=(ROOT/'scripts/verify-published-release.sh').read_text()
        self.assertIn('"$verification_root/candidate-artifacts/$artifact.pom"',text)
        self.assertIn('scripts.v51.candidate_artifacts validate-directory',text)
        self.assertIn('compatibility/v51-style-consumer/pom.xml',text)
        self.assertIn('if [[ "$version" == 5.1.* ]]; then',text)
        self.assertLess(text.index('compatibility/v51-style-consumer/pom.xml'),text.index('Published release verification: PASS'))

    def test_release_gate_invokes_baseline_check_with_its_required_arguments(self):
        script=(ROOT/'scripts/verify-v51-phase7-release.sh').read_text().replace('\\\n','')
        invocation=next(line for line in script.splitlines() if line.startswith('python3 -m scripts.v51.native_set_review check'))
        args=shlex.split(invocation);args[0]=sys.executable
        result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__ == '__main__':unittest.main()
