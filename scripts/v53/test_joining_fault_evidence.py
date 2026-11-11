"""Trace mutations are synthetic; native evidence is qualified separately."""
import copy
import unittest
from unittest.mock import patch

from . import joining_fault_evidence as gate
from . import test_joining_source_loss as fixture


def observed_trace(kind, connections=False):
    """Synthetic fixture with the terminals and socket metadata used by live capture."""
    values=fixture.trace(kind);events,wires,ids,root=values
    rows=gate.n.causal(*values);insertions=[]
    for i,row in enumerate(rows):
        send=events[row['sent']];receive=events[row['received']]
        client=dict(id=f'00000000-0000-0000-0000-{2*i+1:012d}',
                    local=dict(address='127.0.0.1',port=57000+i),
                    remote=dict(address='127.0.0.1',port=ids[receive['node']]['port']))
        server=dict(id=f'00000000-0000-0000-0000-{2*i+2:012d}',local=copy.deepcopy(client['remote']),remote=copy.deepcopy(client['local']))
        if connections:
            for field in ('sent','received','offered','delivered'):
                if row[field] is not None:events[row[field]]['connection']=copy.deepcopy(client if field in ('sent','delivered') else server)
            wires[i]['connection']=copy.deepcopy(server)
        if row['delivered'] is None:
            for original,direction in ((receive,'INBOUND'),(send,'OUTBOUND')):
                terminal={k:copy.deepcopy(v) for k,v in original.items() if k!='bytes'}
                terminal.update(event='NETWORK_ATTEMPT_FAILED',direction=direction,reason='IO')
                insertions.append((row['offered']+1,terminal))
    for at,event in reversed(insertions):events.insert(at,event)
    return values


class JoiningFaultEvidenceTest(unittest.TestCase):
    def test_all_negatives_keep_exact_reasons_for_terminal_and_connection_formats(self):
        for connections in (False,True):
            for kind in gate.loss.KINDS:
                original=observed_trace(kind,connections);result=gate.trace(*original)
                expected=gate.negative_reasons(result['transportFormat'])
                self.assertEqual(set(gate.NEGATIVES),set(expected))
                for name,reason in expected.items():
                    values=copy.deepcopy(original);gate.mutate(*values,name)
                    with self.subTest(connections=connections,kind=kind,case=name),self.assertRaises(ValueError) as caught:
                        gate.trace(*values)
                    self.assertEqual(reason,str(caught.exception))
    def test_every_declared_negative_rejects_its_exact_boundary_for_all_reply_kinds(self):
        for kind in gate.loss.KINDS:
            original=fixture.trace(kind);self.assertEqual(kind,gate.trace(*original)['sourceFault'])
            for name,reason in gate.NEGATIVES.items():
                values=copy.deepcopy(original);gate.mutate(*values,name)
                with self.subTest(kind=kind,case=name),self.assertRaises(ValueError) as caught:gate.trace(*values)
                self.assertEqual(reason,str(caught.exception))

    def test_full_original_physical_peer_failure_stops_trace_acceptance(self):
        with patch.object(gate.n.s.collection,'inventory',return_value={}), \
             patch.object(gate.peer,'validate',side_effect=ValueError('invalid physical')),patch.object(gate,'inputs') as inputs:
            with self.assertRaisesRegex(ValueError,'^invalid physical$'):gate.validate('/unused')
            inputs.assert_not_called()

    def test_original_is_replayed_before_any_negative(self):
        with patch.object(gate,'validate',side_effect=ValueError('invalid original')),patch.object(gate,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):gate.qualify('/unused')
            mutate.assert_not_called()

    def test_mutations_leave_original_trace_and_files_unchanged(self):
        original=fixture.trace();before=copy.deepcopy(original)
        with patch.object(gate,'validate',return_value={'status':'PASS'}), \
             patch.object(gate.n.s.collection,'inventory',return_value={'files':{}}),patch.object(gate,'inputs',return_value=original):
            result=gate.qualify('/unused')
        self.assertEqual(len(gate.NEGATIVES),len(result['negatives']));self.assertTrue(result['originalPreserved'])
        self.assertEqual(before,original)

    def test_healthy_trace_cannot_count_as_a_fault_experiment(self):
        events,wires,ids,root=fixture.trace();events=[v for v in events if v['event'] not in (gate.loss.ARM,gate.loss.DONE)]
        with self.assertRaisesRegex(ValueError,'^joining fault declaration required$'):gate.trace(events,wires,ids,root)

    def test_accepted_or_unrelated_negative_is_not_counted(self):
        for reason in (None,'unrelated failure'):
            with patch.object(gate,'validate',return_value={}),patch.object(gate.n.s.collection,'inventory',return_value={}), \
                 patch.object(gate,'inputs',return_value=fixture.trace()),patch.object(gate,'mutate'), \
                 patch.object(gate,'trace',side_effect=ValueError(reason) if reason else None):
                prefix='joining unrelated fault negative:' if reason else 'joining fault mutation accepted:'
                with self.assertRaisesRegex(ValueError,'^'+prefix):gate.qualify('/unused')

    def test_original_changes_during_success_or_negative_replay_are_rejected(self):
        with patch.object(gate.n.s.collection,'inventory',side_effect=[{}, {'changed':True}]), \
             patch.object(gate.peer,'validate',return_value={}),patch.object(gate,'inputs',return_value=fixture.trace()):
            with self.assertRaisesRegex(ValueError,'^joining fault original changed$'):gate.validate('/unused')
        with patch.object(gate,'validate',return_value={}),patch.object(gate.n.s.collection,'inventory',side_effect=[{}, {'changed':True}]), \
             patch.object(gate,'inputs',return_value=fixture.trace()):
            with self.assertRaisesRegex(ValueError,'^joining fault negative changed original$'):gate.qualify('/unused')


if __name__=='__main__':unittest.main()
