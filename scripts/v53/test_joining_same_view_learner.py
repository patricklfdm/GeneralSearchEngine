"""Continuous learner state, custody separation and original force boundaries."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import joining_same_view_learner as m
from .test_joining_retention_evidence import Inputs


def event(point,node='node-2',scope=None):
    return dict(node=node,event=point,**({} if scope is None else dict(scope=scope)))


class JoiningSameViewLearnerTest(unittest.TestCase):
    def custody(self):
        return [event(p,'node-4','learner-admission') for p in ['LEARNER_PLAN_BEFORE_RETURN',*m.ADMISSION,'LEARNER_REPLICA_CREATED']]

    def ledger(self):
        v=Inputs();before=m.learner.frame(dict(root=v.cap['root'],owner=v.identities[1],revision=0,previous=None,plan=v.learner_plans[0]))
        state=m.learner.decode(before);state['plan']['possible'].append(v.endpoint(4))
        after=m.learner.frame(dict(state,revision=1,previous=m.sha(before)))
        return before,after

    def reader(self,events=()):
        r=m.Replay.__new__(m.Replay);r.events=list(events);r.root=Path('/original');r.model=SimpleNamespace(joining='node-4')
        r.base=SimpleNamespace(sources=[]);r.state={};r.steps=[];r.used=set();r.callbacks=set();r.tx=[];r.comparisons=0;r.selected=0;r.reseals=0
        return r

    def test_custody_has_its_own_sequence_and_is_not_a_ledger_revision(self):
        rows=self.custody()+[event(p) for p in m.WRITES]
        tx,custody=m.observations(rows,'node-4')
        self.assertEqual(set(range(1,12)),custody)
        self.assertEqual([dict(node='node-2',scope=None,start=13,end=19)],tx)

    def test_admission_missing_duplicate_or_foreign_owner_is_rejected(self):
        for change in ('missing','duplicate','owner'):
            rows=self.custody()
            if change=='missing':rows.pop(4)
            elif change=='duplicate':rows.insert(4,dict(rows[4]))
            else:rows[4]['node']='node-1'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining learner exact admission retention sequence$'):
                m.observations(rows,'node-4')

    def test_custody_must_finish_between_plan_and_replica_creation(self):
        for rows in ([*self.custody()[1:-1],self.custody()[0],self.custody()[-1]],
                     [self.custody()[0],self.custody()[-1],*self.custody()[1:-1]]):
            with self.assertRaisesRegex(ValueError,'^joining learner admission before replica$'):m.observations(rows,'node-4')

    def test_interleaved_regular_writes_are_separate_from_custody(self):
        prefix=self.custody();rows=prefix+[r for p in m.WRITES for r in [event(p),event(p,'node-4','continuation-owner')]]
        tx,_=m.observations(rows,'node-4')
        self.assertEqual([('node-2',13,25),('node-4',14,26)],[(v['node'],v['start'],v['end']) for v in tx])

    def test_regular_force_rename_scope_and_partial_write_fail_closed(self):
        for change in ('force','rename','scope','partial'):
            values=[event(p,'node-4','continuation-owner') for p in m.WRITES]
            if change=='force':values.pop(3)
            elif change=='rename':values[3],values[5]=values[5],values[3]
            elif change=='scope':values[-1]['scope']='initial-owner'
            else:values.pop()
            reason='incomplete durable write' if change=='partial' else 'exact write force order'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining learner '+reason+'$'):
                m.observations(self.custody()+values,'node-4')

    def test_unknown_recovery_or_forged_event_data_cannot_be_ignored(self):
        for row,reason in [(event('LEARNER_RETENTION_DISCARDED'),'unsupported retention event'),
                           (dict(event(m.WRITES[0]),revision=9),'event shape')]:
            with self.assertRaisesRegex(ValueError,'^joining learner '+reason+'$'):m.observations(self.custody()+[row],'node-4')

    def test_change_requires_one_owned_write_and_exact_revision_predecessor(self):
        before,after=self.ledger();r=self.reader();r.state['node-2']=before;r.tx=[dict(node='node-2',scope=None,start=1,end=7)]
        r.change('node-2',after,0,8,'selected');self.assertEqual(after,r.state['node-2']);self.assertEqual({1},r.used)
        self.assertEqual(m.sha(before),r.steps[0]['before']);self.assertEqual(1,r.steps[0]['revision'])
        for field,value in [('revision',2),('previous','f'*64),('owner',dict(m.learner.decode(before)['owner'],storage='00000000-0000-0000-0000-000000000099'))]:
            changed=m.learner.decode(after);changed[field]=value;r=self.reader();r.state['node-2']=before;r.tx=[dict(node='node-2',scope=None,start=1,end=7)]
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining learner exact revision predecessor$'):
                r.change('node-2',m.learner.frame(changed),0,8,'selected')
            self.assertEqual(before,r.state['node-2'])

    def test_noop_cannot_consume_a_write_or_change_a_revision(self):
        before,_=self.ledger();r=self.reader();r.state['node-2']=before
        r.change('node-2',before,0,8,'selected');self.assertEqual([],r.steps)
        r.tx=[dict(node='node-2',scope=None,start=1,end=7)]
        with self.assertRaisesRegex(ValueError,'^joining learner selected durable write count$'):r.change('node-2',before,0,8,'selected')

    def test_force_chain_cannot_cross_boundary_or_be_reused(self):
        before,after=self.ledger()
        for lower,upper in [(1,8),(0,7)]:
            r=self.reader();r.state['node-2']=before;r.tx=[dict(node='node-2',scope=None,start=1,end=7)]
            with self.assertRaisesRegex(ValueError,'^joining learner record durable write count$'):r.change('node-2',after,lower,upper,'record')
        for used,scope in [({1},None),(set(),'foreign')]:
            r=self.reader();r.state['node-2']=before;r.tx=[dict(node='node-2',scope=scope,start=1,end=7)];r.used=used
            with self.assertRaisesRegex(ValueError,'^joining learner original write owner$'):r.change('node-2',after,0,8,'record')

    def selection(self,*,noop=False,missing=False,wrong_intent=False,early=False):
        before,after=self.ledger();after=before if noop else after
        points=['INSTALL_PARENT_FORCED','SELECTED_RETENTION_COMPLETED']
        if not noop:points+=m.WRITES+([] if missing else [m.RETURNS[-1]])
        points+=['INSTALL_BEFORE_RETURN'];r=self.reader([event(p) for p in points]);r.state['node-2']=before
        if not noop:r.tx=[dict(node='node-2',scope=None,start=0 if early else 2,end=8)]
        own=dict(node='node-2',start=len(points)-1,members={'selected.gsr':b'selection'},identity=m.learner.decode(before)['owner'],
                 packet=dict(objects={} if wrong_intent else {m.sha(b'intent'):b'intent'}))
        r.files=lambda own:{m.FILE:after}
        with patch.object(m.f,'decode',return_value=dict(sources=[])),patch.object(m.learner,'intent',return_value=b'intent'), \
                patch.object(m.a.physical.c,'merge_learner',return_value=after):r.selection(own)
        return r

    def test_selected_noop_preserves_ledger_without_write_or_completion(self):
        r=self.selection(noop=True);self.assertEqual(1,r.selected);self.assertEqual([],r.steps);self.assertEqual(set(),r.callbacks)

    def test_selected_change_binds_local_before_intent_peer_completion_and_force(self):
        r=self.selection();self.assertEqual(1,len(r.steps));self.assertEqual({9},r.callbacks)
        for kw,reason in [(dict(missing=True),'selected completion count'),(dict(wrong_intent=True),'selected original before ledger'),
                          (dict(early=True),'selected durable write count')]:
            with self.subTest(kw=kw),self.assertRaisesRegex(ValueError,'^joining learner '+reason+'$'):self.selection(**kw)

    def test_frozen_capture_must_match_continuous_state(self):
        before,after=self.ledger();r=self.reader();r.state['node-2']=before
        source=dict(node='node-2',packet={},value=dict(ballot=dict(counter=7)))
        with patch.object(m.init.retention,'source',return_value=(b'wrapper',m.learner.decode(before))):r.capture(source)
        with patch.object(m.init.retention,'source',return_value=(b'wrapper',m.learner.decode(after))):
            with self.assertRaisesRegex(ValueError,'^joining learner exact continuous ledger: grant-7: node-2$'):r.capture(source)

    def test_reopen_preserves_bytes_between_current_and_peer_recovery(self):
        before,after=self.ledger();names=['CURRENT_DIRECTORY_FORCED',*m.RESEAL,'RETENTION_RECOVERY_ACTIVE_FORCED']
        r=self.reader([event(p) for p in names]);r.state['node-2']=before
        with patch.object(m.disk,'inventory',return_value={m.FILE:before}):r.reopen('node-2',None,2)
        self.assertEqual(before,r.state['node-2']);self.assertEqual(1,r.reseals)
        with patch.object(m.disk,'inventory',return_value={m.FILE:after}):
            with self.assertRaisesRegex(ValueError,'^joining learner exact continuous ledger: reopen: node-2$'):r.reopen('node-2',None,2)
        for points,at,reason in [(names[:1]+[names[2],names[1],names[3]],1,'reopen force order'),
                                  (names[1:3]+[names[0],names[3]],1,'reopen before current force')]:
            r.events=[event(p) for p in points]
            with self.assertRaisesRegex(ValueError,'^joining learner '+reason+'$'):r.reopen('node-2',None,at)

    def test_original_prerequisite_failure_stops_new_replay_and_negative_workers(self):
        with patch.object(m.a.n.s.collection,'inventory',return_value={}),patch.object(m.prior,'validate',side_effect=ValueError('original')),patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^original$'):m.validate('/unused')
            replay.assert_not_called()
        with patch.object(m,'validate',side_effect=ValueError('original')),patch.object(m,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/unused',workers=4)
            pool.assert_not_called()

    def test_flags_keep_full_physical_process_and_phase_closure_unqualified(self):
        with patch.object(m.a.n.s.collection,'inventory',return_value={}),patch.object(m.prior,'validate',return_value={}),patch.object(m,'replay',return_value={}):
            result=m.validate('/unused')
        self.assertTrue(result['learnerLedgerCompositionQualified']);self.assertTrue(result['futureLedgerCompositionQualified'])
        for field in ('sameViewPhysicalQualified','completePhysicalQualified','forceAndNetworkQualified','processDeathQualified','phase3Complete'):
            self.assertIs(False,result[field])
        with patch.object(m.a.n.s.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(m.prior,'validate',return_value={}),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining learner original changed$'):m.validate('/unused')

    def test_workers_have_bounded_integer_parallelism(self):
        for value in (0,5,True,2.5):
            with patch.object(m,'validate') as original,self.assertRaisesRegex(ValueError,'^joining learner replay workers$'):m.qualify('/unused',workers=value)
            original.assert_not_called()

    def negative(self,change=None,error=None,accepted=False):
        before=dict(files={'original':'hash','events.json':'events','wire.json':'wire'},directories=['empty']);after=copy.deepcopy(before)
        events=[event('CURRENT_VALIDATED')];changed=copy.deepcopy(events)
        if change=='file':after['files']['wire.json']='wrong'
        elif change=='directory':after['directories']=[]
        elif change=='observation':changed[0]['event']='CURRENT_FILES_FORCED'
        name='unbound-write'
        with patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),patch.object(m.a.n.s.collection,'inventory',return_value=after), \
                patch.object(m.a.n.s.collection,'read_json',side_effect=[events,changed]), \
                patch.object(m,'replay',side_effect=None if accepted else ValueError(error or m.NEGATIVES[name])):
            return m.negative('/unused',before,name)

    def test_negative_preserves_physical_wire_directory_and_other_event_inputs(self):
        for change,reason in [('file','original files'),('directory','original files'),('observation','other observations')]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining learner negative changed '+reason+'$'):self.negative(change)

    def test_wrong_rejection_or_accepted_negative_cannot_pass(self):
        with self.assertRaisesRegex(ValueError,'^joining learner unrelated negative:'):self.negative(error='wrong')
        with self.assertRaisesRegex(ValueError,'^joining learner accepted mutation:'):self.negative(accepted=True)
        self.assertTrue(self.negative()['originalFilesAndOtherObservationsUnchanged'])


if __name__=='__main__':unittest.main()
