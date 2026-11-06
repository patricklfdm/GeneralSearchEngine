"""Short binding guards; mocked prerequisites never qualify a native history."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_storage_coverage as p
from . import test_native_carried_storage_coverage as ownership_fixture
from . import test_storage_coverage_binding as binding_fixture


class NativeCarriedApplicationStorageCoverageTest(unittest.TestCase):
    def targets(self):
        value=ownership_fixture.NativeStorageOwnershipQualificationTest().targets()
        charges=value['owners'][0]['snapshots'][0]['required']
        charges[:]=[v for v in charges if v['owner']!='application-replay-input']
        return value

    def test_complete_original_capture_chain_precedes_every_resource_claim(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p.prerequisite,'validate',side_effect=ValueError('invalid original')),\
             patch.object(p,'plans') as plans,patch.object(p.shared,'project') as project:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.validate(temp)
            plans.assert_not_called();project.assert_not_called()

    def test_only_original_maintenance_inventory_earns_partial_binding(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p.prerequisite,'validate',return_value={'maintenance':{'capturedPrefixes':7}}),\
             patch.object(p,'plans',return_value=['original rows']),\
             patch.object(p.shared,'project',return_value={'expectedCallbacks':7}) as project:
            result=p.validate(temp)
            project.assert_called_once_with(Path(temp)/'previous/previous/observed',['original rows'],families=p.FAMILIES)
            self.assertTrue(result['capturedCallbackBytesQualified'])
            self.assertEqual('application-maintenance-three-families',result['captureScope'])
            for field in ('allSevenFamiliesCaptured','applicationAndRetirementChargeBindingQualified',
                          'wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):self.assertFalse(result[field])

    def test_missing_capture_count_or_changed_original_cannot_pass(self):
        for counts,drift,reason in ((6,False,'original capture count'),(7,True,'original changed')):
            with tempfile.TemporaryDirectory() as temp,patch.object(p.prerequisite,'validate',return_value={'maintenance':{'capturedPrefixes':7}}),\
                 patch.object(p,'plans',return_value=[]),patch.object(p.shared,'project',return_value={'expectedCallbacks':counts}),\
                 patch.object(p.collection,'inventory',side_effect=[{}, {'changed':True} if drift else {}]):
                with self.assertRaisesRegex(ValueError,reason):p.validate(temp)

    def test_plan_union_requires_all_families_and_preserves_index_order(self):
        parts={key:[dict(life=2,eventIndex=at),dict(life=1,eventIndex=at)] for at,key in enumerate(p.prerequisite.FAMILIES)}
        with patch.object(p.prerequisite,'plans',return_value=parts):
            rows=p.plans('original');self.assertEqual([(1,0),(1,1),(1,2),(2,0),(2,1),(2,2)],[(v['life'],v['eventIndex']) for v in rows])
        parts.pop('floors')
        with patch.object(p.prerequisite,'plans',return_value=parts),self.assertRaisesRegex(ValueError,'complete maintenance plans'):p.plans('original')

    def test_partial_case_scope_does_not_weaken_the_default_full_gate(self):
        projected=self.targets()
        self.assertEqual(p.OWNER_CASES,set(p.shared.ownership_targets(projected,families=p.FAMILIES)))
        with self.assertRaisesRegex(ValueError,'complete original owner cases'):p.shared.ownership_targets(projected)
        full=ownership_fixture.NativeStorageOwnershipQualificationTest().targets()
        self.assertEqual(p.shared.OWNER_CASES,set(p.shared.ownership_targets(full)))
        with self.assertRaisesRegex(ValueError,'complete original owner cases'):p.shared.ownership_targets(full,families=p.FAMILIES)
        with self.assertRaisesRegex(ValueError,'supported family scope'):p.shared.ownership_targets(projected,families='unknown')

    def test_each_partial_owner_case_still_requires_an_actual_physical_witness(self):
        for at in range(len(p.OWNER_CASES)):
            projected=self.targets();projected['owners'][0]['snapshots'][0]['required'].pop(at)
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'complete original owner cases'):
                p.shared.ownership_targets(projected,families=p.FAMILIES)

    def test_maintenance_callback_union_includes_original_local_pins(self):
        events=[dict(node='node-1',event=point) for point in
                ('FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED')]
        rows=[dict(life=2,eventIndex=i) for i in range(len(events))]
        p.shared.complete_callbacks(rows,events,2,families=p.FAMILIES)
        for changed in (rows[:-1],[*rows,rows[0]]):
            with self.assertRaisesRegex(ValueError,'complete family callbacks'):p.shared.complete_callbacks(changed,events,2,families=p.FAMILIES)

    def test_failed_original_cannot_earn_balanced_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'validate',side_effect=ValueError('invalid original')),\
             patch.object(p.shared,'ownership_targets') as targets,patch.object(p.shared,'rename_owner') as mutate:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify(temp)
            targets.assert_not_called();mutate.assert_not_called()

    def negative_fixture(self):
        rows,trace,events,bounds=binding_fixture.StorageCoverageBindingTest().fixture()
        projected={'owners':[p.shared.coverage.bind(rows,trace,events,bounds,'node-1',2,closed=True,
                                                   ordinals=p.shared.coverage.ordinal_plans(rows))]}
        targets={name:dict(life=2,node='node-1',unit=name,owner=owner,eventIndex=0,point='POINT_A')
                 for name,owner in (('MISC','current-authority'),('JOURNAL','membership-grants'))}
        return rows,trace,events,bounds,projected,targets

    def test_balanced_owner_mutations_reject_with_real_trace_replay(self):
        rows,trace,events,bounds,projected,targets=self.negative_fixture();before=copy.deepcopy(trace)
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'validate',return_value={'coverage':projected}),\
             patch.object(p,'plans',return_value=rows),patch.object(p.shared,'ownership_targets',return_value=targets) as choose,\
             patch.object(p.shared.resource,'read',side_effect=lambda _,name,*args:events if name=='events.json' else bounds),\
             patch.object(p.shared.coverage.t,'read',return_value=(b'',trace)):
            result=p.qualify(temp)
        choose.assert_called_once_with(projected,families=p.FAMILIES)
        self.assertEqual(sorted(targets),[v['case'] for v in result['negatives']])
        self.assertTrue(all(v['balancedOriginalTotals'] and v['reason']=='storage coverage original charge owner' for v in result['negatives']))
        self.assertEqual(before,trace);self.assertTrue(result['originalStorageUnchanged'])

    def test_unrelated_or_accepted_negative_gets_no_credit(self):
        rows,trace,events,bounds,projected,targets=self.negative_fixture()
        for error,reason in ((ValueError('unrelated'),'unrelated negative'),(None,'accepted unrelated owner')):
            with tempfile.TemporaryDirectory() as temp,patch.object(p,'validate',return_value={'coverage':projected}),\
                 patch.object(p,'plans',return_value=rows),patch.object(p.shared,'ownership_targets',return_value=targets),\
                 patch.object(p.shared.resource,'read',side_effect=lambda _,name,*args:events if name=='events.json' else bounds),\
                 patch.object(p.shared.coverage.t,'read',return_value=(b'',trace)),patch.object(p.shared.coverage,'bind',side_effect=error):
                with self.assertRaisesRegex(ValueError,reason):p.qualify(temp)

    def test_extended_plans_bind_original_application_lifetime_without_mutating_input(self):
        first=[dict(eventIndex=8,node='node-1',point='APPLY_ACK_DIRECTORY_FORCED',files={})]
        old=[dict(life=2,eventIndex=9,node='node-1',point='STAGED_RETIREMENT_BEFORE_RETURN',files={})]
        with patch.object(p.prerequisite,'plans',return_value={key:[key] for key in p.prerequisite.FAMILIES}),\
             patch.object(p.prerequisite.prerequisite.prerequisite,'plans',return_value=first) as interrupted,\
             patch.object(p.prerequisite.prerequisite,'plans',return_value=old) as retired:
            parts=p.application_plans('/original')
        self.assertEqual(1,parts['application'][0]['life']);self.assertNotIn('life',first[0]);self.assertEqual(old,parts['old-end'])
        interrupted.assert_called_once_with('/original');retired.assert_called_once_with('/original')
        with patch.object(p.prerequisite,'plans',return_value={key:[key] for key in p.prerequisite.FAMILIES}),\
             patch.object(p.prerequisite.prerequisite.prerequisite,'plans',return_value=[]),\
             patch.object(p.prerequisite.prerequisite,'plans',return_value=old),self.assertRaisesRegex(ValueError,'nonempty captured families'):
            p.application_plans('/original')

    def test_extended_projection_rejects_missing_family_swapped_counts_and_shared_callback(self):
        names=[*p.prerequisite.FAMILIES,'application','old-end']
        parts={key:[dict(life=2,node='node-1',eventIndex=i,point='POINT',files={'root.gsr':{'bytes':1,'sha256':'a'*64}})] for i,key in enumerate(names)}
        original={'maintenance':{'families':{key:{'capturedPrefixes':1} for key in p.prerequisite.FAMILIES}},
                  'original':{'original':{'application':{'capturedPrefixes':1}},'retirement':{'lifetime':{'capturedPrefixes':1}}}}
        for case,reason in (('missing','exact five families'),('counts','exact family capture counts'),('duplicate','ordered unique callbacks')):
            changed=copy.deepcopy(parts)
            if case=='missing':changed.pop('application')
            elif case=='counts':changed['old-end'].extend(changed.pop('application'));changed['application']=[]
            else:changed['application'][0]['eventIndex']=changed['old-end'][0]['eventIndex']
            with self.subTest(case=case),patch.object(p.shared.resource,'read') as read,self.assertRaisesRegex(ValueError,reason):
                p.captured_projection('/original',changed,original)
            read.assert_not_called()

    def test_extended_entry_keeps_five_captures_distinct_from_full_seven_and_runtime(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p.prerequisite,'validate',return_value={'original':True}),\
             patch.object(p,'application_plans',return_value={'five':'families'}),\
             patch.object(p,'captured_projection',return_value={'expectedCallbacks':2217}) as project,\
             patch.object(p.shared,'project') as maintenance:
            result=p.validate(temp,include_application=True)
        project.assert_called_once_with(Path(temp)/'previous/previous/observed',{'five':'families'},{'original':True})
        maintenance.assert_not_called();self.assertTrue(result['applicationAndRetirementChargeBindingQualified'])
        self.assertEqual('application-five-captured-families',result['captureScope'])
        for field in ('allSevenFamiliesCaptured','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):self.assertFalse(result[field])

    def test_extended_original_failure_never_reaches_any_projection(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(p.prerequisite,'validate',side_effect=ValueError('invalid five-family original')),\
             patch.object(p,'application_plans') as plans,patch.object(p,'captured_projection') as project:
            with self.assertRaisesRegex(ValueError,'invalid five-family original'):p.qualify(temp,include_application=True)
        plans.assert_not_called();project.assert_not_called()

    def test_extended_qualification_uses_complete_owner_vocabulary_and_real_balanced_replay(self):
        rows,trace,events,bounds,projected,targets=self.negative_fixture()
        with tempfile.TemporaryDirectory() as temp,patch.object(p,'validate',return_value={'coverage':projected}) as original,\
             patch.object(p,'application_plans',return_value={'synthetic':rows}),\
             patch.object(p.shared,'ownership_targets',return_value=targets) as choose,\
             patch.object(p.shared.resource,'read',side_effect=lambda _,name,*args:events if name=='events.json' else bounds),\
             patch.object(p.shared.coverage.t,'read',return_value=(b'',trace)):
            result=p.qualify(temp,include_application=True)
        original.assert_called_once_with(Path(temp),include_application=True)
        choose.assert_called_once_with(projected)
        self.assertEqual(sorted(targets),[v['case'] for v in result['negatives']])
        self.assertTrue(all(v['balancedOriginalTotals'] for v in result['negatives']))


if __name__=='__main__':unittest.main()
