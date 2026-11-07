"""Small-history disk preconditions; these do not measure runtime resources."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import backup_resource_capacity as c


class BackupResourceCapacityTest(unittest.TestCase):
    def test_exact_stage_thresholds_and_independent_transport_scope(self):
        with tempfile.TemporaryDirectory() as path:
            for stage,limit in c.FREE_BY_STAGE.items():
                with self.subTest(stage=stage),patch.object(c.shutil,'disk_usage',return_value=SimpleNamespace(free=limit)):
                    result=c.check(path,stage)
                    self.assertEqual((limit,limit),(result['freeBytes'],result['minimumFreeBytes']))
                    self.assertEqual('PASS',result['status'])
                    for key in ('runtimeBudgetsChanged','maximumImageQualified','phase3Complete'):self.assertFalse(result[key])
                with patch.object(c.shutil,'disk_usage',return_value=SimpleNamespace(free=limit-1)):
                    with self.assertRaisesRegex(ValueError,'insufficient disk'):c.check(path,stage)
        self.assertEqual({'execute':40*c.GIB,'verify-download':40*c.GIB,'verify':23*c.GIB},c.FREE_BY_STAGE)

    def test_invalid_stage_missing_directory_and_file_rejected_before_disk_probe(self):
        with tempfile.TemporaryDirectory() as path,patch.object(c.shutil,'disk_usage') as probe:
            for stage in ('maximum',None,False,1):
                with self.assertRaisesRegex(ValueError,'capacity stage'):c.check(path,stage)
            with self.assertRaises(FileNotFoundError):c.check(Path(path)/'missing','execute')
            file=Path(path)/'file';file.write_text('original')
            with self.assertRaisesRegex(ValueError,'workspace directory'):c.check(file,'execute')
            probe.assert_not_called()


if __name__=='__main__':unittest.main()
