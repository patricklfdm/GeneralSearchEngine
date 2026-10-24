"""Independent replay safeguards for forced empty vote before context withdrawal."""
import unittest
from unittest.mock import patch
from . import covered_context_evidence as q


class CoveredContextEvidenceTest(unittest.TestCase):
    def states(self):
        before={'selector.gsr':b'new','pending.accept':b'original vote','pending.context':b'original context',
                'source/exact':b'source','floor-copies/floor.gsr':b'floor'}
        after={k:v for k,v in before.items() if k!='pending.context'};after['pending.accept']=q.c.EMPTY
        return before,after

    def test_invalid_original_stops_before_any_mutation(self):
        with patch.object(q,'validate',side_effect=ValueError('invalid original')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):q.qualify('profiles','interruptions','accept','proof')
            copied.assert_not_called()

    def test_clear_is_forced_before_context_is_removed(self):
        before,after=self.states();final,events=q.transaction(before,after)
        self.assertEqual(after,final)
        for first,second in [('SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED'),('SETTLED_VOTE_PARENT_FORCED','CONTEXT_SETTLEMENT_EMPTY_FORCED'),('CONTEXT_SETTLEMENT_EMPTY_FORCED','CONTEXT_REDUNDANT_DELETED'),('CONTEXT_REDUNDANT_PARENT_FORCED','CONTEXT_SETTLEMENT_CLEARED')]:
            self.assertLess(events.index(first),events.index(second))
        self.assertIn('pending.context',before);self.assertEqual(b'original vote',before['pending.accept'])

    def test_every_cleanup_cut_retains_authority_and_recovers_again(self):
        before,after=self.states()
        for cut in q.CUTS[4:]:
            with self.subTest(cut=cut):
                first,_=q.transaction(before,after,cut)
                retry='CONTEXT_SETTLEMENT_EMPTY_FORCED' if 'pending.context' in first else 'ACCEPT_ACTIVE_FORCED'
                second,_=q.transaction(first,after,retry);final,_=q.transaction(second,after)
                self.assertEqual(after,final);self.assertEqual(b'floor',first['floor-copies/floor.gsr']);self.assertEqual(b'source',second['source/exact'])

    def test_partial_empty_candidate_never_erases_original_early(self):
        before,after=self.states();first,_=q.transaction(before,after,'SETTLED_VOTE_PREFIX_WRITTEN')
        self.assertEqual(q.c.EMPTY[:6],first['pending.accept.next']);self.assertEqual(b'original vote',first['pending.accept'])
        second,events=q.transaction(first,after,'CONTEXT_SETTLEMENT_EMPTY_FORCED')
        self.assertNotIn('SETTLED_VOTE_CANDIDATE_CREATED',events);self.assertEqual(q.c.EMPTY,second['pending.accept']);self.assertIn('pending.context',second)

    def test_conflicting_empty_candidate_is_rejected(self):
        before,after=self.states()
        for value in (b'wrong',q.c.EMPTY+b'extra'):
            changed=dict(before,**{'pending.accept.next':value})
            with self.assertRaisesRegex(ValueError,'exact empty candidate'):q.transaction(changed,after)
            self.assertEqual(b'original vote',changed['pending.accept'])

    def test_completed_vote_with_unexplained_candidate_is_rejected(self):
        before,after=self.states();before['pending.accept']=q.c.EMPTY;before['pending.accept.next']=b''
        with self.assertRaisesRegex(ValueError,'unexpected empty candidate'):q.transaction(before,after)

    def test_completed_cleanup_only_reseals(self):
        _,after=self.states();final,events=q.transaction(after,after)
        self.assertEqual(after,final);self.assertEqual(q.covered.OPEN+q.covered.SEAL+['FLOOR_COPY_BEFORE_RETURN'],events)
        with self.assertRaisesRegex(ValueError,'not reached'):q.transaction(after,after,'CONTEXT_SETTLEMENT_VALIDATED')

    def test_unknown_phase_does_not_default_to_certificate(self):
        for phase in ('',None,'PROOF_ONLY',True):
            with self.subTest(phase=phase),self.assertRaisesRegex(ValueError,'phase'):q.phase_names(phase)


if __name__=='__main__':unittest.main()
