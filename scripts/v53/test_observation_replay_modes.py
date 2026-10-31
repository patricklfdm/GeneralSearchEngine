"""Mode selection and original-first guards for retained-history replay."""
from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_dispatch_evidence as native
from . import round_driver_evidence as driver
from . import carried_slot_evidence as carried
from . import heartbeat_round_evidence as heartbeat


class ObservationReplayModesTest(unittest.TestCase):
    def test_invalid_confirmed_original_stops_before_all_negative_copies(self):
        for reader in (native, driver, carried, heartbeat):
            with self.subTest(reader=reader.__name__), patch.object(reader, 'validate', side_effect=ValueError('invalid original')) as validate, patch.object(reader.shutil, 'copytree') as copy:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    reader.qualify(Path('/original'), confirmed_retention=True)
                self.assertEqual(1, validate.call_count)
                self.assertEqual((Path('/original'),), validate.call_args.args)
                self.assertIs(True, validate.call_args.kwargs.get('confirmed_retention'))
                copy.assert_not_called()

    def test_legacy_default_is_not_automatically_retried_as_confirmed(self):
        for reader in (native, driver, carried, heartbeat):
            with self.subTest(reader=reader.__name__), patch.object(reader, 'validate', side_effect=ValueError('legacy mismatch')) as validate, patch.object(reader.shutil, 'copytree') as copy:
                with self.assertRaisesRegex(ValueError, '^legacy mismatch$'):reader.qualify(Path('/original'))
                self.assertEqual(1, validate.call_count)
                self.assertEqual((Path('/original'),), validate.call_args.args)
                self.assertIs(False, validate.call_args.kwargs.get('confirmed_retention', False))
                copy.assert_not_called()


if __name__ == '__main__': unittest.main()
