import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import pending_checkpoint_evidence as q


class PendingCheckpointEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_successful_mutation_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(q,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(q.shutil,'copytree') as copies:
                with self.assertRaisesRegex(ValueError,'invalid original'):q.qualify(Path(temp))
                validate.assert_called_once();copies.assert_not_called()


if __name__=='__main__':unittest.main()
