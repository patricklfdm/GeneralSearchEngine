"""Binding mutation coverage; synthetic originals are not native acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import export_allocation_negatives as n,native_resource_evidence as native
from .test_export_allocation_coverage import fixture,bind


class ExportAllocationNegativesTest(unittest.TestCase):
    def test_all_eighteen_exact_negatives_across_every_session_role(self):
        for role in n.r.exports.ROLES:
            data=fixture(role,True);bindings=bind(data);before=copy.deepcopy((data,bindings));progress=[]
            rows=n.replay(*data[:2],bindings,progress.append)
            with self.subTest(role=role):
                self.assertEqual([dict(case=k,status='REJECTED',reason=v) for k,v in n.NEGATIVES.items()],rows)
                self.assertEqual(18,len(rows));self.assertEqual(18,progress[-1]['completed']);self.assertEqual(before,(data,bindings))

    def test_invalid_original_or_missing_scope_cannot_receive_negative_credit(self):
        data=fixture();bindings=bind(data);data[1]['node-1']['failed']=True
        with patch.object(n,'mutate') as mutate,self.assertRaisesRegex(ValueError,'complete bounded recorder'):
            n.replay(*data[:2],bindings)
        mutate.assert_not_called()
        data=fixture();bindings=bind(data)
        # Even otherwise admitted export inventories must exercise all scopes.
        for v in bindings.values():v['scope']='session'
        with patch.object(n.r,'replay',return_value={}),patch.object(n,'mutate') as mutate,\
             self.assertRaisesRegex(ValueError,'all three original scopes required'):n.replay(*data[:2],bindings)
        mutate.assert_not_called()

    def test_unrelated_errors_and_accepted_mutations_cannot_pass(self):
        data=fixture();bindings=bind(data)
        with patch.object(n.r,'replay',side_effect=[{},ValueError('unrelated')]),\
             self.assertRaisesRegex(ValueError,'unrelated negative'):n.replay(*data[:2],bindings)
        with patch.object(n,'mutate'),self.assertRaisesRegex(ValueError,'accepted mutation'):n.replay(*data[:2],bindings)

    def test_native_export_output_is_empty_and_never_an_input_authority(self):
        for target,complete in (({},False),({'forged':'proof'},True),([],True)):
            with patch.object(native.publication,'validate') as physical,\
                 self.assertRaisesRegex(ValueError,'empty complete-export output only'):
                native.validate('/unused','5-REPLACE-required-four',complete_exports=complete,export_bindings_out=target)
            physical.assert_not_called()

    def test_failed_original_publishes_no_partial_export_bindings(self):
        output={}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'control-close-captures').mkdir()
            with patch.object(native.publication,'validate',side_effect=ValueError('invalid physical original')),\
                 self.assertRaisesRegex(ValueError,'invalid physical original'):
                native.validate(tmp,'5-REPLACE-required-four',complete_exports=True,export_bindings_out=output)
        self.assertEqual({},output)


if __name__=='__main__':unittest.main()
