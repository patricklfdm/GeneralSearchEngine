import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest
from . import cloud_package as p, cloud_bundle as bundle


def save(path, value): path.write_text(json.dumps(value))


def fixture(root):
    root.mkdir(); modes = {}; pins = []; candidates = []
    for mode, version in zip(p.MODES, ('4.4.0', '5.0.0', '5.1.0-SNAPSHOT')):
        jars = []
        for name in ('general-search-engine',) if mode == p.MODES[0] else ('general-search-engine', 'general-search-engine-replication'):
            path = 'artifacts/'+name+'-'+version+'.jar'; target = root/path; target.parent.mkdir(exist_ok=True)
            target.write_bytes(path.encode()); jars.append(path)
            if mode == p.MODES[2]:
                candidates.append(dict(path=('general-search-engine-replication/target/' if 'replication' in name else 'target/')+target.name, sha256=p.sha(target.read_bytes())))
            else: pins.append(dict(artifact=name, version=version, sha256=p.sha(target.read_bytes())))
        directory = 'classes-'+mode; (root/directory).mkdir(); (root/directory/'Probe.class').write_bytes(b'classes')
        modes[mode] = dict(jars=jars, classes=directory, main=p.MAINS[mode])
    (root/'runtime/bin').mkdir(parents=True); (root/'runtime/bin/java').write_bytes(b'java'); (root/'runtime/bin/java').chmod(0o755)
    (root/'guest.py').write_bytes(b'guest'); (root/'workload.json').write_bytes(b'{}')
    save(root/'published-controls.json', dict(artifacts=pins))
    build = dict(binding=dict(source='a'*40), files=candidates); save(root/'ci-build-manifest.json', build)
    manifest = dict(schema=p.SCHEMA, source='a'*40, paidCloud=False, fullRemoteQualification=False,
        buildManifestSha256=p.sha((root/'ci-build-manifest.json').read_bytes()), buildBinding=build['binding'],
        modes=modes, jvmArguments=[], workloadSha256=p.sha(b'{}'), files=p.inventory(root))
    save(root/'manifest.json', manifest); return manifest


def archive(path, entries):
    with tarfile.open(path, 'w:gz') as tar:
        for name, raw, kind in entries:
            info = tarfile.TarInfo(name); info.size = len(raw); info.mode = 0o644; info.type = kind
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): info.linkname = '/tmp/unrelated'
            tar.addfile(info, io.BytesIO(raw))
    return p.sha(path.read_bytes())


class PackageTest(unittest.TestCase):
    def setUp(self): self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)/'guest'; self.value = fixture(self.root)
    def test_valid_isolated_classpaths_and_source(self):
        self.assertEqual(p.verify(self.root, 'a'*40), self.value)
        for mode in p.MODES:
            cmd = p.command(self.root, mode, check=True)
            cp = cmd[cmd.index('-cp')+1].split(':')
            self.assertEqual(len(cp), 2 if mode == p.MODES[0] else 3)
        with self.assertRaises(ValueError): p.verify(self.root, 'b'*40)
    def test_jlink_support_jar_is_not_a_sixth_application_jar(self):
        support = self.root/'runtime/lib/jrt-fs.jar'; support.parent.mkdir(); support.write_bytes(b'jlink support')
        self.value['files'] = p.inventory(self.root); save(self.root/'manifest.json', self.value)
        p.verify(self.root)
        (self.root/'unexpected.jar').write_bytes(b'classpath pollution')
        self.value['files'] = p.inventory(self.root); save(self.root/'manifest.json', self.value)
        with self.assertRaisesRegex(ValueError, 'five distinct JARs'): p.verify(self.root)
    def test_extra_missing_changed_and_executable_members(self):
        java = self.root/'runtime/bin/java'; java.chmod(0o644)
        with self.assertRaises(ValueError): p.verify(self.root)
        java.chmod(0o755); (self.root/'extra').write_bytes(b'')
        with self.assertRaises(ValueError): p.verify(self.root)
        (self.root/'extra').unlink(); java.write_bytes(b'changed')
        with self.assertRaises(ValueError): p.verify(self.root)
        java.unlink()
        with self.assertRaises(ValueError): p.verify(self.root)
    def test_candidate_change_cannot_be_hidden_by_refreshing_inventory(self):
        jar = self.root/self.value['modes'][p.MODES[2]]['jars'][0]; jar.write_bytes(b'other build')
        self.value['files'] = p.inventory(self.root); save(self.root/'manifest.json', self.value)
        with self.assertRaisesRegex(ValueError, 'candidate'): p.verify(self.root)
    def test_classpath_leak_and_paid_scope_rejected(self):
        self.value['modes'][p.MODES[0]]['jars'].append(self.value['modes'][p.MODES[1]]['jars'][1]); save(self.root/'manifest.json', self.value)
        with self.assertRaisesRegex(ValueError, 'isolation'): p.verify(self.root)
        self.value['paidCloud'] = True; save(self.root/'manifest.json', self.value)
        with self.assertRaisesRegex(ValueError, 'scope'): p.verify(self.root)
    def test_links_rejected(self):
        (self.root/'link').symlink_to(self.root/'guest.py')
        with self.assertRaisesRegex(ValueError, 'linked'): p.verify(self.root)
    def test_archive_digest_checked_before_extracting(self):
        path = self.root.parent/'bad.tar.gz'; path.write_bytes(b'not tar'); target = self.root.parent/'unpack'
        with self.assertRaisesRegex(ValueError, 'digest'): p.unpack(path, target, '0'*64, 'a'*40)
        self.assertFalse(target.exists())
    def test_archive_member_attacks(self):
        for i, entries in enumerate(([('../escape', b'x', tarfile.REGTYPE)], [('/absolute', b'x', tarfile.REGTYPE)],
                [('link', b'', tarfile.SYMTYPE)], [('hard', b'', tarfile.LNKTYPE)],
                [('x', b'a', tarfile.REGTYPE), ('x', b'b', tarfile.REGTYPE)])):
            with self.subTest(entries=entries):
                path = self.root.parent/f'bad-{i}.tar.gz'; digest = archive(path, entries)
                with self.assertRaises(ValueError): p.unpack(path, self.root.parent/f'unpack-{i}', digest, 'a'*40)
        self.assertFalse((self.root.parent/'escape').exists())
    def test_standalone_service_import_keeps_authenticated_payload_immutable(self):
        (self.root/'guest.py').write_bytes(Path(p.__file__).read_bytes())
        for name in bundle.GUEST_INPUTS:
            target=self.root/'source-inputs'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(bundle.ROOT/name,target)
        folder=self.root/'source-inputs/scripts/v51'
        self.value['files']=p.inventory(self.root);save(self.root/'manifest.json',self.value)
        result=subprocess.run([sys.executable,'-I',str(self.root/'guest.py'),'service','--help'],capture_output=True,check=True,text=True)
        self.assertIn('start,serve,query,submit,cancel,shutdown,ready,part',result.stdout)
        p.verify(self.root)
        self.assertEqual(list(self.root.rglob('__pycache__')),[])
        (folder/'cloud_guest.py').write_text('raise RuntimeError("must not run")\n')
        result=subprocess.run([sys.executable,'-I',str(self.root/'guest.py'),'service','--help'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('package inventory changed',result.stderr)
        self.assertNotIn('must not run',result.stderr)
    def test_duplicate_json_keys_rejected(self):
        (self.root/'manifest.json').write_bytes(b'{"schema":1,"schema":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate'): p.verify(self.root)

if __name__ == '__main__': unittest.main()
