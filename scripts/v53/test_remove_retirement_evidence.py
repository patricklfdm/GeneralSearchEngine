"""Capacity-derived retirement, both generation slots and rejection boundaries."""
from contextlib import ExitStack
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from . import remove_retirement_evidence as r
from . import test_retirement_evidence as retirement_fixture
from . import test_joining_retirement_replay as source_fixture


class RemoveRetirementEvidenceTest(unittest.TestCase):
    def source_ballots(self, *, proposer=None, incarnation=None, counter=None):
        files,identifier,current,coverage,old_basis,_=source_fixture.JoiningRetirementReplayTest().decision_inputs()
        old=r.f.decode(old_basis,'records','BASIS')['ballot']
        rows=r.c.journal(files['grants.gsr'],current[2]['capsule']['root'],'node-1')
        fresh=dict(old,**({'proposer':proposer} if proposer else {}),
                   **({'incarnation':incarnation} if incarnation else {}),
                   **({'counter':counter} if counter is not None else {}))
        replacement=[r.f.encode('records',kind,dict(value,ballot=fresh)) for kind,_,value in rows[-2:]]
        files['grants.gsr']=b''.join(raw for _,raw,_ in rows[:-2])+b''.join(replacement)
        current=(current[0],dict(current[1],**{'promise.gsr':replacement[0],'basis.gsr':replacement[1]}),current[2])
        with patch.object(r.c,'current',return_value=current):
            after,decisions=r.source_plans(files,'node-1',coverage)
        return files,after,decisions,identifier,replacement

    def test_same_counter_higher_proposer_can_retire_the_superseded_source(self):
        before,after,decisions,identifier,kept=self.source_ballots(proposer='node-3')
        self.assertEqual([identifier],[v['identifier'] for v in decisions])
        self.assertNotIn('sources/'+identifier,after);self.assertIn('sources/'+identifier,before)
        self.assertEqual(b''.join(kept),after['grants.gsr'])
        self.assertEqual(r.physical(after),decisions[0]['steps'][-1][1])

    def test_same_counter_and_proposer_compare_incarnation_too(self):
        _,after,decisions,identifier,kept=self.source_ballots(incarnation='ffffffff-ffff-ffff-ffff-ffffffffffff')
        self.assertEqual(1,len(decisions));self.assertNotIn('sources/'+identifier,after)
        self.assertEqual(b''.join(kept),after['grants.gsr'])

    def test_equal_or_older_ballot_never_supplies_retirement_authority(self):
        for changed in ({},{'counter':1}):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'non-increasing grant promise'):
                self.source_ballots(**changed)

    def generation(self,total=7,*,alter=None,recover=None):
        image=b'actual original image';name=r.sha(image)+'.image';node='node-1';root='a'*64
        cap=dict(root=root,cut=dict(index=0),catalog='b'*64,application=r.sha(image));point=r.c.anchor(cap)
        original={'generation.gsr':b'manifest','source.gscp':b'source','promise.gsr':b'promise',name:image}
        members={'source.gscp':b'current',name:image}
        files={'generations/a':None,'generations/a/generation.gsr':b'active','generations/a/source.gscp':b'current',
               'generations/a/'+name:image,'generations/b':None,'pending.accept':r.c.EMPTY,
               'floor-copies/floor.gsr':b'floor','selector.gsr':b'selector'}
        files.update({'generations/b/'+k:v for k,v in original.items()})
        for i in range(total-2):files[f'floor-copies/{i}/'+name]=image
        manifest=dict(node=node,generation='b',root=root,files=[dict(path=k,size=len(v),sha256=r.sha(v)) for k,v in sorted(original.items()) if k!='generation.gsr'])
        copies={node:dict(members=members,manifest=b'active',identity=dict(storage='00000000-0000-0000-0000-000000000001'))}
        if alter=='borrowed':members[name]=b'wrong'
        elif alter=='manifest':manifest['files'].pop()
        elif alter=='pending':files['pending.accept']=b'unsettled'
        elif alter=='extra-generation':files['generations/c']=None
        with patch.object(r.c,'current',return_value=('generations/a/',members,dict(capsule=cap))), \
                patch.object(r.f,'decode',return_value=manifest),patch.object(r.c.p,'decode',return_value=dict(capsule=cap)), \
                patch.object(r.r.peer.t.confirmation,'endpoints',return_value={0:point}):
            return r.generation_plan(files,node,copies,recover=recover)

    def test_seven_image_capacity_selects_borrowing_without_a_log_hint(self):
        after,steps,details=self.generation(7)
        self.assertTrue(details['borrowedImages']);self.assertEqual(7,details['physicalImagesPeak'])
        events=[point for point,_ in steps]
        self.assertIn('RETIREMENT_BORROWED_IMAGES_FORCED',events);self.assertNotIn('RETIREMENT_IMAGE_WRITTEN',events)
        self.assertFalse(any(k.startswith('generations/b') for k in after))
        self.assertEqual(4,events.count('RETIREMENT_FILE_DELETED'));self.assertEqual(3,events.count('RETIREMENT_SAVED_FILE_DELETED'))

    def test_six_images_copy_the_exact_original_without_borrowing(self):
        _,steps,details=self.generation(6);events=[point for point,_ in steps]
        self.assertFalse(details['borrowedImages']);self.assertEqual(7,details['physicalImagesPeak'])
        self.assertIn('RETIREMENT_IMAGE_FORCED',events);self.assertNotIn('RETIREMENT_BORROW_FORCED',events)
        self.assertEqual(4,events.count('RETIREMENT_SAVED_FILE_DELETED'))

    def test_over_capacity_or_wrong_borrowed_bytes_cannot_authorize_retirement(self):
        with self.assertRaisesRegex(ValueError,'^REMOVE retirement original application capacity$'):self.generation(8)
        with self.assertRaisesRegex(ValueError,'^REMOVE retirement exact borrowed local image$'):self.generation(7,alter='borrowed')

    def test_incomplete_manifest_unsettled_vote_or_extra_slot_refuses(self):
        for altered,reason in [('manifest','inactive member authority'),('pending','unsettled original'),('extra-generation','exact inactive generation')]:
            with self.subTest(altered=altered),self.assertRaisesRegex(ValueError,'^REMOVE retirement '+reason+'$'):self.generation(alter=altered)

    def test_borrowed_transaction_recovers_each_boundary_in_either_slot(self):
        initial,original,authority=retirement_fixture.RetirementEvidenceTest().fixture()
        for slot in ('a','b'):
            start={name.replace('generations/a','generations/'+slot):value for name,value in initial.items()}
            opposite='b' if slot=='a' else 'a';start['generations/'+opposite]=dict(directory=True);start['generations/'+opposite+'/keep']=r.images.old.entry(b'keep')
            steps,_=r.images.transaction(start,original,authority,b'bound',True,slot=slot);final=steps[-1][1]
            for _,state in steps:
                resumed,_=r.images.transaction(state,original,authority,b'bound',True,slot=slot)
                self.assertEqual(final,resumed[-1][1] if resumed else state)
                self.assertIn('generations/'+opposite+'/keep',state)
            self.assertNotIn('generations/'+slot,final)

    def test_borrowed_and_copied_transactions_reject_invalid_slots(self):
        initial,original,authority=retirement_fixture.RetirementEvidenceTest().fixture()
        for borrow in (True,False):
            for slot in ('../a','c','a/source.gscp',''):
                with self.subTest(borrow=borrow,slot=slot),self.assertRaisesRegex(ValueError,'^retirement transaction slot$'):
                    r.images.transaction(initial,original,authority,b'bound',borrow,slot=slot)

    def test_default_copied_transaction_preserves_previous_result(self):
        initial,original,authority=retirement_fixture.RetirementEvidenceTest().fixture()
        self.assertEqual(r.images.old.transaction(initial,original,authority),r.images.transaction(initial,original,authority,None,False))

    def test_explicit_source_coverage_does_not_fall_back_or_invent_an_anchor(self):
        files,identifier,current,coverage,_,_=source_fixture.JoiningRetirementReplayTest().decision_inputs()
        with patch.object(r.sources.disk,'current',return_value=current),patch.object(r.sources.t,'require_coverage',return_value=coverage) as fallback:
            expected=r.sources.decision(files,'node-1',identifier)
            fallback.reset_mock();self.assertEqual(expected,r.sources.decision(files,'node-1',identifier,coverage=coverage));fallback.assert_not_called()
            with self.assertRaisesRegex(ValueError,'governing source coverage'):r.sources.decision(files,'node-1',identifier,coverage={})
            fallback.assert_not_called()

    def test_invalid_profile_or_original_stops_qualification(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^REMOVE retirement profile$'):r.validate('/unused','3-REMOVE')
        inventory.assert_not_called()
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.r,'validate',side_effect=ValueError('original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^original$'):r.validate('/unused','4-REMOVE')
        replay.assert_not_called()
        with patch.object(r,'validate',side_effect=ValueError('original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^original$'):r.qualify('/unused','4-REMOVE')
        pool.assert_not_called()

    def test_worker_bounds_refuse_before_original_read(self):
        for workers in (0,5,True,1.1):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'^REMOVE retirement replay workers$'):
                r.qualify('/unused','4-REMOVE',workers=workers)
            validate.assert_not_called()

    def negative(self,change=None,error=None,accepted=False):
        before=dict(files={'authority':'a','wire.json':'w','events.json':'e'},directories=['empty']);after=copy.deepcopy(before)
        original=[dict(node='node-1',event='CURRENT_VALIDATED')];changed=copy.deepcopy(original)
        if change=='file':after['files']['wire.json']='changed'
        elif change=='directory':after['directories']=[]
        elif change=='observation':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
        name='duplicate-delete'
        with ExitStack() as stack:
            for obj,key,value in [(r.shutil,'copytree',None),(r,'mutate',None),(r.n.collection,'inventory',after)]:stack.enter_context(patch.object(obj,key,return_value=value))
            stack.enter_context(patch.object(r.n.collection,'read_json',side_effect=[original,changed]))
            stack.enter_context(patch.object(r.r,'replay',side_effect=ValueError('old retention') if change=='precondition' else None))
            stack.enter_context(patch.object(r,'replay',side_effect=None if accepted else ValueError(error or r.NEGATIVES[name])))
            return r.negative('/unused','4-REMOVE',before,name)

    def test_negative_preserves_physical_files_directories_and_other_observations(self):
        for change,reason in [('file','original files'),('directory','original files'),('observation','other observations')]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^REMOVE retirement negative changed '+reason+'$'):self.negative(change)

    def test_existing_retention_failure_is_not_a_new_transaction_rejection(self):
        with self.assertRaisesRegex(ValueError,'^old retention$'):self.negative('precondition')

    def test_unrelated_error_and_accepted_mutation_fail(self):
        with self.assertRaisesRegex(ValueError,'^REMOVE unrelated retirement negative:'):self.negative(error='unrelated')
        with self.assertRaisesRegex(ValueError,'^REMOVE retirement mutation accepted:'):self.negative(accepted=True)
        self.assertEqual('PASS',self.negative()['retentionReplay'])


if __name__=='__main__':unittest.main()
