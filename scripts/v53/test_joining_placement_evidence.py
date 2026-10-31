"""Focused projection/rejection tests; the original history qualifies the gate."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_placement_evidence as j
from . import test_joining_catalog_evidence as phases
from . import test_source_packet as packets


def original():
    capsule, _, objects = packets.fixture(); cap = j.f.decode(capsule, 'records', 'CAPSULE')
    catalog = j.f.catalog(); root = j.f.encode('records', 'ROOT', j.f.sample(catalog['records']['ROOT']['schema'], catalog['types']))
    objects[j.sha(root)] = root
    parts, _, identities, _ = phases.JoiningCatalogEvidenceTest().phase()
    image = b'independent image'
    files = {'source.gscp': j.disk.packet_bytes(cap, objects, {j.sha(image): len(image)}), j.sha(image)+'.image': image,
             'ancestry.gsr': b'original verified bridges', 'selected.gsr': b'old owner selection',
             'promise.gsr': j.f.encode('records', 'PROMISE', dict(root=cap['root'], view='b'*64,
                 ballot=dict(counter=99, proposer='node-2', incarnation=identities['node-2']['storage']), basisId=None))}
    return files, identities['node-4'], parts['CERTIFICATE'], root


class JoiningPlacementEvidenceTest(unittest.TestCase):
    def test_adoption_uses_certificate_fence_without_importing_old_campaign(self):
        args = original(); before = dict(args[0]); files = j.adopted(*args)
        promise = j.f.decode(files['grants.gsr'], 'records', 'PROMISE')
        cert = j.f.decode(args[2], 'records', 'CERTIFICATE')
        self.assertEqual(cert['ballot'], promise['ballot']); self.assertEqual(cert['authority'], promise['view'])
        self.assertIsNone(promise['basisId']); self.assertEqual(before, args[0])
        self.assertEqual(args[2], files['generations/a/adopted-certificate.gsr'])
        self.assertEqual(j.disk.EMPTY, files['pending.accept'])
        self.assertNotIn('generations/a/selected.gsr', files)
        self.assertNotIn('generations/a/basis.gsr', files)
        manifest = j.f.decode(files['generations/a/generation.gsr'], 'records', 'GENERATION')
        self.assertTrue(all(manifest[k] is None for k in ('basis', 'selection', 'ownedTail')))

    def test_original_images_and_ancestry_survive_adoption(self):
        args = original(); files = j.adopted(*args)
        for name, raw in args[0].items():
            if name.endswith('.image') or name in ('source.gscp', 'ancestry.gsr'):
                self.assertEqual(raw, files['generations/a/'+name])
        selector = j.f.decode(files['selector.gsr'], 'records', 'SELECTOR')
        self.assertEqual('node-4', selector['node'])
        self.assertEqual(j.sha(files['generations/a/generation.gsr']), selector['digest'])

    def test_foreign_root_cannot_enter_a_complete_packet(self):
        files, identity, certificate, _ = original()
        with self.assertRaisesRegex(ValueError, '^joining placement original ROOT object$'):
            j.adopted(files, identity, certificate, b'foreign root')

    def test_recorded_keys_are_not_replaced_with_local_stat_results(self):
        owner = j.Placement.__new__(j.Placement)
        owner.identities = {'replica': {'generations/a': {'key': 'unmounted-original-inode', 'directory': True}}}
        with patch.object(Path, 'stat', side_effect=AssertionError('must not inspect original paths')):
            self.assertEqual('unmounted-original-inode', owner.key('replica', 'generations/a'))
        with self.assertRaisesRegex(ValueError, '^joining placement original identity missing$'):
            owner.key('replica', 'missing')

    def test_scratch_cannot_overlap_any_present_or_absent_root(self):
        def binding(path):
            return dict(path=path, parentRealPath=str(Path(path).parent), parentFileKey='parent', fileStoreName='store', fileStoreType='ext4')
        owner = j.Placement.__new__(j.Placement)
        owner.snap = SimpleNamespace(identities={'replica': dict(path=binding('/original/run/replica'), present=True),
                                                'materialization': dict(path=binding('/original/run/core'), present=False)})
        self.assertEqual(binding('/original/run/receiving'), owner.scratch(binding('/original/run/receiving')))
        for path in ('/original/run', '/original/run/replica', '/original/run/replica/nested', '/original/run/core'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '^joining placement scratch overlaps original$'):
                owner.scratch(binding(path))

    def test_atomic_move_prefix_does_not_claim_sibling_names(self):
        for name in ('generations', 'generations/a/generation.gsr', 'grants.gsr', 'sources/uuid/source.gscp'):
            self.assertTrue(j.moved(name))
        for name in ('generations-other', 'generation.gsr', 'grants.gsr.next', 'sources-copy/source.gscp', 'node.gsr'):
            self.assertFalse(j.moved(name))

    def test_absent_sidecar_still_binds_to_same_plan_and_original_parent(self):
        owner = j.Placement.__new__(j.Placement); owner.plan = 'a'*64
        prefixes = dict(initialTyped='learner-', intent='learner-intent-', pendingIntent='learner-pending-intent-',
            voterStage='learner-voter-', custody='learner-custody-', placement='learner-placement-', retirement='learner-retired-',
            nativeOwner='joined-owner-', slots='learner-slots-', slotTyped='learner-slot-b-', successor='learner-successor-', successorTyped='learner-ready-')
        rows = {family: dict(path='/original/run/.gse-v53-'+prefix+owner.plan, parentFileKey='parent', fileStoreName='store', fileStoreType='ext4')
                for family, prefix in prefixes.items()}
        rows.update(operation=dict(path='/original/run/operation', parentFileKey='parent', fileStoreName='store', fileStoreType='ext4'),
                    replica=dict(fileStoreName='store', fileStoreType='ext4'))
        owner.snap = SimpleNamespace(identities={name: dict(path=value) for name,value in rows.items()})
        owner.paths(); rows['successor']['parentFileKey'] = 'different parent'
        with self.assertRaisesRegex(ValueError, '^joining placement original parent identity$'): owner.paths()
        rows['successor']['parentFileKey'] = 'parent'; rows['successor']['path'] += '-different-plan'
        with self.assertRaisesRegex(ValueError, '^joining placement deterministic sidecar path$'): owner.paths()
        rows['successor']['path'] = rows['successor']['path'].removesuffix('-different-plan'); rows['replica']['fileStoreName'] = 'different filesystem'
        with self.assertRaisesRegex(ValueError, '^joining placement atomic move filesystem$'): owner.paths()

    def test_family_check_rejects_unlisted_empty_directory(self):
        owner = j.Placement.__new__(j.Placement)
        owner.snap = SimpleNamespace(identities={'replica': dict(files=[dict(name='.', identity=dict(directory=True)),
            dict(name='unowned', identity=dict(directory=True))])})
        owner.expected = {'replica': {'.': None}}
        with self.assertRaisesRegex(ValueError, '^joining placement exact family: replica$'): owner.match('replica')

    def test_invalid_original_is_not_negative_evidence(self):
        with patch.object(j, 'validate', side_effect=ValueError('original failed')), patch.object(j.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^original failed$'): j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_prior_gate_failure_cannot_count_as_new_rejection(self):
        with patch.object(j, 'validate', return_value={}) as checked, patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.transition, 'validate', side_effect=ValueError('prior gate failed')):
            with self.assertRaisesRegex(ValueError, '^prior gate failed$'): j.qualify(Path('/original'))
            self.assertEqual(1, checked.call_count)

    def test_unrelated_rejection_is_not_a_pass(self):
        with patch.object(j, 'validate', side_effect=[{}, ValueError('wrong reason')]), patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.transition, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining unrelated placement negative:'): j.qualify(Path('/original'))

    def test_accepted_mutation_is_a_failure(self):
        with patch.object(j, 'validate', return_value={}), patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.transition, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining placement mutation accepted:'): j.qualify(Path('/original'))


if __name__ == '__main__': unittest.main()
