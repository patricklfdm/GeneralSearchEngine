"""Compact accounting fixtures; native authority is tested by original replay."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_learner_resources as n
from . import resource_transitions as t
from .test_resource_transitions import trace


def observations():
    state={};changes=[];bounds=[];events={k:[] for k in ('initial','cancel','resume')};expected={};usages={}
    limits=(384*t.MIB,512*t.MIB,64*t.MIB)
    def change(event,removed=(),added=()):
        for v in removed:del state[t.key(v)]
        for v in added:state[t.key(v)]=v
        changes.append(dict(event=event,removed=sorted(copy.deepcopy(removed),key=t.order_key),
            added=sorted(copy.deepcopy(added),key=t.order_key),usage=t.usage(state,limits)))
    def mark(kind,name,point=''):
        bounds.append(dict(ordinal=len(bounds),kind=kind,name=name,point=point,sequence=len(changes)-1,usage=t.usage(state,limits)))
        if kind=='CALLBACK':events[name].append(point)
    def snapshot(name):
        mark('SNAPSHOT',name);expected[name]=copy.deepcopy(state);usages[name]=t.usage(state,limits)
    misc=n.charge('MISC','learner-plan',2*t.MIB);typed=n.charge('APPLICATION','learner-typed-backup',64*t.MIB)
    gen=n.charge('GENERATION','learner-prepared:'+'a'*64,10)
    change('START');mark('POOL','start')
    for phase,source,image,terminal,terminal_image in (
        ('initial','original-capsule','original-image','cancel-capsule','cancel-image'),
        ('resume','learner-store','learner-store:abc.image','learner-cancellation','cancel:abc.image')):
        first=n.charge('LEARNER',source,10);app=n.charge('APPLICATION',image,4)
        for v in (misc,first,app,typed):change('RESERVE',added=[v])
        claim=dict(gen,bytes=0,claimSource=source);change('GENERATION_CLAIM',added=[claim])
        mark('CALLBACK',phase,'LEARNER_PREPARED_BEFORE_SELECT')
        change('GENERATION_COMMIT',removed=[first,claim],added=[gen]);mark('CALLBACK',phase,'LEARNER_PREPARED_BEFORE_RETURN')
        if phase=='initial':snapshot(n.STAGES[0])
        end=n.charge('LEARNER',terminal,20);endapp=n.charge('APPLICATION',terminal_image,5)
        for v in (end,endapp):change('RESERVE',added=[v])
        mark('CALLBACK','cancel' if phase=='initial' else 'resume','LEARNER_CANCEL_ACTIVE_PLAN_FORCED')
        # A neutral original observation separates adoption from close.
        change('STORAGE_GROW',removed=[end],added=[end])
        mark('CALLBACK','cancel' if phase=='initial' else 'resume','LEARNER_CANCEL_BEFORE_RETURN')
        snapshot(n.STAGES[1] if phase=='initial' else n.STAGES[3])
        for label,released in [('cancel',[endapp,end]),('typed',[]),('store',[typed,app,gen,misc])]:
            mark('CLOSE_BEGIN',phase+'-'+label)
            for v in released:change('RELEASE',removed=[v])
            mark('CLOSE_RETURN',phase+'-'+label)
        snapshot(n.STAGES[2] if phase=='initial' else n.STAGES[4])
    return trace(changes),bounds,expected,usages,events,dict(initial='original-capsule',resume='learner-store')


class NativeLearnerResourcesTest(unittest.TestCase):
    def test_lifetimes_are_bound_to_exact_original_owners_and_handoffs(self):
        value=observations();saved=copy.deepcopy(value);result=n.bind(*value)
        self.assertEqual(6,result['closeIntervals']);self.assertEqual(2,len(result['generationSelections']))
        self.assertTrue(result['continuousOwnershipQualified']);self.assertEqual(saved,value)
        for key in ('wholeRuntimeResourcesQualified','transientPhysicalBytesQualified','phase3Complete'):self.assertIs(False,result[key])

    def test_all_resource_negatives_require_the_specific_expected_reason(self):
        for name,reason in n.NEGATIVES.items():
            with self.subTest(name=name):
                value=observations();n.mutate(value,name)
                with self.assertRaises(ValueError) as failure:n.bind(*value)
                self.assertEqual(reason,str(failure.exception))

    def test_release_reacquire_cannot_hide_behind_equal_stage_totals(self):
        value=observations();n.mutate(value,'release-reacquire-gap');t.replay(value[0])
        replay=n.states(value[0])
        for row in value[1]:
            if row['kind']=='SNAPSHOT':self.assertEqual(value[2][row['name']],replay[row['sequence']])
        with self.assertRaisesRegex(ValueError,'continuous original ownership'):n.bind(*value)

    def test_renamed_initial_claim_is_valid_accounting_but_foreign_authority(self):
        value=observations();n.mutate(value,'foreign-generation-source');t.replay(value[0])
        with self.assertRaisesRegex(ValueError,'original generation claim'):n.bind(*value)

    def test_invalid_original_stops_before_resource_or_negative_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'original').mkdir();(root/'resources').mkdir()
            with patch.object(n.c,'validate',side_effect=ValueError('invalid original')),patch.object(n,'derive') as derived,patch.object(n,'mutate') as mutated:
                with self.assertRaisesRegex(ValueError,'invalid original'):n.qualify(root)
                derived.assert_not_called();mutated.assert_not_called()

    def test_failed_or_unrelated_negative_cannot_count_as_rejected(self):
        for error in (None,ValueError('unrelated')):
            with self.subTest(error=error),patch.object(n,'bind',side_effect=error):
                with self.assertRaisesRegex(ValueError,'learner resources (accepted|unrelated) negative'):
                    n.rejected(lambda:n.bind(),'expected','case')

    def test_current_retention_does_not_bypass_original_learner_ledgers(self):
        with patch.object(n.c,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'requires original learner ledgers'):n.c.validate('/missing',current_retention=True)
            inventory.assert_not_called()

    def test_boundary_types_and_order_are_strict(self):
        for field,value in (('sequence',True),('ordinal',False),('sequence',-1),('name',[])):
            changed=observations();changed[1][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'exact boundary'):n.bind(*changed)

    def test_current_failure_bound_is_per_original_request_as_well_as_total(self):
        row=dict(node='node-3',kind='FUTURE_RETENTION_INTENT',request='a'*64,
            failure='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required')
        with patch.object(n.c.d,'read',return_value=[row]*4):
            with self.assertRaisesRegex(ValueError,'unexpected native failure'):
                n.c.native_failures(Path('/unused'),retained_learners=True,current_retention=True)


if __name__=='__main__':unittest.main()
