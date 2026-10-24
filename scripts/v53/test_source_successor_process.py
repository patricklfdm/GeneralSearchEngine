import unittest
from unittest.mock import patch
from . import source_successor_process_evidence as q


class SourceSuccessorProcessTest(unittest.TestCase):
    def original(self):
        return q.q.state({'grants.gsr':b'old','pending.accept':b'forced','sources':None,
                          'sources/old':None,'sources/old/source.gscp':b'original','sources/old/one.image':b'image'})

    def test_second_file_boundary_is_distinct(self):
        first,_=q.transaction(self.original(),b'authority',b'compact','old','SOURCE_RETIREMENT_FILE_DELETED')
        second,_=q.transaction(self.original(),b'authority',b'compact','old','SOURCE_RETIREMENT_FILE_DELETED@2')
        self.assertEqual(1,len(first)-len(second));self.assertIn('sources/old',second)
        self.assertEqual(first['pending.accept'],second['pending.accept'])

    def test_after_clear_recovery_does_not_delete_again(self):
        final,_=q.transaction(self.original(),b'authority',b'compact','old')
        interrupted,events=q.transaction(final,b'authority',b'compact','old','ACCEPT_ACTIVE_FORCED')
        self.assertEqual(final,interrupted);self.assertEqual('ACCEPT_ACTIVE_FORCED',events[-1])
        reopened,events=q.transaction(interrupted,b'authority',b'compact','old')
        self.assertEqual(final,reopened);self.assertFalse(any(v.startswith('SOURCE_RETIREMENT_') for v in events))

    def test_unknown_or_missing_occurrence_refused(self):
        for cut in ('missing','SOURCE_RETIREMENT_FILE_DELETED@3'):
            with self.assertRaisesRegex(ValueError,'absent crash cut'):q.transaction(self.original(),b'authority',b'compact','old',cut)

    def test_invalid_original_prevents_mutations(self):
        with patch.object(q,'validate',side_effect=ValueError('invalid original')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):q.qualify('raw')
            copied.assert_not_called()

    def test_fixed_complete_boundaries(self):
        self.assertEqual(15,len(set(q.CUTS)));self.assertEqual(15,len(q.VARIANTS))
        self.assertIn('SOURCE_RETIREMENT_FILE_DELETED@2',q.CUTS)


if __name__=='__main__':unittest.main()
