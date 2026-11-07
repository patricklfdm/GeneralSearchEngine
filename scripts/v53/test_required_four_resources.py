"""Entry ordering and exact family checks; synthetic summaries are not evidence."""
import copy
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import required_four_resources as m
from .test_required_four_resource_run import replay
from .test_export_allocation_coverage import fixture as exports_fixture,bind as bind_exports


class RequiredFourResourcesTest(unittest.TestCase):
    def setup_gate(self,stack,events=None,progress=None):
        expected_progress=progress
        order=[];original=replay()['original'];exports_data=exports_fixture('joining-intent',True);bindings=bind_exports(exports_data)
        original['exportAllocationCoverage']=m.exports.r.replay(*exports_data[:2],bindings)
        data=({'owners':[{'identity':{'node':'n'}}],'root':'root'},exports_data[0],[],events or [])
        inventory=stack.enter_context(patch.object(m.native.collection,'inventory',return_value={'immutable':'original'}))
        def validation(*args,**kwargs):
            order.append('original');self.assertEqual(kwargs,{'joined_files':True,'joined_closes':True,'complete_exports':True,'activation_control':True,'export_bindings_out':{}})
            self.assertEqual(args[1],m.PROFILE);kwargs['export_bindings_out'].update(copy.deepcopy(bindings));return original
        validate=stack.enter_context(patch.object(m.native,'validate',side_effect=validation))
        stack.enter_context(patch.object(m.native,'load',return_value=data))
        stack.enter_context(patch.object(m.control_close_evidence,'load',return_value=exports_data[1]))
        stack.enter_context(patch.object(m.handoff.r,'original',return_value=SimpleNamespace(owner=object())))
        stack.enter_context(patch.object(m.handoff.r,'project',return_value={'from':'original','node':'n'}))
        stack.enter_context(patch.object(m.files.maintenance,'Replay'))
        stack.enter_context(patch.object(m.files.r,'derive',return_value={'from':'original','node':'n'}))
        stack.enter_context(patch.object(m.files.r.transfers,'load',return_value={}))
        stack.enter_context(patch.object(m.native.collection,'read_json',return_value=[]))
        stack.enter_context(patch.object(m.slot.r,'required_four_publications',return_value={'derived':'original'}))
        stack.enter_context(patch.object(m.native.publication,'collect',return_value=[]))
        for family,module in [('accounting',m.accounting),('handoff',m.handoff),('files',m.files),('network-close',m.network_close),('joining-close',m.joining_close),('export-allocations',m.exports)]:
            def negative(*args,family=family,**kwargs):
                self.assertEqual('original',order[0]);order.append(family);return replay()['negatives'][family]
            stack.enter_context(patch.object(module,'replay',side_effect=negative))
        for family,module,key in [('voting-control',m.voting,'votingControlResources'),('slot-control',m.slot,'slotControlResources'),
                                  ('activation-control',m.activation,'activationControlResources')]:
            def negative(data,progress=None,*,family=family,key=key):
                self.assertIs(expected_progress,progress)
                self.assertEqual('original',order[0]);order.append(family)
                self.assertEqual(data[:6],(data[0],[],exports_data[0],[],{'n':{'node':'n'}},'root'))
                if family!='voting-control':self.assertEqual(data[6:],({'derived':'original'},[]))
                return dict(original=original[key],negatives=replay()['negatives'][family])
            stack.enter_context(patch.object(module,'replay',side_effect=negative))
        return order,inventory,validate,original

    def test_one_complete_original_then_all_147_negatives(self):
        updates=[];progress=updates.append
        with ExitStack() as stack:
            order,inventory,validate,_=self.setup_gate(stack,progress=progress);result=m.qualify('/synthetic',progress)
        self.assertEqual(['original',*m.NEGATIVES],order);self.assertEqual(1,validate.call_count)
        self.assertEqual(2,inventory.call_count);self.assertEqual(147,sum(map(len,result['negatives'].values())))
        m.check_result(result);self.assertFalse(result['combinedResourcesQualified']);self.assertFalse(result['phase3Complete'])

    def test_invalid_original_stops_before_loading_or_counting_mutations(self):
        with patch.object(m.native.collection,'inventory',return_value={}),\
             patch.object(m.native,'validate',side_effect=ValueError('bad physical original')),\
             patch.object(m.native,'load') as load,patch.object(m.accounting,'replay') as negatives,\
             self.assertRaisesRegex(ValueError,'bad physical original'):m.qualify('/synthetic')
        load.assert_not_called();negatives.assert_not_called()

    def test_scope_and_required_original_bindings_cannot_be_missing_or_partial(self):
        for label in ('status','profile','accounting','handoff','files','network-close','joining-close','cleanup','exports',
                      'votingControlResources','slotControlResources','activationControlResources','overclaim'):
            with ExitStack() as stack:
                order,_,_,original=self.setup_gate(stack)
                if label=='status':original['status']='PARTIAL'
                elif label=='profile':original['profile']='5-REPLACE'
                elif label=='accounting':original['nativeBudgetAccountingQualified']=False
                elif label=='handoff':original['joinedHandoffResources']['continuousHandoffQualified']=False
                elif label=='files':original.pop('joinedFileResources')
                elif label=='network-close':original.pop('ownerCloseResources')
                elif label=='joining-close':original.pop('joinedOwnerCloses')
                elif label=='cleanup':original.pop('sourceCleanupIntervals')
                elif label=='exports':original.pop('exportAllocationCoverage')
                elif label.endswith('ControlResources'):original.pop(label)
                else:original['wholeRuntimeResourcesQualified']=True
                with self.subTest(label=label),self.assertRaisesRegex(ValueError,'complete original'):m.qualify('/synthetic')
                self.assertEqual(['original'],order)

    def test_historical_six_family_receipt_cannot_claim_new_control_coverage(self):
        value=replay();value['schema']='gse-v53-required-four-resources-v1'
        for family in ('voting-control','slot-control','activation-control'):value['negatives'].pop(family)
        with self.assertRaisesRegex(ValueError,'qualification scope'):m.check_result(value)

    def test_negative_control_original_must_equal_full_original(self):
        for module in (m.voting,m.slot,m.activation):
            with ExitStack() as stack:
                self.setup_gate(stack)
                stack.enter_context(patch.object(module,'replay',return_value={'original':{'status':'PASS'},'negatives':[]}))
                with self.assertRaisesRegex(ValueError,'original control binding output'):m.qualify('/synthetic')

    def test_original_must_still_be_unchanged_after_all_mutations(self):
        with ExitStack() as stack:
            _,inventory,_,_=self.setup_gate(stack);inventory.side_effect=[{'before':1},{'after':2}]
            with self.assertRaisesRegex(ValueError,'original changed'):m.qualify('/synthetic')

    def test_export_binding_output_is_replayed_before_any_negative_not_trusted_from_summary(self):
        for corrupt in ('missing','altered','summary'):
            with ExitStack() as stack:
                order,_,validate,original=self.setup_gate(stack);good=validate.side_effect
                def bad(*args,**kwargs):
                    result=good(*args,**kwargs);bindings=kwargs['export_bindings_out']
                    if corrupt=='missing':bindings.clear()
                    elif corrupt=='altered':next(iter(bindings.values()))['bytes']+=1
                    else:result['exportAllocationCoverage']['allocationBindingsSha256']='f'*64
                    return result
                validate.side_effect=bad
                with self.subTest(corrupt=corrupt),self.assertRaises(ValueError):m.qualify('/synthetic')
                self.assertEqual(['original'],order)

    def test_all_export_scopes_and_limited_claims_are_required(self):
        for field,value in [('byScope',dict(session=3)),('allocations',True),('allocations',4),
                            ('unclaimedAllocations',['missing']),('wholeRuntimeResourcesQualified',True),
                            ('failedConstructorExportsQualified',True),('allExportFailurePathsQualified',True)]:
            original=replay()['original'];original['exportAllocationCoverage'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'complete original export scope'):m.check_original(original)

    def test_each_family_exact_names_order_status_and_reason(self):
        for family in m.NEGATIVES:
            for mutation in ('missing-family','missing-row','duplicated','reordered','reason','status'):
                value=replay();rows=value['negatives'][family]
                if mutation=='missing-family':del value['negatives'][family]
                elif mutation=='missing-row':rows.pop()
                elif mutation=='duplicated':rows.append(copy.deepcopy(rows[0]))
                elif mutation=='reordered':rows.reverse()
                else:rows[0][mutation]='different'
                with self.subTest(family=family,mutation=mutation),self.assertRaisesRegex(ValueError,'exact negative families'):m.check_result(value)

    def test_no_acceptance_from_counts_or_broader_claims(self):
        for key in ('originalFirst','originalPreserved','combinedResourcesQualified','phase3Complete'):
            value=replay();value[key]=not value[key]
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'qualification scope'):m.check_result(value)
        value=replay();value['negativeCount']=47
        with self.assertRaisesRegex(ValueError,'qualification scope'):m.check_result(value)


if __name__=='__main__':unittest.main()
