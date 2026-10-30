from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_restart_evidence as a


class AutomaticRestartEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_supply_negative_success(self):
        with patch.object(a, 'validate', side_effect=ValueError('invalid original')), patch.object(a.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): a.qualify('unused')
            copied.assert_not_called()

    def test_links_reject_before_reading_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'real').write_bytes(b'original'); (root/'linked').symlink_to('real')
            with patch.object(a.b, 'original') as original:
                with self.assertRaisesRegex(ValueError, '^automatic restart regular inventory$'): a.validate(root)
                original.assert_not_called()

    def test_missing_inventory_cannot_be_treated_as_producer_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'restart-result.json').write_text('{"status":"PASS"}')
            with patch.object(a.b, 'original') as original:
                with self.assertRaisesRegex(ValueError, '^context selection automatic restart original history inventory$'): a.validate(root)
                original.assert_not_called()


if __name__ == '__main__': unittest.main()
