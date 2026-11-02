"""Original membership fences, retained promises and profile ballot scope."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import joining_profile_ballot_evidence as p

b=p.ballot


def event(point,node='node-6',scope='continuation-owner'):
    return dict(node=node,event=point,**({} if scope is None else dict(scope=scope)))


class ProfileBallotTest(unittest.TestCase):
    def certificate(self,index=10,counter=8,proposer='node-1'):
        value=b.f.sample(b.f.catalog()['records']['CERTIFICATE']['schema'],b.f.catalog()['types'])
        value.update(root='a'*64,index=index,ballot=dict(counter=counter,proposer=proposer,incarnation='00000000-0000-0000-0000-000000000001'))
        return b.f.encode('records','CERTIFICATE',value),value

    def packet(self,certificates):
        return dict(capsule=dict(root='a'*64,cut=dict(index=11),items=[dict(kind='MEMBERSHIP',certificate=b.sha(raw)) for raw in certificates]),
                    objects={b.sha(raw):raw for raw in certificates})

    def test_fence_is_highest_membership_ballot_not_terminal_index_or_range(self):
        high,_=self.certificate(4,9);later,_=self.certificate(10,8);barrier,_=self.certificate(11,100)
        packet=self.packet([high,later]);packet['capsule']['items'].append(dict(kind='RANGE',certificate=b.sha(barrier)));packet['objects'][b.sha(barrier)]=barrier
        raw,value=b.membership_fence(packet,{'adopted-certificate.gsr':high},'a'*64)
        self.assertEqual(high,raw);self.assertEqual(4,value['index'])
        for wrong in (later,barrier):
            with self.assertRaisesRegex(ValueError,'^joining ballot exact adopted membership fence$'):
                b.membership_fence(packet,{'adopted-certificate.gsr':wrong},'a'*64)

    def test_equal_membership_ballots_select_last_original_item(self):
        first,_=self.certificate(4);last,_=self.certificate(10)
        self.assertEqual(last,b.membership_fence(self.packet([first,last]),{'adopted-certificate.gsr':last},'a'*64)[0])
        with self.assertRaisesRegex(ValueError,'^joining ballot exact adopted membership fence$'):
            b.membership_fence(self.packet([first,last]),{'adopted-certificate.gsr':first},'a'*64)

    def test_fence_requires_original_object_digest_and_membership_item(self):
        raw,_=self.certificate();packet=self.packet([raw]);packet['objects'][b.sha(raw)]=b'changed'
        with self.assertRaisesRegex(ValueError,'^joining ballot original membership certificate$'):
            b.membership_fence(packet,{'adopted-certificate.gsr':raw},'a'*64)
        with self.assertRaisesRegex(ValueError,'^joining ballot missing membership fence$'):
            b.membership_fence(self.packet([]),{},'a'*64)
        with self.assertRaises(ValueError):b.membership_fence(self.packet([raw]),{'adopted-certificate.gsr':raw},'b'*64)

    def test_no_adoption_is_valid_only_when_both_callbacks_and_windows_are_absent(self):
        self.assertEqual([],b.adoption_transactions([],[],('node-1','node-6'),'node-6'))
        rows=[event(v) for v in b.ADOPTION]
        with self.assertRaisesRegex(ValueError,'^joining ballot original adopted generation$'):
            b.adoption_transactions(rows,[],('node-6',),'node-6')

    def test_interleaved_adoptions_bind_each_actual_owner_and_return(self):
        rows=[event(point,node,scope) for point in b.ADOPTION for node,scope in [('node-4',None),('node-6','continuation-owner')]]
        windows=[dict(node='node-4',start=4),dict(node='node-6',start=5)]
        tx=b.adoption_transactions(rows,windows,('node-4','node-6'),'node-6')
        self.assertEqual([(0,2,4),(1,3,5)],[(v['start'],v['fenced'],v['end']) for v in tx])

    def test_missing_duplicate_reordered_foreign_adoption_boundaries_fail(self):
        for change in ('missing','duplicate','order','scope','foreign','incomplete'):
            rows=[event(v) for v in b.ADOPTION]
            if change=='missing':rows.pop(1)
            elif change=='duplicate':rows.insert(1,dict(rows[0]))
            elif change=='order':rows[0],rows[1]=rows[1],rows[0]
            elif change=='scope':rows[0]['scope']='initial-owner'
            elif change=='foreign':rows[0]['node']='node-9'
            else:rows.pop()
            with self.subTest(change=change),self.assertRaises(ValueError):
                b.adoption_transactions(rows,[dict(node='node-6',start=len(rows)-1)],('node-6',),'node-6')

    def adoption(self,old_counter=6,*,old_proposer='node-1',write=None):
        raw,cert=self.certificate();old=dict(root='a'*64,view='b'*64,ballot=dict(cert['ballot'],counter=old_counter,proposer=old_proposer),basisId='00000000-0000-0000-0000-000000000002')
        before=b.f.encode('records','PROMISE',old);changed=b.ballot_order(old['ballot'])<b.ballot_order(cert['ballot'])
        after=b.f.encode('records','PROMISE',dict(root='a'*64,view=cert['authority'],ballot=cert['ballot'],basisId=None)) if changed else before
        points=[*b.PROMISE] if (changed if write is None else write) else []
        rows=[event('OTHER'),event('OTHER'),event(b.ADOPTION[0]),*[event(v) for v in points],event(b.ADOPTION[1]),event(b.ADOPTION[2])]
        own=dict(node='node-6',start=len(rows)-1,packet=self.packet([raw]),members={'adopted-certificate.gsr':raw,'promise.gsr':after})
        r=b.Replay.__new__(b.Replay);r.events=rows;r.owners=('node-1','node-6');r.model=SimpleNamespace(root='a'*64,joining='node-6',phases=[{}]*9+[{'CERTIFICATE':raw}])
        r.base=SimpleNamespace(sources=[],windows=[own]);r.captures=[];r.promise_points=set();r.promise_history=[(0,'node-6',before)];r.adoption_fences=[]
        r.state=b.State('a'*64);r.state.seed('node-6',7,old_counter)
        return r,own,before,after

    def bind(self,reader):
        actions=[]
        with patch.object(b.a.c,'owner_lifetime'):reader.adoptions(actions)
        for _,kind,args in sorted(actions):getattr(reader.state if kind=='promise' else reader,kind)(*args)
        return actions

    def test_adoption_appends_exact_fence_without_allocating_or_granting(self):
        r,own,before,after=self.adoption();actions=self.bind(r)
        self.assertEqual(['promise','fence'],[v[1] for v in actions]);self.assertEqual(7,r.state.counters['node-6']);self.assertEqual(8,r.state.observed['node-6'])
        self.assertEqual({3,4,5},r.promise_points);self.assertEqual(b.sha(after),r.adoption_fences[0]['promise'])
        self.assertEqual((11,10),(r.adoption_fences[0]['cut'],r.adoption_fences[0]['certificateIndex']))
        self.assertEqual(b.sha(before),r.adoption_fences[0]['priorPromise'])

    def test_equal_or_stronger_original_promise_is_retained_byte_for_byte(self):
        for counter,proposer in ((9,'node-1'),(8,'node-2'),(8,'node-1')):
            r,own,before,after=self.adoption(counter,old_proposer=proposer);actions=self.bind(r)
            self.assertEqual(before,after);self.assertEqual(['fence'],[v[1] for v in actions]);self.assertEqual(set(),r.promise_points)
            self.assertFalse(r.adoption_fences[0]['promiseAppended']);self.assertEqual(counter,r.state.observed['node-6'])

    def test_missing_new_promise_or_extra_unchanged_promise_is_rejected(self):
        for counter,write,reason in ((6,False,'exact promise force order'),(9,True,'unchanged adoption wrote promise')):
            r,_,_,_=self.adoption(counter,write=write)
            with self.assertRaisesRegex(ValueError,'^joining ballot '+reason+'$'):self.bind(r)

    def test_same_counter_cannot_substitute_original_promise_bytes_or_certificate(self):
        r,own,_,after=self.adoption();value=b.f.decode(after,'records','PROMISE');value['view']='d'*64
        own['members']['promise.gsr']=b.f.encode('records','PROMISE',value)
        with self.assertRaisesRegex(ValueError,'^joining ballot exact original adoption promise$'):self.bind(r)
        r,own,_,_=self.adoption();r.model.phases[9]={'CERTIFICATE':self.certificate(10,7)[0]}
        with self.assertRaisesRegex(ValueError,'^joining ballot adopted certificate original history$'):self.bind(r)

    def test_future_or_missing_prior_promise_cannot_supply_adoption_authority(self):
        r,_,before,_=self.adoption();r.promise_history=[(20,'node-6',before)]
        with self.assertRaisesRegex(ValueError,'^joining ballot adoption missing original prior promise$'):self.bind(r)
        r,_,_,_=self.adoption();r.promise_history.append((20,'node-6',self.adoption(100)[2]));self.bind(r)
        self.assertTrue(r.adoption_fences[0]['promiseAppended'])

    def test_latest_original_grant_force_supplies_retained_promise(self):
        r,own,_,after=self.adoption(9);r.promise_history=[(-1,'node-6',self.adoption(6)[2])]
        r.events=[event('OTHER'),event('OTHER'),*[event(v) for v in b.PROMISE],event('GRANT_BEFORE_RETURN'),event('GRANT_CAPTURED'),*r.events]
        own['start']+=7;r.captures=[dict(node='node-6',returnEvent=5,capturedEvent=6)]
        r.base.sources=[dict(node='node-6',start=6,promise=after)];r.promise_points={2,3,4}
        self.bind(r);self.assertFalse(r.adoption_fences[0]['promiseAppended']);self.assertEqual(b.sha(after),r.adoption_fences[0]['priorPromise'])

    def test_fence_observation_cannot_advance_allocator_silently(self):
        r,_,_,_=self.adoption()
        with self.assertRaisesRegex(ValueError,'^joining ballot adoption observed promise$'):r.fence('node-6',8)
        self.assertEqual(7,r.state.counters['node-6'])

    def test_mutations_use_actual_old_and_joining_owners(self):
        rows=[event(v,'node-4',None) for v in b.WRITES]+[event(v,'node-6','repeated-basis-owner') for v in b.WRITES]
        reader=SimpleNamespace(events=rows,model=SimpleNamespace(joining='node-6'),owners=('node-1','node-4','node-6'),tx=b.allocations(rows,('node-1','node-4','node-6'),'node-6'))
        with tempfile.TemporaryDirectory() as tmp:b.mutate(Path(tmp),'wrong-joining-scope',reader=reader)
        self.assertTrue(all(v.get('scope')=='initial-owner' for v in rows[7:]));self.assertTrue(all('scope' not in v for v in rows[:7]))

    def test_original_retention_failure_stops_new_ballot_and_negative_workers(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.prior,'validate',side_effect=ValueError('invalid original')), \
             patch.object(p,'Replay') as replay,patch.object(p,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused','5-REPLACE')
            replay.assert_not_called();pool.assert_not_called()

    def test_unused_reservation_negative_crosses_actual_owner_boundary_without_new_capture(self):
        rows=[event(v,'node-4',None) for v in b.WRITES]+[event('CURRENT_BEFORE_CAPTURE','node-6','repeated-basis-owner')]+[
            event(v,'node-6','repeated-basis-owner') for v in b.WRITES]+[event('CURRENT_VALIDATED')]
        reader=SimpleNamespace(events=rows,model=SimpleNamespace(joining='node-6'),owners=('node-1','node-4','node-6'),
                               tx=b.allocations(rows,('node-1','node-4','node-6'),'node-6'))
        original_other=[v for v in rows if v['event'] not in b.WRITES]
        with tempfile.TemporaryDirectory() as tmp:b.mutate(Path(tmp),'unused-after-owner',reader=reader)
        self.assertEqual(original_other,[v for v in rows if v['event'] not in b.WRITES])
        boundary=rows.index(original_other[-1]);spare=b.allocations(rows,reader.owners,'node-6')[-1]
        self.assertGreater(spare['start'],boundary);self.assertEqual('repeated-basis-owner',spare['scope'])

    def test_result_keeps_full_cohort_and_phase_unqualified_and_checks_immutability(self):
        r=SimpleNamespace(run=Mock(return_value={}),adoption_fences=[])
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.prior,'validate',return_value={}),patch.object(p,'Replay',return_value=r):
            result=p.validate('/unused','5-REPLACE')
            self.assertTrue(result['ballotCompositionQualified'])
            for field in ('allMembershipProfilesQualified','currentSourceNativeCohortQualified','processDeathQualified','phase3Complete'):self.assertIs(False,result[field])
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.prior,'validate'),patch.object(p,'Replay',return_value=r):
            with self.assertRaisesRegex(ValueError,'^joining profile ballot original changed$'):p.validate('/unused','4-ADD')

    def negative(self,change=None,error=None,accepted=False,missing=False):
        before=dict(files={'original':'a','wire.json':'b','events.json':'c'},directories=['empty']);after=copy.deepcopy(before)
        rows=[event('CURRENT_VALIDATED')];changed=copy.deepcopy(rows)
        if change=='file':after['files']['wire.json']='wrong'
        elif change=='directory':after['directories']=[]
        elif change=='event':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
        reader=Mock();reader.run.side_effect=None if accepted else ValueError(error or p.NEGATIVES['force-missing'])
        with patch.object(p.shutil,'copytree'),patch.object(p,'mutate',side_effect=StopIteration if missing else None), \
             patch.object(p.collection,'inventory',return_value=after),patch.object(p.collection,'read_json',side_effect=[rows,changed]),patch.object(p,'Replay',return_value=reader):
            return p.negative('/unused',before,'4-ADD','force-missing')

    def test_negatives_preserve_files_wire_directories_and_other_observations(self):
        for change,reason in [('file','original files'),('directory','original files'),('event','other observations')]:
            with self.assertRaisesRegex(ValueError,'^joining profile ballot negative changed '+reason+'$'):self.negative(change)

    def test_missing_target_wrong_error_or_accepted_mutation_cannot_pass(self):
        for kwargs,reason in [(dict(missing=True),'missing negative target'),(dict(error='wrong'),'unrelated ballot negative'),(dict(accepted=True),'mutation accepted')]:
            with self.assertRaisesRegex(ValueError,reason):self.negative(**kwargs)
        self.assertEqual('REJECTED',self.negative()['status'])

    def test_only_original_absence_makes_adoption_negatives_inapplicable(self):
        for fences,absent in (([],2),([dict(promiseAppended=False)],1),([dict(promiseAppended=True)],0)):
            with patch.object(p,'validate',return_value=dict(adoptionFences=fences)),patch.object(p.collection,'inventory',return_value={}), \
                 patch.object(p,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(p,'negative',side_effect=lambda root,before,profile,name:dict(case=name,status='REJECTED')):
                result=p.qualify('/unused','4-ADD',workers=2)
            self.assertEqual(21-absent,result['rejected']);self.assertEqual(absent,result['notApplicable']);self.assertEqual(21,len(result['negatives']))

    def test_workers_are_bounded_and_errors_remain_failures(self):
        for workers in (0,5,True,1.5):
            with patch.object(p,'validate') as original,self.assertRaisesRegex(ValueError,'^joining profile ballot replay workers$'):p.qualify('/unused','4-ADD',workers=workers)
            original.assert_not_called()
        with patch.object(p,'validate',return_value=dict(adoptionFences=[])),patch.object(p.collection,'inventory',return_value={}), \
             patch.object(p,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(p,'negative',side_effect=ValueError('missing original target')):
            with self.assertRaisesRegex(ValueError,'^joining profile ballot negative matrix failed$'):p.qualify('/unused','4-ADD')


if __name__=='__main__':unittest.main()
