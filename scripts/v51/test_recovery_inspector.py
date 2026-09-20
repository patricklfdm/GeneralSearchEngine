"""Recovery oracle negatives use independently encoded, internally consistent frames."""
import shutil
import tempfile
from pathlib import Path
import unittest

from . import format_encoder as enc
from . import format_inspector as f
from . import recovery_inspector as r
from .storage_fixture import create, records, b64, sha
from .storage_inspector import inspect, inventory
from .recovery_harness import witness


class RecoveryInspectorTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.records = create(self.root); self.node = self.root / 'node-1'; self.manifest_raw = (self.node / 'manifest.gsr').read_bytes()
        self.manifest = dict(f.inspect(self.manifest_raw, 'MANIFEST'), digest=r.digest(self.manifest_raw))

    def generation(self, node='node-1'):
        root = self.root / node
        for name, kind in [('promises.gsr', 'PROMISE'), ('accepted.gsr', 'ACCEPT'), ('proofs.gsr', 'PROOF')]:
            with (root / name).open('ab') as stream: stream.write(self.records[kind])
        entry = f.inspect(r.raw(f.inspect(self.records['ACCEPT'], 'ACCEPT')['entry']), 'ENTRY')
        s = dict(manifestDigest=self.manifest['digest'], baseSequence=0, applicationSequence=1, application=b64(b'one'),
                 anchors=[{k: entry[k] for k in ('originEpoch', 'originIncarnation', 'payloadDigest', 'operation')} | {'entryDigest': f.inspect(self.records['PROOF'], 'PROOF')['entryDigest']}], terminalProof=b64(self.records['PROOF']))
        files = {'snapshot.gsr': enc.encode('SNAPSHOT', s)}
        for name, kind in [('accepted.gsr', 24), ('proofs.gsr', 6)]: files[name] = enc.encode('JOURNAL', dict(manifestDigest=self.manifest['digest'], node=node, recordKind=kind))
        seal = enc.encode('GENERATION', dict(manifestDigest=self.manifest['digest'], node=node, snapshotDigest=r.digest(files['snapshot.gsr']), prefixIndex=1,
                         selectedDigest=None, files=[dict(path=k, size=len(v), sha256=sha(v)) for k, v in sorted(files.items())]))
        files['generation.gsr'] = seal; directory = root / 'generation-a'; directory.mkdir()
        for k, v in files.items(): (directory / k).write_bytes(v)
        (root / 'current.gsr').write_bytes(enc.encode('SELECTOR', dict(manifestDigest=self.manifest['digest'], node=node, generation='generation-a', generationDigest=r.digest(seal))))
        (root / 'generation-started.gsr').write_bytes(enc.encode('STARTED', dict(manifestDigest=self.manifest['digest'], node=node)))
        return files

    def selection(self):
        sources = []; snapshot = (self.node / 'generation-a/snapshot.gsr').read_bytes()
        for node in ('node-1', 'node-2'):
            image = enc.encode('IMAGE', dict(manifestDigest=self.manifest['digest'], snapshot=b64(snapshot), acceptances=[]))
            basis = dict(manifestDigest=self.manifest['digest'], node=node, ballot=dict(epoch=5, proposer='node-1', incarnation='11111111-1111-1111-1111-111111111111'),
                         basisId='33333333-3333-3333-3333-333333333333', imageBytes=len(image), imageDigest=r.digest(image), accepted=None,
                         files=[dict(path='image.gsr', size=len(image), sha256=sha(image))])
            descriptor = enc.encode('BASIS', basis); directory = self.node / 'transfer/selection-a'; directory.mkdir(parents=True, exist_ok=True)
            (directory / f'basis-{node}.gsr').write_bytes(descriptor); (directory / f'image-{node}.gsr').write_bytes(image)
            sources.append(dict(node=node, basisId=basis['basisId'], basisDigest=r.digest(descriptor)))
        with (self.node / 'promises.gsr').open('ab') as stream: stream.write(records(self.manifest_raw, epoch=5)['PROMISE'])
        value = dict(manifestDigest=self.manifest['digest'], ballot=basis['ballot'], bases=sources, prefixIndex=1,
                     prefixDigest=f.inspect(self.records['PROOF'], 'PROOF')['entryDigest'], nextEntry=None, sourceBallot=None)
        (self.node / 'selected.gsr').write_bytes(enc.encode('SELECTED', value)); return value

    def floor(self):
        sources = []
        for node in ('node-1', 'node-2'):
            root = self.root / node; directory = self.node / 'transfer/floor-a' / node; directory.mkdir(parents=True)
            for name in r.GENERATION: shutil.copyfile(root / 'generation-a' / name, directory / name)
            shutil.copyfile(root / 'current.gsr', directory / 'current.gsr')
            sources.append(dict(node=node, generationDigest=r.digest((directory / 'generation.gsr').read_bytes()), snapshotDigest=r.digest((directory / 'snapshot.gsr').read_bytes())))
        value = dict(manifestDigest=self.manifest['digest'], node='node-1', index=1, entryDigest=f.inspect(self.records['PROOF'], 'PROOF')['entryDigest'], sources=sources)
        (self.node / 'recovery-floor.gsr').write_bytes(enc.encode('FLOOR', value)); return value

    def test_complete_generation_and_frozen_selection_agree_without_rewriting(self):
        self.generation(); self.selection(); before = inventory(self.node); result = inspect(self.node)
        self.assertEqual((5, 1, 1), (result['promisedEpoch'], result['provenThrough'], result['applicationSequence'])); self.assertEqual(before, inventory(self.node))

    def test_missing_selector_never_uses_older_root(self):
        self.generation(); (self.node / 'current.gsr').unlink()
        with self.assertRaisesRegex(ValueError, 'selector'): inspect(self.node)

    def test_missing_or_changed_active_generation_never_falls_back(self):
        self.generation(); (self.node / 'generation-a/snapshot.gsr').write_bytes(b'broken')
        with self.assertRaises(ValueError): inspect(self.node)

    def test_rechecksummed_selected_prefix_change_is_rejected(self):
        self.generation(); value = self.selection(); value['prefixIndex'] = 0
        (self.node / 'selected.gsr').write_bytes(enc.encode('SELECTED', value))
        with self.assertRaisesRegex(ValueError, 'selected proven prefix'): inspect(self.node)

    def test_frozen_image_identity_and_complete_inventory_are_required(self):
        self.generation(); self.selection(); image = self.node / 'transfer/selection-a/image-node-2.gsr'; image.write_bytes(image.read_bytes()[:-1])
        with self.assertRaises(ValueError): inspect(self.node)

    def test_floor_requires_both_complete_sources_not_only_two_descriptors(self):
        self.generation(); self.generation('node-2'); self.floor(); self.assertEqual('PASS', inspect(self.node)['status'])
        (self.node / 'transfer/floor-a/node-2/snapshot.gsr').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)): inspect(self.node)

    def test_rechecksummed_wrong_floor_cut_is_rejected(self):
        self.generation(); self.generation('node-2'); value = self.floor(); value['index'] = 0
        (self.node / 'recovery-floor.gsr').write_bytes(enc.encode('FLOOR', value))
        with self.assertRaisesRegex(ValueError, 'source cut'): inspect(self.node)

    def test_partial_unpublished_generation_is_not_selected(self):
        self.generation(); inactive = self.node / 'generation-b'; inactive.mkdir(); (inactive / 'generation.gsr').write_bytes(b'partial')
        self.assertEqual(1, inspect(self.node)['provenThrough'])
        (inactive / 'unexpected').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'inventory'): inspect(self.node)

    def test_force_witness_is_bound_to_exact_bytes_and_process(self):
        files = {'selected.gsr': {'size': 123, 'sha256': 'a'*64}}
        forced = dict(pid=5, stage='SELECTED_AFTER_FORCE', files={'transfer/selected.pending.gsr': files['selected.gsr']})
        ack = dict(pid=5, stage='SELECTED_ACK', files=files); witness([forced, ack], 'SELECTED', files)
        for rows in ([ack], [dict(forced, pid=6), ack], [dict(forced, files={}), ack]):
            with self.assertRaisesRegex(ValueError, 'force'): witness(rows, 'SELECTED', files)


if __name__ == '__main__': unittest.main()
