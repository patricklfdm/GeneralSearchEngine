"""Release gates reject substituted evidence, stale runtime inputs and broken packages."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from . import release_baseline as b, release_preparation as r
from .evidence import strict, encoded


class BaselineTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        rules = b.policy()
        for directory in rules['runtimeSource']['directories']:
            shutil.copytree(b.ROOT/directory, self.root/directory)
        for name in [*rules['runtimeSource']['files'], b.DOCS+'/release-preparation.json',
                     *(b.DOCS+'/'+name for name in rules['cloudFiles'])]:
            dest = self.root/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(b.ROOT/name, dest)

    def test_accepted_baseline_needs_neither_historical_git_nor_network(self):
        with patch('subprocess.check_output', side_effect=AssertionError('no history/network')):
            result = b.check(self.root)
        self.assertEqual(15, result['totals']['members'])
        self.assertEqual(5, len(result['measuredArtifactPins']))
        self.assertTrue(result['candidateJarEqualityToCloudNotAsserted'])

    def test_jointly_rewriting_registry_and_receipt_cannot_substitute_authority(self):
        for name, modify in (
            ('phase6-cloud-review.json', lambda v: v['source'].update(source='f'*40)),
            ('phase6-cloud-provenance.json', lambda v: v['acceptanceRun'].update(run_attempt=2)),
            ('cloud-benchmark-baselines.json', lambda v: v['baselines'][0].update(releaseCandidateQualified=True)),
            ('experiment-retention-recovery.json', lambda v: v['originals'].pop('experiment')),
            ('published-controls.json', lambda v: v['artifacts'][0].update(sha256='0'*64)),
        ):
            path = self.root/b.DOCS/name; raw = path.read_bytes(); value = strict(raw); modify(value)
            path.write_bytes(encoded(value))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'accepted release input changed'):
                b.check(self.root)
            path.write_bytes(raw)
        path = self.root/b.DOCS/'release-preparation.json'; value = strict(path.read_bytes())
        value['acceptedVerifierSource'] = 'f'*40; path.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError, 'policy changed'): b.check(self.root)

    def test_runtime_addition_change_deletion_and_build_drift_require_review(self):
        path = self.root/'src/main/java/Unexpected.java'; path.write_text('class Unexpected {}')
        with self.assertRaisesRegex(ValueError, 'runtime/build source differs'): b.check(self.root)
        path.unlink()
        for name in ('pom.xml', 'general-search-engine-replication/pom.xml',
                     'general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/ReplicaReadToken.java'):
            path = self.root/name; raw = path.read_bytes(); path.write_bytes(raw+b'\n')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'runtime/build source differs'): b.check(self.root)
            path.unlink()
            with self.assertRaises(ValueError): b.check(self.root)
            path.write_bytes(raw)

    def test_linked_evidence_or_runtime_is_rejected(self):
        for name in (b.DOCS+'/phase6-cloud-review.json', 'pom.xml'):
            path = self.root/name; raw = path.read_bytes(); path.unlink(); path.symlink_to(b.ROOT/name)
            with self.assertRaisesRegex(ValueError, 'regular file'): b.check(self.root)
            path.unlink(); path.write_bytes(raw)


class PackagingTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.version = '5.2.0-SNAPSHOT'; self.paths = []
        for artifact, marker, java_module in zip(r.ARTIFACTS, r.MARKERS, r.MODULES):
            module = self.root if artifact == r.ARTIFACTS[0] else self.root/artifact
            (module/'target').mkdir(parents=True)
            pom = ('<project><groupId>io.github.patricklfdm</groupId><artifactId>'+artifact+
                   '</artifactId><version>'+self.version+'</version></project>').encode()
            (module/'pom.xml').write_bytes(pom)
            java = module/'src/main/java'/f'{r.PACKAGE}{marker}.java'
            java.parent.mkdir(parents=True); java.write_bytes(b'fixture')
            for suffix, extension in (('', '.class'), ('-sources', '.java'), ('-javadoc', '.html')):
                path = module/'target'/f'{artifact}-{self.version}{suffix}.jar'
                prefix = java_module+'/' if suffix == '-javadoc' else ''
                values = {prefix+r.PACKAGE+marker+extension: b'fixture'}
                if not suffix:
                    values['META-INF/MANIFEST.MF'] = ('Manifest-Version: 1.0\r\nImplementation-Version: '+self.version+'\r\n').encode()
                    values[f'META-INF/maven/io.github.patricklfdm/{artifact}/pom.xml'] = pom
                    if artifact == r.ARTIFACTS[1]: values[r.SERVICE] = (r.PROCESSOR+'\n').encode()
                self.write(path, values); self.paths.append((path, values))

    def write(self, path, values):
        with zipfile.ZipFile(path, 'w') as jar:
            for name, value in values.items(): jar.writestr(name, value)

    def test_nine_jars_three_poms_and_original_hashes(self):
        result = r.artifact_inventory(self.root, self.version)
        self.assertEqual(12, len(result))
        self.assertTrue(all(v['bytes'] > 0 and len(v['sha256']) == 64 for v in result.values()))

    def test_every_missing_classifier_and_pom_rejects(self):
        paths = [p for p, _ in self.paths]+[self.root/'pom.xml', *(self.root/a/'pom.xml' for a in r.ARTIFACTS[1:])]
        for path in paths:
            raw = path.read_bytes(); path.unlink()
            with self.subTest(path=path), self.assertRaises(ValueError): r.artifact_inventory(self.root, self.version)
            path.write_bytes(raw)

    def test_wrong_version_embedded_pom_services_missing_api_and_test_leaks(self):
        path, original = self.paths[0]
        changes = [dict(original, **{'META-INF/MANIFEST.MF': b'Implementation-Version: 5.1.0\n'}),
                   dict(original, **{next(n for n in original if n.endswith('pom.xml')): b'<project/>'}),
                   {k: v for k, v in original.items() if not k.endswith('.class')},
                   dict(original, **{r.SERVICE: r.PROCESSOR.encode()})]
        for name in ('fixture/v52/Control.class', 'io/replication/v52/test.json', 'compatibility/api.txt'):
            changes.append(dict(original, **{name: b'leak'}))
        for values in changes:
            self.write(path, values)
            with self.assertRaises(ValueError): r.artifact_inventory(self.root, self.version)
        self.write(path, original)
        path, original = self.paths[3]
        for value in (b'wrong.Processor', b''):
            self.write(path, dict(original, **{r.SERVICE: value}))
            with self.assertRaisesRegex(ValueError, 'processor service'): r.artifact_inventory(self.root, self.version)

    def test_duplicate_and_symlinked_jar_rejects(self):
        path, original = self.paths[0]
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(path, 'a') as jar: jar.writestr(next(iter(original)), b'duplicate')
        with self.assertRaisesRegex(ValueError, 'duplicate'): r.artifact_inventory(self.root, self.version)
        other = path.with_suffix('.copy'); path.rename(other); path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'regular file'): r.artifact_inventory(self.root, self.version)

    def test_stale_sources_classifier_is_not_accepted_with_current_main_jar(self):
        path, original = self.paths[1]
        values = dict(original); values[next(iter(values))] = b'old source'
        self.write(path, values)
        with self.assertRaisesRegex(ValueError, 'packaged sources differ'): r.artifact_inventory(self.root, self.version)

    def test_javadoc_requires_the_exact_java_module_directory(self):
        for index in (2, 5, 8):
            path, original = self.paths[index]; name = next(iter(original))
            for changed in (name.split('/', 1)[1], 'wrong.module/'+name.split('/', 1)[1]):
                self.write(path, {changed: b'documentation'})
                with self.assertRaisesRegex(ValueError, 'missing packaged API'): r.artifact_inventory(self.root, self.version)
            self.write(path, original)

    def test_failure_receipt_preserved_and_no_candidate_claim(self):
        output = self.root/'audit'
        with patch.object(b, 'check', side_effect=ValueError('baseline rejected')):
            with self.assertRaisesRegex(ValueError, 'baseline rejected'): r.run(output, self.root/'controls')
        receipt = strict((output/'receipt.json').read_bytes())
        self.assertEqual('FAIL', receipt['status'])
        for name in ('candidateFrozen', 'publication', 'paidCloud', 'rawCloudReplayed'): self.assertFalse(receipt[name])
        with self.assertRaises(FileExistsError): r.run(output, self.root/'controls')


if __name__ == '__main__': unittest.main()
