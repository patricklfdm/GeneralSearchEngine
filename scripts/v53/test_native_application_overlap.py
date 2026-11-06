"""Synthetic selection/admission guards; no native execution is claimed here."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_application_overlap as m
from .test_replica_storage_coverage import file,charge,row,D,A,UUID
from . import test_storage_coverage_binding as binding

LIMITS=(384*m.t.MIB,512*m.t.MIB,64*m.t.MIB)
CASE='final-application-kill'


def fixture():
    files={'generations':D,'sources':D,'floor-copies':D,'retirement':D,'retirement/images.json':file(3)}
    ordinals={}
    for name in ('a','b'):
        prefix='generations/'+name;files.update({prefix:D,prefix+'/generation.gsr':file(4),prefix+'/'+A+'.image':file(11)})
    for name in (UUID,'22222222-3333-4444-5555-666666666666'):
        prefix='sources/'+name;files.update({prefix:D,prefix+'/source.gscp':file(5),prefix+'/'+A+'.image':file(11)})
    for name in ('b'*64,'c'*64,'d'*64):
        prefix='floor-copies/'+name;files.update({prefix:D,prefix+'/generation.gsr':file(6),prefix+'/'+A+'.image':file(11)})
        ordinals[prefix]=[A+'.image']
    state={k:charge(*k,1024) for k in set(m.storage.coverage.owners(files,ordinals).values())}
    state['CONTROL','waiting']=charge('CONTROL','waiting',4096)
    return files,state,ordinals


def observation(files=None,state=None,ordinals=None,*,life=1,node='node-1',at=0):
    if files is None:files,state,ordinals=fixture()
    r=dict(row(at,'TEST_CAPTURE',files,node,life),ordinals=ordinals)
    snapshot=dict(life=life,node=node,eventIndex=at,point=r['point'],sequence=10,
                  usage=m.t.usage(state,LIMITS),**m.storage.coverage.compare(files,state,ordinals))
    return r,snapshot,state


def point(**kwargs):
    r,s,state=observation(**kwargs);return m.point(r,s,state,LIMITS,'e'*64)


class ApplicationOverlapTest(unittest.TestCase):
    def test_same_callback_counts_all_identical_image_copies(self):
        r,s,state=observation();p=m.point(r,s,state,LIMITS,'e'*64)
        self.assertEqual(7,p['nonemptyPhysicalOwnerCounts']['APPLICATION'])
        self.assertEqual(77,p['physicalApplicationBytes'])
        self.assertEqual(6,p['nonemptyPhysicalOwnerCounts']['SOURCE'])
        self.assertEqual(2,p['nonemptyPhysicalOwnerCounts']['GENERATION'])
        self.assertEqual(36*m.t.MIB,p['unspentProtectedHeadroomBytes'])
        self.assertGreater(p['reservedMetadataBytes'],p['physicalMetadataBytes'])
        self.assertEqual(1,p['unboundReservationCount'])
        result=m.summarize([p]);self.assertEqual(1,result['simultaneousSaturatedCallbacks'])
        self.assertTrue(all(result[k] is False for k in m.FALSES))

    def test_zero_length_member_and_empty_directory_are_not_nonempty_sources(self):
        for empty in ('file','directory','absent'):
            files,state,ordinals=fixture()
            del files['retirement/images.json']
            if empty=='file':files['retirement/images.json']=file(0)
            if empty=='directory':files['retirement/source']=D
            p=point(files=files,state=state,ordinals=ordinals)
            with self.subTest(empty=empty):
                self.assertEqual(6,p['chargedCounts']['SOURCE'])
                self.assertEqual(5,p['nonemptyPhysicalOwnerCounts']['SOURCE'])
                self.assertFalse(m.summarize([p])['simultaneousCountsObserved'])

    def test_no_saturation_from_different_callbacks_owners_or_lifetimes(self):
        for location in (dict(at=1),dict(node='node-2'),dict(life=2)):
            first=point();first['nonemptyPhysicalOwnerCounts']['SOURCE']=5
            second=point(**location);second['nonemptyPhysicalOwnerCounts']['APPLICATION']=6
            with self.subTest(location=location):
                value=m.summarize([first,second]);self.assertFalse(value['simultaneousCountsObserved'])
                self.assertEqual(0,value['simultaneousSaturatedCallbacks'])

    def test_peak_carries_the_entire_original_point_and_first_tie(self):
        first=point();second=point(life=2)
        first.update(physicalMetadataBytes=120,physicalApplicationBytes=10,physicalBytes=130)
        second.update(physicalMetadataBytes=20,physicalApplicationBytes=140,physicalBytes=160)
        value=m.summarize([first,second]);peaks=value['peaks']
        self.assertEqual(first,peaks['physicalMetadataBytes'])
        self.assertEqual(second,peaks['physicalApplicationBytes'])
        self.assertEqual(second,peaks['physicalBytes'])
        self.assertEqual(first,peaks['reservedMetadataBytes'])
        self.assertEqual(160,peaks['physicalBytes']['physicalBytes'])
        self.assertEqual(1,value['ownerLifetimes'][4]['simultaneousSaturatedCallbacks'])
        self.assertEqual(0,value['ownerLifetimes'][1]['callbacks'])
        self.assertIsNone(value['ownerLifetimes'][1]['firstSimultaneousSaturation'])

    def test_witnesses_have_independent_mutation_storage(self):
        p=point();value=m.summarize([p]);before=copy.deepcopy(value)
        value['peaks']['physicalBytes']['physicalBytes']+=1
        self.assertEqual(before['ownerLifetimes'],value['ownerLifetimes'])
        self.assertEqual(before['peaks']['physicalMetadataBytes'],value['peaks']['physicalMetadataBytes'])
        self.assertEqual(before['peaks']['physicalMetadataBytes'],p)
        value['requiredSimultaneousCounts']['SOURCE']=99
        self.assertEqual(6,m.COUNTS['SOURCE'])

    def test_each_derived_witness_attack_has_exact_rejection(self):
        expected=m.summarize([point()])
        for name,reason in m.NEGATIVES.items():
            changed=copy.deepcopy(expected);m.mutate(changed,name)
            with self.subTest(name=name),self.assertRaises(ValueError) as caught:m.check_claim(changed,expected)
            self.assertEqual(reason,str(caught.exception))

    def test_inventory_and_original_charge_binding_cannot_be_replaced(self):
        for alteration in ('inventory','owner','usage','snapshot'):
            r,s,state=observation()
            if alteration=='inventory':r['files']['retirement/images.json']['bytes']+=1
            elif alteration=='owner':state.pop(('SOURCE','retirement'))
            elif alteration=='usage':s['usage']['metadata']+=1
            else:s['physicalBytes']+=1
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):m.point(r,s,state,LIMITS,'e'*64)

    def test_exact_callback_identity_not_boolean_or_foreign_owner(self):
        for key,value in (('life',True),('life',2),('node','node-2'),('eventIndex',False),('point','OTHER'),('sequence',True)):
            r,s,state=observation();s[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):m.point(r,s,state,LIMITS,'e'*64)

    def test_missing_duplicate_and_reordered_points_reject(self):
        a=point();b=point(at=1)
        for points in ([],[a,a],[b,a]):
            with self.subTest(points=len(points)),self.assertRaises(ValueError):m.summarize(points)


class OriginalAdmissionTest(unittest.TestCase):
    def test_failed_original_prevents_derivation_and_negatives(self):
        with patch.object(m.admission,'collect',return_value={'inventory':[]}),\
             patch.object(m.admission.transients,'validate',side_effect=ValueError('original failed')),\
             patch.object(m,'derive') as derive,patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original failed$'):m.qualify(Path('/synthetic'),CASE)
        derive.assert_not_called();mutate.assert_not_called()

    def test_scope_check_precedes_selection(self):
        with patch.object(m.admission,'collect',return_value={'inventory':[]}),\
             patch.object(m.admission.transients,'validate',return_value={}),\
             patch.object(m.admission,'check_original',side_effect=ValueError('wrong case')),patch.object(m,'derive') as derive:
            with self.assertRaisesRegex(ValueError,'^wrong case$'):m.validate(Path('/synthetic'),CASE)
        derive.assert_not_called()

    def test_original_must_be_unchanged_after_selection(self):
        with patch.object(m.admission,'collect',side_effect=[{'inventory':[]},{'inventory':[1]}]),\
             patch.object(m.admission.transients,'validate',return_value={}),\
             patch.object(m.admission,'check_original'),patch.object(m,'derive',return_value=m.summarize([point()])):
            with self.assertRaisesRegex(ValueError,'^overlap original changed$'):m.validate(Path('/synthetic'),CASE)

    def test_no_observed_saturation_cannot_credit_negative_qualification(self):
        p=point();p['nonemptyPhysicalOwnerCounts']['SOURCE']=5
        with patch.object(m.admission,'collect',return_value={'inventory':[]}),\
             patch.object(m,'validate',return_value={'overlap':m.summarize([p])}),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'require observed saturation'):m.qualify(Path('/synthetic'),CASE)
        mutate.assert_not_called()

    def test_exact_checkpoint_reconstruction_uses_original_trace(self):
        values=binding.StorageCoverageBindingTest().fixture();rows,trace,events,bounds=values
        covered=binding.StorageCoverageBindingTest().run_binding(values)
        original={'coverage':{'callbacks':2,'owners':[
            dict(life=life,node='node-'+str(n),snapshots=covered['snapshots'] if (life,n)==(2,1) else [])
            for life in (1,2) for n in range(1,5)]}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.admission.transients.model,'plans',return_value=({},None)))
            stack.enter_context(patch.object(m.admission.transients.prerequisite,'application_plans',return_value={}))
            stack.enter_context(patch.object(m.admission.transients,'combine',return_value=(rows,None)))
            stack.enter_context(patch.object(m.t,'read',return_value=(b'original trace',trace)))
            result=m.derive(Path('/synthetic'),original)
            self.assertEqual(2,result['callbacks'])
            self.assertEqual(20,result['peaks']['physicalBytes']['physicalBytes'])
            self.assertEqual(m.h.digest(b'original trace'),result['peaks']['physicalBytes']['resourceTraceSha256'])
            original['coverage']['owners'][4]['snapshots'][0]['sequence']=3
            with self.assertRaisesRegex(ValueError,'original charge owner'):m.derive(Path('/synthetic'),original)

    def test_cli_failure_is_retained_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'out'
            with patch.object(m,'qualify',side_effect=ValueError('broken original')):
                with self.assertRaisesRegex(ValueError,'broken original'):m.run('/synthetic',CASE,output)
            receipt=m.h.snapshot.f.canonical({'failure':{'type':'ValueError','message':'broken original'},'phase3Complete':False,'status':'FAIL'})
            self.assertEqual(json.loads(receipt),json.loads((output/'receipt.json').read_text()))
            with self.assertRaises(FileExistsError):m.run('/synthetic',CASE,output)


if __name__=='__main__':unittest.main()
