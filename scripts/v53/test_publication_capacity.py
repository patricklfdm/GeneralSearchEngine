import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import publication_capacity_evidence as e


class PublicationCapacityTest(unittest.TestCase):
    def test_incomplete_original_cannot_be_counted_as_negative_rejection(self):
        with patch.object(e,'validate',side_effect=ValueError('original failed')),patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original failed'):e.qualify('missing')
            copy.assert_not_called()

    def test_alias_does_not_count_as_an_unchanged_physical_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'original').write_bytes(b'original');(root/'alias').symlink_to('original')
            with self.assertRaisesRegex(ValueError,'refusal symlink'):e.inventory(root)

    def test_missing_case_is_not_a_partial_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'refusal case inventory'):e.validate(temp)


if __name__=='__main__':unittest.main()
