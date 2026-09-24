"""Bundle boundaries; use tiny outputs so docs-only checks need no JDK/Maven."""
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import ci_v51_bundle as b


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'producer'; self.root.mkdir()
        self.consumer = self.base / 'consumer'; self.consumer.mkdir()
        self.source = 'a' * 40
        self.identity = dict(source=self.source, checkoutSha256='b' * 64, java={'version': 'pinned'})
        binding_patch = patch.object(b, 'binding', return_value=self.identity)
        binding_patch.start(); self.addCleanup(binding_patch.stop)
        for root in (self.root, self.consumer):
            (root / 'pom.xml').write_text('<project><version>5.1.0-SNAPSHOT</version></project>')
        self.state = self.base / 'state.json'; self.bundle = self.base / 'bundle'
        b.prepare(self.root, self.source, self.state)
        self.roots = b.layout(self.root)
        for name in self.roots[:2]: self.write(name, b'jar fixture')
        for name in ('V51StorageWorker', 'V51ProtocolWorker', 'V51RuntimeWorker'):
            self.write(b.CLASSES + '/package/' + name + '.class', b'class fixture')
        for name in b.REQUIRED_SUITES:
            self.write(b.REPORTS + '/TEST-package.' + name + '.xml',
                       f'<testsuite name="package.{name}" tests="30" errors="0" failures="0" skipped="0"/>'.encode())
        b.create(self.root, self.source, self.state, self.bundle)

    def write(self, name, data):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)

    def restore(self):
        with patch.object(b, 'git', return_value=b'pom.xml\0'):
            return b.restore(self.consumer, self.source, self.bundle)

    def manifest(self, change):
        path = self.bundle / 'manifest.json'; value = json.loads(path.read_text())
        change(value); b.save(path, value)

    def repack(self, change):
        archive = self.bundle / 'build.tar.gz'
        with tarfile.open(archive) as tar:
            members = [(v, tar.extractfile(v).read()) for v in tar]
        members = change(members)
        with tarfile.open(archive, 'w:gz') as tar:
            for info, data in members: tar.addfile(info, io.BytesIO(data) if info.isfile() else None)
        self.manifest(lambda m: m.update(archiveSha256=b.digest(archive.read_bytes())))

    def test_minimal_restore_preserves_bytes_and_rebases_freshness(self):
        future = (self.consumer / 'pom.xml').stat().st_mtime_ns + 10_000_000_000
        os.utime(self.consumer / 'pom.xml', ns=(future, future))
        receipt = self.restore()
        self.assertEqual('PASS', receipt['status'])
        expected = json.loads((self.bundle / 'manifest.json').read_text())['files']
        for entry in expected:
            path = self.consumer / entry['path']
            self.assertEqual(entry['sha256'], b.digest(path.read_bytes()))
            self.assertGreaterEqual(path.stat().st_mtime_ns, future)
        self.assertFalse((self.consumer / 'target/classes').exists())
        self.assertFalse((self.consumer / '.m2').exists())

    def test_archive_is_deterministic_across_file_timestamps(self):
        original = (self.bundle / 'build.tar.gz').read_bytes()
        for path in self.root.rglob('*'):
            if path.is_file(): os.utime(path, None)
        b.create(self.root, self.source, self.state, self.bundle)
        self.assertEqual(original, (self.bundle / 'build.tar.gz').read_bytes())

    def test_wrong_source_toolchain_or_layout_rejected_before_restoring(self):
        for key in ('source', 'checkoutSha256', 'java'):
            with self.subTest(key=key), patch.object(b, 'binding', return_value={**self.identity, key: 'wrong'}):
                with self.assertRaisesRegex(ValueError, 'source/toolchain'): self.restore()
        self.manifest(lambda m: m.update(roots=['wrong']))
        with self.assertRaisesRegex(ValueError, 'layout'): self.restore()
        self.assertFalse((self.consumer / 'target').exists())

    def test_dirty_build_binding_or_stale_output_rejected(self):
        with patch.object(b, 'binding', return_value={**self.identity, 'checkoutSha256': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'changed during build'):
                b.create(self.root, self.source, self.state, self.bundle)
        os.utime(self.root / self.roots[0], ns=(0, 0))
        with self.assertRaisesRegex(ValueError, 'stale build'):
            b.create(self.root, self.source, self.state, self.bundle)

    def test_corrupt_archive_and_file_hash_rejected(self):
        archive = self.bundle / 'build.tar.gz'; original = archive.read_bytes()
        archive.write_bytes(original + b'corrupt')
        with self.assertRaisesRegex(ValueError, 'archive hash'): self.restore()
        archive.write_bytes(original)
        self.manifest(lambda m: m['files'][0].update(sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'member hash'): self.restore()

    def test_missing_or_duplicate_manifest_paths_rejected(self):
        original = (self.bundle / 'manifest.json').read_bytes()
        self.manifest(lambda m: m['files'].append(m['files'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.restore()
        (self.bundle / 'manifest.json').write_bytes(original)
        self.manifest(lambda m: m['files'].pop())
        with self.assertRaisesRegex(ValueError, 'unexpected'): self.restore()

    def test_traversal_absolute_and_unapproved_paths_rejected(self):
        original = (self.bundle / 'manifest.json').read_bytes()
        for path in ('../escape', '/tmp/escape', 'target/classes/X.class', b.CLASSES + '/../../escape'):
            with self.subTest(path=path):
                (self.bundle / 'manifest.json').write_bytes(original)
                self.manifest(lambda m: m['files'][0].update(path=path))
                with self.assertRaisesRegex(ValueError, 'bundle path'): self.restore()

    def test_missing_member_rejected(self):
        self.repack(lambda members: members[:-1])
        with self.assertRaisesRegex(ValueError, 'missing archive'): self.restore()

    def test_duplicate_member_rejected(self):
        self.repack(lambda members: members + [members[0]])
        with self.assertRaisesRegex(ValueError, 'duplicate archive'): self.restore()

    def test_archive_link_rejected(self):
        def link(members):
            members[0][0].type = tarfile.SYMTYPE; members[0][0].linkname = '/tmp/escape'
            return members
        self.repack(link)
        with self.assertRaisesRegex(ValueError, 'linked'): self.restore()

    def test_existing_output_and_linked_parent_rejected(self):
        path = self.consumer / self.roots[0]; path.parent.mkdir(); path.write_bytes(b'existing')
        with self.assertRaisesRegex(ValueError, 'existing'): self.restore()
        self.assertEqual(b'existing', path.read_bytes()); path.unlink(); path.parent.rmdir()
        external = self.base / 'external'; external.mkdir(); path.parent.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'linked destination'): self.restore()
        self.assertFalse(list(external.iterdir()))

    def test_missing_failed_or_skipped_prerequisites_rejected(self):
        name = next(iter(b.REQUIRED_SUITES)); path = self.root / (b.REPORTS + '/TEST-package.' + name + '.xml')
        original = path.read_bytes()
        for bad in (b'tests="0"', b'failures="1"', b'errors="1"', b'skipped="1"'):
            attribute = bad.split(b'=')[0]
            import re
            path.write_bytes(re.sub(attribute + b'="[0-9]+"', bad, original))
            with self.assertRaisesRegex(ValueError, 'suite|prerequisite'):
                b.create(self.root, self.source, self.state, self.bundle)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing executed'):
            b.create(self.root, self.source, self.state, self.bundle)

    def test_oversized_manifest_rejected(self):
        self.manifest(lambda m: m['files'][0].update(size=b.MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'bundle size'): self.restore()

    def test_cli_keeps_failure_receipt(self):
        receipt = self.base / 'failed-restore.json'
        argv = ['bundle', 'restore', '--source', self.source, '--workspace', str(self.consumer),
                '--bundle', str(self.base / 'missing'), '--receipt', str(receipt)]
        with patch('sys.argv', argv):
            self.assertEqual(2, b.main())
        self.assertEqual('FAIL', json.loads(receipt.read_text())['status'])
        self.assertFalse((self.consumer / 'target').exists())

    def test_binding_checks_checkout_content_modes_and_java(self):
        java = subprocess.CompletedProcess([], 0, '', ' java.runtime.version = 21.0.12+8-LTS\n java.vendor = Eclipse Adoptium\n')
        with patch.object(b, 'git', side_effect=lambda root, *args: self.source.encode() if args[0] == 'rev-parse' else b'pom.xml\0'), patch.object(b.subprocess, 'run', return_value=java):
            initial = REAL_BINDING(self.root, self.source)
            (self.root / 'pom.xml').write_text('changed')
            self.assertNotEqual(initial['checkoutSha256'], REAL_BINDING(self.root, self.source)['checkoutSha256'])
            before = REAL_BINDING(self.root, self.source)
            (self.root / 'pom.xml').chmod(0o755)
            self.assertNotEqual(before['checkoutSha256'], REAL_BINDING(self.root, self.source)['checkoutSha256'])
            java.stderr = java.stderr.replace('21.0.12+8-LTS', '21.0.13+1-LTS')
            self.assertNotEqual(before['java'], REAL_BINDING(self.root, self.source)['java'])
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'): REAL_BINDING(self.root, 'c' * 40)


REAL_BINDING = b.binding

if __name__ == '__main__':
    unittest.main()
