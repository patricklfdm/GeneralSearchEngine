import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import departing_end_evidence as e


class DepartingEndEvidenceTest(unittest.TestCase):
    def test_departure_requires_all_six_original_files_and_no_vote(self):
        for files in ({}, {n: b'' for n in e.FILES if n != 'application.image'}, {n: b'' for n in (*e.FILES, 'ack.gsr')}):
            with self.assertRaisesRegex(ValueError, 'nonvoting inventory'):
                e.materialization(files, b'', b'', '4-REMOVE')

    def test_invalid_original_cannot_qualify_negative_cases(self):
        with patch.object(e, 'validate', side_effect=ValueError('original failed')) as original, patch.object(e.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, 'original failed'): e.qualify('absent')
            original.assert_called_once(); copy.assert_not_called()

    def test_complete_replay_has_no_ack_force_or_ack_return(self):
        files = {n: b'example' for n in e.FILES}
        actual, exists, events = e.simulate(files, {}, False)
        self.assertEqual(files, actual); self.assertTrue(exists)
        names = [v['event'] for v in events]
        self.assertFalse(any('ACK' in n for n in names))
        self.assertLess(names.index('APPLY_IMAGE_FORCED'), names.index('APPLY_END_FORCED'))
        self.assertEqual(['APPLY_END_FORCED', 'APPLY_NONVOTING_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'], names[-3:])

    def test_incomplete_or_wrong_matrix_refuses_before_reading_case_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = dict(schema='gse-v53-departing-end-v1', cases=[], expectedCases=170, powerLoss=False, protocolAuthority='conditional-fixture')
            (root/'receipt.json').write_bytes(e.canonical(receipt))
            with self.assertRaisesRegex(ValueError, 'complete crash matrix'): e.validate(root)
            receipt['protocolAuthority'] = 'native'; (root/'receipt.json').write_bytes(e.canonical(receipt))
            with self.assertRaisesRegex(ValueError, 'qualification scope'): e.validate(root)

    def test_changed_recovery_prefix_refuses_before_accepting_final_bytes(self):
        files = {n: b'example' for n in e.FILES}
        with self.assertRaisesRegex(ValueError, 'original prefix'):
            e.simulate(files, {'application.image': b'wrong'}, True)


if __name__ == '__main__': unittest.main()
