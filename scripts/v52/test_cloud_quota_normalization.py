"""Offline regression tests for provider quota-counter normalization."""
from copy import deepcopy
import unittest
from . import cloud_preflight as f


class QuotaNormalizationTest(unittest.TestCase):
    def observed(self, limit=1000, usage=-100, required=390, metric='SSD_TOTAL_GB'):
        return f.quota([dict(metric=metric,limit=limit,usage=usage)],{metric:required})[metric]

    def test_positive_usage_keeps_existing_result_shape(self):
        self.assertEqual(dict(required=390,available=800),self.observed(usage=200))

    def test_zero_usage_keeps_existing_result_shape(self):
        self.assertEqual(dict(required=390,available=1000),self.observed(usage=0))

    def test_negative_usage_passes_with_observation_and_warning(self):
        self.assertEqual(dict(required=390,available=1000,limit=1000,reportedUsage=-100,
                              effectiveUsage=0,warning='NEGATIVE_QUOTA_USAGE_NORMALIZED'),self.observed())

    def test_negative_usage_never_increases_limit(self):
        for usage in (-0.5,-100,-10000,-1e308):
            with self.subTest(usage=usage):
                self.assertEqual(1000,self.observed(usage=usage)['available'])
                with self.assertRaisesRegex(ValueError,'quota headroom'):
                    self.observed(usage=usage,required=1001)

    def test_normalization_applies_to_each_expected_quota_metric(self):
        for metric in ('SSD_TOTAL_GB','CPUS','N2_CPUS','CPUS_ALL_REGIONS','INSTANCES','FIREWALLS'):
            with self.subTest(metric=metric):
                self.assertEqual(1000,self.observed(metric=metric)['available'])

    def test_exact_limit_and_zero_limit_boundaries(self):
        self.assertEqual(1000,self.observed(required=1000)['available'])
        self.assertEqual(0,self.observed(limit=0,required=0)['available'])
        with self.assertRaisesRegex(ValueError,'quota headroom'):
            self.observed(limit=0,required=1)

    def test_positive_usage_still_blocks_insufficient_headroom(self):
        for usage in (611,1000,1100):
            with self.subTest(usage=usage),self.assertRaisesRegex(ValueError,'quota headroom'):
                self.observed(usage=usage)
        self.assertEqual(390,self.observed(usage=610)['available'])

    def test_negative_limit_is_not_normalized(self):
        for limit in (-1,-1000):
            with self.subTest(limit=limit),self.assertRaisesRegex(ValueError,'quota numbers'):
                self.observed(limit=limit)

    def test_nonfinite_and_nonnumeric_values_still_reject(self):
        invalid=(float('nan'),float('inf'),float('-inf'),True,False,None,'-100',[],{})
        for field in ('limit','usage'):
            for value in invalid:
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'quota numbers'):
                    self.observed(**{field:value})

    def test_input_observation_is_not_mutated(self):
        rows=[dict(metric='SSD_TOTAL_GB',limit=1000,usage=-100)]
        original=deepcopy(rows)
        f.quota(rows,{'SSD_TOTAL_GB':390})
        self.assertEqual(original,rows)

    def test_duplicate_missing_and_malformed_metrics_still_reject(self):
        row=dict(metric='SSD_TOTAL_GB',limit=1000,usage=-100)
        with self.assertRaisesRegex(ValueError,'duplicate quota metric'):
            f.quota([row,deepcopy(row)],{'SSD_TOTAL_GB':390})
        with self.assertRaises(KeyError):
            f.quota([row],{'CPUS':1})
        for field in ('limit','usage'):
            bad=deepcopy(row);bad.pop(field)
            with self.subTest(field=field),self.assertRaises(KeyError):
                f.quota([bad],{'SSD_TOTAL_GB':1})
        for rows in (None,{},[None],[dict(metric=True,limit=1000,usage=-100)]):
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,'quota inventory'):
                f.quota(rows,{'SSD_TOTAL_GB':1})

    def test_all_metrics_must_have_enough_headroom(self):
        rows=[dict(metric='SSD_TOTAL_GB',limit=1000,usage=-100),dict(metric='CPUS',limit=24,usage=20)]
        with self.assertRaisesRegex(ValueError,'quota headroom: CPUS'):
            f.quota(rows,{'SSD_TOTAL_GB':390,'CPUS':12})

    def test_available_matches_capped_formula_over_numeric_grid(self):
        for limit in (0,1,10,1000):
            for usage in (-10000,-100,-0.5,0,0.5,10,1000,1001):
                expected=limit-max(0,usage)
                with self.subTest(limit=limit,usage=usage):
                    if expected < 0:
                        with self.assertRaisesRegex(ValueError,'quota headroom'):
                            self.observed(limit=limit,usage=usage,required=0)
                    else:
                        result=self.observed(limit=limit,usage=usage,required=0)
                        self.assertEqual(expected,result['available'])
                        self.assertLessEqual(result['available'],limit)
