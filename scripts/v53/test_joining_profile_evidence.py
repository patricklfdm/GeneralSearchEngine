from itertools import combinations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joining_profile_evidence as e


class JoiningProfileEvidenceTest(unittest.TestCase):
    def test_all_five_topologies_keep_separate_old_and_new_majorities(self):
        for profile in e.PROFILES:
            size,kind,old,new=e.topology(profile);view=dict(old=old,new=new)
            universe=sorted(set(old)|set(new));live=old[:size//2+1]
            for count in range(len(universe)+1):
                for selected in combinations(universe,count):
                    valid=len(set(selected)&set(old))>=len(old)//2+1 and len(set(selected)&set(new))>=len(new)//2+1
                    if valid:e.c.catalog.majority(view,list(selected))
                    else:
                        with self.assertRaises(ValueError):e.c.catalog.majority(view,list(selected))
            if profile=='3-ADD':
                with self.assertRaisesRegex(ValueError,'^both governing majorities$'):e.c.catalog.majority(view,live)
            else:e.c.catalog.majority(view,live)
            self.assertEqual(size if kind=='REPLACE' else size+1,len(new))
            self.assertNotIn(new[-1],old)

    def test_unknown_profile_or_missing_history_never_reaches_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(e,'PrefixReplay') as replay:
            for profile in ('5-ADD','3-REMOVE','4-REMOVE','5-REMOVE','3-add'):
                with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):e.validate(directory,profile)
            for profile in e.PROFILES:
                with self.assertRaisesRegex(ValueError,'^joining prefix consecutive history$'):e.validate(directory,profile)
            replay.assert_not_called()

    def test_invalid_original_cannot_supply_five_successful_negatives(self):
        with patch.object(e.c.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify(Path('/original'),'4-ADD')
            copytree.assert_not_called()

    def test_pending_reader_does_not_claim_native_snapshot(self):
        replay=e.PrefixReplay.__new__(e.PrefixReplay);replay.placed=None;replay.path=Path('/original')
        with patch.object(e.c.joining,'read',return_value=object()) as read:
            replay.placed_snapshot();replay.placed_snapshot()
            read.assert_called_once_with(Path('/original/joining-originals-pending'),stage='pending')


if __name__=='__main__':unittest.main()
