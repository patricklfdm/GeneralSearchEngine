import unittest
from unittest.mock import patch
from . import measurement_model as model,measurement_runtime_evidence as e


class MeasurementRuntimeEvidenceTest(unittest.TestCase):
    def test_only_published_control_may_lack_new_application_generation(self):
        for mode in model.MODES:
            self.assertEqual(7,e.publication_generation(dict(applicationGeneration=7),mode))
            if mode=='published-v51-legacy-strong':self.assertIsNone(e.publication_generation({},mode))
            else:
                with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'missing application generation'):e.publication_generation({},mode)
            for value in (True,0,-1,'1',None):
                with self.subTest(mode=mode,value=value),self.assertRaisesRegex(ValueError,'generation type'):e.publication_generation(dict(applicationGeneration=value),mode)

    def test_invalid_original_never_counts_as_successful_negative_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('original physical evidence failed')) as check:
            with self.assertRaisesRegex(ValueError,'original physical evidence failed'):e.negatives('unused',{}, {})
        check.assert_called_once_with('unused',{}, {})


if __name__=='__main__':unittest.main()
