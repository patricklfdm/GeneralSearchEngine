"""Focused continuous-ledger guards; native negative replay is separate."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_carried_transition_retention as r
from . import test_joining_peer_evidence as peer_tests


class NativeCarriedTransitionRetentionTest(unittest.TestCase):
    def opens(self):
        events=[];live={'node-1':[],'node-2':[]}
        for life in (1,2):
            opened={}
            for node in live:
                names=['CURRENT_VALIDATED',*r.peer.RESEAL,*r.future.RESEAL,'ACCEPT_ACTIVE_PARENT_FORCED','NODE_OPEN']
                events.extend(dict(node=node,event=name) for name in names);opened[node]=len(events)-1
            closed=len(events);events.append(dict(node=None,event='GROUP_CRASH' if life==1 else 'END'))
            for node in live:live[node].append((opened[node],closed))
        return SimpleNamespace(events=events,live=live)

    def test_each_original_open_has_its_own_exact_reseal(self):
        base=self.opens();rows=r.open_reseals(base)
        self.assertEqual([('node-1',1),('node-1',2),('node-2',1),('node-2',2)],[(v['node'],v['life']) for v in rows])
        self.assertEqual(['life-1-opened','life-2-opened']*2,[v['path'] for v in rows])

    def test_resumed_reseal_cannot_borrow_the_precrash_force_or_reverse_its_order(self):
        for change in ('missing','reverse','scope','before-death','after-accept'):
            base=self.opens();second=r.open_reseals(base)[1];end=second['peer']
            if change=='missing':base.events[end]['event']='missing'
            elif change=='reverse':base.events[end],base.events[end-1]=base.events[end-1],base.events[end]
            elif change=='scope':base.events[end]['scope']='old-owner'
            elif change=='before-death':base.events[end],base.events[base.live['node-1'][0][1]]=base.events[base.live['node-1'][0][1]],base.events[end]
            else:
                at=second['future'];base.events[at],base.events[at+1]=base.events[at+1],base.events[at]
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original open recovery interval|exact open reseal order'):
                r.open_reseals(base)

    def test_unknown_reseal_outside_an_owner_lifetime_is_not_ignored(self):
        base=self.opens();base.events.append(dict(node='node-9',event=r.peer.RESEAL[0]))
        with self.assertRaisesRegex(ValueError,'unbound open reseal'):r.open_reseals(base)

    def test_initial_peer_revision_comes_from_admitted_prefix_not_reopen_snapshot(self):
        for kind in ('INTENT','FINAL'):
            reader=r.PeerReplay.__new__(r.PeerReplay);reader.root=Path('/original');reader.kind=kind
            group={'node-1':{r.peer.FILE:b'prefix derived'}}
            with patch.object(r.p.t,'prelude',return_value=(SimpleNamespace(group=group),None,None)) as prelude:
                self.assertIs(group,reader.initial_states())
            prelude.assert_called_once_with(reader.root,kind)

    def test_peer_reopen_compares_exact_continuous_revision_without_reset(self):
        before,after=peer_tests.JoiningPeerEvidenceTest().ledger();reader=r.PeerReplay.__new__(r.PeerReplay)
        reader.root=Path('/original');reader.state={'node-2':after};reader.comparisons=0;reader.open_steps=[]
        row=dict(node='node-2',path='life-2-opened',life=2)
        with patch.object(r.c,'inventory',return_value={r.peer.FILE:after}):reader.reseal(row)
        with patch.object(r.c,'inventory',return_value={r.peer.FILE:before}),self.assertRaisesRegex(ValueError,'exact original ledger'):
            reader.reseal(row)
        self.assertEqual({'node-2':after},reader.state);self.assertEqual(1,len(reader.open_steps))

    def test_future_reopen_cannot_clear_existing_state(self):
        reader=r.FutureReplay.__new__(r.FutureReplay);reader.root=Path('/original');reader.callbacks=set();reader.open_steps=[];reader.comparisons=0
        reader.state={'node-2':dict(meta={'revision':3},raw=b'forced target',records={'certificate':b'original'})}
        row=dict(node='node-2',path='life-2-opened',life=2,futureEvents=[10,11])
        with patch.object(r.c,'inventory',return_value={r.future.future.FILE:b'forced target'}):reader.reseal(row)
        before=deepcopy(reader.state)
        with patch.object(r.c,'inventory',return_value={r.future.future.FILE:b'reset'}),self.assertRaisesRegex(ValueError,'exact continuous ledger'):
            reader.reseal(row)
        self.assertEqual(before,reader.state);self.assertEqual({10,11},reader.callbacks)

    def peer_write(self):
        before,after=peer_tests.JoiningPeerEvidenceTest().ledger();reader=r.PeerReplay.__new__(r.PeerReplay)
        reader.tx=[dict(node='node-2',start=2,end=8,scope=None)];reader.steps=[];reader.used=set();reader.live={'node-2':[(0,10),(20,30)]}
        return reader,(before,after,'observe:node-3')

    def test_peer_write_requires_one_original_owner_lifetime_and_exact_predecessor(self):
        reader,change=self.peer_write();reader.sequence('node-2',[change],0,30,'maintenance');self.assertEqual(1,len(reader.steps))
        for mutation in ('death','owner','predecessor'):
            reader,change=self.peer_write()
            if mutation=='death':reader.tx[0]['end']=22
            elif mutation=='owner':reader.tx[0]['scope']='foreign'
            else:
                state=r.peer.peers.decode(change[1]);state['previous']='a'*64
                change=(change[0],r.peer.peers.frame(state),change[2])
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'write crosses owner death|original write owner|exact revision chain'):
                reader.sequence('node-2',[change],0,30,'maintenance')

    def test_future_transaction_cannot_span_death_or_reuse_a_write(self):
        reader=r.FutureReplay.__new__(r.FutureReplay);reader.model=SimpleNamespace(joining=None);reader.used=set()
        reader.base=SimpleNamespace(live={'node-2':[(0,10),(20,30)]});reader.tx=[dict(node='node-2',start=2,end=8,scope=None)]
        reader.transaction('node-2',0,30)
        with self.assertRaisesRegex(ValueError,'original write owner'):reader.transaction('node-2',0,30)
        reader.used.clear();reader.tx[0]['end']=22
        with self.assertRaisesRegex(ValueError,'write crosses owner death'):reader.transaction('node-2',0,30)

    def test_remote_future_ack_binds_original_target_certificate_revision_and_forced_bytes(self):
        target=dict(node='node-3',storage='original');certificate=b'original certificate'
        row=dict(kind='FUTURE_RETENTION_INTENT',received=9,offered=14,request=dict(sender={'node':'node-1'},
            recipient={'node':'node-2'},payload=dict(certificate=r.sha(certificate),peer=target)),
            response=dict(payload=dict(revision=7,digest=r.sha(b'forced ledger'))))
        for change in (None,'target','certificate','revision','digest','early-response','late-receive'):
            value=deepcopy(row);reader=r.FutureReplay.__new__(r.FutureReplay)
            reader.state={'node-2':dict(meta={'revision':7},raw=b'forced ledger')};reader.base=SimpleNamespace(rows=[value])
            if change=='target':value['request']['payload']['peer']['storage']='other'
            elif change=='certificate':value['request']['payload']['certificate']='0'*64
            elif change=='revision':value['response']['payload']['revision']=6
            elif change=='digest':value['response']['payload']['digest']='0'*64
            elif change=='early-response':value['offered']=12
            elif change=='late-receive':value['received']=11
            if change is None:reader.recording_exchange('node-2','node-1',target,certificate,dict(start=10,end=12),13)
            else:
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original recording exchange|remote ACK after force'):
                    reader.recording_exchange('node-2','node-1',target,certificate,dict(start=10,end=12),13)

    def test_proposer_record_completes_before_any_target_dispatch(self):
        target=dict(node='node-2',storage='original');certificate=b'original certificate'
        rows=[dict(kind='FUTURE_RETENTION_INTENT',sent=at,request=dict(sender={'node':'node-1'},recipient={'node':node},
            payload=dict(certificate=r.sha(certificate),peer=target))) for node,at in (('node-2',14),('node-3',20))]
        reader=r.FutureReplay.__new__(r.FutureReplay);reader.base=SimpleNamespace(rows=rows)
        reader.recording_exchange('node-1','node-1',target,certificate,dict(start=10,end=12),13)
        rows[1]['sent']=12
        with self.assertRaisesRegex(ValueError,'local ACK before send'):
            reader.recording_exchange('node-1','node-1',target,certificate,dict(start=10,end=12),13)

    def test_component_scope_does_not_claim_transient_bytes_or_cohort(self):
        with patch.object(r,'PeerReplay'),patch.object(r,'FutureReplay'):result=r.replay('/original','FINAL')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['retentionRevisionCompositionQualified'])
        for name in ('transientBytesCaptured','coreScratchInventoryReplay','cohortAdmitted','phase3Complete'):self.assertFalse(result[name])

    def test_invalid_original_prevents_both_positive_and_negative_credit(self):
        with patch.object(r.x.process.collection,'inventory',return_value={}),patch.object(r.m,'validate',side_effect=ValueError('bad original')),\
                patch.object(r,'replay') as replay,patch.object(r,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/original')
            replay.assert_not_called();negative.assert_not_called()

    def test_mutated_original_after_replay_is_not_a_pass(self):
        with patch.object(r.x.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(r.m,'validate',return_value=dict(maintenance={'kind':'FINAL'})),patch.object(r,'replay'):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/original')

    def test_negatives_protect_wire_child_actions_and_exact_component_reason(self):
        before=dict(files={'ledger':'a','wire.json':'w','events.json':'e'},directories=['empty'])
        for change in ('file','directory','child','event','wrong-reason','accepted','correct'):
            after=deepcopy(before);reason=r.NEGATIVES['future']['unbound-write']
            if change=='file':after['files']['wire.json']='changed'
            elif change=='directory':after['directories']=[]
            with ExitStack() as stack:
                for obj,name,kw in ((r.shutil,'copytree',{}),(r,'mutate',{}),(r.x.process.collection,'inventory',dict(return_value=after)),
                    (r,'non_target',dict(side_effect=[[1],[2] if change=='child' else [1]])),
                    (r.x.process,'read',dict(side_effect=[[dict(event='NODE_OPEN')],[dict(event='OTHER' if change=='event' else 'NODE_OPEN')]]))):
                    stack.enter_context(patch.object(obj,name,**kw))
                reader=stack.enter_context(patch.object(r,'FutureReplay'))
                reader.return_value.run.side_effect=None if change=='accepted' else ValueError('wrong' if change=='wrong-reason' else reason)
                if change=='correct':self.assertEqual(reason,r.negative('/original','FINAL',before,'future','unbound-write')['reason'])
                else:
                    expected={'file':'physical or wire inputs','directory':'physical or wire inputs','child':'other observations',
                              'event':'other observations','wrong-reason':'wrong negative','accepted':'accepted mutation'}[change]
                    with self.subTest(change=change),self.assertRaisesRegex(ValueError,expected):r.negative('/original','FINAL',before,'future','unbound-write')


if __name__=='__main__':unittest.main()
