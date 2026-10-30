"""Synthetic archive checks; these fixtures are not executed Java/CI evidence."""
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_inputs as p
from .evidence import encoded, digest, strict


def binding():
    return dict(source='a'*40, checkoutSha256='b'*64,
                java={'java.runtime.version': '21.0.12+8-LTS', 'java.vendor': 'Eclipse Adoptium'})


def roots():
    return [f'target/general-search-engine-{p.VERSION}.jar',
            f'{p.build.MODULE}/target/general-search-engine-replication-{p.VERSION}.jar', p.build.CLASSES, p.build.REPORTS]


def tar_bytes(files, *, extra=(), fmt=tarfile.USTAR_FORMAT):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz', format=fmt) as output:
        for name, raw in files:
            item = tarfile.TarInfo(name); item.size = len(raw); output.addfile(item, io.BytesIO(raw))
        for item in extra: output.addfile(item)
    return stream.getvalue()


def shared(directory):
    files = {name: ('synthetic-'+name).encode() for name in roots()[:2]}
    for worker in ('V51StorageWorker', 'V51ProtocolWorker', 'V51RuntimeWorker'):
        files[p.build.CLASSES+'/'+worker+'.class'] = b'synthetic-class'
    for suite in p.build.REQUIRED_SUITES | {'V52ReadTokenTest', 'V52PublicApiInventoryTest', 'V51PublicApiInventoryTest'}:
        files[p.build.REPORTS+'/TEST-'+suite+'.xml'] = (
            '<testsuite name="test.'+suite+'" tests="1" failures="0" errors="0" skipped="0"/>').encode()
    archive = tar_bytes(sorted(files.items())); (directory/'build.tar.gz').write_bytes(archive)
    meta = dict(schema=p.build.SCHEMA, binding=binding(), roots=roots(), archiveSha256=digest(archive),
                files=[dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(files.items())])
    (directory/'manifest.json').write_bytes(encoded(meta)); return meta, files


class InputsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.build = self.root/'build'; self.build.mkdir()
        self.meta, self.files = shared(self.build)
        self.raw, self.candidate = p.build_files(self.build, binding(), roots())
        self.published = {name: ('synthetic-published-'+name).encode() for name in p.CONTROL_NAMES}
        self.pins = {name: digest(raw) for name, raw in self.published.items()}
        self.controls_raw = (p.suite.PLAN.parent/'published-controls.json').read_bytes()
        self.payload = p.payload(binding(), self.raw, self.controls_raw, self.candidate, self.published)
        self.index = p.manifest(binding(), self.raw, self.controls_raw, self.payload)
        self.archive = self.root/'inputs.tar.gz'; p.pack(self.archive, self.index, self.payload)

    def verify(self):
        return p.verify_archive(self.archive, binding(), self.raw, self.controls_raw, self.candidate, self.pins)

    def rewrite_build(self, mutate):
        changed = deepcopy(self.meta); mutate(changed); (self.build/'manifest.json').write_bytes(encoded(changed))

    def repack(self, rows, **kwargs):
        self.archive.write_bytes(tar_bytes([(p.INDEX, encoded(self.index)), *rows], **kwargs))

    def test_complete_build_and_input_bytes_pass_without_executing_packaged_code(self):
        result = self.verify(); p.validate_proof(result)
        self.assertEqual('INPUTS_VERIFIED_NOT_ADMITTED', result['status']); self.assertFalse(result['paidAdmission'])
        self.assertEqual(2, len(self.candidate)); self.assertEqual(8, len(self.payload))
        self.assertEqual(digest(self.archive.read_bytes()), result['packageSha256'])

    def test_package_is_deterministic_across_directories_and_creation_times(self):
        other = self.root/'other'; other.mkdir(); p.pack(other/p.ARCHIVE, self.index, self.payload)
        self.assertEqual(self.archive.read_bytes(), (other/p.ARCHIVE).read_bytes())

    def test_inspect_does_not_trust_a_success_receipt(self):
        (self.build/'receipt.json').write_bytes(b'{"status":"PASS"}')
        self.rewrite_build(lambda v: v.update(archiveSha256='0'*64))
        with self.assertRaisesRegex(ValueError, 'archive hash'): p.build_files(self.build, binding(), roots())

    def test_build_source_java_and_layout_drift_reject(self):
        for change in (lambda v: v['binding'].update(source='c'*40), lambda v: v['binding'].update(checkoutSha256='c'*64),
                       lambda v: v['binding']['java'].update(**{'java.vendor':'other'}), lambda v: v['roots'].reverse()):
            with self.subTest(change=change):
                self.rewrite_build(change)
                with self.assertRaisesRegex(ValueError, 'binding/layout'): p.build_files(self.build, binding(), roots())

    def test_build_paths_duplicates_and_boolean_sizes_reject(self):
        for change in (lambda v:v['files'].append(v['files'][0]), lambda v:v['files'][0].update(path='../escape'),
                       lambda v:v['files'][0].update(path='target/unlisted.jar'), lambda v:v['files'][0].update(size=True),
                       lambda v:v['files'][0].update(size=p.MAX_BYTES+1)):
            with self.subTest(change=change):
                self.rewrite_build(change)
                with self.assertRaises(ValueError): p.build_files(self.build, binding(), roots())

    def test_original_build_hash_and_each_member_are_checked(self):
        rows = sorted(self.files.items()); rows[0] = (rows[0][0], b'corrupt')
        archive = tar_bytes(rows); (self.build/'build.tar.gz').write_bytes(archive)
        with self.assertRaisesRegex(ValueError, 'archive hash'): p.build_files(self.build, binding(), roots())
        self.rewrite_build(lambda v:v.update(archiveSha256=digest(archive)))
        with self.assertRaisesRegex(ValueError, 'member size|member hash'): p.build_files(self.build, binding(), roots())

    def test_build_must_include_actual_prerequisite_reports(self):
        name = next(n for n in self.files if n.endswith('V52ReadTokenTest.xml'))
        del self.files[name]; archive = tar_bytes(sorted(self.files.items())); (self.build/'build.tar.gz').write_bytes(archive)
        self.rewrite_build(lambda v:v.update(archiveSha256=digest(archive), files=[r for r in v['files'] if r['path'] != name]))
        with self.assertRaisesRegex(ValueError, 'missing executed'): p.build_files(self.build, binding(), roots())

    def test_failed_or_skipped_required_java_suite_rejects(self):
        name = next(n for n in self.files if n.endswith('V52ReadTokenTest.xml'))
        for attr in ('failures', 'errors', 'skipped'):
            self.files[name] = f'<testsuite name="V52ReadTokenTest" tests="1" {attr}="1"/>'.encode()
            archive = tar_bytes(sorted(self.files.items())); (self.build/'build.tar.gz').write_bytes(archive)
            self.rewrite_build(lambda v:v.update(archiveSha256=digest(archive), files=[
                dict(path=k, size=len(raw), sha256=digest(raw)) for k, raw in sorted(self.files.items())]))
            with self.assertRaisesRegex(ValueError, 'failed or empty|skipped prerequisite'): p.build_files(self.build, binding(), roots())

    def test_build_archive_extra_duplicate_and_link_members_reject(self):
        link = tarfile.TarInfo('linked'); link.type = tarfile.SYMTYPE; link.linkname = '/etc/passwd'
        for rows, extra in (([*self.files.items(), ('unexpected', b'x')], ()),
                            ([*self.files.items(), next(iter(self.files.items()))], ()), (list(self.files.items()), (link,))):
            archive = tar_bytes(rows, extra=extra); (self.build/'build.tar.gz').write_bytes(archive)
            self.rewrite_build(lambda v:v.update(archiveSha256=digest(archive)))
            with self.assertRaises(ValueError): p.build_files(self.build, binding(), roots())

    def test_build_sparse_or_extended_header_rejects_before_payload(self):
        item = tarfile.TarInfo('extension'); item.type = tarfile.XHDTYPE
        archive = tar_bytes([], extra=(item,)); (self.build/'build.tar.gz').write_bytes(archive)
        self.rewrite_build(lambda v:v.update(archiveSha256=digest(archive)))
        with self.assertRaisesRegex(ValueError, 'extension/link'): p.build_files(self.build, binding(), roots())

    def test_input_links_including_linked_parents_reject(self):
        direct = self.root/'direct'; direct.symlink_to(self.build/'manifest.json')
        parent = self.root/'parent'; parent.symlink_to(self.build, target_is_directory=True)
        for path in (direct, parent/'manifest.json'):
            with self.assertRaisesRegex(ValueError, 'file type'): p.regular(path, p.MAX_JSON)

    def test_package_missing_extra_duplicate_and_linked_member_reject(self):
        rows = list(self.payload.items()); link = tarfile.TarInfo('link'); link.type = tarfile.LNKTYPE; link.linkname = rows[0][0]
        for values, extra in ((rows[:-1], ()), (rows+[('extra', b'x')], ()), (rows+[rows[0]], ()), (rows, (link,))):
            self.repack(values, extra=extra)
            with self.assertRaises(ValueError): self.verify()

    def test_package_inventory_and_payload_cannot_both_substitute_candidate(self):
        key = 'artifacts/'+next(iter(self.candidate)); self.payload[key] = b'substitute'
        self.index['files'][key] = dict(bytes=len(self.payload[key]), sha256=digest(self.payload[key]))
        self.repack(list(self.payload.items()))
        with self.assertRaisesRegex(ValueError, 'source/build/input drift'): self.verify()

    def test_package_inventory_and_payload_cannot_both_substitute_published_control(self):
        key = 'artifacts/'+next(iter(self.pins)); self.payload[key] = b'substitute'
        self.index['files'][key] = dict(bytes=len(self.payload[key]), sha256=digest(self.payload[key]))
        self.repack(list(self.payload.items()))
        with self.assertRaisesRegex(ValueError, 'published input hash'): self.verify()

    def test_package_source_build_controls_and_scope_are_exact(self):
        original = deepcopy(self.index)
        for change in (lambda v:v['source'].update(source='c'*40), lambda v:v.update(buildManifestSha256='0'*64),
                       lambda v:v.update(controlsManifestSha256='0'*64), lambda v:v.update(schema='gse-v51-guest-package-v1')):
            self.index = deepcopy(original); change(self.index); self.repack(list(self.payload.items()))
            with self.assertRaisesRegex(ValueError, 'source/build/input drift'): self.verify()

    def test_package_inventory_enforces_bounds_before_reading_members(self):
        original = deepcopy(self.index); name = next(iter(self.payload))
        for size in (True, -1, (64 << 20)+1):
            self.index = deepcopy(original); self.index['files'][name]['bytes'] = size
            self.repack(list(self.payload.items()))
            with self.assertRaises(ValueError): self.verify()

    def test_package_requires_inventory_first_and_no_extended_headers(self):
        self.archive.write_bytes(tar_bytes(list(self.payload.items())))
        with self.assertRaisesRegex(ValueError, 'first inventory'): self.verify()
        item = tarfile.TarInfo('extension'); item.type = tarfile.XHDTYPE
        self.archive.write_bytes(tar_bytes([], extra=(item,)))
        with self.assertRaisesRegex(ValueError, 'extension/link'): self.verify()

    def test_changed_controls_and_promoted_copied_proof_reject(self):
        proof = self.verify()
        for key, value in (('paidAdmission', True), ('fullRemoteQualification', True), ('packageBytes', True),
                           ('controlsManifestSha256', '0'*64)):
            wrong = dict(proof, **{key:value})
            with self.assertRaises(ValueError): p.validate_proof(wrong)
        root = self.root/'source'; path = root/'docs/v5x/v5.2'; path.mkdir(parents=True)
        (path/'published-controls.json').write_bytes(self.controls_raw+b' ')
        with self.assertRaisesRegex(ValueError, 'manifest'): p.controls(root)

    def test_public_inspection_uses_current_checkout_and_rechecks_after_archive(self):
        with patch.object(p, 'checkout', side_effect=[binding(), dict(binding(), checkoutSha256='c'*64)]) as source, \
             patch.object(p.build, 'layout', return_value=roots()), patch.object(p, 'controls', return_value=(self.controls_raw, self.pins)):
            with self.assertRaisesRegex(ValueError, 'changed during'): p.inspect(self.root, 'a'*40, self.build, self.archive)
            self.assertEqual(2, source.call_count)

    def test_public_create_never_overwrites_and_inspects_actual_package(self):
        directory = self.root/'controls'; directory.mkdir()
        for name, raw in self.published.items(): (directory/name).write_bytes(raw)
        with patch.object(p, 'checkout', return_value=binding()), patch.object(p.build, 'layout', return_value=roots()), \
             patch.object(p, 'controls', return_value=(self.controls_raw, self.pins)):
            proof = p.create(self.root, 'a'*40, self.build, directory, self.root/'created')
            self.assertEqual(proof, p.inspect(self.root, 'a'*40, self.build, self.root/'created'/p.ARCHIVE))
            with self.assertRaises(FileExistsError): p.create(self.root, 'a'*40, self.build, directory, self.root/'created')
        self.assertEqual(self.meta, strict((self.build/'manifest.json').read_bytes()))

    def test_clean_checkout_observation_uses_git_and_rejects_untracked_or_dirty_files(self):
        repo = self.root/'repo'; repo.mkdir()
        def git(*args): return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)
        git('init'); (repo/'tracked').write_text('original'); git('add', 'tracked')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        source = git('rev-parse', 'HEAD').decode().strip(); bound = dict(binding(), source=source)
        with patch.object(p.build, 'binding', return_value=bound), patch.object(p.build, 'layout', return_value=roots()):
            self.assertEqual(bound, p.checkout(repo, source))
            final_roots = [name.replace('5.2.0-SNAPSHOT', '5.2.0') for name in roots()]
            with patch.object(p.build, 'layout', return_value=final_roots):
                with self.assertRaisesRegex(ValueError, 'input candidate version'): p.checkout(repo, source)
            (repo/'untracked').write_text('x')
            with self.assertRaisesRegex(ValueError, 'dirty checkout'): p.checkout(repo, source)
            (repo/'untracked').unlink(); (repo/'tracked').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'dirty checkout'): p.checkout(repo, source)


if __name__ == '__main__': unittest.main()
