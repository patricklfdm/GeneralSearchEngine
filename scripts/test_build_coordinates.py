import hashlib
from pathlib import Path
import tempfile
import unittest
from scripts import build_coordinates as b, ci_v51_bundle
from scripts.v51 import artifact_version as historical


class BuildCoordinatesTest(unittest.TestCase):
    def test_current_is_closed_and_historical_allowlist_stays_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for version in (*b.VERSIONS,'5.2.0','5.2.1-SNAPSHOT','5.2.0-SNAPSHOT-forged','6.0.0'):
                (root/'pom.xml').write_text('<project><version>'+version+'</version></project>')
                if version in b.VERSIONS:
                    self.assertEqual(version,b.current(root))
                    self.assertIn(version,ci_v51_bundle.layout(root)[0])
                else:
                    with self.assertRaises(ValueError):b.current(root)
            self.assertEqual(('5.1.0-SNAPSHOT','5.1.0'),historical.VERSIONS)
            with self.assertRaises(ValueError):historical.candidate_pair([n+'-5.2.0-SNAPSHOT.jar' for n in b.MODULES])

    def test_new_regression_pair_requires_exact_source_and_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pom=root/'pom.xml';pom.write_text('<project><version>5.2.0-SNAPSHOT</version></project>')
            source={'pom.xml':hashlib.sha256(pom.read_bytes()).hexdigest()}
            pair=[n+'-5.2.0-SNAPSHOT.jar' for n in b.MODULES]
            b.regression_pair(pair,source,root)
            for names,inventory in ((pair,{}),(pair,{'pom.xml':'0'*64}),(pair[:1],source),(pair*2,source),
                                     ([pair[0],pair[1].replace('5.2.0-SNAPSHOT','5.1.0')],source)):
                with self.assertRaises(ValueError):b.regression_pair(names,inventory,root)

    def test_v52_shared_build_requires_the_new_executed_tests(self):
        roots=['target/general-search-engine-5.2.0-SNAPSHOT.jar','replication.jar',ci_v51_bundle.CLASSES,ci_v51_bundle.REPORTS]
        files={name:b'jar' for name in roots[:2]}
        for worker in ('V51StorageWorker','V51ProtocolWorker','V51RuntimeWorker'):
            files[ci_v51_bundle.CLASSES+'/pkg/'+worker+'.class']=b'class'
        def add(name):
            files[ci_v51_bundle.REPORTS+'/TEST-'+name+'.xml']=f'<testsuite name="pkg.{name}" tests="1" failures="0" errors="0" skipped="0"/>'.encode()
        for name in ci_v51_bundle.REQUIRED_SUITES:add(name)
        with self.assertRaisesRegex(ValueError,'missing executed'):ci_v51_bundle.prerequisites(files,roots)
        for name in ('V52ReadTokenTest','V52PublicApiInventoryTest','V51PublicApiInventoryTest'):add(name)
        ci_v51_bundle.prerequisites(files,roots)
        key=ci_v51_bundle.REPORTS+'/TEST-V52ReadTokenTest.xml';files[key]=files[key].replace(b'skipped="0"',b'skipped="1"')
        with self.assertRaisesRegex(ValueError,'skipped prerequisite'):ci_v51_bundle.prerequisites(files,roots)

    def test_v53_requires_both_prior_reads_and_membership_declarations(self):
        roots=['target/general-search-engine-5.3.0-SNAPSHOT.jar','replication.jar',ci_v51_bundle.CLASSES,ci_v51_bundle.REPORTS]
        files={name:b'jar' for name in roots[:2]}
        for worker in ('V51StorageWorker','V51ProtocolWorker','V51RuntimeWorker'):
            files[ci_v51_bundle.CLASSES+'/pkg/'+worker+'.class']=b'class'
        required=ci_v51_bundle.REQUIRED_SUITES | {'V52ReadTokenTest','V52PublicApiInventoryTest',
            'V51PublicApiInventoryTest','V53DeclarationsTest','V53PublicApiInventoryTest'}
        for name in required:
            files[ci_v51_bundle.REPORTS+'/TEST-'+name+'.xml']=f'<testsuite name="pkg.{name}" tests="1" failures="0" errors="0" skipped="0"/>'.encode()
        ci_v51_bundle.prerequisites(files,roots)
        for name in required:
            key=ci_v51_bundle.REPORTS+'/TEST-'+name+'.xml';original=files.pop(key)
            with self.assertRaisesRegex(ValueError,'missing executed'):ci_v51_bundle.prerequisites(files,roots)
            files[key]=original.replace(b'skipped="0"',b'skipped="1"')
            with self.assertRaisesRegex(ValueError,'skipped prerequisite'):ci_v51_bundle.prerequisites(files,roots)
            files[key]=original
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pom=root/'pom.xml';pom.write_text('<project><version>5.3.0-SNAPSHOT</version></project>')
            source={'pom.xml':hashlib.sha256(pom.read_bytes()).hexdigest()}
            pair=[n+'-5.3.0-SNAPSHOT.jar' for n in b.MODULES]
            b.regression_pair(pair,source,root)
            with self.assertRaises(ValueError):b.regression_pair(pair,{},root)
            with self.assertRaises(ValueError):historical.candidate_pair(pair)
