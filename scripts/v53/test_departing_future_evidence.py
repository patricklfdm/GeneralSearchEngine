import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import departing_future_evidence as e
from . import future_retention_evidence as f


class DepartingFutureEvidenceTest(unittest.TestCase):
    def test_invalid_original_does_not_count_as_successful_negatives(self):
        with patch.object(e, 'validate', side_effect=ValueError('original failed')) as original, patch.object(e.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, 'original failed'): e.qualify('absent')
            original.assert_called_once(); copied.assert_not_called()

    def test_missing_or_extra_originals_fail_before_decoding(self):
        for values in ({}, {n: b'' for n in e.RECORDS[:-1]}, {n: b'' for n in (*e.RECORDS, 'ack.gsr')}):
            with self.assertRaisesRegex(ValueError, 'exact original inventory'): e.originals({}, values)

    def test_nine_record_frame_cannot_bypass_departure_validation(self):
        with patch.object(e, 'originals', side_effect=ValueError('not an exact departure')) as check:
            with self.assertRaisesRegex(ValueError, 'not an exact departure'):
                f.frame({}, {n: b'x' for n in e.RECORDS})
            check.assert_called_once()

    def test_existing_ten_record_and_empty_encoding_are_byte_identical(self):
        for values in ({}, {n: n.encode() for n in f.RECORDS}):
            metadata = dict(original='unchanged framing')
            body = f.s.part(f.f.canonical(metadata))+struct.pack('>I', len(values))
            body += b''.join(f.s.part(values[n]) for n in f.RECORDS if n in values)
            expected = struct.pack('>IHHI', 0x47534654, 1, 3, 44+len(body))+bytes.fromhex(e.d.digest(body))+body
            self.assertEqual(expected, f.frame(metadata, values))

    def test_incomplete_profile_matrix_refuses_before_consuming_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); (p/'receipt.json').write_bytes(e.canonical(dict(schema='gse-v53-departing-future-v1', authority='conditional-fixture', cases=[])))
            with self.assertRaisesRegex(ValueError, 'complete profile matrix'): e.validate(p)


if __name__ == '__main__': unittest.main()
