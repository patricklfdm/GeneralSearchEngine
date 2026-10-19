import copy
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from . import evidence as e,model as m,token

BINDING=dict(source='a'*40,tree='b'*64,artifacts={'candidate':'c'*64},run='local',attempt=1,process='synthetic-node-1-g1',seed=52,codec='synthetic-v1')

class FoundationTest(unittest.TestCase):
    def test_relocated_original_and_all_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'original';e.save(root,e.fixture(BINDING));expected=e.negatives(root,BINDING)
            moved=Path(temp)/'relocated';shutil.copytree(root,moved)
            with self.assertRaisesRegex(ValueError,'N15'):e.read(moved,BINDING)
            self.assertEqual(expected,e.negatives(moved,BINDING,str(root.resolve())))
            self.assertEqual([f'N{i:02}' for i in range(1,17)],[v['case'] for v in expected])
            bad=e.fixture(BINDING);bad['read']['sequence']=0;e.save(root,bad)
            with self.assertRaisesRegex(ValueError,'N07'):e.negatives(root,BINDING)

    def test_source_and_process_bindings_are_not_borrowable(self):
        for key,value in [('source','f'*40),('tree','f'*64),('artifacts',{}),('run','other'),('attempt',2),('process','other')]:
            v=e.fixture(BINDING);v['binding'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'N14'):e.validate(v,BINDING)

    def test_semantic_variants(self):
        changes=[('N06',lambda v:v['authority'].update(publications=[])),('N07',lambda v:v['read']['value'].update(ranking=[])),
                 ('N08',lambda v:v['read'].update(barrier=None)),('N10',lambda v:v['read'].update(deadline=5)),
                 ('N12',lambda v:v['read']['viewUses'][0].update(thread='other')),
                 ('N13',lambda v:v['read'].update(resources=[]))]
        for reason,change in changes:
            v=e.fixture(BINDING);change(v)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):e.validate(v,BINDING)

    def test_model_resource_cap_is_incomplete(self):
        self.assertEqual('INCOMPLETE',m.explore(max_states=2)['status'])
        self.assertEqual('PASS',m.explore(depth=3)['status'])

    def test_model_active_cancellation_keeps_view_until_release(self):
        r=m.Read('stale',phase=m.ACTIVE,cut=0,invoked=1)
        s=m.State(reads=(r,));events=dict(m.transitions(s))
        cancelled=events['0:cancel-active'];self.assertEqual(m.ACTIVE,cancelled.reads[0].phase)
        self.assertTrue(cancelled.reads[0].cancelled)
        self.assertEqual(m.CANCELLED,dict(m.transitions(cancelled))['0:release'].reads[0].phase)
        self.assertNotIn('publish',dict(m.transitions(replace(cancelled,accepted=1,proven=1,sequence=(0,1)))))

    def test_model_invariants_reject_fabricated_states(self):
        invalid=[m.State(proven=1),m.State(reads=(m.Read('stale',phase=m.WAIT,cut=0),)),
                 m.State(reads=(m.Read('minimum',phase=m.ACTIVE,cut=0,invoked=1),)),
                 m.State(reads=(m.Read('strong',phase=m.ACTIVE,cut=0,invoked=1),)),
                 m.State(reads=(m.Read('stale',phase=m.ACTIVE,cut=0,invoked=2),))]
        for state in invalid:
            with self.subTest(state=state),self.assertRaises(ValueError):m.check(state)

    def test_fair_publication_schedule_completes_ready_waiters(self):
        state=m.State(reads=(m.Read('minimum',minimum=1),m.Read('minimum',minimum=1)))
        for event in ('0:admit','1:admit','accept','proof','publish','0:capture','0:release','0:complete','1:capture','1:release','1:complete'):
            state=dict(m.transitions(state))[event];m.check(state)
        self.assertTrue(all(r.phase==m.SUCCESS for r in state.reads))
        self.assertEqual(1,state.published)

    def test_noop_can_advance_index_without_application_sequence(self):
        state=dict(m.transitions(m.State()))['accept']
        state=next(s for event,s in m.transitions(state) if event=='proof' and s.sequence==(0,0))
        state=dict(m.transitions(state))['publish'];m.check(state)
        self.assertEqual((1,0),(state.published,state.sequence[-1]))

    def test_inventory_cannot_hide_additional_files_or_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);e.save(root,e.fixture(BINDING));(root/'unlisted').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError,'N15'):e.read(root,BINDING)
            (root/'unlisted').unlink();(root/'inventory.json').write_text('{"schema":1,"schema":2}')
            with self.assertRaisesRegex(ValueError,'N15'):e.read(root,BINDING)

    def test_model_failure_keeps_the_failing_transition(self):
        from unittest.mock import patch
        import json
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'model.json'
            with patch.object(m,'transitions',return_value=[('forged',m.State(proven=1))]):
                with self.assertRaises(ValueError):m.run(output)
            result=json.loads(output.read_text());self.assertEqual('FAIL',result['status'])
            self.assertEqual('forged',json.loads(result['error'])['event'])
