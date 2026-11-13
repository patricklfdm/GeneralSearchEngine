"""Continuous comparison at both native cold boundaries; no synthetic admission."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import process_joint_history as m


def events():
    result=[dict(node=m.NODE,event='EARLIER')]
    for scope in (m.process.SCOPE,m.SCOPE):
        result.extend(dict(node=m.NODE,scope=scope,event=p) for p in m.history.control.c.n.phase.slot_storage.CURRENT)
        result.append(dict(node=m.NODE,scope=scope,event='FLOOR_RESERVED'))
    result.append(dict(node=m.NODE,scope=m.SCOPE,event='FLOOR_RELEASE_BEFORE_RETURN'))
    return result


class ProcessJointHistoryTest(unittest.TestCase):
    def test_missing_child_request_uses_the_connection_boundary_rejection(self):
        from . import test_joining_connections as fixture
        events,wires,ids,root=fixture.joined()
        events.pop(6)  # Scoped AFTER_REQUEST_READ; its later OFFER remains.
        with self.assertRaisesRegex(ValueError,'^'+m.NEGATIVES['child-request'][1]+'$'):
            fixture.e.replay(events,wires,ids,root)

    def test_exact_disjoint_original_cold_boundaries_without_event_projection(self):
        original=events();before=copy.deepcopy(original)
        self.assertEqual({m.NODE:((1,m.process.SCOPE),(7,m.SCOPE))},m.lifetimes(original));self.assertEqual(before,original)
        for mode,reason in [('missing','declared original cold lifetime'),('order','child current force order'),
                            ('overlap','disjoint original cold owners')]:
            changed=copy.deepcopy(original)
            if mode=='missing':changed[1]['event']='REMOVED_CURRENT'
            elif mode=='order':changed[2],changed[3]=changed[3],changed[2]
            else:changed.append(dict(node=m.NODE,scope=m.process.SCOPE,event='FLOOR_RESERVED'))
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,reason):m.lifetimes(changed)

    def test_both_peer_reseals_compare_the_derived_state_and_never_seed_it(self):
        r=m.PeerReplay.__new__(m.PeerReplay);r.root=Path('/original');r.events=events();r.model=SimpleNamespace(joining='node-6')
        r.state={m.NODE:b'derived'};r.comparisons=0
        for at,path in [(1,'process/before-open'),(7,'after-reopen')]:
            with patch.object(m.disk,'inventory',return_value={m.ledger.peer.FILE:b'derived'}) as inventory:
                r.reseal((at,m.NODE));inventory.assert_called_once_with(r.root/'joint-floor-recovery'/path)
            with patch.object(m.disk,'inventory',return_value={m.ledger.peer.FILE:b'fresh-chain'}):
                with self.assertRaisesRegex(ValueError,'exact original ledger'):r.reseal((at,m.NODE))
        self.assertEqual({m.NODE:b'derived'},r.state);self.assertEqual(2,r.comparisons)

    def test_two_owners_do_not_change_other_voters_or_joiner(self):
        r=m.PeerReplay.__new__(m.PeerReplay);r.events=events();r.model=SimpleNamespace(joining='node-6')
        self.assertEqual([None,m.process.SCOPE,m.process.SCOPE,m.SCOPE],[r.write_scope(m.NODE,i) for i in (0,1,6,7)])
        self.assertIsNone(r.write_scope('node-1',8));self.assertEqual('continuation-owner',r.write_scope('node-6',8))

    def test_ballot_reopens_compare_both_originals_and_forbid_intervening_allocations(self):
        r=m.BallotReplay.__new__(m.BallotReplay);r.events=events()
        self.assertEqual([(1,'original',(m.NODE,'joint-floor-recovery/process/before-open',m.process.SCOPE)),
                          (7,'original',(m.NODE,'joint-floor-recovery/after-reopen',m.SCOPE))],r.reopen_actions())
        r.events.insert(7,dict(node=m.NODE,scope=m.process.SCOPE,event='ALLOCATOR_BEFORE_WRITE'))
        with self.assertRaisesRegex(ValueError,'allocation during floor recovery'):r.reopen_actions()

    def test_original_owner_binding_rejects_a_self_consistent_sidecar_reset(self):
        r=m.Initialization.__new__(m.Initialization);r.root=Path('/original');r.group={m.NODE:{'allocator.gsr':b'derived'}}
        with patch.object(m.history.Initialization,'confirmations'),patch.object(m.disk,'inventory',return_value={'allocator.gsr':b'changed'}):
            with self.assertRaisesRegex(ValueError,'independently derived interrupted owner'):r.confirmations()

    def test_native_initial_floor_does_not_claim_a_direct_fixture_confirmation(self):
        original=m.history.Replay.__new__(m.history.Replay);original.expected_confirmations={'node-1',m.NODE,'node-3'}
        native=m.Replay.__new__(m.Replay);native.expected_confirmations=original.expected_confirmations
        self.assertEqual({'node-1',m.NODE,'node-3'},original.direct_fixture_nodes());self.assertEqual((1,1),original.recovered_counts)
        self.assertEqual({'node-1','node-3'},native.direct_fixture_nodes());self.assertEqual((2,0),native.recovered_counts)

    def test_original_failure_prevents_any_negative_qualification(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'validate',side_effect=ValueError('bad original')),patch.object(m,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify(tmp)
            negative.assert_not_called()

    def test_each_negative_needs_its_exact_reason_and_preserves_original(self):
        name='child-current';reason=m.NEGATIVES[name][1]
        for result in (None,ValueError('unrelated'),ValueError(reason)):
            with self.subTest(result=result),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'events.json').write_bytes(m.f.canonical(events()));(root/'protected').write_bytes(b'keep')
                before=m.h.inventory(root)
                with patch.object(m,'check_stage',side_effect=result):
                    if result is not None and str(result)==reason:self.assertEqual('REJECTED',m.negative(root,name,before)['status'])
                    else:
                        with self.assertRaisesRegex(ValueError,'accepted mutation' if result is None else 'unrelated rejection'):
                            m.negative(root,name,before)
                self.assertEqual(before,m.h.inventory(root))

    def test_negatives_cannot_overwrite_unrelated_physical_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'protected').write_bytes(b'keep');before=m.h.inventory(root)
            def overwrite(path,name):(path/'protected').write_bytes(b'changed');return 'events.json'
            with patch.object(m,'mutate',side_effect=overwrite),patch.object(m,'check_stage') as replay:
                with self.assertRaisesRegex(ValueError,'changed protected input'):m.negative(root,'child-current',before)
                replay.assert_not_called()
            with self.assertRaisesRegex(ValueError,'unknown negative'):m.mutate(root,'unknown')
            self.assertEqual(before,m.h.inventory(root))


if __name__=='__main__':unittest.main()
