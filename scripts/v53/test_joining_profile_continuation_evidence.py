"""Conditional reader regressions; native original replay is a separate gate."""
import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_profile_continuation_evidence as e
from .test_joining_retention_evidence import Inputs


class JoiningProfileContinuationEvidenceTest(unittest.TestCase):
    def reconcile(self, profile, change=None):
        size, kind, _, new = e.topology(profile); v = Inputs(size,kind=='REPLACE')
        state=dict(root=v.cap['root'],owner=v.identities[0],revision=5,previous='d'*64,plan=copy.deepcopy(v.peer_plans[0]))
        for row in state['plan']['peers']:row['renewals']=[v.endpoint(2)]
        cap=copy.deepcopy(v.cap);cap['cut']['view']=dict(generation=1,old=new,new=new,operation=None)
        if change:change(state,cap)
        raw=e.c.peers.frame(state);files={e.c.PEERS:raw,'unchanged':b'original'}
        available={i:v.endpoint(i) for i in (2,3)}
        with patch.object(e.disk,'current',return_value=('',{},dict(capsule=cap))), \
             patch.object(e.c.t,'require_coverage',return_value=available):result=e.c.reconcile(files)
        return state,raw,result

    def test_final_only_removes_retired_identity_and_keeps_survivor_debt(self):
        for profile in e.PROFILES:
            with self.subTest(profile=profile):
                before,raw,result=self.reconcile(profile);after=e.c.peers.decode(result[e.c.PEERS])
                new=e.topology(profile)[3]
                self.assertEqual([row for row in before['plan']['peers'] if row['identity']['node'] in new],after['plan']['peers'])
                self.assertEqual(6,after['revision']);self.assertEqual(e.sha(raw),after['previous'])
                self.assertEqual(b'original',result['unchanged'])

    def test_joint_cannot_discard_old_identity(self):
        for profile in ('3-REPLACE','4-REPLACE','5-REPLACE'):
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining continuation reconciliation identity set$'):
                self.reconcile(profile,lambda state,cap:cap['cut']['view'].update(operation='b'*64))

    def test_new_identity_requires_a_real_joining_copy(self):
        def change(state,cap):
            state['plan']['peers'].pop()
            view=state['plan']['view'];state['plan']['view']=dict(view,new=list(view['old']),operation=None)
        with self.assertRaisesRegex(ValueError,'^joining continuation reconciliation identity set$'):
            self.reconcile('4-ADD',change)

    def test_removed_peer_debt_must_be_covered_before_discard(self):
        def change(state,cap):state['plan']['peers'][2]['possible'][0]['catalog']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining continuation reconciliation coverage$'):
            self.reconcile('3-REPLACE',change)

    def test_same_view_does_not_rewrite_ledger_or_drop_debt(self):
        def change(state,cap):cap['cut']['view']=copy.deepcopy(state['plan']['view'])
        _,raw,result=self.reconcile('5-REPLACE',change)
        self.assertEqual(raw,result[e.c.PEERS])

    def campaign(self,profile,names):
        size,kind,old,new=e.topology(profile);v=Inputs(size,kind=='REPLACE')
        value=e.f.sample(e.f.catalog()['records']['SELECTED']['schema'],e.f.catalog()['types'])
        value.update(root=v.cap['root'],cut=v.cap['cut'],sources=[dict(voter=n,basisId='00000000-0000-0000-0001-'+str(i+1).zfill(12),basisDigest=str(i+1)*64)
            for i,n in enumerate(names)])
        reader=e.Continuation.__new__(e.Continuation);reader.joining=new[-1]
        reader.initialization=SimpleNamespace(voters=tuple(old[:size//2+1]))
        reader.replay=SimpleNamespace(phases=[{}]*9+[{'SELECTED':e.f.encode('records','SELECTED',value)}],states=[{}]*9+[v.cap])
        with patch.object(e.p.Continuation,'campaign') as underlying:reader.campaign(9,8)
        underlying.assert_called_once_with(9,8)
        return reader

    def test_overlapping_majorities_can_leave_joiner_unselected(self):
        for profile in ('3-REPLACE','4-ADD','4-REPLACE','5-REPLACE'):
            size,_,old,_=e.topology(profile);names=old[:size//2+1]
            with self.subTest(profile=profile):self.assertEqual(tuple(names),self.campaign(profile,names).voters)

    def test_three_add_requires_more_than_two_old_voters(self):
        with self.assertRaisesRegex(ValueError,'^both governing majorities$'):self.campaign('3-ADD',['node-1','node-2'])
        self.assertEqual(('node-1','node-2','node-4'),self.campaign('3-ADD',['node-1','node-2','node-4']).voters)

    def test_offline_owner_cannot_supply_a_selected_original(self):
        with self.assertRaisesRegex(ValueError,'^joining profile selected reachable owners$'):
            self.campaign('3-ADD',['node-1','node-2','node-3'])

    def preparation(self,profile,change=None):
        size,kind,old,_=e.topology(profile);v=Inputs(size,kind=='REPLACE');voters=old[:size//2+1]
        sources=dict(zip(voters,v.sources()));basis=e.f.decode(sources['node-1'][0],'records','BASIS')
        promise=e.f.encode('records','PROMISE',{k:basis[k] for k in ('root','view','ballot','basisId')})
        ids={i['node']:i for i in v.identities};group={n:{'node.gsr':e.f.encode('records','NODE',dict(root=basis['root'],identity=i))} for n,i in ids.items()}
        rows=[]
        def pair(kind,answer,fields,sender,recipient,request,response):
            def encoded(k,value):return base64.b64encode(e.f.encode('wire',k,value)).decode()
            rows.append(dict(withheld=False,request=encoded(kind,dict(fields,sender=ids[sender],recipient=ids[recipient],payload=request)),
                response=encoded(answer,dict(fields,sender=ids[recipient],recipient=ids[sender],payload=response))))
        for index,node in enumerate(voters[1:],1):
            fields={k:basis[k] for k in ('root','view','ballot')}
            fields.update(trace='00000000-0000-0001-0000-'+str(index).zfill(12),sequence=1)
            pair('PREPARE','PROMISE',fields,'node-1',node,dict(promise=e.sha(promise)),dict(basis=e.sha(sources[node][0])))
            fields['trace']='00000000-0000-0002-0000-'+str(index).zfill(12)
            tid='00000000-0000-0003-0000-'+str(index).zfill(12);digest=e.sha(promise)
            pair('CHUNK','SOURCE_OFFER',fields,node,'node-1',dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes=''),
                dict(id=tid,digest=digest,bytes=len(promise),kind='RECORD'))
            fields['sequence']=2
            pair('CHUNK','CHUNK',fields,node,'node-1',dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes=''),
                dict(id=tid,action='DATA',offset=0,digest=digest,bytes=base64.b64encode(promise).decode()))
            fields['sequence']=3;pair('TRANSFER_COMMIT','TRANSFER_COMMIT',fields,node,'node-1',dict(id=tid,digest=digest),dict(id=tid,digest=digest))
        if change:change(rows)
        with patch.object(e.s.collection,'read_json',return_value=rows):
            return e.prepared_exchanges('/original',group,v.ballot,sources,voters)

    def test_preparation_binds_each_old_majority_promise_transfer(self):
        for profile in e.PROFILES:
            size,_,old,_=e.topology(profile)
            with self.subTest(profile=profile):
                result=self.preparation(profile)
                self.assertEqual(old[1:size//2+1],result['oldPeers'])
                self.assertEqual((size//2)*3,result['originalPromiseTransferExchanges'])

    def test_missing_third_old_preparation_fails(self):
        for profile in ('4-ADD','4-REPLACE','5-REPLACE'):
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining profile preparation response count$'):
                self.preparation(profile,lambda rows:rows.pop(4))

    def shared_trace(self, rows, sequence=2):
        trace=e.c.exchange.wire(rows[0]['request'])[1]['trace']
        for field in ('request','response'):
            kind,value=e.c.exchange.wire(rows[4][field]);value.update(trace=trace,sequence=sequence)
            rows[4][field]=base64.b64encode(e.f.encode('wire',kind,value)).decode()

    def test_native_multi_peer_preparation_increments_shared_trace(self):
        result=self.preparation('5-REPLACE',self.shared_trace)
        self.assertEqual(['node-2','node-3'],result['oldPeers'])
        self.assertEqual(6,result['originalPromiseTransferExchanges'])

    def test_shared_trace_cannot_duplicate_or_skip_sequence(self):
        for sequence in (1,3):
            with self.subTest(sequence=sequence),self.assertRaisesRegex(ValueError,'original correlation'):
                self.preparation('5-REPLACE',lambda rows:self.shared_trace(rows,sequence))

    def test_shared_trace_response_arrival_order_is_not_request_sequence(self):
        def change(rows):
            self.shared_trace(rows);rows[:]=rows[4:]+rows[:4]
        self.assertEqual(['node-2','node-3'],self.preparation('5-REPLACE',change)['oldPeers'])

    def test_third_old_response_cannot_borrow_second_owner_identity(self):
        def change(rows):
            kind,value=e.c.exchange.wire(rows[4]['response'])
            value['sender']=e.c.exchange.wire(rows[0]['response'])[1]['sender']
            rows[4]['response']=base64.b64encode(e.f.encode('wire',kind,value)).decode()
        with self.assertRaisesRegex(ValueError,'^joining profile preparation original correlation$'):self.preparation('4-REPLACE',change)

    def test_duplicate_prepare_cannot_replace_missing_peer(self):
        def change(rows):rows[4]=copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError,'^joining profile preparation exact peers$'):self.preparation('5-REPLACE',change)

    def test_promise_transfer_requires_commit_not_just_matching_data(self):
        with self.assertRaisesRegex(ValueError,'^joining profile preparation promise incomplete transcript$'):
            self.preparation('4-ADD',lambda rows:rows.pop())

    def adoption(self,profile='3-REPLACE'):
        fixture=json.loads((Path(__file__).parent/'testdata/joining-adoption-events.json').read_text())
        joining=e.topology(profile)[3][-1]
        return [dict(row,node=joining) for row in fixture['rows']],joining,{n:b'conditional' for n in fixture['memberNames']}

    def test_original_adoption_order_requires_real_joining_identity(self):
        for profile in e.PROFILES:
            events,joining,members=self.adoption(profile)
            with self.subTest(profile=profile):self.assertEqual((0,len(events)-1),e.adoption_order(events,joining,members,True))

    def test_missing_force_or_premature_selector_is_rejected(self):
        for mode in ('missing','premature'):
            events,joining,members=self.adoption()
            if mode=='missing':events.pop(next(i for i,v in enumerate(events) if v['event']=='CURRENT_FILES_FORCED'))
            else:
                a=next(i for i,v in enumerate(events) if v['event']=='INSTALL_GENERATION_FORCED')
                events[a],events[a+1]=events[a+1],events[a]
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^joining profile original adoption force order$'):
                e.adoption_order(events,joining,members,True)

    def test_other_owner_cannot_substitute_for_adoption(self):
        for profile in ('4-ADD','5-REPLACE'):
            events,joining,members=self.adoption(profile);events[0]['node']='node-4'
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'^joining profile original adoption owner$'):
                e.adoption_order(events,joining,members,True)

    def test_owner_mutation_preserves_recovery_entry_and_targets_return(self):
        events,joining,members=self.adoption()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'events.json').write_bytes(e.f.canonical(events))
            e.mutate(root,'adoption-owner-substituted')
            changed=json.loads((root/'events.json').read_bytes())
        self.assertEqual(events[:-1],changed[:-1]);self.assertEqual('node-1',changed[-1]['node'])
        with self.assertRaisesRegex(ValueError,'^joining profile original adoption owner$'):
            e.adoption_order(changed,joining,members,True)

    def test_second_adoption_cannot_be_ignored(self):
        events,joining,members=self.adoption();events+=copy.deepcopy(events)
        with self.assertRaisesRegex(ValueError,'^joining profile original adoption transaction count$'):
            e.adoption_order(events,joining,members,True)

    def test_promise_force_cannot_be_claimed_when_no_new_promise_written(self):
        events,joining,members=self.adoption()
        with self.assertRaisesRegex(ValueError,'^joining profile original adoption force order$'):
            e.adoption_order(events,joining,members,False)
        events=[v for v in events if not v['event'].startswith('PROMISE_')]
        e.adoption_order(events,joining,members,False)

    def test_unknown_profile_fails_before_opening_original(self):
        with patch.object(e.s.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):e.validate('/unused','5-ADD')
            inventory.assert_not_called()

    def test_invalid_original_is_not_negative_qualification(self):
        with patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('invalid original')), \
             patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/original','3-REPLACE')
            copied.assert_not_called()

    def negative(self,prior_error=None,target_error=None,recovery=None):
        def validate(*args):
            if args[0]==Path('/original'):return dict(recovery=recovery)
            if target_error:raise target_error
            return {}
        with patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=validate), \
             patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.preceding,'validate',side_effect=prior_error), \
             patch.dict(e.COMMON_NEGATIVES,{'conditional':'expected rejection'},clear=True):
            return e.qualify('/original','3-REPLACE')

    def test_earlier_gate_failure_cannot_count_as_rejection(self):
        with self.assertRaisesRegex(ValueError,'^bad prefix$'):self.negative(prior_error=ValueError('bad prefix'))

    def test_unrelated_failure_cannot_count_as_rejection(self):
        with self.assertRaisesRegex(ValueError,'^joining profile continuation unrelated negative:'):
            self.negative(target_error=ValueError('wrong reason'))

    def test_mutation_must_be_rejected(self):
        with self.assertRaisesRegex(ValueError,'^joining profile continuation accepted mutation:'):self.negative()

    def test_absent_adoption_does_not_fabricate_adoption_negatives(self):
        result=self.negative(target_error=ValueError('expected rejection'))
        self.assertEqual(['conditional'],[v['case'] for v in result['negatives']])
        self.assertEqual('PASS',result['negatives'][0]['initializationGate'])


if __name__=='__main__':unittest.main()
