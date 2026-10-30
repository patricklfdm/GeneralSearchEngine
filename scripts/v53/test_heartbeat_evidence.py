from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import heartbeat_evidence as h


class HeartbeatEvidenceTest(unittest.TestCase):
    def test_bad_original_cannot_be_replaced_by_negative_outcomes(self):
        with patch.object(h,'validate',side_effect=ValueError('invalid original')),patch.object(h.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):h.qualify('unused')
            copied.assert_not_called()

    def test_linked_original_rejected_before_bootstrap_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'real').write_bytes(b'original');(root/'linked').symlink_to('real')
            with patch.object(h.b,'original') as decode:
                with self.assertRaisesRegex(ValueError,'^discovered selection regular inventory$'):h.validate(root)
                decode.assert_not_called()


if __name__=='__main__':unittest.main()
