"""Safeguards for original-first and exact-prefix covered-vote replay."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import covered_minority_evidence as m


class CoveredMinorityEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_before_mutations_or_copy(self):
        with patch.object(m,'clean',side_effect=ValueError('invalid clean original')),patch.object(m,'interrupted') as second,patch.object(m.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid clean original'):m.qualify('clean','interrupted')
            second.assert_not_called();copy.assert_not_called()

    def test_invalid_interrupted_original_stops_before_negatives(self):
        with patch.object(m,'clean',return_value={}),patch.object(m,'interrupted',side_effect=ValueError('invalid interrupted original')),patch.object(m.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid interrupted original'):m.qualify('clean','interrupted')
            copy.assert_not_called()

    def test_no_empty_or_linked_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            for validator in (m.clean,m.interrupted):
                for path in (root,link):
                    with self.subTest(validator=validator.__name__,path=path),self.assertRaisesRegex(ValueError,'inventory'):validator(path)

    def test_twice_interrupted_clear_retains_old_vote_until_rename(self):
        before={'selector.gsr':b'installed','pending.accept':b'original','original/source':b'original source'}
        after=dict(before,**{'pending.accept':m.c.EMPTY})
        first,events=m.transaction(before,after,'SETTLED_VOTE_PREFIX_WRITTEN')
        self.assertEqual(b'original',first['pending.accept']);self.assertEqual(m.c.EMPTY[:6],first['pending.accept.next'])
        self.assertEqual('SETTLED_VOTE_PREFIX_WRITTEN',events[-1])
        second,events=m.transaction(first,after,'SETTLED_VOTE_CANDIDATE_PARENT_FORCED')
        self.assertEqual(b'original',second['pending.accept']);self.assertEqual(m.c.EMPTY,second['pending.accept.next'])
        self.assertNotIn('SETTLED_VOTE_CANDIDATE_CREATED',events)
        final,events=m.transaction(second,after)
        self.assertEqual(after,final);self.assertNotIn('SETTLED_VOTE_CANDIDATE_CREATED',events)
        self.assertLess(events.index('SETTLED_VOTE_PARENT_FORCED'),events.index('ACCEPT_ACTIVE_FORCED'))
        self.assertEqual(b'original',before['pending.accept'])

    def test_completed_empty_replacement_only_reseals_and_returns(self):
        after={'selector.gsr':b'installed','pending.accept':m.c.EMPTY}
        final,events=m.transaction(after,after)
        self.assertEqual(after,final);self.assertEqual(m.OPEN+m.SEAL+['FLOOR_COPY_BEFORE_RETURN'],events)
        with self.assertRaisesRegex(ValueError,'not reached'):m.transaction(after,after,'SETTLED_VOTE_VALIDATED')

    def test_empty_owner_trace_cannot_claim_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'calls.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'complete owner calls'):m.calls(root)

    def test_unknown_mutation_is_an_error(self):
        with self.assertRaisesRegex(ValueError,'unknown covered mutation'):m.mutate(Path('.'),'unknown',Path('.'))


if __name__=='__main__':unittest.main()
