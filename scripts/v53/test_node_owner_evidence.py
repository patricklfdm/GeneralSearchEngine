from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_owner_evidence as n


class NodeOwnerEvidenceTest(unittest.TestCase):
    def test_invalid_original_precedes_every_negative_mutation(self):
        with patch.object(n, 'validate', side_effect=ValueError('invalid original')), patch.object(n.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): n.qualify('unused')
            copied.assert_not_called()

    def test_link_rejects_before_original_reconstruction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'real').write_bytes(b'original'); (root/'link').symlink_to('real')
            with patch.object(n.b, 'original') as original:
                with self.assertRaises(ValueError): n.validate(root)
                original.assert_not_called()

    def test_producer_pass_cannot_replace_original_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'node-result.json').write_text('{"producerPassed":true}')
            with patch.object(n.b, 'original') as original:
                with self.assertRaisesRegex(ValueError, 'node owner original history inventory'): n.validate(root)
                original.assert_not_called()


if __name__ == '__main__': unittest.main()
