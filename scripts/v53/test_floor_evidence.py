import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import floor_evidence as e
from . import floor_negatives as n
from . import floor_qualification as q


class FloorEvidenceTest(unittest.TestCase):
    def test_old_joint_and_new_profiles_cover_each_crash_boundary(self):
        rows=e.cases();self.assertEqual(315,len(rows));self.assertEqual(315,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (0,6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})

    def test_all_full_copies_precede_floor_authority(self):
        copies={'aa':{'generation.gsr':b'a','source.gscp':b's','00.image':b'i'},'bb':{'generation.gsr':b'b','source.gscp':b't','11.image':b'j'}}
        rows,files,writes,dirs=e.transaction(copies,b'floor');events=[r['event'] for r in rows]
        boundary=events.index('FLOOR_AUTHORITY_WRITTEN')
        self.assertLess(events.index('FLOOR_COPIES_FORCED'),boundary)
        for name,index in writes.items():
            if name!='floor-copies/floor.gsr':self.assertLess(index,boundary)
        self.assertEqual(2,events.count('FLOOR_COPY_DIRECTORY_FORCED'))
        self.assertLess(events.index('FLOOR_AUTHORITY_FORCED'),events.index('FLOOR_BEFORE_RETURN'))

    def test_force_observations_remain_owner_bound(self):
        events=e.opened(['node-2','node-3'])
        for node in ('node-1','node-2','node-3'):
            force=events.index(dict(node=node,event='CURRENT_GENERATION_FORCED'))
            result=events.index(dict(node=node,event='FLOOR_COPY_BEFORE_RETURN'))
            self.assertLess(force,result)

    def test_receipt_cannot_grant_deletion_or_network_ack(self):
        manifest=dict(cut={'index':7});floor=b'floor';row=dict(floor=e.c.sha(floor),cut=manifest['cut'],networkAck=False,deletion=False)
        e.result([row],manifest,floor)
        for field in ('networkAck','deletion'):
            with self.assertRaisesRegex(ValueError,'floor returned binding'):e.result([dict(row,**{field:True})],manifest,floor)

    def test_invalid_original_does_not_count_as_successful_rejection(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copied.assert_not_called()

    def test_unrelated_failure_is_not_an_expected_negative(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated floor negative'):n.run('absent')

    def test_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
