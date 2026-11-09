"""Admission and mutation targeting; conditional traces are not native history proof."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import required_four_network as e
from . import test_joining_connections as fixture


class RequiredFourNetworkTest(unittest.TestCase):
    def test_legacy_observations_never_enter_exact_connection_gate(self):
        events,wires,ids,root=fixture.joined()
        for row in events+wires:row.pop('connection',None)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'events.json').write_bytes(e.network.f.canonical(events));(path/'wire.json').write_bytes(e.network.f.canonical(wires))
            with patch.object(e.network,'network') as network,self.assertRaisesRegex(ValueError,'original connection observations absent'):
                e.replay(path)
            network.assert_not_called()

    def test_new_mutations_reject_at_exact_connection_gate(self):
        names=set(e.NEGATIVES)-set(e.network.NEGATIVES)
        for name in names:
            with self.subTest(case=name),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);events,wires,ids,root=fixture.joined()
                (path/'events.json').write_bytes(e.network.f.canonical(events));(path/'wire.json').write_bytes(e.network.f.canonical(wires))
                self.assertEqual(2,e.connections.replay(events,wires,ids,root)['attempts'])
                e.mutate(path,name)
                with self.assertRaises(ValueError) as caught:
                    changed,wire=e.observations(path);e.connections.replay(changed,wire,ids,root)
                self.assertEqual(e.NEGATIVES[name],str(caught.exception))

    def test_terminal_mutations_bind_overlapping_late_failure_without_hash_guessing(self):
        for offered in (False,True):
            events,wires,ids,root=fixture.joined()
            if not offered:events.pop(7);wires.pop(0)
            result=e.connections.replay(events,wires,ids,root);cases,targets=e.terminal_plan(result)
            self.assertEqual(6,len(cases));self.assertGreater(targets['terminal-receiver-missing'],targets['terminal-caller-missing'])
            for name,reason in cases.items():
                with self.subTest(offered=offered,case=name),tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp);(path/'events.json').write_bytes(e.network.f.canonical(events));(path/'wire.json').write_bytes(e.network.f.canonical(wires))
                    e.mutate(path,name,terminal=targets[name])
                    with self.assertRaises(ValueError) as caught:
                        changed,wire=e.observations(path);e.connections.replay(changed,wire,ids,root)
                    self.assertEqual(reason,str(caught.exception))
        self.assertEqual(({},{}),e.terminal_plan(dict(failed=[])))

    def test_existing_negative_families_are_complete_and_authority_reasons_unchanged(self):
        self.assertTrue(e.network.NEGATIVES.keys()<=e.NEGATIVES.keys())
        for name,reason in e.network.NEGATIVES.items():
            if name not in {'missing-send','missing-request','late-request','overlapping-retry','wrong-send-owner',
                            'wrong-send-kind','wrong-server-lifetime','wrong-client-lifetime','missing-delivery'}:
                self.assertEqual(reason,e.NEGATIVES[name])

    def test_missing_receiver_outcome_removes_offer_and_failure_only_on_exact_socket(self):
        events,wires,ids,root=fixture.joined();result=e.connections.replay(events,wires,ids,root)
        cases,targets=e.terminal_plan(result);at=targets['terminal-receiver-missing'];identifier=events[at]['connection']['id']
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'events.json').write_bytes(e.network.f.canonical(events));original=e.network.f.canonical(wires)
            (path/'wire.json').write_bytes(original);e.mutate(path,'terminal-receiver-missing',terminal=at)
            changed,wire=e.observations(path)
            self.assertEqual(original,(path/'wire.json').read_bytes())
            self.assertEqual([v for v in events if v.get('connection',{}).get('id')!=identifier],
                             [v for v in changed if v.get('connection',{}).get('id')!=identifier])
            self.assertEqual(1,len([v for v in changed if v.get('connection',{}).get('id')==identifier]))
            with self.assertRaisesRegex(ValueError,'connection incomplete invocation'):e.connections.replay(changed,wire,ids,root)

    def test_complete_physical_original_must_pass_before_network_or_mutations(self):
        with patch.object(e.collection,'inventory',return_value={}),patch.object(e.physical,'validate',side_effect=ValueError('physical original')):
            for entry in (e.validate,e.qualify):
                with patch.object(e,'replay') as network,patch.object(e.shutil,'copytree') as copied:
                    with self.assertRaisesRegex(ValueError,'physical original'):entry('/unused')
                    network.assert_not_called();copied.assert_not_called()

    def test_successful_original_requires_all_slots_and_preserved_inventory(self):
        for result in (dict(slots=10,ownedSlotTransactions=34),dict(slots=11,ownedSlotTransactions=33)):
            with patch.object(e.collection,'inventory',return_value={}),patch.object(e.physical,'validate',return_value={}),patch.object(e,'replay',return_value=result):
                with self.assertRaisesRegex(ValueError,'complete network slots'):e.validate('/unused')
        with patch.object(e.collection,'inventory',side_effect=[{'old':1},{'old':2}]),patch.object(e.physical,'validate',return_value={}),patch.object(e,'replay',return_value=dict(slots=11,ownedSlotTransactions=34)):
            with self.assertRaisesRegex(ValueError,'original changed'):e.validate('/unused')

    def test_unrelated_failure_and_accepted_mutation_never_count_as_rejection(self):
        inventory=dict(files={},directories=[])
        for result,reason in ((ValueError('unrelated'),'unrelated network negative'),({},'mutation accepted')):
            with patch.object(e.collection,'inventory',return_value=inventory),patch.object(e,'validate',return_value={}),patch.object(e,'terminal_targets',return_value=({},{})),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e,'replay',side_effect=[result]):
                with self.assertRaisesRegex(ValueError,reason):e.qualify('/unused')

    def test_negative_cannot_change_physical_authority_before_network_replay(self):
        original=dict(files={'selector.gsr':'original'},directories=['generations'])
        changed=dict(files={'selector.gsr':'substitute'},directories=['generations'])
        with patch.object(e.collection,'inventory',side_effect=[original,changed]),patch.object(e,'validate',return_value={}),patch.object(e,'terminal_targets',return_value=({},{})),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'changed physical inputs'):e.qualify('/unused')
            replay.assert_not_called()


if __name__=='__main__':unittest.main()
