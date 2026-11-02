import unittest
import struct
from unittest.mock import patch
from pathlib import Path
from . import carried_slot_evidence as e


class CarriedSlotEvidenceTest(unittest.TestCase):
    def test_data_fixture_bytes_bind_the_exact_key_and_document(self):
        text=b'303:admitted-original'
        expected=b'\x01'+struct.pack('>HIII',1,1,4,303)+struct.pack('>I',len(text))+text
        self.assertEqual(expected,e.d.fixture_data((303,'admitted-original')))
        for document in ((304,'admitted-original'),(303,'changed')):
            self.assertNotEqual(expected,e.d.fixture_data(document))

    def test_data_scope_rejects_before_reading_an_unknown_payload_kind(self):
        with patch.object(e.b.t.plans,'read') as read:
            for kind in ('CONTROL','INTENT','FINAL',None,True):
                with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'carried payload kind'):
                    e.validate(Path('/unread-original'),kind=kind)
        read.assert_not_called()

    def test_data_negatives_extend_every_prior_physical_check(self):
        for phase in e.PHASES:
            barrier=e.negative_cases(phase,confirmed_retention=True)
            data=e.negative_cases(phase,confirmed_retention=True,kind='DATA')
            self.assertEqual(26,len(barrier));self.assertEqual(33 if phase=='APPLIED' else 32,len(data))
            self.assertEqual(barrier,{k:data[k] for k in barrier})
            self.assertTrue(set(e.DATA_NEGATIVES).issubset(data))
            self.assertEqual(phase=='APPLIED','data-old-image' in data)
        with self.assertRaisesRegex(ValueError,'declared negative scope'):e.negative_cases('UNKNOWN',kind='DATA')

    def test_bad_data_original_cannot_count_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('broken data')) as validate,patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'broken data'):
                e.qualify(Path('/data-original'),confirmed_retention=True,kind='DATA')
        validate.assert_called_once_with(Path('/data-original'),confirmed_retention=True,kind='DATA');copy.assert_not_called()

    def test_bad_original_stops_before_any_mutation(self):
        with patch.object(e, 'validate', side_effect=ValueError('broken original')) as validate, patch.object(e.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, '^broken original$'):
                e.qualify(Path('/unread-original'))
        validate.assert_called_once_with(Path('/unread-original'))
        copy.assert_not_called()

if __name__ == '__main__': unittest.main()
