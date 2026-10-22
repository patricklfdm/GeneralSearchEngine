import unittest
from unittest.mock import patch
from . import selection_evidence as e
from . import selection_negatives as n


def row(cut,ballot=None,entry=None):
    return dict(basis=dict(cut=dict(index=cut)),accept=None if ballot is None else dict(index=cut+1,ballot=dict(counter=ballot,proposer='node-1',incarnation='disk'),entry=entry))


class SelectionEvidenceTest(unittest.TestCase):
    def test_covered_minority_tail_is_retained_but_cannot_displace_longest_proven_slot(self):
        short=row(8,10,'minority');longer=row(9);before=repr(short)
        longest,tail=e.decide([short,longer]);self.assertIs(longer,longest);self.assertIsNone(tail);self.assertEqual(before,repr(short))

    def test_only_highest_next_slot_and_no_equal_ballot_conflict(self):
        first=row(9,3,'older');second=row(9,8,'carried');third=row(9,8,'carried')
        self.assertEqual('carried',e.decide([first,second,third])[1])
        with self.assertRaisesRegex(ValueError,'conflicting'):e.decide([first,second,row(9,8,'other')])

    def test_invalid_original_never_counts_as_negative_success(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.run('absent')
            copy.assert_not_called()


if __name__=='__main__':unittest.main()
