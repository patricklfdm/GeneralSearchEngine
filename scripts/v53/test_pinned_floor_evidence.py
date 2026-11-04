import unittest
from unittest.mock import patch
from . import pinned_floor_evidence as e


class PinnedFloorEvidenceTest(unittest.TestCase):
    def test_local_original_is_forced_before_selector_and_proposal(self):
        h='a'*64
        selector=e.f.encode('records','SELECTOR',dict(root='b'*64,node='node-1',generation='a',digest=h))
        copies={h:{'generation.gsr':b'local','source.gscp':b's','00.image':b'i'},
                'remote':{'generation.gsr':b'peer','source.gscp':b'p','11.image':b'j'}}
        events,files,dirs=e.floor_plan(copies,b'floor',selector)
        self.assertEqual(selector,files[e.PIN]);self.assertNotIn('floor-copies/'+h,dirs)
        self.assertNotIn('floor-copies/'+h+'/00.image',files)
        self.assertIn('floor-copies/remote/11.image',files)
        for a,b in zip(('FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED'),
                       ('FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED','FLOOR_PROPOSAL_WRITTEN')):
            self.assertLess(events.index(a),events.index(b))
        self.assertLess(events.index('FLOOR_COPIES_FORCED'),events.index('FLOOR_AUTHORITY_WRITTEN'))

    def test_missing_local_original_cannot_create_a_pin(self):
        selector=e.f.encode('records','SELECTOR',dict(root='b'*64,node='node-1',generation='a',digest='a'*64))
        with self.assertRaisesRegex(ValueError,'local original absent'):e.floor_plan({},b'floor',selector)

    def test_release_keeps_local_selector_pin_until_copied_originals_are_gone(self):
        events=e.release_events({'floor-copies/a':dict(directory=True),'floor-copies/a/a.image':dict(bytes=1),e.PIN:dict(bytes=20)})
        self.assertLess(events.index('FLOOR_RELEASE_RELINQUISHED'),events.index('FLOOR_RELEASE_FILE_DELETED'))
        self.assertLess(events.index('FLOOR_RELEASE_COPY_DELETED'),events.index('FLOOR_RELEASE_LOCAL_CLEARED'))
        self.assertLess(events.index('FLOOR_RELEASE_LOCAL_CLEARED'),events.index('FLOOR_RELEASE_AUTHORITY_CLEARED'))

    def test_invalid_original_never_counts_as_negative_qualification(self):
        with patch.object(e.original,'history_inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'bad original'):e.qualify('absent')
            copied.assert_not_called()

    def test_unrelated_error_is_not_a_qualified_negative(self):
        with patch.object(e.original,'history_inventory',return_value={}),patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'):
            with self.assertRaisesRegex(ValueError,'unrelated negative'):e.qualify('absent')

    def test_original_evidence_cannot_change_during_qualification(self):
        with patch.object(e.original,'history_inventory',side_effect=[{},dict(changed=True)]),patch.object(e,'validate',side_effect=[{}]+[ValueError(v) for v in e.NEGATIVES.values()]),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'):
            with self.assertRaisesRegex(ValueError,'original evidence changed'):e.qualify('absent')


if __name__=='__main__':unittest.main()
