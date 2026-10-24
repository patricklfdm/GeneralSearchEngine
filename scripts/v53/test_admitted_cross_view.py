"""Reader regressions for complete originals and genuine joint majorities."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import admitted_cross_view_evidence as q


class AdmittedCrossViewTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_negative_qualification(self):
        with patch.object(q,'validate',side_effect=ValueError('original failure')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failure'):q.qualify('missing')
            copied.assert_not_called()

    def test_missing_or_linked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'missing'
            with self.assertRaises(ValueError):q.validate(root)
            real=Path(temp)/'real';real.mkdir();root.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):q.validate(root)

    def test_surviving_voters_satisfy_both_removal_majorities(self):
        for size in (4,5):
            old=['node-'+str(i) for i in range(1,size+1)];new=old[:-1]
            q.context.majority(dict(old=old,new=new),new)

    def test_old_majority_does_not_substitute_for_new_majority(self):
        view=dict(old=['node-1','node-2','node-3','node-4','node-5'],new=['node-1','node-2','node-3','node-4'])
        with self.assertRaisesRegex(ValueError,'both governing majorities'):q.context.majority(view,['node-1','node-2','node-5'])

    def test_removed_or_duplicate_voter_is_not_a_new_stable_quorum(self):
        view=dict(old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'])
        for names in (['node-1','node-1','node-2'],['node-1','node-2','node-4']):
            with self.assertRaisesRegex(ValueError,'quorum identity/order'):q.context.majority(view,names)


if __name__=='__main__':unittest.main()
