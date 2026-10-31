"""Grammar and provenance regression tests; synthetic rows are not native proof."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import transfer_process_evidence as e


def row(event,value):return dict(life=1,event=event,value=value)


def attempt(kind='success'):
    result=[row('CALL',dict(request='q',expected='SOURCE_OFFER',deadline=123))]
    wires=[('CLIENT_WIRE','BEFORE_REQUEST_WRITE'),('SERVER_WIRE','AFTER_REQUEST_READ'),('SERVER_WIRE','BEFORE_RESPONSE_WRITE')]
    if kind=='success':wires.append(('CLIENT_WIRE','AFTER_RESPONSE_READ'))
    if kind=='dead':wires=[]
    for side,event in wires:
        value=dict(event=event,request='q')
        if event in ('BEFORE_RESPONSE_WRITE','AFTER_RESPONSE_READ'):value['response']='a'
        result.append(row(side,value))
    if kind=='cut':result += [row('SERVER_cut',{}),row('LOCK_HELD',123)]
    result.append(row('REPLY',dict(request='q',response='a')) if kind=='success' else row('FAILURE',dict(request='q',reason='IO')))
    return result


class TransferProcessEvidenceTest(unittest.TestCase):
    def test_complete_profile_axes_are_exact(self):
        self.assertEqual(18,len(e.PROFILES));self.assertEqual(18,len({e.name(v) for v in e.PROFILES}))
        self.assertEqual({3,4,5},{v['size'] for v in e.PROFILES});self.assertEqual({'halt','kill'},{v['mode'] for v in e.PROFILES})
        self.assertEqual({'SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'},{v['point'] for v in e.PROFILES})

    def test_success_cut_and_dead_connection_have_distinct_observations(self):
        for kind in ('success','cut','dead'):
            with self.subTest(kind=kind):
                observed=e.attempts(attempt(kind));self.assertEqual(1,len(observed));e.exchange(observed[0],('q','a','SOURCE_OFFER'),kind)
                self.assertEqual(kind=='success',observed[0]['reply'])

    def test_dead_connection_may_write_before_disconnect_but_never_receive(self):
        rows=attempt('dead');rows.insert(1,row('CLIENT_WIRE',dict(event='BEFORE_REQUEST_WRITE',request='q')))
        e.exchange(e.attempts(rows)[0],('q','a','SOURCE_OFFER'),'dead')
        rows.insert(2,row('SERVER_WIRE',dict(event='AFTER_REQUEST_READ',request='q')))
        with self.assertRaisesRegex(ValueError,'dead donor retry order'):e.exchange(e.attempts(rows)[0],('q','a','SOURCE_OFFER'),'dead')

    def test_cut_cannot_be_a_delivered_reply(self):
        rows=attempt('cut');rows[-1]=row('REPLY',dict(request='q',response='a'))
        with self.assertRaisesRegex(ValueError,'interrupted TCP order'):e.exchange(e.attempts(rows)[0],('q','a','SOURCE_OFFER'),'cut')

    def test_missing_read_and_send_do_not_prove_success(self):
        for index in (1,2):
            rows=attempt();del rows[index]
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'successful TCP order'):
                e.exchange(e.attempts(rows)[0],('q','a','SOURCE_OFFER'),'success')

    def test_unbound_and_incomplete_attempts_fail(self):
        with self.assertRaisesRegex(ValueError,'unbound exchange'):e.attempts([attempt()[-1]])
        with self.assertRaisesRegex(ValueError,'incomplete attempt'):e.attempts(attempt()[:-1])

    def test_worker_open_cannot_interleave_with_an_attempt(self):
        rows=attempt();rows.insert(2,row('SERVER_OPEN',{}))
        with self.assertRaisesRegex(ValueError,'observation inside attempt'):e.attempts(rows)

    def test_request_response_and_failure_reason_are_exact(self):
        rows=attempt();rows[2]['value']['request']='other'
        with self.assertRaisesRegex(ValueError,'exact attempt request'):e.attempts(rows)
        rows=attempt();rows[-1]['value']['response']='other'
        with self.assertRaisesRegex(ValueError,'original response bytes'):e.exchange(e.attempts(rows)[0],('q','a','SOURCE_OFFER'),'success')
        rows=attempt('cut');rows[-1]['value']['reason']='DEADLINE'
        with self.assertRaisesRegex(ValueError,'original IO failure'):e.attempts(rows)

    def test_positions_preserve_cut_between_offered_response_and_failure(self):
        rows=attempt('cut');v=e.attempts(rows)[0]
        self.assertEqual([1,2,3],v['wirePositions']);self.assertEqual(6,v['end'])

    def test_process_identity_requires_actual_exit_modes_and_distinct_positive_pids(self):
        for mode,code in (('halt',73),('kill',137)):
            profile=dict(size=3,point='CHUNK',mode=mode)
            original=dict(profile,parentPid=1,children=[dict(life=1,pid=2,exit=code),dict(life=2,pid=3,exit=0)],status='PASS',phase3Complete=False)
            e.process_identity(original,profile)
            for changed in ('same','bool','exit','closure'):
                v=copy.deepcopy(original)
                if changed=='same':v['children'][1]['pid']=v['parentPid']
                elif changed=='bool':v['children'][0]['pid']=True
                elif changed=='exit':v['children'][0]['exit']=0
                else:v['phase3Complete']=0
                with self.subTest(mode=mode,changed=changed),self.assertRaises(ValueError):e.process_identity(v,profile)

    def test_duplicate_pipe_keys_are_not_original_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'stdout';p.write_text('{"action":"A","action":"B","value":0}\n')
            with self.assertRaisesRegex(ValueError,'duplicate pipe key'):e.pipe(p)

    def test_original_must_validate_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',side_effect=ValueError('original bad')),\
                patch.object(e.shutil,'copytree') as copier:
            with self.assertRaisesRegex(ValueError,'original bad'):e.qualify(temp)
            copier.assert_not_called()

    def test_exact_negative_reason_and_original_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'marker').write_bytes(b'original');before=e.fault.history.inventory(root)
            with patch.object(e,'NEGATIVES',[('test','exact')]),patch.object(e,'mutate',side_effect=lambda p,_:(p/'marker').write_bytes(b'changed')),\
                    patch.object(e,'validate',side_effect=[{},ValueError('exact')]):
                result=e.qualify(root)
            self.assertTrue(result['originalPreserved']);self.assertEqual(before,e.fault.history.inventory(root))
            self.assertEqual([dict(case='test',reason='exact',status='REJECTED')],result['negatives'])

    def test_unrelated_or_accepted_negative_is_not_qualification(self):
        for outcome in (ValueError('other'),ValueError('exact plus extra'),{}):
            with tempfile.TemporaryDirectory() as temp,patch.object(e,'NEGATIVES',[('test','exact')]),patch.object(e,'mutate'),\
                    patch.object(e,'validate',side_effect=[{},outcome]):
                with self.assertRaises(ValueError):e.qualify(temp)

    def test_original_edit_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'marker';p.write_bytes(b'original')
            with patch.object(e,'NEGATIVES',[('test','exact')]),patch.object(e,'mutate',side_effect=lambda *_:p.write_bytes(b'changed')),\
                    patch.object(e,'validate',side_effect=[{},ValueError('exact')]):
                with self.assertRaisesRegex(ValueError,'original modified'):e.qualify(root)

    def test_incomplete_or_linked_matrix_is_not_full_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);link=root/'link';link.symlink_to(root,target_is_directory=True)
            for p in (link,root/'missing',root):
                with self.subTest(path=p),self.assertRaises(ValueError):e.validate(p)


if __name__=='__main__':unittest.main()
