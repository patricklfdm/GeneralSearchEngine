"""Checkpoint boundaries, authority loss, retention, and unsafe implementations."""
from dataclasses import replace
import gzip
import io
from contextlib import redirect_stdout
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import ballot_model as b
from . import transition_model as t
from . import transition_research as tr
from . import recovery_model as m
from . import recovery_oracle as o
from . import recovery_research as r
from .membership_model import NODES


def setup(before=3,after=4,view='joint',tail=True,mutant=None):
    source,owner=r.fixture(before,after,view,tail)
    return m.Store(source,owner,mutant=mutant),o.Input(source.root,source.initial,source.world.events)


def through(store, boundary):
    for cut in r.steps(store):
        if cut==boundary:return
    raise ValueError('unknown boundary: '+boundary)


def packet_for(store, owner):
    if owner==store.owner:return store.current()
    original=m.Store(store.source,owner).current()
    return replace(original,generation='b-1',snapshot=original.chain,suffix=())


class RecoveryModelTest(unittest.TestCase):
    def test_every_force_boundary_in_old_joint_and_new_views(self):
        for view in r.VIEWS:
            for tail in (False,True):
                store,oracle=setup(view=view,tail=tail);cuts=[]
                for cut in r.steps(store):
                    with self.subTest(view=view,tail=tail,cut=cut):
                        observed=r.crash_copy(store);oracle.check(observed.events)
                        self.assertEqual(bool(observed.current().tail),tail);cuts.append(cut)
                self.assertIn('retirement-staged',cuts)
                self.assertEqual(3,oracle.check(r.crash_copy(store).events)['deletedFiles'])

    def test_no_authority_elision_or_latest_configuration_shortcut(self):
        store,_=setup(view='new');packet=store.current()
        short=replace(packet,snapshot=(),suffix=packet.chain[-1:])
        with self.assertRaisesRegex(ValueError,'authority/predecessor'):store.source.validate(short)
        foreign=replace(packet,snapshot=(replace(packet.chain[0],authority=replace(packet.chain[0].authority,root='foreign')),),suffix=packet.chain[1:])
        with self.assertRaisesRegex(ValueError,'authority/predecessor'):store.source.validate(foreign)

    def test_unresolved_acceptance_remains_owned_and_exact(self):
        store,_=setup();old=store.current();replacement=replace(old,generation='b-1',snapshot=old.chain,suffix=())
        for tail in (None,replace(old.tail,value='other'),replace(old.tail,owner='node-6'),
                     replace(old.tail,authority=replace(old.tail.authority,index=old.tail.authority.index+1))):
            with self.subTest(tail=tail),self.assertRaises(ValueError):store.begin(replace(replacement,tail=tail))
        self.assertEqual({'a'},set(store.files))

    def test_local_source_must_be_exact_selected_packet(self):
        store,_=setup();through(store,'selector-forced')
        view=store.source.validate(store.current());votes=tr.quorums(view)[0]
        packets=[packet_for(store,n) for n in votes]
        packets[0]=replace(packets[0],generation='a-0')
        with self.assertRaisesRegex(ValueError,'exact local'):store.prepare_floor(packets)

    def test_joint_floor_requires_both_majorities(self):
        for before,after,votes in ((3,4,NODES[:2]),(4,3,NODES[:2])):
            store,_=setup(before,after);through(store,'selector-forced')
            with self.assertRaisesRegex(ValueError,'configuration quorum'):
                store.prepare_floor(tuple(packet_for(store,n) for n in votes))

    def test_removed_and_duplicate_floor_witnesses_reject(self):
        store,_=setup(3,3,'new');through(store,'selector-forced')
        with self.assertRaisesRegex(ValueError,'voter identity'):
            store.prepare_floor(tuple(packet_for(store,n) for n in ('node-1',store.owner)))
        with self.assertRaisesRegex(ValueError,'voter identity'):
            store.prepare_floor((store.current(),store.current()))

    def test_incomplete_sources_cannot_force_floor(self):
        store,_=setup();through(store,'floor-staged')
        store.force_source(store.owner,'snapshot')
        with self.assertRaisesRegex(ValueError,'complete files|seal before files'):store.force_source(store.owner,'seal')
        with self.assertRaisesRegex(ValueError,'incomplete durable floor'):store.force_floor()
        store.crash();store.reopen()
        self.assertIsNone(store.floor);self.assertEqual({},store.floor_copies)
        with self.assertRaisesRegex(ValueError,'durable floor'):store.stage_retirement()

    def test_floor_materializes_source_inventory_once(self):
        store,_=setup();through(store,'selector-forced')
        votes=tr.quorums(store.source.validate(store.current()))[0]
        store.prepare_floor(packet_for(store,n) for n in votes)
        self.assertEqual(votes,tuple(p.owner for p in store.floor_plan))
        with self.assertRaisesRegex(ValueError,'incomplete durable floor'):store.force_floor()

    def test_missing_or_corrupt_selected_generation_fails_closed(self):
        for kind in ('absent-selector','absent-file','corrupt-file'):
            store,_=setup();through(store,'selector-forced')
            if kind=='absent-selector':store.selector=None
            elif kind=='absent-file':del store.files['b']['journal']
            else:store.files['b']['seal']=b'corrupt'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'active'):store.reopen()
            self.assertIn('a',store.files)  # Old bytes cannot authorize fallback.

    def test_no_selector_without_complete_forced_files(self):
        store,_=setup();through(store,'generation-snapshot')
        with self.assertRaisesRegex(ValueError,'complete generation'):store.stage_selector()
        with self.assertRaisesRegex(ValueError,'complete files'):store.force_file('seal')

    def test_retirement_staging_is_not_deletion_authority(self):
        store,oracle=setup();through(store,'retirement-staged');store.crash();store.reopen()
        with self.assertRaisesRegex(ValueError,'durable retirement'):store.delete_file('snapshot')
        store.stage_retirement();store.force_retirement();store.delete_file('snapshot')
        oracle.check(r.crash_copy(store).events)

    def test_partial_deletion_resumes_from_exact_retained_inventory(self):
        store,oracle=setup();through(store,'delete-snapshot');store.crash();store.reopen()
        store.delete_file('journal');store.crash();store.reopen();store.delete_file('seal')
        store.delete_directory();store.clear_retirement();store.crash();store.reopen()
        self.assertEqual(3,oracle.check(store.events)['deletedFiles']);self.assertEqual({'b'},set(store.files))

    def test_changed_retirement_bytes_or_lost_floor_prevent_delete(self):
        for kind in ('retired-file','source-file','floor-id'):
            store,_=setup();through(store,'retirement-forced')
            if kind=='retired-file':store.files['a']['journal']=b'changed'
            elif kind=='source-file':store.floor_copies[store.owner]['snapshot']=b'changed'
            else:store.floor=('0'*64,store.floor[1])
            with self.subTest(kind=kind),self.assertRaises(ValueError):store.delete_file('snapshot')

    def test_retirement_identity_blocks_reuse_even_after_directory_removal(self):
        store,oracle=setup();through(store,'delete-directory')
        next_packet=replace(store.current(),generation='a-2')
        with self.assertRaisesRegex(ValueError,'still owned'):store.begin(next_packet)
        store.crash();store.reopen()
        with self.assertRaisesRegex(ValueError,'still owned'):store.begin(next_packet)
        store.clear_retirement();store.begin(next_packet)
        oracle.check(r.crash_copy(store).events)

    def test_new_generation_cannot_reuse_a_retired_generation_identity(self):
        store,_=setup();old=store.current();through(store,'retirement-cleared')
        with self.assertRaisesRegex(ValueError,'generation'):store.begin(old)
        store.begin(replace(store.current(),generation='a-2'))

    def test_frozen_basis_and_advanced_root_promise_survive_retirement(self):
        store,oracle=setup();before=store.promise;basis=store.basis
        through(store,'retirement-cleared');store.crash();store.reopen()
        self.assertGreater(store.promise,before);self.assertEqual(basis,store.basis);oracle.check(store.events)

    def test_capacity_refusals_leave_active_generation_intact(self):
        store,_=setup();original=store.current();packet=replace(original,generation='b-1',snapshot=original.chain,suffix=())
        with patch.object(m,'MAX_PACKET_BYTES',1),self.assertRaisesRegex(ValueError,'packet byte capacity'):
            store.source.validate(packet)
        with patch.object(m,'MAX_RETAINED_BYTES',store.usage()),self.assertRaisesRegex(ValueError,'retained byte capacity'):
            store.begin(packet)
        self.assertEqual({'a'},set(store.files));self.assertEqual(original,store.current())

    def test_actual_certificate_and_change_limits_reject_without_truncation(self):
        world=t.World(NODES[:3]);chain=()
        for index in range(m.MAX_CERTIFICATES+1):chain=tr.commit(world,chain,t.Entry('DATA',payload=str(index)))
        with self.assertRaisesRegex(ValueError,'certificate capacity'):m.Store(m.AuthoritySource(world),'node-1')
        world=t.World(NODES[:3]);chain=()
        for index in range(m.MAX_CHANGES+1):
            target=NODES[:4] if index%2==0 else NODES[:3];operation='op-'+str(index)
            chain=tr.commit(world,chain,t.Entry('INTENT',operation,target))
            chain=tr.commit(world,chain,t.Entry('FINAL',operation,target))
        with self.assertRaisesRegex(ValueError,'history capacity'):m.Store(m.AuthoritySource(world),'node-1')

    def test_five_unsafe_implementations_have_specific_oracle_failures(self):
        for mutant,reason in (('drop-tail','checkpoint loses prefix/tail'),
                              ('selector-before-force','unforced selector'),
                              ('delete-without-floor','delete without durable floor'),
                              ('reset-promise','root promise changed'),
                              ('reuse-retiring-slot','reuse of owned')):
            with self.subTest(mutant=mutant):
                correct,check=setup();through(correct,'retirement-cleared');check.check(r.crash_copy(correct).events)
                store,oracle=setup(mutant=mutant)
                if mutant=='drop-tail':
                    old=store.current();store.begin(replace(old,generation='b-1',snapshot=old.chain,suffix=(),tail=None))
                elif mutant=='delete-without-floor':
                    through(store,'selector-forced');store.stage_retirement();store.force_retirement();store.delete_file('snapshot')
                elif mutant=='reuse-retiring-slot':
                    through(store,'delete-directory');store.begin(replace(store.current(),generation='a-2'))
                else:through(store,'selector-staged' if mutant=='selector-before-force' else 'selector-forced')
                with self.assertRaisesRegex(b.SafetyViolation,reason):oracle.check(r.crash_copy(store).events)

    def test_portable_replay_validates_original_before_evidence_mutations(self):
        store,oracle=setup();through(store,'retirement-cleared');events=r.crash_copy(store).events
        record=dict(root=store.source.root,old=store.source.initial,sourceEvents=store.source.world.events,events=events)
        raw=json.loads(m.raw(record));decoded=r.decode(raw)
        self.assertEqual(3,o.Input(decoded['root'],decoded['old'],decoded['sourceEvents']).check(decoded['events'])['deletedFiles'])
        for kind in ('floor-force','selector-force','retirement-force','file-force','source-force'):
            changed=list(events);at=next(i for i,e in enumerate(changed) if e['event']==kind);del changed[at]
            with self.subTest(kind=kind),self.assertRaises(b.SafetyViolation):oracle.check(changed)
        changed=list(events);changed[-1]=dict(changed[-1],basis='00')
        with self.assertRaisesRegex(b.SafetyViolation,'basis'):oracle.check(changed)
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay({})
        bad=json.loads(m.raw(record));bad['root']='foreign'
        with self.assertRaises(b.SafetyViolation):
            decoded=r.decode(bad);o.Input(decoded['root'],decoded['old'],decoded['sourceEvents'])

    def test_optimized_python_keeps_rejections(self):
        code='''from scripts.v53.test_recovery_model import setup, through
store,_=setup();through(store,'selector-forced')
try:store.stage_retirement()
except ValueError:print('rejected')
else:raise RuntimeError('unsafe deletion accepted')
'''
        result=subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual('rejected',result.stdout.strip())

    def test_replay_cannot_relabel_one_tail_history_as_both_cases(self):
        examples={}
        for tail in (False,True):
            store,_=setup(tail=tail);through(store,'retirement-cleared')
            record=dict(root=store.source.root,old=store.source.initial,sourceEvents=store.source.world.events,
                        events=r.crash_copy(store).events,cut='retirement-cleared',profile=(3,4),view='joint',tail=tail)
            examples[f'3-4/joint/tail-{int(tail)}']=json.loads(m.raw(record))
        with patch.object(tr,'PROFILES',((3,4),)):
            # Keep VIEWS unchanged: it also defines the certified prefix lengths.
            with self.assertRaisesRegex(ValueError,'inventory'):r.replay(examples)
        # Complete the inventory using real cases; then forge only one coverage label.
        for view in ('old','new'):
            for tail in (False,True):
                store,_=setup(view=view,tail=tail);through(store,'retirement-cleared')
                record=dict(root=store.source.root,old=store.source.initial,sourceEvents=store.source.world.events,
                            events=r.crash_copy(store).events,cut='retirement-cleared',profile=(3,4),view=view,tail=tail)
                examples[f'3-4/{view}/tail-{int(tail)}']=json.loads(m.raw(record))
        with patch.object(tr,'PROFILES',((3,4),)):
            self.assertEqual(6,r.replay(examples)['histories'])
            examples['3-4/joint/tail-0']=dict(examples['3-4/joint/tail-1'],tail=False)
            with self.assertRaisesRegex(ValueError,'coverage mismatch'):r.replay(examples)

    def test_limited_cli_is_incomplete_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'evidence'
            args=[sys.executable,'-m','scripts.v53.recovery_research','--output',str(output),'--max-cases','1']
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(2,result.returncode,result.stderr)
            data=(output/'receipt.json').read_bytes();receipt=json.loads(data)
            self.assertEqual('INCOMPLETE',receipt['status']);self.assertEqual(1,receipt['counts']['cases'])
            self.assertFalse(receipt['productionQualified'])
            self.assertEqual(1,subprocess.run(args,capture_output=True).returncode)
            self.assertEqual(data,(output/'receipt.json').read_bytes())

    def test_failed_driver_retains_original_input_and_partial_journal(self):
        def failure(store):
            yield 'initial'
            store.advance_promise(b.Ballot(store.promise.counter+1,store.owner,'failure-fixture'))
            raise ValueError('injected force failure')
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'evidence'
            with patch.object(r,'steps',failure),patch.object(sys,'argv',['research','--output',str(output)]),redirect_stdout(io.StringIO()):
                self.assertEqual(2,r.main())
            receipt=json.loads((output/'receipt.json').read_text())
            self.assertEqual('FAIL',receipt['status']);self.assertEqual('injected force failure',receipt['message'])
            data=(output/'failed-case.json.gz').read_bytes()
            self.assertEqual(m.sha(data),receipt['failedCaseSha256'])
            retained=r.decode(json.loads(gzip.decompress(data)))
            o.Input(retained['root'],retained['old'],retained['sourceEvents'])
            self.assertEqual('promise-force',retained['events'][-1]['event'])


if __name__=='__main__':unittest.main()
