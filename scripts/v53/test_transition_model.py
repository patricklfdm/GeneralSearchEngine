"""State-machine, local adoption, persistence and independent-oracle regressions."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import ballot_model as b
from . import transition_model as t
from . import transition_research as r
from .membership_model import NODES

OLD=NODES[:3]
NEW=NODES[:4]


def ready_intent(world, chain, target=NEW):
    votes=r.quorums(world.authority(OLD[0]))[0]
    handle=world.start(votes[0],t.Entry('INTENT','A',target))
    r.exchange(world,handle,'prepare',votes);world.select(handle)
    r.exchange(world,handle,'accept',votes);r.exchange(world,handle,'proof',votes)
    return handle,chain+(world.certificate(handle),)


def check(world):
    return t.check_history(world.root,world.initial,world.events)


class TransitionModelTest(unittest.TestCase):
    def test_add_remove_and_replace_profiles_recover_both_transition_boundaries(self):
        for before,after in r.PROFILES:
            old=NODES[:before];new=NODES[:after] if before!=after else NODES[1:after+1]
            for boundary in ('intent','final'):
                with self.subTest(before=before,after=after,boundary=boundary):
                    world,result=r.scenario(old,new,boundary,'proof-partial')
                    self.assertEqual(4,result['longestPrefix'])
                    self.assertEqual(new,world.authority(new[0]).old)
                    self.assertEqual('stable',world.authority(new[0]).stage)

    def test_all_force_cuts_preserve_or_reselect_intent_as_required(self):
        for cut in r.CUTS:
            with self.subTest(cut=cut):
                world,_=r.scenario(OLD,NEW,'intent',cut)
                selected=t.Entry.read(world.nodes['node-1'].chain[1].value)
                self.assertEqual('operation-B' if cut in
                    ('prepare-staged','prepare-forced','accept-staged') else 'operation-A',selected.operation)

    def test_competing_targets_use_the_same_slot_and_recover_chosen_intent(self):
        world=t.World(OLD);chain=r.commit(world,(),t.Entry('DATA',payload='before'))
        a=world.start('node-1',t.Entry('INTENT','A',NEW))
        r.exchange(world,a,'prepare',('node-1','node-2'));world.select(a)
        r.exchange(world,a,'accept',('node-1','node-2'))
        other=('node-1','node-2','node-5')
        c=world.start('node-3',t.Entry('INTENT','B',other))
        self.assertEqual(a[0],c[0]);self.assertIs(world.slots[a[0]],world.slots[c[0]])
        r.exchange(world,c,'prepare',('node-2','node-3'))
        self.assertEqual(t.Entry('INTENT','A',NEW),world.select(c))
        r.exchange(world,c,'accept',('node-2','node-3'));r.exchange(world,c,'proof',('node-2','node-3'))
        chain+=(world.certificate(c),);r.install_all(world,chain)
        self.assertEqual('A',world.authority('node-4').operation)
        check(world)

    def test_no_pipeline_before_predecessor_has_both_durable_certificates(self):
        world=t.World(OLD);handle=world.start('node-1',t.Entry('INTENT','A',NEW))
        r.exchange(world,handle,'prepare',('node-1','node-2'));world.select(handle)
        r.exchange(world,handle,'accept',('node-1','node-2'))
        with self.assertRaisesRegex(ValueError,'quorum'):world.certificate(handle)
        self.assertEqual('stable',world.authority('node-1').stage)
        with self.assertRaisesRegex(ValueError,'stable entry'):world.start('node-1',t.Entry('FINAL','A',NEW))
        with self.assertRaisesRegex(ValueError,'not current voter'):world.start('node-4',t.Entry('DATA'))
        check(world)

    def test_unforced_prefix_does_not_admit_learner_after_restart(self):
        world=t.World(OLD);_,chain=ready_intent(world,())
        world.install('node-4',chain);world.crash('node-4');world.restart('node-4')
        self.assertEqual((),world.nodes['node-4'].chain)
        with self.assertRaisesRegex(ValueError,'not current voter'):world.start('node-4',t.Entry('DATA'))
        world.install('node-4',chain);world.force_install('node-4')
        world.crash('node-4');world.restart('node-4')
        handle=world.start('node-4',t.Entry('FINAL','A',NEW))
        self.assertEqual('joint',handle[0].stage)
        check(world)

    def test_prefix_installation_serializes_with_pending_votes(self):
        world=t.World(OLD);handle=world.start('node-1',t.Entry('DATA',payload='x'))
        request=world.send(handle,'prepare',('node-2',))[0]
        world.deliver(handle[0],request)
        with self.assertRaisesRegex(ValueError,'busy'):world.install('node-2',())
        world.crash('node-2');world.restart('node-2')
        world.install('node-2',())
        another=world.send(handle,'prepare',('node-2',))[0]
        self.assertFalse(world.deliver(handle[0],another))
        world.force_install('node-2');check(world)

    def test_joint_rejects_unrelated_intent_data_and_barrier(self):
        world=t.World(OLD);_,chain=ready_intent(world,());r.install_all(world,chain)
        for entry in (t.Entry('DATA'),t.Entry('BARRIER'),t.Entry('INTENT','B',NEW),
                      t.Entry('FINAL','wrong',NEW),t.Entry('FINAL','A',NODES[:5])):
            with self.subTest(entry=entry),self.assertRaisesRegex(ValueError,'matching FINAL'):
                world.start('node-1',entry)
        handle=world.start('node-1',t.Entry('FINAL','A',NEW))
        self.assertEqual(2,handle[0].index);check(world)

    def test_removed_leader_and_lagging_old_quorum_cannot_resume_service(self):
        target=('node-1','node-2','node-4');world=t.World(OLD)
        _,chain=ready_intent(world,(),target)
        r.install_all(world,chain,('node-1','node-2','node-4'))
        handle=world.start('node-1',t.Entry('FINAL','A',target))
        r.exchange(world,handle,'prepare',('node-1','node-2'));world.select(handle)
        r.exchange(world,handle,'accept',('node-1','node-2'));r.exchange(world,handle,'proof',('node-1','node-2'))
        chain+=(world.certificate(handle),);r.install_all(world,chain,('node-1','node-2','node-4'))
        # Node 3 still has genesis and attempts an old-era DATA at index 1.
        stale=world.start('node-3',t.Entry('DATA',payload='stale'))
        for request in world.send(stale,'prepare',OLD):
            node=world.slots[stale[0]].messages[request].voter
            if world.deliver(stale[0],request):
                world.force(stale[0],node);world.deliver(stale[0],world.slots[stale[0]].next_message)
        with self.assertRaisesRegex(ValueError,'prepare quorum'):world.select(stale)
        world.install('node-3',chain);world.force_install('node-3')
        with self.assertRaisesRegex(ValueError,'not current voter'):world.start('node-3',t.Entry('DATA'))
        check(world)

    def test_certificate_witness_variants_do_not_change_log_identity(self):
        world=t.World(OLD);handle=world.start('node-1',t.Entry('INTENT','A',NEW))
        for phase in ('prepare','accept','proof'):
            r.exchange(world,handle,phase,OLD)
            if phase=='prepare':world.select(handle)
        full=world.certificate(handle)
        left=replace(full,accepts=full.accepts[:2],proofs=full.proofs[:2])
        right=replace(full,accepts=full.accepts[1:],proofs=full.proofs[1:])
        world.verify(left);world.verify(right)
        self.assertNotEqual(left,right);self.assertEqual(left.entry_id,right.entry_id)
        world.install('node-1',(left,));world.force_install('node-1')
        world.install('node-2',(right,));world.force_install('node-2')
        self.assertEqual(world.authority('node-1'),world.authority('node-2'))
        check(world)

    def test_reproof_on_new_ballot_preserves_parent_identity(self):
        world=t.World(OLD);handle,chain=ready_intent(world,())
        previous=chain[0]
        again=world.start('node-3',t.Entry('INTENT','B',('node-1','node-2','node-5')))
        r.exchange(world,again,'prepare',('node-2','node-3'));world.select(again)
        r.exchange(world,again,'accept',('node-2','node-3'));r.exchange(world,again,'proof',('node-2','node-3'))
        current=world.certificate(again)
        self.assertNotEqual(previous.ballot,current.ballot)
        self.assertEqual(previous.entry_id,current.entry_id)
        world.install('node-1',(previous,));world.force_install('node-1')
        world.install('node-2',(current,));world.force_install('node-2')
        self.assertEqual(world.authority('node-1'),world.authority('node-2'));check(world)

    def test_full_chain_rejects_missing_ancestors_and_foreign_certificates(self):
        world=t.World(OLD);chain=r.commit(world,(),t.Entry('DATA',payload='first'))
        _,chain=ready_intent(world,chain)
        t.fold(world.root,OLD,chain,world.verify)
        cert=chain[-1]
        wrong=replace(cert,authority=replace(cert.authority,root='foreign'))
        mutations=[chain[1:],tuple(reversed(chain)),chain[:-1]+(wrong,),
                   chain[:-1]+(replace(cert,accepts=cert.accepts[:1]),),
                   chain[:-1]+(replace(cert,proofs=cert.proofs[:1]),),
                   chain[:-1]+(replace(cert,proofs=(cert.proofs[0],)*2),),
                   chain[:-1]+(replace(cert,proofs=cert.accepts),),
                   chain[:-1]+(replace(cert,ballot=replace(cert.ballot,counter=99)),),
                   chain[:-1]+(replace(cert,value=t.Entry('INTENT','other',NEW).value()),)]
        for changed in mutations:
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                t.fold(world.root,OLD,changed,world.verify)
        check(world)

    def test_prefix_cannot_regress_and_transfer_preserves_promises(self):
        world=t.World(OLD);chain=r.commit(world,(),t.Entry('DATA',payload='first'))
        promise=world.nodes['node-1'].slots[1].promise
        with self.assertRaisesRegex(ValueError,'regression'):world.install('node-1',())
        world.install('node-1',chain);world.force_install('node-1')
        world.crash('node-1');world.restart('node-1')
        self.assertEqual(promise,world.nodes['node-1'].slots[1].promise);check(world)

    def test_oracle_detects_install_before_force_mutant(self):
        world=t.World(OLD,mutant='install-before-force');_,chain=ready_intent(world,())
        world.install('node-4',chain);world.crash('node-4');world.restart('node-4')
        handle=world.start('node-4',t.Entry('FINAL','A',NEW))
        request=world.send(handle,'prepare',('node-4',))[0];world.deliver(handle[0],request)
        with self.assertRaisesRegex(b.SafetyViolation,'request without forced predecessor'):check(world)

    def test_oracle_detects_skipping_local_predecessor_mutant(self):
        world=t.World(OLD,mutant='bypass-local-prefix');_,chain=ready_intent(world,())
        world.install('node-1',chain);world.force_install('node-1')
        handle=world.start('node-1',t.Entry('FINAL','A',NEW))
        # Node 4 has not installed the intent or its prefix.
        request=world.send(handle,'prepare',('node-4',))[0];world.deliver(handle[0],request)
        with self.assertRaisesRegex(b.SafetyViolation,'request without forced predecessor'):check(world)

    def test_oracle_detects_old_only_joint_quorum_mutant(self):
        world=t.World(OLD);_,chain=ready_intent(world,());r.install_all(world,chain)
        def unsafe(authority,nodes):return len(set(nodes)&set(authority.old))>len(authority.old)//2
        with patch.object(t.Authority,'quorum',unsafe):
            handle=world.start('node-1',t.Entry('FINAL','A',NEW))
            r.exchange(world,handle,'prepare',('node-1','node-2'));world.select(handle)
            r.exchange(world,handle,'accept',('node-1','node-2'));r.exchange(world,handle,'proof',('node-1','node-2'))
            world.certificate(handle)
        with self.assertRaisesRegex(b.SafetyViolation,'chain certificate quorum'):check(world)

    def test_model_enforces_research_bounds_and_target_semantics(self):
        authority=t.genesis('root',OLD)
        for entry in (t.Entry('FINAL','x',NEW),t.Entry('INTENT','x',OLD),
                      t.Entry('INTENT','x',NODES[:5]),t.Entry('DATA','unexpected'),
                      t.Entry('DATA',payload='x'*129)):
            with self.subTest(entry=entry),self.assertRaises(ValueError):t.successor(authority,entry)
        with self.assertRaisesRegex(ValueError,'slot bound'):
            t.successor(replace(authority,index=33),t.Entry('DATA'))
        with self.assertRaisesRegex(ValueError,'chain bound'):
            t.fold('root',OLD,(None,)*33,lambda _:None)

    def test_authority_rejects_ambiguous_types_and_unjustified_view(self):
        authority=t.genesis('root',OLD)
        for fields in ({'index':True},{'generation':True},{'predecessor':'not-a-digest'},
                       {'old':tuple(reversed(OLD))},{'new':NEW},{'operation':True}):
            with self.subTest(fields=fields),self.assertRaises(ValueError):replace(authority,**fields)

    def test_serialized_examples_replay_and_invalid_original_is_not_a_negative_pass(self):
        examples={}
        for boundary in ('intent','final'):
            for cut in r.CUTS:
                world,_=r.scenario(OLD,NEW,boundary,cut)
                examples[boundary+'/'+cut]=dict(root=world.root,old=OLD,boundary=boundary,cut=cut,events=world.events)
        world,_=r.walk();examples['size-walk']=dict(root=world.root,old=OLD,events=world.events)
        raw=json.loads(t.encoded(examples))
        self.assertEqual(15,r.replay(raw)['histories'])
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay({})
        # A missing forced-prefix event must be rejected independently of live World state.
        row=raw['intent/prepare-staged']
        event=next(item for item in row['events'] if item['event']=='install-force')
        index=row['events'].index(event);row['events'].pop(index)
        with self.assertRaises(b.SafetyViolation):r.replay(raw)
        row['events'].insert(index,event)
        row['root']='wrong-history'
        with self.assertRaisesRegex(b.SafetyViolation,'forced predecessor|authority mismatch'):r.replay(raw)

    def test_size_walk_carries_full_authority_chain_across_four_operations(self):
        world,result=r.walk()
        self.assertEqual(13,result['longestPrefix']);self.assertEqual(4,world.authority('node-1').generation)
        self.assertEqual(OLD,world.authority('node-1').old)

    def test_cli_keeps_partial_evidence_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'evidence'
            cmd=[sys.executable,'-m','scripts.v53.transition_research','--output',str(output),'--max-cases','0']
            result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(2,result.returncode,result.stderr)
            original=(output/'receipt.json').read_bytes();self.assertEqual('INCOMPLETE',json.loads(original)['status'])
            again=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(0,again.returncode)
            self.assertEqual(original,(output/'receipt.json').read_bytes())

    def test_failed_case_retains_trace_and_optimized_checks_survive(self):
        with patch.object(t.World,'select',side_effect=ValueError('injected selection failure')):
            with self.assertRaisesRegex(ValueError,'injected') as failure:
                r.scenario(OLD,NEW,'intent','accept-forced')
        self.assertTrue(failure.exception.research_case['events'])
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'failed'
            with patch.object(sys,'argv',['transition_research','--output',str(output)]), \
                    patch.object(r,'run',side_effect=failure.exception),patch('builtins.print'):
                self.assertEqual(2,r.main())
            receipt=json.loads((output/'receipt.json').read_text())
            self.assertEqual('FAIL',receipt['status']);self.assertIn('failedCaseSha256',receipt)
            self.assertTrue(json.loads((output/'failed-case.json').read_text())['events'])
        code="""
from scripts.v53 import transition_model as t
try:t.successor(t.genesis('root',('node-1','node-2','node-3')),t.Entry('FINAL','x',('node-1','node-2','node-4')))
except ValueError:raise SystemExit(0)
raise SystemExit('unproven transition accepted')
"""
        result=subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
