import unittest
from unittest.mock import patch
from . import full_journal_evidence as q


class FullJournalTest(unittest.TestCase):
    def test_shared_budget_preserves_application_completion(self):
        self.assertEqual(31_279_080,q.LIMIT);self.assertEqual(32*1024*1024,q.LIMIT+q.ALLOWANCE)

    def test_fixture_is_exact_complete_frames_at_adjacent_boundaries(self):
        base=dict(root='0'*64,view='1'*64,ballot=dict(counter=2,proposer='node-1',incarnation='00000000-0000-0000-0000-000000000001'),basisId='00000000-0000-0000-0000-000000000002')
        for size in (180000,180001):
            data,last,count=q.filled(b'prefix',base,size);self.assertEqual(size,len(data));self.assertTrue(data.endswith(last));self.assertGreater(count,100)
            rows=q.capture.g.journal(data[6:],'0'*64,'node-1');self.assertEqual(count,len(rows));self.assertTrue(all(v[0]=='PROMISE' for v in rows))

    def test_rotation_recovery_keeps_original_until_atomic_rename(self):
        original={'grants.gsr':b'old','original.source':b'protected'}
        first,_=q.rotate(original,b'compact','JOURNAL_ROTATION_CREATED');self.assertEqual(b'',first[q.rotation.PENDING])
        second,events=q.rotate(first,b'compact','JOURNAL_ROTATION_FORCED');self.assertEqual(b'old',second['grants.gsr']);self.assertNotIn('JOURNAL_ROTATION_CREATED',events)
        final,_=q.rotate(second,b'compact');self.assertEqual({'grants.gsr':b'compact','original.source':b'protected'},final)
        self.assertEqual((final,[]),q.rotate(final,b'compact'))

    def test_absent_rotation_boundary_refused(self):
        with self.assertRaisesRegex(ValueError,'absent rotation cut'):q.rotate({'grants.gsr':b'same'},b'same','JOURNAL_ROTATION_CREATED')

    def test_invalid_original_cannot_count_as_negative_success(self):
        with patch.object(q,'validate',side_effect=ValueError('original failure')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failure'):q.qualify('raw')
            copied.assert_not_called()


if __name__=='__main__':unittest.main()
