"""Actual owner lifetimes, one local recording, and exact original negatives."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import joining_profile_ledger_evidence as p
from . import test_joining_same_view_future as ff
from . import test_joining_same_view_learner as lf


class ProfileLedgerTest(unittest.TestCase):
    def test_future_constructor_uses_actual_joiner_and_old_node_four(self):
        for profile in ('4-ADD','5-REPLACE'):
            _,kind,old,new=p.topology(profile);joining=new[-1]
            events=[ff.event(point,node,scope) for node,scope in [('node-4',None),(joining,'continuation-owner')] for point in p.future.WRITES]
            base=SimpleNamespace(events=events,model=SimpleNamespace(joining=joining,old=old,kind=kind))
            with patch.object(p.peer.maintenance,'Replay',return_value=base):reader=p.FutureReplay('/original',profile)
            self.assertEqual(['node-4',joining],[v['node'] for v in reader.tx]);self.assertIs(base,reader.base)

    def test_learner_constructor_separates_actual_joiner_admission_from_revisions(self):
        for profile in ('4-REPLACE','5-REPLACE'):
            _,kind,old,new=p.topology(profile);joining=new[-1]
            events=[lf.event(point,joining,'learner-admission') for point in ['LEARNER_PLAN_BEFORE_RETURN',*p.learner.ADMISSION,'LEARNER_REPLICA_CREATED']]
            events += [lf.event(point,'node-4') for point in p.learner.WRITES]
            base=SimpleNamespace(events=events,model=SimpleNamespace(joining=joining,old=old,kind=kind))
            with patch.object(p.peer.maintenance,'Replay',return_value=base):reader=p.LearnerReplay('/original',profile)
            self.assertEqual(11,len(reader.admission));self.assertEqual(['node-4'],[v['node'] for v in reader.tx])

    def test_unused_original_voters_still_require_each_ledger_reopen(self):
        model=SimpleNamespace(old=['node-1','node-2','node-3','node-4','node-5'],joining='node-6',kind='REPLACE',original={})
        for module in (p.future,p.learner):
            reader=module.Replay.__new__(module.Replay);reader.root=Path('/original');reader.model=model
            reader.base=SimpleNamespace(phases={},windows=[],sources=[],rows=[])
            reader.events=[dict(node=model.joining,event='JOINING_RETENTION_BEFORE_RETURN')]
            reader.events += [dict(node=node,event=module.RESEAL[-1],**({} if scope is None else dict(scope=scope)))
                              for node,scope in p.peer.peer.owner_lifetimes(model) if node!='node-5']
            reader.state={};reader.comparisons=0
            with patch.object(module.disk,'inventory',return_value={}):
                with self.assertRaisesRegex(ValueError,'^joining '+('future' if module is p.future else 'learner')+' exact reopen count$'):reader.run()

    def future_exchange(self):
        reader=ff.JoiningSameViewFutureTest().reader();target=dict(node='node-4');certificate=b'original certificate'
        def row(recipient,sent):
            return dict(kind='FUTURE_RETENTION_INTENT',sent=sent,received=21,offered=30,
                        request=dict(sender=dict(node='node-2'),recipient=dict(node=recipient),payload=dict(peer=target,certificate=p.future.sha(certificate))),
                        response=dict(payload=dict(revision=1,digest=p.future.sha(b'original ledger'))))
        reader.base=SimpleNamespace(rows=[row('node-1',10),row('node-4',20)])
        reader.state={'node-4':dict(meta=dict(revision=1),raw=b'original ledger')}
        return reader,target,certificate

    def test_future_local_ack_precedes_every_original_recipient_send(self):
        reader,target,certificate=self.future_exchange()
        reader.recording_exchange('node-2','node-2',target,certificate,{},9)
        with self.assertRaisesRegex(ValueError,'^joining future local ACK before send$'):
            reader.recording_exchange('node-2','node-2',target,certificate,{},15)

    def test_future_exchange_binds_original_proposer_certificate_and_target(self):
        for change in ('proposer','certificate','target'):
            reader,target,certificate=self.future_exchange()
            for row in reader.base.rows:
                if change=='proposer':row['request']['sender']['node']='node-1'
                elif change=='certificate':row['request']['payload']['certificate']='f'*64
                else:row['request']['payload']['peer']=dict(node='node-3')
            with self.assertRaisesRegex(ValueError,'^joining future original recording exchange$'):
                reader.recording_exchange('node-2','node-2',target,certificate,{},9)

    def test_future_remote_ack_requires_exact_derived_bytes_revision_and_force_interval(self):
        for change in (None,'digest','revision','force','offered'):
            reader,target,certificate=self.future_exchange();row=reader.base.rows[1];tx=dict(start=22)
            if change in ('digest','revision'):row['response']['payload'][change]='f'*64 if change=='digest' else 2
            elif change=='force':tx['start']=20
            elif change=='offered':row['offered']=23
            if change is None:reader.recording_exchange('node-4','node-2',target,certificate,tx,25)
            else:
                with self.assertRaisesRegex(ValueError,'^joining future remote ACK after force$'):
                    reader.recording_exchange('node-4','node-2',target,certificate,tx,25)

    def recording(self):
        reader=lf.JoiningSameViewLearnerTest().reader([dict(event='OTHER') for _ in range(80)])
        for index,node in ((10,'node-1'),(20,'node-2'),(30,'node-3')):reader.events[index]=dict(event=p.learner.RETURNS[0],node=node)
        def row(peer,sent,received,offered):
            return dict(kind='LEARNER_RETENTION_INTENT',sent=sent,received=received,offered=offered,delivered=40,
                        request=dict(sender=dict(node='node-1',storage='original'),recipient=dict(node=peer),trace='round-1',
                                     view=dict(old=['node-1','node-2','node-3','node-4']),ballot=dict(counter=3),payload=dict(request='a'*64)))
        rows=[row('node-2',15,18,22),row('node-3',16,28,32)]
        def current(node,start,end):
            if end is None or not 0<=start<=end<60:raise ValueError('outside original generation')
            return dict(node=node,start=0,end=60,path=node)
        reader.base=SimpleNamespace(rows=rows,current=Mock(side_effect=current))
        return reader

    def test_two_remote_recordings_consume_the_one_local_write_only_once(self):
        reader=self.recording();actions=reader.recording_actions()
        self.assertEqual([(10,'node-1'),(20,'node-2'),(30,'node-3')],[(at,args[0]) for at,_,args in actions])
        self.assertEqual((0,15),actions[0][2][-2:]);self.assertEqual((18,22),actions[1][2][-2:])
        self.assertEqual((28,32),actions[2][2][-2:])
        self.assertEqual([],reader.steps)

    def test_recording_uses_earliest_send_not_row_order(self):
        reader=self.recording();reader.base.rows.reverse();actions=reader.recording_actions()
        self.assertEqual(15,actions[0][2][-1]);self.assertEqual('node-2',actions[1][2][0])

    def test_late_or_undelivered_reply_does_not_move_original_force_to_new_generation(self):
        for delivered in (None,70):
            reader=self.recording();reader.base.rows[-1]['delivered']=delivered
            self.assertEqual(3,len(reader.recording_actions()))
            reader.base.current.assert_any_call('node-1',15,16)

    def test_mixed_round_context_and_duplicate_remote_voter_are_rejected(self):
        for field in ('sender','view','ballot','payload','duplicate','local'):
            reader=self.recording();q=reader.base.rows[-1]['request']
            if field=='sender':q[field]['storage']='changed'
            elif field in ('view','ballot','payload'):q[field]=dict(changed=True)
            else:q['recipient']['node']='node-2' if field=='duplicate' else 'node-1'
            reason='duplicate original recording voter' if field in ('duplicate','local') else 'mixed original recording round'
            with self.assertRaisesRegex(ValueError,'^joining learner '+reason+'$'):reader.recording_actions()

    def test_recording_cannot_cross_sending_generation(self):
        reader=self.recording();reader.base.rows[-1]['sent']=65
        with self.assertRaisesRegex(ValueError,'^outside original generation$'):reader.recording_actions()

    def test_actual_joiner_write_scope_remains_required(self):
        before,after=lf.JoiningSameViewLearnerTest().ledger()
        for joining in ('node-5','node-6'):
            states=[p.learner.learner.decode(v) for v in (before,after)]
            for state in states:state['owner']=dict(state['owner'],node=joining)
            first=p.learner.learner.frame(states[0]);states[1]['previous']=p.learner.sha(first);last=p.learner.learner.frame(states[1])
            for scope in ('continuation-owner','initial-owner'):
                reader=lf.JoiningSameViewLearnerTest().reader();reader.model.joining=joining;reader.state={joining:first}
                reader.tx=[dict(node=joining,scope=scope,start=1,end=7)]
                if scope=='continuation-owner':reader.change(joining,last,0,8,'selected');self.assertEqual({1},reader.used)
                else:
                    with self.assertRaisesRegex(ValueError,'^joining learner original write owner$'):reader.change(joining,last,0,8,'selected')

    def test_original_peer_failure_prevents_both_layers_and_mutations(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.peer,'validate',side_effect=ValueError('invalid original')), \
             patch.object(p,'FutureReplay') as future,patch.object(p,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused','5-REPLACE')
            future.assert_not_called();pool.assert_not_called()

    def test_validation_counts_actual_joiner_writes_and_keeps_remaining_gates_open(self):
        reader=SimpleNamespace(model=SimpleNamespace(joining='node-6'),steps=[dict(node='node-6'),dict(node='node-1')],run=Mock(return_value={}))
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.peer,'validate',return_value={}), \
             patch.object(p,'FutureReplay'),patch.object(p,'LearnerReplay',return_value=reader):
            result=p.validate('/unused','5-REPLACE')
            self.assertEqual(1,result['joiningLearnerWrites'])
            for key in ('ballotCompositionQualified','allMembershipProfilesQualified','processDeathQualified','phase3Complete'):self.assertIs(False,result[key])
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.peer,'validate'), \
             patch.object(p,'FutureReplay'),patch.object(p,'LearnerReplay',return_value=reader):
            with self.assertRaisesRegex(ValueError,'^joining profile ledgers original changed$'):p.validate('/unused','5-REPLACE')

    def negative(self,change=None,error=None,accepted=False,missing=False):
        before=dict(files={'events.json':'a','wire.json':'b','original':'c'},directories=['empty']);after=copy.deepcopy(before)
        events=[dict(node='node-1',event='CURRENT_VALIDATED')];changed=copy.deepcopy(events)
        if change=='file':after['files']['wire.json']='changed'
        elif change=='directory':after['directories']=[]
        elif change=='event':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
        name='write-force-missing';reader=Mock();reader.run.side_effect=None if accepted else ValueError(error or p.future.NEGATIVES[name])
        with patch.object(p.shutil,'copytree'),patch.object(p.future,'mutate',side_effect=StopIteration if missing else None), \
             patch.object(p.collection,'inventory',return_value=after),patch.object(p.collection,'read_json',side_effect=[events,changed]), \
             patch.object(p,'FutureReplay',return_value=reader):return p.negative('/unused',before,'4-ADD','future',name)

    def test_negative_preserves_wire_files_directories_and_other_observations(self):
        for change,reason in [('file','original files'),('directory','original files'),('event','other observations')]:
            with self.assertRaisesRegex(ValueError,'^joining profile ledger negative changed '+reason+'$'):self.negative(change)

    def test_missing_target_unrelated_rejection_and_accepted_mutation_are_failures(self):
        for kw,reason in [(dict(missing=True),'missing negative target'),(dict(error='unrelated'),'unrelated ledger negative'),(dict(accepted=True),'mutation accepted')]:
            with self.assertRaisesRegex(ValueError,reason):self.negative(**kw)
        self.assertEqual('REJECTED',self.negative()['status'])

    def test_only_absent_joiner_write_is_inapplicable_and_not_counted_as_rejection(self):
        for writes in (0,2):
            with patch.object(p,'validate',return_value=dict(joiningLearnerWrites=writes)),patch.object(p.collection,'inventory',return_value={}), \
                 patch.object(p,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(p,'negative',side_effect=lambda root,before,profile,stage,name:dict(stage=stage,case=name,status='REJECTED')) as negative:
                result=p.qualify('/unused','3-REPLACE',workers=2)
            self.assertEqual(45-(writes==0),result['rejected']);self.assertEqual(int(writes==0),result['notApplicable'])
            self.assertEqual(45,len(result['negatives']));self.assertEqual(result['rejected'],negative.call_count)

    def test_worker_bounds_fail_before_original_and_worker_failure_cannot_pass(self):
        for workers in (0,5,True,1.5):
            with patch.object(p,'validate') as validate,self.assertRaisesRegex(ValueError,'^joining profile ledger replay workers$'):p.qualify('/unused','4-ADD',workers=workers)
            validate.assert_not_called()
        with patch.object(p,'validate',return_value=dict(joiningLearnerWrites=0)),patch.object(p.collection,'inventory',return_value={}), \
             patch.object(p,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(p,'negative',side_effect=ValueError('original target missing')):
            with self.assertRaisesRegex(ValueError,'^joining profile ledger negative matrix failed$'):p.qualify('/unused','3-REPLACE')


if __name__=='__main__':unittest.main()
