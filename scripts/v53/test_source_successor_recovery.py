import unittest
from unittest.mock import patch
from . import source_successor_recovery_evidence as q


class SourceSuccessorRecoveryTest(unittest.TestCase):
    def original(self):
        return q.state({'grants.gsr':b'old', 'pending.accept':b'forced', 'sources':None,
                        'sources/old':None, 'sources/old/source.gscp':b'original', 'sources/old/one.image':b'image'})

    def test_force_cut_retains_every_original_file(self):
        initial = self.original()
        state, events = q.advance(initial, b'decision', b'compact', 'old', q.CUTS[0])
        self.assertEqual({**initial, q.release.AUTHORITY:q.release.r.entry(b'decision')}, state)
        self.assertEqual('SOURCE_RETIREMENT_FORCED', events[-1])
        self.assertNotIn('SOURCE_RETIREMENT_FILE_DELETED', events)

    def test_repeated_recovery_preserves_vote_and_decision_until_deletion(self):
        initial = self.original()
        state, _ = q.advance(initial, b'decision', b'compact', 'old', q.CUTS[2])
        state, events = q.advance(state, b'decision', b'compact', 'old', q.CUTS[1])
        self.assertEqual(initial['pending.accept'], state['pending.accept'])
        self.assertIn(q.release.AUTHORITY, state)
        self.assertNotIn('JOURNAL_ROTATION_CREATED', events)
        state, events = q.advance(state, b'decision', b'compact', 'old')
        self.assertEqual({'grants.gsr':q.release.r.entry(b'compact'), 'pending.accept':initial['pending.accept'],
                          'sources':dict(directory=True)}, state)
        self.assertEqual(['SOURCE_RETIREMENT_CLEARED','SOURCE_RETIREMENT_BEFORE_RETURN'], events[-2:])

    def test_missing_cut_is_not_a_clean_success(self):
        with self.assertRaisesRegex(ValueError, 'missing cut'): q.advance(self.original(), b'decision', b'compact', 'old', 'missing')

    def test_completed_transaction_cannot_be_claimed_as_interrupted(self):
        with self.assertRaisesRegex(ValueError, 'missing transaction'): q.advance(q.state({'grants.gsr':b'compact'}), b'decision', b'compact', 'old')

    def test_bad_original_cannot_count_as_negative_qualification(self):
        with patch.object(q, 'validate', side_effect=ValueError('invalid original')), patch.object(q.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, 'invalid original'): q.qualify('raw')
            copied.assert_not_called()

    def test_fixed_cases_and_negative_reasons(self):
        self.assertEqual(4, len(set(q.CUTS))); self.assertEqual(4, len(q.REASONS)); self.assertEqual(10, len(q.VARIANTS))


if __name__ == '__main__': unittest.main()
