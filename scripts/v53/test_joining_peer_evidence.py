"""Continuous-ledger reader boundaries; native qualification is separate."""
from contextlib import ExitStack
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_peer_evidence as p
from .test_peer_confirmation_evidence import fixture


class JoiningPeerEvidenceTest(unittest.TestCase):
    def ledger(self):
        state,_=fixture();before=p.peers.frame(state);plan=copy.deepcopy(state['plan'])
        future=copy.deepcopy(plan['peers'][2]['possible'][0]);future['cut']['index']=3
        plan['peers'][2]['possible'].append(future)
        return before,p.updated(before,plan)

    def events(self,node='node-2',scope=None):
        return [dict(node=node,event=name,**({} if scope is None else dict(scope=scope))) for name in p.WRITES]

    def reader(self):
        reader=p.Replay.__new__(p.Replay)
        reader.model=SimpleNamespace(joining='node-4')
        reader.tx=p.transactions([dict(node='node-2',event='start'),*self.events()])
        reader.used=set();reader.steps=[]
        return reader

    def guards(self,stack):
        for module,name,default in ((p,'validate',{}),(p.n.s.collection,'inventory',dict(files={},directories=[])),
                                    (p.shutil,'copytree',None),(p,'mutate',None),(p.n,'network',None),
                                    (p.e,'replay',None),(p.c,'replay',None),(p.m,'replay',None)):
            stack.enter_context(patch.object(module,name,return_value=default))

    def opens(self):
        return [dict(node=node,event=event,**({} if scope is None else dict(scope=scope))) for node,scope in p.OWNERS
                for event in ['CURRENT_VALIDATED','LEARNER_RETENTION_RECOVERY_PARENT_FORCED',*p.RESEAL,'FUTURE_RETENTION_RECOVERY_FORCED']]

    def test_all_original_opens_have_a_distinct_completed_reseal(self):
        events=self.opens();expected=[(i*5+3,node) for i,(node,_) in enumerate(p.OWNERS)]
        self.assertEqual(expected,p.reseal_lifetimes(events))

    def test_reseal_requires_both_forces_and_original_scope(self):
        for mutation in ('missing','duplicate','scope'):
            events=self.opens()
            if mutation=='missing':events.pop(3)
            elif mutation=='duplicate':events.insert(4,copy.deepcopy(events[3]))
            else:events[3]['scope']='foreign-owner'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining peer exact open reseal count$'):
                p.reseal_lifetimes(events)

    def test_open_reseal_parent_cannot_precede_active_file_force(self):
        events=self.opens();events[2],events[3]=events[3],events[2]
        with self.assertRaisesRegex(ValueError,'^joining peer open reseal force order$'):p.reseal_lifetimes(events)

    def test_open_reseal_must_precede_future_recovery(self):
        events=self.opens();events[2:5]=[events[4],events[2],events[3]]
        with self.assertRaisesRegex(ValueError,'^joining peer open reseal force order$'):p.reseal_lifetimes(events)

    def test_reseal_from_an_unrecognized_owner_cannot_be_ignored(self):
        events=self.opens();events.extend(dict(v,scope='unbound-owner') for v in events[2:4])
        with self.assertRaisesRegex(ValueError,'^joining peer unbound open reseal$'):p.reseal_lifetimes(events)

    def test_reseal_preserves_exact_derived_revision_and_original_bytes(self):
        reader=self.reader();before,after=self.ledger();reader.state={'node-2':before};reader.comparisons=0;reader.root=Path('/unused')
        with patch.object(p.disk,'inventory',return_value={p.FILE:before}):
            reader.reseal((3,'node-2'))
        self.assertEqual(before,reader.state['node-2']);self.assertEqual(1,reader.comparisons)
        with patch.object(p.disk,'inventory',return_value={p.FILE:after}):
            with self.assertRaisesRegex(ValueError,'^joining peer exact original ledger: open-reseal: node-2$'):reader.reseal((3,'node-2'))

    def test_noop_preserves_exact_bytes_revision_and_old_obligations(self):
        before,_=self.ledger();plan=copy.deepcopy(p.peers.decode(before)['plan'])
        self.assertEqual(before,p.updated(before,plan))
        self.assertEqual([0,1],[v['cut']['index'] for v in plan['peers'][2]['renewals']])

    def test_real_update_keeps_previous_hash_owner_and_retained_endpoints(self):
        before,after=self.ledger();p.revision(before,after);a,b=map(p.peers.decode,(before,after))
        self.assertEqual((a['revision']+1,p.sha(before),a['owner']),(b['revision'],b['previous'],b['owner']))
        self.assertEqual(a['plan']['peers'][2]['renewals'],b['plan']['peers'][2]['renewals'])
        self.assertEqual([2,3],[v['cut']['index'] for v in b['plan']['peers'][2]['possible']])

    def test_revision_gaps_wrong_predecessor_and_recycled_owner_refuse(self):
        before,after=self.ledger()
        for field in ('revision','previous','owner'):
            changed=p.peers.decode(after)
            if field=='revision':changed[field]+=1
            elif field=='previous':changed[field]='f'*64
            else:changed[field]['storage']='00000000-0000-0000-0000-000000000099'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining peer exact revision chain$'):
                p.revision(before,p.peers.frame(changed))
        with self.assertRaisesRegex(ValueError,'^joining peer exact revision chain$'):p.revision(before,before)

    def test_interleaved_owners_keep_separate_seven_force_chains(self):
        left,right=self.events(),self.events('node-4','continuation-owner')
        result=p.transactions([v for pair in zip(left,right) for v in pair])
        self.assertEqual([('node-2',0,12,None),('node-4',1,13,'continuation-owner')],
                         [(v['node'],v['start'],v['end'],v['scope']) for v in result])

    def test_missing_force_reordered_rename_and_scope_change_are_not_durable(self):
        for mutation in ('missing','rename','scope'):
            events=self.events()
            if mutation=='missing':events.pop(3)
            elif mutation=='rename':events[3],events[5]=events[5],events[3]
            else:events[4]['scope']='other'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining peer exact write force order$'):
                p.transactions(events)

    def test_incomplete_final_write_cannot_disappear_at_eof(self):
        with self.assertRaisesRegex(ValueError,'^joining peer incomplete durable write$'):p.transactions(self.events()[:-1])

    def test_force_must_be_strictly_inside_its_authority_lifetime(self):
        changes=[(*self.ledger(),'observation')]
        reader=self.reader();reader.sequence('node-2',changes,0,8,'maintenance');self.assertEqual({1},reader.used)
        for lower,upper in ((1,8),(0,7),(8,9)):
            with self.subTest(lower=lower,upper=upper),self.assertRaisesRegex(ValueError,'^joining peer maintenance durable write count$'):
                self.reader().sequence('node-2',changes,lower,upper,'maintenance')

    def test_noop_cannot_consume_an_actual_write(self):
        with self.assertRaisesRegex(ValueError,'^joining peer selected durable write count$'):
            self.reader().sequence('node-2',[],0,8,'selected')

    def test_one_force_chain_cannot_complete_two_semantic_changes(self):
        changes=[(*self.ledger(),'selected')];reader=self.reader();reader.sequence('node-2',changes,0,8,'selected')
        with self.assertRaisesRegex(ValueError,'^joining peer original write owner$'):reader.sequence('node-2',changes,0,8,'selected')

    def test_whole_chain_foreign_scope_and_wrong_ledger_owner_refuse(self):
        for wrong in ('scope','owner'):
            reader=self.reader();changes=[(*self.ledger(),'publish')]
            if wrong=='scope':reader.tx[0]['scope']='foreign-owner'
            else:
                reader.tx[0]['node']='node-1'
            with self.subTest(wrong=wrong),self.assertRaisesRegex(ValueError,'^joining peer original write owner$'):
                reader.sequence('node-1' if wrong=='owner' else 'node-2',changes,0,8,'publication')

    def test_captured_or_cold_ledger_must_equal_continuously_derived_bytes(self):
        reader=self.reader();before,after=self.ledger();reader.state={'node-2':before};reader.comparisons=0
        reader.compare('node-2',before,'grant');self.assertEqual(1,reader.comparisons)
        with self.assertRaisesRegex(ValueError,'^joining peer exact original ledger: cold: node-2$'):reader.compare('node-2',after,'cold')

    def test_validate_requires_full_original_maintenance_gate(self):
        with patch.object(p.n.s.collection,'inventory',return_value={}),patch.object(p.m,'validate',side_effect=ValueError('invalid original')),patch.object(p,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.validate('/unused')
            replay.assert_not_called()

    def test_validate_refuses_any_original_inventory_change(self):
        with patch.object(p.n.s.collection,'inventory',side_effect=[{}, {'changed':1}]),patch.object(p.m,'validate'),patch.object(p,'replay'):
            with self.assertRaisesRegex(ValueError,'^joining peer original changed$'):p.validate('/unused')

    def test_invalid_original_prevents_all_negative_execution(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')),patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused')
            copied.assert_not_called()

    def test_negative_must_preserve_physical_files_wire_and_directories(self):
        original=dict(files={'wire.json':'original','authority':'original'},directories=['original'])
        for altered in (dict(files={'wire.json':'altered','authority':'original'},directories=['original']),
                        dict(files={'wire.json':'original','authority':'altered'},directories=['original']),
                        dict(files=original['files'],directories=[])):
            with ExitStack() as stack:
                self.guards(stack);stack.enter_context(patch.object(p.n.s.collection,'inventory',side_effect=[original,altered]))
                network=stack.enter_context(patch.object(p.n,'network'))
                with self.assertRaisesRegex(ValueError,'^joining peer negative changed physical inputs$'):p.qualify('/unused')
                network.assert_not_called()

    def test_prior_maintenance_failure_cannot_count_as_peer_rejection(self):
        with ExitStack() as stack:
            self.guards(stack);stack.enter_context(patch.object(p.m,'replay',side_effect=ValueError('invalid maintenance')))
            replay=stack.enter_context(patch.object(p,'replay'))
            with self.assertRaisesRegex(ValueError,'^invalid maintenance$'):p.qualify('/unused')
            replay.assert_not_called()

    def test_unrelated_error_and_accepted_mutation_fail_qualification(self):
        for failure,reason in ((None,'joining peer mutation accepted: force-missing'),
                               (ValueError('unrelated'),'joining unrelated peer negative: force-missing: unrelated')):
            with ExitStack() as stack:
                self.guards(stack);stack.enter_context(patch.object(p,'replay',side_effect=failure))
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.qualify('/unused')

    def test_qualification_rechecks_original_inventory_after_all_variants(self):
        with ExitStack() as stack:
            self.guards(stack);stack.enter_context(patch.object(p,'NEGATIVES',{}))
            stack.enter_context(patch.object(p.n.s.collection,'inventory',side_effect=[dict(files={},directories=[]),dict(files={},directories=['changed'])]))
            with self.assertRaisesRegex(ValueError,'^joining peer negative changed original$'):p.qualify('/unused')


if __name__=='__main__':unittest.main()
