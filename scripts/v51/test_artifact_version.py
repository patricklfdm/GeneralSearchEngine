"""Final coordinates must not invalidate pinned historical snapshot evidence."""
from pathlib import Path
import tempfile
import unittest
from . import artifact_version as v


class ArtifactVersionTest(unittest.TestCase):
    def test_exact_current_coordinate_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for version in (*v.VERSIONS, '5.0.0', '5.1.0-SNAPSHOT-forged', '5.2.0'):
                (root/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><version>'+version+'</version></project>')
                if version in v.VERSIONS:self.assertEqual(version,v.current(root))
                else:
                    with self.assertRaises(ValueError):v.current(root)
            for version in v.VERSIONS:
                v.check_manifest(('Manifest-Version: 1.0\r\nImplementation-Version: '+version+'\r\n').encode(),version)
                for raw in (b'Implementation-Version: 5.0.0\n',('Implementation-Version: '+version+'-forged\n').encode(),
                            ('Implementation-Version: '+version+'\n').encode()*2):
                    with self.assertRaises(ValueError):v.check_manifest(raw,version)

    def test_historical_and_final_pairs_both_pass_but_mixed_or_wrong_roles_fail(self):
        for version in v.VERSIONS:
            v.candidate_pair([f'{name}-{version}.jar' for name in v.MODULES])
        for names in (['general-search-engine-5.1.0.jar','general-search-engine-replication-5.1.0-SNAPSHOT.jar'],
                      ['general-search-engine-5.1.0.jar']*2,
                      ['evil-5.1.0.jar','general-search-engine-replication-5.1.0.jar'],
                      [f'{name}-5.2.0.jar' for name in v.MODULES]):
            with self.assertRaises(ValueError):v.candidate_pair(names)
