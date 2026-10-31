from pathlib import Path
import unittest
from unittest.mock import patch
from . import joining_profile_physical_evidence as e


class JoiningProfilePhysicalEvidenceTest(unittest.TestCase):
    def test_every_profile_reaches_all_three_explicitly_scoped_readers(self):
        for profile in e.PROFILES:
            size,kind,_,_=e.topology(profile)
            with patch.object(e.s.collection,'inventory',return_value={}), \
                 patch.object(e.phase,'validate',return_value={'status':'PASS'}) as phase, \
                 patch.object(e.publication,'validate',return_value={'status':'PASS'}) as publication, \
                 patch.object(e.transition,'validate',return_value={'status':'PASS'}) as transition:
                result=e.validate('/original',profile)
                for reader in (phase,publication,transition):reader.assert_called_once_with(Path('/original'),size=size,kind=kind)
                self.assertEqual('PARTIAL',result['status']);self.assertEqual(profile,result['profile'])
                for field in ('phase3Complete','completePhysicalQualified','forceAndNetworkQualified','processDeathQualified'):
                    self.assertFalse(result[field])

    def test_unknown_profile_is_rejected_before_reading_evidence(self):
        with patch.object(e.s.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):e.validate('/original','5-ADD')
            inventory.assert_not_called()

    def test_mutation_recomputes_the_successor_with_the_actual_profile(self):
        for profile in e.PROFILES:
            size,kind,_,_=e.topology(profile)
            with patch.object(e.transition,'mutate') as mutate:
                e.mutate(Path('/copy'),'applied-allocator',profile)
                mutate.assert_called_once_with(Path('/copy'),'applied-allocator',size=size,kind=kind)

    def test_invalid_original_cannot_supply_negative_results(self):
        with patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify('/original','4-ADD')
            copied.assert_not_called()

    def qualification(self,gate_error=None,semantic_error=None):
        with patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',return_value={}), \
             patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.s,'validate',side_effect=semantic_error), \
             patch.object(e,'gate',side_effect=gate_error):
            return e.qualify('/original','4-ADD')

    def test_unrelated_failure_does_not_count_as_negative_qualification(self):
        with self.assertRaisesRegex(ValueError,'^joining profile physical unrelated negative: foreign-force-owner: unrelated$'):
            self.qualification(ValueError('unrelated'))

    def test_accepted_mutation_cannot_count_as_rejection(self):
        with self.assertRaisesRegex(ValueError,'^joining profile physical accepted mutation: foreign-force-owner$'):self.qualification()

    def test_prior_semantic_failure_cannot_count_as_new_physical_rejection(self):
        with self.assertRaisesRegex(ValueError,'^bad semantic input$'):self.qualification(semantic_error=ValueError('bad semantic input'))

    def test_original_inventory_changes_are_detected(self):
        with patch.object(e.s.collection,'inventory',side_effect=[{}, {'changed':True}]),patch.object(e,'gate',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining profile physical original changed$'):e.validate('/original','5-REPLACE')


if __name__=='__main__':unittest.main()
