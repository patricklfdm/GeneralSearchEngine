"""Global durable grants, immutable source selection and publication fencing."""
from dataclasses import replace
import gzip
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import activation_model as a
from . import activation_oracle as o
from . import activation_research as r


def setup(view='old',tail=False,mutant=None):
    source,node=r.rr.fixture(3,4,view,tail)
    return a.Engine(source.world,mutant=mutant),node


def selected(mutant=None,tail=False):
    engine,node=setup(mutant=mutant,tail=tail);handle=r.begin(engine,node)
    votes=r.votes_for(engine,node);r.selected(engine,handle,votes)
    return engine,handle,votes


class ActivationModelTest(unittest.TestCase):
    def test_declared_cuts_in_each_view_with_and_without_tail(self):
        for view in r.rr.VIEWS:
            for tail in (False,True):
                for cut in r.CUTS:
                    with self.subTest(view=view,tail=tail,cut=cut):
                        _,audit=r.scenario(3,4,view,tail,cut)
                        self.assertGreaterEqual(audit['activations'],1)

    def test_allocator_force_precedes_start_and_crash_burns_reservation(self):
        engine,node=setup();first=engine.allocate(node)
        with self.assertRaisesRegex(ValueError,'unforced'):engine.start(node)
        engine.force_allocation(node);engine.crash(node);engine.restart(node)
        with self.assertRaisesRegex(ValueError,'unforced'):engine.start(node)
        second=engine.allocate(node);self.assertGreater(second.counter,first.counter)
        engine.force_allocation(node);engine.start(node);o.check(engine.evidence())

    def test_counter_exhaustion_fails_before_mutating_allocator(self):
        engine,node=setup();engine.roots[node].counter=2**63-1
        with self.assertRaisesRegex(ValueError,'ballot counter'):engine.allocate(node)
        self.assertIsNone(engine.roots[node].allocation)

    def test_no_outbound_prepare_before_own_basis_force(self):
        engine,node=setup();handle=r.begin(engine,node)
        with self.assertRaisesRegex(ValueError,'own basis'):engine.prepare(handle,'node-2')
        engine.prepare(handle,node);engine.force_grant(node)
        with self.assertRaisesRegex(ValueError,'own basis'):engine.prepare(handle,'node-2')
        engine.force_basis(node);engine.prepare(handle,'node-2');o.check(engine.evidence())

    def test_partial_basis_cannot_be_resampled_under_same_ballot(self):
        engine,node=setup();handle=r.begin(engine,node)
        engine.prepare(handle,node);engine.force_grant(node);engine.crash(node);engine.restart(node)
        with self.assertRaisesRegex(ValueError,'incomplete frozen basis'):engine.prepare(handle,node)
        new=r.begin(engine,node);self.assertGreater(new[1],handle[1]);r.prepare(engine,new,node)
        o.check(engine.evidence())

    def test_duplicate_prepare_returns_original_basis_after_acceptance(self):
        engine,handle,votes=selected();r.installed(engine,handle,votes)
        node=votes[1];basis=engine.roots[node].basis
        r.exchange(engine,handle,'accept',votes)
        self.assertIsNone(basis.accepted)
        self.assertEqual('DUPLICATE',engine.prepare(handle,node));engine.fetch(handle,node)
        self.assertEqual(basis,engine.roots[node].basis);o.check(engine.evidence())

    def test_selected_quorum_must_include_proposer_and_complete_sources(self):
        engine,node=setup();handle=r.begin(engine,node)
        for peer in ('node-1','node-2','node-3'):r.prepare(engine,handle,peer)
        with self.assertRaisesRegex(ValueError,'local basis'):engine.select(handle,('node-2','node-3'))
        with self.assertRaisesRegex(ValueError,'local basis'):engine.select(handle,('node-1','node-1'))
        engine.select(handle,('node-1','node-2'));engine.force_selection(handle)
        with self.assertRaisesRegex(ValueError,'fixed'):engine.select(handle,('node-1','node-3'))
        o.check(engine.evidence())

    def test_unfetched_source_cannot_count_and_higher_promise_invalidates_fetch(self):
        engine,node=setup();handle=r.begin(engine,node)
        r.prepare(engine,handle,node);r.prepare(engine,handle,'node-2',fetch=False)
        with self.assertRaisesRegex(ValueError,'incomplete selected'):engine.select(handle,('node-1','node-2'))
        engine.observe('node-2',a.b.Ballot(handle[1].counter+1,'node-3','future'))
        with self.assertRaisesRegex(ValueError,'unavailable'):engine.fetch(handle,'node-2')
        o.check(engine.evidence())

    def test_source_unavailable_after_selection_requires_new_ballot(self):
        engine,handle,votes=selected();engine.crash('node-2')
        with self.assertRaisesRegex(ValueError,'stale'):engine.stage_install(handle,'node-2')
        r.prepare(engine,handle,'node-3')
        with self.assertRaisesRegex(ValueError,'fixed'):engine.select(handle,('node-1','node-3'))
        fresh=r.begin(engine,'node-1');r.selected(engine,fresh,('node-1','node-3'))
        self.assertTrue(r.finish(engine,fresh,('node-1','node-3')))
        engine.restart('node-2');o.check(engine.evidence())

    def test_installation_force_and_all_selected_acks_precede_accept(self):
        engine,handle,votes=selected()
        with self.assertRaisesRegex(ValueError,'incomplete selected installation'):engine.send(handle,'accept',votes)
        engine.stage_install(handle,votes[0])
        with self.assertRaisesRegex(ValueError,'ACK unavailable'):engine.install_ack(handle,votes[0])
        engine.force_install(votes[0]);engine.install_ack(handle,votes[0])
        with self.assertRaisesRegex(ValueError,'incomplete selected installation'):engine.send(handle,'accept',votes)
        o.check(engine.evidence())

    def test_higher_promise_fences_pending_install_and_late_publication(self):
        engine,handle,votes=selected();node=votes[1]
        engine.stage_install(handle,node);engine.observe(node,a.b.Ballot(handle[1].counter+1,node,'higher'))
        with self.assertRaisesRegex(ValueError,'fenced'):engine.force_install(node)
        o.check(engine.evidence())
        engine,handle,votes=selected();r.installed(engine,handle,votes)
        r.exchange(engine,handle,'accept',votes);r.exchange(engine,handle,'proof',votes)
        engine.certify(handle);engine.stage_publication(handle)
        engine.observe(handle[1].proposer,a.b.Ballot(handle[1].counter+1,'node-3','higher'))
        with self.assertRaisesRegex(ValueError,'fenced'):engine.published(handle)
        self.assertIsNone(engine.roots[handle[1].proposer].ready);o.check(engine.evidence())

    def test_recovered_data_needs_fresh_barrier_and_callback(self):
        engine,handle,votes=selected(tail=True)
        self.assertFalse(r.finish(engine,handle,votes));self.assertIsNone(engine.roots[handle[1].proposer].ready)
        ready=r.recover_ready(engine);self.assertGreater(ready[1],handle[1])
        self.assertEqual(ready[1],engine.roots[ready[1].proposer].ready);o.check(engine.evidence())

    def test_accepted_intent_is_recovered_then_finalized_before_activation(self):
        old=r.NODES[:3];target=r.NODES[1:4];world=a.t.World(old)
        chain=r.tr.commit(world,(),a.t.Entry('DATA',payload='before'))
        handle=world.start('node-1',a.t.Entry('INTENT','carried-operation',target))
        r.tr.exchange(world,handle,'prepare',old);world.select(handle);r.tr.exchange(world,handle,'accept',old)
        engine=a.Engine(world);ready=r.recover_ready(engine)
        chain=world.nodes[ready[1].proposer].chain
        self.assertEqual(['DATA','INTENT','FINAL','BARRIER'],[a.t.Entry.read(c.value).kind for c in chain])
        self.assertEqual('carried-operation',a.t.Entry.read(chain[1].value).operation)
        self.assertEqual(1,o.check(engine.evidence())['activations'])

    def test_late_complete_basis_does_not_change_forced_selection(self):
        engine,handle,_=selected();decision=engine.campaigns[handle].decision
        r.prepare(engine,handle,'node-3')
        self.assertEqual(decision,engine.campaigns[handle].decision)
        self.assertNotIn('node-3',decision.owners)
        with self.assertRaisesRegex(ValueError,'outside selected'):engine.stage_install(handle,'node-3')
        o.check(engine.evidence())

    def test_joint_final_cannot_activate_removed_proposer(self):
        source,_=r.rr.fixture(3,3,'joint',False);engine=a.Engine(source.world)
        handle=r.begin(engine,'node-1');votes=r.votes_for(engine,'node-1')
        r.selected(engine,handle,votes);self.assertFalse(r.finish(engine,handle,votes))
        self.assertNotIn('node-1',engine.world.authority('node-1').voters)
        engine.allocate('node-1');engine.force_allocation('node-1')
        with self.assertRaisesRegex(ValueError,'ineligible'):engine.start('node-1')
        ready=r.recover_ready(engine);self.assertNotEqual('node-1',ready[1].proposer);o.check(engine.evidence())

    def test_prepare_rejects_divergent_local_view_until_explicit_sync(self):
        engine,node=setup(view='joint');handle=r.begin(engine,node);r.selected(engine,handle,r.votes_for(engine,node))
        r.finish(engine,handle,r.votes_for(engine,node))
        fresh=r.begin(engine,node);r.prepare(engine,fresh,node)
        before=engine.roots['node-2'].promise
        with self.assertRaisesRegex(ValueError,'synchronized prefix'):engine.prepare(fresh,'node-2')
        engine.sync('node-2',engine.world.nodes[node].chain)
        self.assertGreaterEqual(engine.roots['node-2'].promise,before)
        r.prepare(engine,fresh,'node-2');o.check(engine.evidence())

    def test_pending_global_basis_blocks_prefix_installation(self):
        engine,node=setup();handle=r.begin(engine,node);engine.prepare(handle,node);engine.force_grant(node)
        with self.assertRaisesRegex(ValueError,'writer busy'):engine.sync(node,engine.world.nodes[node].chain)
        engine.force_basis(node);o.check(engine.evidence())

    def test_pending_prefix_blocks_campaign_and_grant_in_reverse_order(self):
        engine,node=setup();handle=r.begin(engine,node);r.prepare(engine,handle,node)
        engine.stage_sync('node-2',engine.world.nodes[node].chain)
        with self.assertRaisesRegex(ValueError,'writer busy'):engine.prepare(handle,'node-2')
        engine.allocate('node-2');engine.force_allocation('node-2')
        with self.assertRaisesRegex(ValueError,'writer busy'):engine.start('node-2')
        engine.force_adoption('node-2');engine.complete_sync('node-2');o.check(engine.evidence())

    def test_verified_prefix_adoption_forces_root_floor_before_selector(self):
        engine,handle,votes=selected();r.finish(engine,handle,votes)
        node='node-3';chain=engine.world.nodes[handle[1].proposer].chain
        old=engine.world.nodes[node].chain;engine.stage_sync(node,chain)
        with self.assertRaisesRegex(ValueError,'durable root promise'):engine.complete_sync(node)
        engine.force_adoption(node);self.assertEqual(handle[1],engine.roots[node].promise)
        engine.crash(node);engine.restart(node)
        self.assertEqual(old,engine.world.nodes[node].chain);self.assertIsNone(engine.roots[node].basis)
        engine.sync(node,chain);self.assertEqual(chain,engine.world.nodes[node].chain)
        original=engine.evidence();o.check(original)
        mutated=dict(original,events=[e for e in original['events'] if e['event']!='adoption-force'])
        with self.assertRaises(a.b.SafetyViolation):o.check(mutated)

    def test_five_unsafe_variants_have_specific_failures(self):
        for mutant,reason in (('volatile-allocator','before durable allocation'),('resample-basis','same-ballot basis resampling'),
                              ('replace-selection','changed selected quorum'),('ignore-global-promise','crossed global promise'),
                              ('ready-after-recovery','current-ballot barrier')):
            with self.subTest(mutant=mutant):
                original,_,_=selected(tail=True);r.recover_ready(original);o.check(original.evidence())
                if mutant=='volatile-allocator':
                    engine,node=setup(mutant=mutant);engine.allocate(node);engine.start(node)
                elif mutant=='resample-basis':
                    engine,node=setup(mutant=mutant);handle=r.begin(engine,node)
                    r.prepare(engine,handle,node);node='node-2'
                    engine.prepare(handle,node);engine.force_grant(node);engine.crash(node);engine.restart(node)
                    engine.prepare(handle,node);engine.force_grant(node);engine.force_basis(node)
                elif mutant=='replace-selection':
                    engine,handle,_=selected(mutant);r.prepare(engine,handle,'node-3')
                    engine.select(handle,('node-1','node-3'));engine.force_selection(handle)
                elif mutant=='ignore-global-promise':
                    engine,handle,votes=selected(mutant);r.installed(engine,handle,votes)
                    request=engine.send(handle,'accept',('node-2',))[0]
                    contender=r.begin(engine,'node-2');engine.prepare(contender,'node-2');engine.force_grant('node-2')
                    engine.deliver(handle,request);engine.force_vote(handle,'node-2')
                else:
                    engine,handle,votes=selected(mutant,tail=True);self.assertTrue(r.finish(engine,handle,votes))
                with self.assertRaisesRegex(a.b.SafetyViolation,reason):o.check(engine.evidence())

    def test_portable_trace_and_missing_force_negatives(self):
        record,_=r.scenario(3,3,'old',True,'healthy');encoded=json.loads(a.t.encoded(record))
        original=r.decode(encoded);o.check(original)
        for kind in ('allocate-force','grant-force','basis-ready','selection-force','install-force','publication-stage'):
            changed=dict(original,events=list(original['events']))
            index=next(i for i,e in enumerate(changed['events']) if e['event']==kind);del changed['events'][index]
            with self.subTest(kind=kind),self.assertRaises(a.b.SafetyViolation):o.check(changed)
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay({})

    def test_optimized_python_keeps_allocator_boundary(self):
        code='''from scripts.v53.test_activation_model import setup
e,n=setup();e.allocate(n)
try:e.start(n)
except ValueError:print('rejected')
else:raise RuntimeError('unforced allocation accepted')
'''
        result=subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual('rejected',result.stdout.strip())

    def test_replay_rejects_wrong_size_or_relabelled_tail_coverage(self):
        examples={}
        for tail in (False,True):
            record,_=r.scenario(3,3,'old',tail,'healthy')
            examples[f'old/tail-{int(tail)}/healthy']=json.loads(a.t.encoded(record))
        with patch.object(r.rr,'VIEWS',('old',)),patch.object(r,'CUTS',('healthy',)):
            self.assertEqual(2,r.replay(examples)['histories'])
            altered=dict(examples)
            altered['old/tail-0/healthy']=dict(examples['old/tail-1/healthy'],tail=False)
            with self.assertRaisesRegex(ValueError,'coverage'):r.replay(altered)
            wrong,_=r.scenario(4,4,'old',False,'healthy')
            altered['old/tail-0/healthy']=dict(json.loads(a.t.encoded(wrong)),profile=[3,3])
            with self.assertRaisesRegex(ValueError,'coverage'):r.replay(altered)

    def test_limited_cli_nonoverwrite_and_failed_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'limited'
            command=[sys.executable,'-m','scripts.v53.activation_research','--output',str(output),'--max-cases','1']
            self.assertEqual(2,subprocess.run(command,capture_output=True).returncode)
            before=(output/'receipt.json').read_bytes();self.assertEqual('INCOMPLETE',json.loads(before)['status'])
            self.assertNotEqual(0,subprocess.run(command,capture_output=True).returncode)
            self.assertEqual(before,(output/'receipt.json').read_bytes())
            failed=Path(temp)/'failed'
            with patch.object(a.Engine,'force_grant',side_effect=ValueError('injected grant failure')),patch.object(sys,'argv',['research','--output',str(failed)]),redirect_stdout(io.StringIO()):
                self.assertEqual(2,r.main())
            receipt=json.loads((failed/'receipt.json').read_text());self.assertEqual('injected grant failure',receipt['message'])
            data=(failed/'failed-case.json.gz').read_bytes();self.assertEqual(r.hashlib.sha256(data).hexdigest(),receipt['failedCaseSha256'])
            record=r.decode(json.loads(gzip.decompress(data)));self.assertTrue(record['events'])


if __name__=='__main__':unittest.main()
