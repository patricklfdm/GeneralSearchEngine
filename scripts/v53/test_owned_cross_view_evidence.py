import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import owned_cross_view_evidence as o


class OwnedCrossViewEvidenceTest(unittest.TestCase):
    def test_original_failure_stops_before_negative_mutation(self):
        with patch.object(o,'validate',side_effect=ValueError('original invalid')) as validate, patch.object(o.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original invalid'):o.qualify('/unused')
            validate.assert_called_once_with('/unused');copy.assert_not_called()

    def test_unrelated_failure_does_not_count_as_negative_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'receipt.json').write_bytes(o.e.f.canonical(dict(publicRuntime=False)))
            with patch.object(o,'validate',side_effect=[dict(status='PASS'),ValueError('unrelated corrupt original')]):
                with self.assertRaisesRegex(ValueError,'unrelated negative: scope'):o.qualify(path)

    def test_physical_history_is_checked_before_remote_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'histories').mkdir();(path/'transfers').mkdir();(path/'receipt.json').write_bytes(b'{}')
            with patch.object(o.x,'validate',side_effect=ValueError('invalid actual history')) as history, patch.object(o,'transfer') as transfer:
                with self.assertRaisesRegex(ValueError,'invalid actual history'):o.validate(path)
                history.assert_called_once_with(path/'histories');transfer.assert_not_called()

    def test_numeric_flags_cannot_impersonate_booleans(self):
        for actual,expected in ((0,False),(1,True)):
            with self.assertRaisesRegex(ValueError,'exact flag'):o.same(dict(flag=actual),dict(flag=expected),'exact flag')


if __name__=='__main__':unittest.main()
