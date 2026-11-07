"""Large archive staging never spends the reader's independently reserved disk."""
from pathlib import Path
import unittest
from unittest.mock import patch
from . import maximum_native_capacity as c
from .test_maximum_native_run import capacity_record


class MaximumNativeCapacityTest(unittest.TestCase):
    def test_download_extract_and_execute_leave_all_existing_capacity(self):
        g=c.GIB;archive=129*g
        self.assertGreaterEqual(c.FREE_BY_STAGE['execute'],c.native.FREE_BY_STAGE['execute']+8*g)
        self.assertGreaterEqual(c.FREE_BY_STAGE['verify-download'],2*archive+c.native.FREE_BY_STAGE['verify']+8*g)
        self.assertGreaterEqual(c.FREE_BY_STAGE['verify'],archive+c.native.FREE_BY_STAGE['verify']+8*g)
        for stage,minimum in c.FREE_BY_STAGE.items():
            native_stage='execute' if stage=='execute' else 'verify'
            with patch.object(c.native,'check',return_value=dict(capacity_record(native_stage),freeBytes=minimum)) as native:
                result=c.check(Path('/synthetic'),stage);native.assert_called_once_with(Path('/synthetic'),native_stage)
                self.assertEqual(minimum,result['minimumFreeBytes']);self.assertFalse(result['runtimeBudgetsChanged'])
            with patch.object(c.native,'check',return_value=dict(capacity_record(native_stage),freeBytes=minimum-1)):
                with self.assertRaisesRegex(ValueError,'insufficient disk'):c.check('/synthetic',stage)

    def test_native_host_memory_and_invalid_stage_cannot_be_bypassed(self):
        with patch.object(c.native,'check',side_effect=ValueError('native Linux required')) as native:
            for stage in c.FREE_BY_STAGE:
                with self.assertRaisesRegex(ValueError,'native Linux required'):c.check('/synthetic',stage)
            self.assertEqual(3,native.call_count)
            for stage in ('prepare','',True,None):
                with self.assertRaisesRegex(ValueError,'capacity stage'):c.check('/synthetic',stage)
            self.assertEqual(3,native.call_count)


if __name__=='__main__':unittest.main()
