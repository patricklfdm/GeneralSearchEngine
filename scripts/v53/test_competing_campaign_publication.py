"""Continuation boundaries and unsuccessful pulls; fixtures are not evidence."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import competing_campaign_publication as m
from .test_competing_node_evidence import conversation


def pulls():
    _,_,ids,_=conversation();cat=m.f.catalog()
    statement=m.f.sample(cat['records']['CHECKPOINT']['schema'],cat['types'])
    raw=m.f.encode('records','CHECKPOINT',statement)
    initial={node:{'node.gsr':m.f.encode('records','NODE',dict(root=statement['root'],identity=identity))}
             for node,identity in ids.items()}
    ballot=dict(counter=2,proposer='node-3',incarnation=ids['node-3']['storage'])
    history=SimpleNamespace(initial=initial,voters=['node-1','node-3'],selected=dict(ballot=ballot),
        snapshots={'slot-1-applied':{node:{'applied-end/statement.gsr':raw} for node in ('node-1','node-3')}})
    def request(node,trace):
        ack=m.f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter=node,
            incarnation=ids[node]['storage'],cut=statement['end'],statement=m.sha(raw)))
        return dict(ballot=ballot,sender=ids['node-1'],recipient=ids[node],sequence=1,trace=trace,
                    payload=dict(action='REQUEST',bytes='',digest=m.sha(ack),id=trace,offset=0))
    failed=request('node-2','00000000-0000-0000-0000-000000000007')
    success=request('node-3','00000000-0000-0000-0000-000000000008')
    rows=[dict(kind='PUBLISH',request=dict(recipient=ids['node-1']),received=1)]
    return history,rows,{'failed':('CHUNK',failed),'success':('CHUNK',success)},{'failed':[2,4,6],'success':[8]}


class CompetingCampaignPublicationTest(unittest.TestCase):
    def test_original_maintenance_must_pass_before_installation(self):
        with patch.object(m.p,'inventory'),patch.object(m.preceding,'Replay') as prior,patch.object(m,'selected_install') as install:
            prior.return_value.run.side_effect=ValueError('original maintenance')
            with self.assertRaisesRegex(ValueError,'^original maintenance$'):m.validate('/original')
            install.assert_not_called()

    def test_no_or_multiple_successful_activations_are_not_guessed(self):
        for events in ([],[dict(event='ROUND_INSTALLED')]*2):
            with self.subTest(events=events),patch.object(m.p,'inventory'),patch.object(m.preceding,'Replay') as prior:
                prior.return_value.events=events
                with self.assertRaisesRegex(ValueError,'one successful activation'):m.validate('/original')

    def test_future_request_sequence_reserves_local_first_for_every_leader(self):
        expected={'node-1':{'node-2':2,'node-3':3},'node-2':{'node-1':2,'node-3':3},
                  'node-3':{'node-1':2,'node-2':3}}
        for leader,peers in expected.items():
            for peer,sequence in peers.items():
                with self.subTest(leader=leader,peer=peer):
                    self.assertEqual(sequence,m.network.intent_sequence(list(reversed(expected)),leader,peer))

    def test_future_sequence_refuses_local_or_unknown_peer(self):
        for leader,peer in (('node-1','node-1'),('other','node-1'),('node-1','other')):
            with self.assertRaisesRegex(ValueError,'original remote owner'):
                m.network.intent_sequence(['node-1','node-2','node-3'],leader,peer)

    def test_unanswered_checkpoint_never_contributes_a_receipt(self):
        args=pulls();allowed,traces=m.failed_checkpoints(*args,1,0,10)
        self.assertEqual({'failed'},allowed);self.assertEqual(1,len(traces))
        # Removing the failed request cannot silently hide the scheduled first
        # owner; a successful peer is not a substitute for original attempts.
        del args[2]['failed']
        with self.assertRaisesRegex(ValueError,'missing unsuccessful checkpoint pull'):
            m.failed_checkpoints(*args,1,0,10)

    def test_checkpoint_exhaustion_is_bounded_and_precedes_fallback(self):
        for count in (1,2,4):
            args=pulls();args[3]['failed']=[2]*count
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'has no receipt'):
                m.failed_checkpoints(*args,1,0,10)
        args=pulls();args[3]['success']=[5]
        with self.assertRaisesRegex(ValueError,'fallback before exhaustion'):m.failed_checkpoints(*args,1,0,10)

    def test_unanswered_checkpoint_requires_exact_original_owner_and_statement(self):
        for key,value in (('sequence',2),('ballot',dict(counter=3,proposer='node-3'))):
            args=pulls();args[2]['failed'][1][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'has no receipt'):
                m.failed_checkpoints(*args,1,0,10)
        args=pulls();args[2]['failed'][1]['payload']['digest']='a'*64
        with self.assertRaisesRegex(ValueError,'missing unsuccessful checkpoint pull'):
            m.failed_checkpoints(*args,1,0,10)

    def test_checkpoint_receipt_or_pre_dispatch_pull_is_not_an_exhausted_attempt(self):
        args=pulls();args[1].append(dict(kind='CHUNK',request=args[2]['failed'][1]))
        with self.assertRaisesRegex(ValueError,'has no receipt'):m.failed_checkpoints(*args,1,0,10)
        args=pulls();args[1][0]['received']=3
        with self.assertRaisesRegex(ValueError,'before publication request'):m.failed_checkpoints(*args,1,0,10)

    def test_original_failure_never_counts_as_successful_negatives(self):
        with patch.object(m,'validate',side_effect=ValueError('original')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            mutate.assert_not_called()

    def test_negative_requires_its_exact_reason_and_original_inventory(self):
        for second,reason in ((ValueError('other'),'unrelated competing publication negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(m,'validate',side_effect=[{},second]), \
                    patch.object(m.preceding.prefix.collection.h,'inventory',return_value={}), \
                    patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')

    def test_shared_client_reader_preserves_legacy_nonwriting_restriction(self):
        history=SimpleNamespace(initial=dict.fromkeys(['node-1','node-2','node-3']),voters=['node-1','node-2'])
        events=[dict(node=node,event='NODE_OPEN') for node in history.initial]
        events.append(dict(node='node-3',event='PROMISE_FORCED'))
        with patch.object(m.p,'completion_lifecycle',return_value=[]):
            with self.assertRaisesRegex(ValueError,'unselected owner remains nonwriting'):
                m.p.lifecycle(Path('/original'),history,events)

    def test_shared_scratch_reader_requires_derived_outgoing_owner_set(self):
        history=SimpleNamespace(initial=dict.fromkeys(['node-1','node-2','node-3']),proposer='node-3')
        for owners in ({'node-1'},{'node-3','other'},['node-3']):
            with self.subTest(owners=owners),self.assertRaisesRegex(ValueError,'scratch outgoing owners'):
                m.p.scratch(Path('/original'),history,owners)

    def test_scratch_includes_reserved_owner_even_without_local_grant(self):
        nodes=('node-1','node-2','node-3');history=SimpleNamespace(initial=dict.fromkeys(nodes),proposer='node-3',voters=['node-1','node-3'])
        replay=SimpleNamespace(allocations=[dict(node='node-1'),dict(node='node-3')],
                              by_basis={'only-local':dict(node='node-3',ballot=dict(proposer='node-3'))})
        diagnostics=[dict(node=n,state='READY' if n=='node-3' else 'STARTING',rounds=1,losses=[],failure='') for n in nodes]
        producer=dict(status='PARTIAL',producerPassed=True,nodes=3,automaticOwners=3,defaultBounds=True,physicalReplay=False,phase3Complete=False)
        with patch.object(Path,'read_bytes',return_value=b''),patch.object(m.p.n,'read',side_effect=[producer,diagnostics]), \
                patch.object(m.p,'scratch') as scratch:
            m.closed(Path('/original'),replay,history,[dict(node=n,event='NETWORK_SEND') for n in nodes],0)
            self.assertEqual({'node-1','node-3'},scratch.call_args.args[2])


if __name__=='__main__':unittest.main()
