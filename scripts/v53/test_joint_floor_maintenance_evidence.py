"""Cold-owner boundaries and original-first independent qualification."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joint_floor_maintenance_evidence as e


class JointFloorMaintenanceTest(unittest.TestCase):
    def events(self):
        return [dict(node=e.NODE,scope=e.SCOPE,event=point) for point in (
            'CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED',
            'CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED','FLOOR_RELEASE_BEFORE_RETURN')]

    def test_first_cold_boundary_is_not_later_install_revalidation(self):
        events=self.events();events+=copy.deepcopy(events[:5])
        self.assertEqual((0,5),e.boundary(events))

    def test_force_omission_reordering_and_foreign_owner_refuse(self):
        for mode in ('missing','reorder','scope','owner'):
            events=self.events()
            if mode=='missing':events.pop(1)
            elif mode=='reorder':events[1],events[2]=events[2],events[1]
            elif mode=='scope':events[1]['scope']='foreign'
            else:events[1]['node']='foreign'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original cold force order'):e.boundary(events)

    def test_release_and_owner_cannot_be_inferred(self):
        with self.assertRaisesRegex(ValueError,'missing cold owner'):e.boundary([])
        with self.assertRaisesRegex(ValueError,'missing recovered floor release'):e.boundary(self.events()[:-1])

    def test_qualification_rejects_original_before_mutating(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'validated',side_effect=ValueError('bad original')),patch.object(e,'mutate') as mutation:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify(Path(tmp))
            mutation.assert_not_called()

    def test_unknown_mutation_refuses_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'unknown mutation'):e.mutate(Path(tmp),'unknown')
            self.assertEqual([],list(Path(tmp).iterdir()))


if __name__=='__main__':unittest.main()
