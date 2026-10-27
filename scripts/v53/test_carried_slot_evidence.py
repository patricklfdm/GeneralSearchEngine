import unittest
from unittest.mock import patch
from pathlib import Path
from . import carried_slot_evidence as e


class CarriedSlotEvidenceTest(unittest.TestCase):
    def test_bad_original_stops_before_any_mutation(self):
        with patch.object(e, 'validate', side_effect=ValueError('broken original')) as validate, patch.object(e.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, '^broken original$'):
                e.qualify(Path('/unread-original'))
        validate.assert_called_once_with(Path('/unread-original'))
        copy.assert_not_called()

if __name__ == '__main__': unittest.main()
