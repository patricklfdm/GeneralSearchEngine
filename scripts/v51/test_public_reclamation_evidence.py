import copy
import unittest
from . import test_recovery_inspector as fixtures, format_encoder as enc
from . import public_reclamation_evidence as e


class PublicReclamationEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RecoveryInspectorTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.fixture.generation(); self.fixture.generation('node-2'); self.floor = self.fixture.floor()
        self.files = {str(p.relative_to(self.fixture.node)): p.read_bytes() for p in self.fixture.node.rglob('*') if p.is_file()}
        self.manifest = self.fixture.manifest

    def check(self, files=None): return e.floor_state(self.files if files is None else files, self.manifest, 'node-1')

    def test_two_complete_distinct_sources(self):
        floor, packets, sources = self.check()
        self.assertEqual(floor['index'], 1); self.assertEqual(len(packets), 2)
        self.assertEqual({s['seal']['node'] for s in sources}, {'node-1', 'node-2'})

    def test_descriptor_alone_does_not_qualify_a_source(self):
        files = dict(self.files); del files['transfer/floor-a/node-2/snapshot.gsr']
        with self.assertRaisesRegex(ValueError, 'incomplete'): self.check(files)

    def test_duplicate_source_owner_rejected_even_with_new_floor_checksum(self):
        floor = copy.deepcopy(self.floor); floor['sources'][1] = floor['sources'][0]
        with self.assertRaises(ValueError): self.check(dict(self.files, **{'recovery-floor.gsr': enc.encode('FLOOR', floor)}))

    def test_changed_snapshot_bytes_rejected(self):
        files = dict(self.files); files['transfer/floor-a/node-2/snapshot.gsr'] = b'changed'
        with self.assertRaises(ValueError): self.check(files)

    def test_floor_cannot_move_ahead_of_sources(self):
        floor = dict(self.floor, index=2)
        with self.assertRaises(ValueError): self.check(dict(self.files, **{'recovery-floor.gsr': enc.encode('FLOOR', floor)}))

    def test_floor_does_not_authorize_another_local_voter(self):
        with self.assertRaises(ValueError): e.floor_state(self.files, self.manifest, 'node-3')

    def test_pending_floor_is_not_durable_authority(self):
        files = dict(self.files); files['recovery-floor.pending.gsr'] = files.pop('recovery-floor.gsr')
        with self.assertRaisesRegex(ValueError, 'missing durable'): self.check(files)
        self.assertEqual(e.floor_state(files, self.manifest, 'node-1', 'recovery-floor.pending.gsr')[0]['index'], 1)

    def test_complete_download_precedes_floor_in_same_process(self):
        _, packets, _ = self.check(); data = e.a.storage.canonical(packets[1])
        e.require_download(packets, 'node-1', dict(pid=11, order=3), [dict(pid=11, order=2, bytes=data)])
        for row in (dict(pid=12, order=2, bytes=data), dict(pid=11, order=3, bytes=data), dict(pid=11, order=4, bytes=data)):
            with self.subTest(row=row), self.assertRaises(ValueError): e.require_download(packets, 'node-1', dict(pid=11, order=3), [row])

    def test_partial_download_cannot_authorize_floor(self):
        _, packets, _ = self.check(); data = e.a.storage.canonical(packets[1])
        with self.assertRaises(ValueError): e.require_download(packets, 'node-1', dict(pid=11, order=3), [dict(pid=11, order=2, bytes=data[:-1])])

    def test_unresolved_tail_above_floor_cannot_be_deleted(self):
        floor, _, sources = self.check()
        e.retirement_bound(self.files, '', floor, sources[0]['snapshot'], self.manifest)
        with self.assertRaisesRegex(ValueError, 'exceeds durable floor'):
            e.retirement_bound(self.files, '', dict(floor, index=0), sources[0]['snapshot'], self.manifest)

    def test_root_truncation_preserves_a_valid_journal_header(self):
        data = self.files['accepted.gsr']; size = int.from_bytes(data[12:16], 'big')+48
        self.assertTrue(e.journal_rows(data, 'ACCEPT', self.manifest))
        self.assertEqual(e.journal_rows(data[:size], 'ACCEPT', self.manifest), [])
        e.truncated_journal(data, data[:size], 'ACCEPT', self.manifest)
        header = e.a.f.inspect(data[:size], 'JOURNAL')
        changed_header = enc.encode('JOURNAL', dict(header, node='node-2'))
        with self.assertRaisesRegex(ValueError, 'original header'):
            e.truncated_journal(data, changed_header, 'ACCEPT', self.manifest)
        for changed in (b'', data[:size-1], data[:-1]):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError): e.journal_rows(changed, 'ACCEPT', self.manifest)

    def test_exact_generation_binding_rejects_a_swapped_selector(self):
        files = dict(self.files)
        files['transfer/floor-a/node-2/current.gsr'] = files['transfer/floor-a/node-1/current.gsr']
        with self.assertRaises(ValueError): self.check(files)
