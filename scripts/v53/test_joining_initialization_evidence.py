"""Conditional transition tests, distinct from original-history qualification."""
import base64
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from . import joining_initialization_evidence as j
from .test_joining_retention_evidence import Inputs
from .test_learner_confirmation_evidence import fixture as learner_fixture


def preparing():
    v = Inputs(); owner = v.identities[0]
    metadata = dict(root=v.cap['root'], owner=owner, revision=0, previous=None)
    before = j.f.encode('records', 'PROMISE', dict(root=v.cap['root'], view=j.s.catalog.authority(v.cap['root'], v.view),
        ballot=dict(v.ballot, counter=1), basisId=None))
    files = {'node.gsr': j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=owner)),
        'allocator.gsr': j.f.encode('records', 'ALLOCATOR', dict(root=v.cap['root'], node=owner['node'], counter=1)),
        'grants.gsr': before, 'pending.accept': j.disk.EMPTY,
        j.PEERS: j.peers.frame(dict(metadata, plan=v.peer_plans[0])),
        j.learner.FILE: j.learner.frame(dict(metadata, plan=v.learner_plans[0]))}
    basis, packet = v.sources()[0]; value = j.f.decode(basis, 'records', 'BASIS')
    promise = j.f.encode('records', 'PROMISE', {k:value[k] for k in ('root', 'view', 'ballot', 'basisId')})
    current = ('generations/a/', {v.cap['application']+'.image': b'independent image'}, v.current)
    return v, files, (basis, packet), before+promise+basis, current


class JoiningInitializationEvidenceTest(unittest.TestCase):
    def test_confirmation_moves_old_endpoint_to_renewal_without_discharge(self):
        state = learner_fixture(); proof = state['plan'].pop('confirmation'); point = state['plan']['possible'][0]
        lower = copy.deepcopy(point); lower['cut']['index'] -= 1; state['plan']['possible'] = [lower, point]
        before = j.learner.frame(state); result = j.confirmed_learner(before, proof, point); after = j.learner.decode(result)
        self.assertEqual([point], after['plan']['possible']); self.assertEqual([lower], after['plan']['renewals'])
        self.assertEqual(proof, after['plan']['confirmation']); self.assertEqual(state['revision']+1, after['revision'])
        self.assertEqual(j.sha(before), after['previous']); self.assertEqual(state, j.learner.decode(before))

    def test_equivalent_new_probe_preserves_original_confirmation_and_revision(self):
        state = learner_fixture(); proof = copy.deepcopy(state['plan']['confirmation'])
        for field, kind in [('query', 'LEARNER_HEAD_QUERY'), ('ack', 'LEARNER_HEAD_ACK')]:
            value = j.f.decode(base64.b64decode(proof[field]), 'wire', kind)
            value['trace'] = '00000000-0000-0000-0000-000000000099'
            proof[field] = j.placement.encoded(j.f.encode('wire', kind, value))
        before = j.learner.frame(state)
        self.assertEqual(before, j.confirmed_learner(before, proof, state['plan']['possible'][0]))

    def test_probe_from_another_old_owner_cannot_install_local_confirmation(self):
        state = learner_fixture(); state['owner']['port'] -= 1; before = j.learner.frame(state)
        with self.assertRaisesRegex(ValueError, '^joining initialization original probe owner$'):
            j.confirmed_learner(before, state['plan']['confirmation'], state['plan']['possible'][0])

    def test_reconcile_adds_only_actual_joining_copy_and_preserves_old_uncertainty(self):
        v, files, _, _, current = preparing()
        state = j.peers.decode(files[j.PEERS]); state['plan']['peers'].pop(); before = j.peers.frame(state)
        joined = {'node.gsr': j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=v.joining))}
        with patch.object(j.disk, 'current', side_effect=[current, current]): result = j.reconcile(before, files, joined)
        after = j.peers.decode(result)
        self.assertEqual(state['plan']['peers'], after['plan']['peers'][:-1])
        self.assertEqual(dict(identity=v.joining, possible=[j.disk.anchor(v.cap)]), after['plan']['peers'][-1])
        self.assertEqual(j.sha(before), after['previous']); self.assertEqual(1, after['revision'])

    def test_foreign_or_older_joining_copy_cannot_be_reconciled(self):
        for mode in ('foreign', 'older'):
            v, files, _, _, current = preparing(); state = j.peers.decode(files[j.PEERS]); state['plan']['peers'].pop()
            identity = dict(v.joining); other = copy.deepcopy(current)
            if mode == 'foreign': identity['port'] += 1
            else: other[2]['capsule']['cut']['index'] -= 1
            joined = {'node.gsr': j.f.encode('records', 'NODE', dict(root=v.cap['root'], identity=identity))}
            with self.subTest(mode=mode), patch.object(j.disk, 'current', side_effect=[current, other]), \
                 self.assertRaisesRegex(ValueError, '^joining initialization exact installed joining copy$'):
                j.reconcile(j.peers.frame(state), files, joined)

    def test_preparation_freezes_both_ledgers_without_selection_or_new_generation(self):
        v, files, source, observed, current = preparing(); before = copy.deepcopy(files)
        with patch.object(j.disk, 'current', return_value=current): result, captured = j.prepare(files, v.ballot, observed, set())
        self.assertEqual(source, captured); self.assertEqual(observed, result['grants.gsr'])
        self.assertEqual(before, files)
        self.assertFalse(any(name.startswith('generations/') or 'selected' in name for name in result))
        self.assertEqual(files[j.PEERS], result[j.PEERS]); self.assertEqual(files[j.learner.FILE], result[j.learner.FILE])
        self.assertEqual(2, j.f.decode(result['allocator.gsr'], 'records', 'ALLOCATOR')['counter'])
        packet = j.disk.p.decode(captured[1]); basis = j.f.decode(captured[0], 'records', 'BASIS')
        for magic, maximum in ((0x47535250, 65536), (0x47534c46, 32768)):
            _, frozen = j.retention.source(packet, basis, magic, maximum)
            self.assertEqual(v.identities[0], frozen['owner'])

    def test_captured_source_identity_cannot_be_reused(self):
        v, files, source, observed, current = preparing(); identifier = j.f.decode(source[0], 'records', 'BASIS')['basisId']
        with patch.object(j.disk, 'current', return_value=current), self.assertRaisesRegex(ValueError, '^joining initialization fresh original source identity$'):
            j.prepare(files, v.ballot, observed, {identifier})

    def test_preparation_cannot_silently_rewrite_preceding_grant_or_accept_extra_record(self):
        v, files, _, observed, current = preparing()
        extra = j.f.decode(files['grants.gsr'], 'records', 'PROMISE'); extra['ballot']['counter'] = 3
        for value in (observed[len(files['grants.gsr']):], observed+j.f.encode('records', 'PROMISE', extra)):
            with patch.object(j.disk, 'current', return_value=current), self.assertRaisesRegex(ValueError, '^joining initialization exact prepared grant suffix$'):
                j.prepare(files, v.ballot, value, set())

    def test_pending_accept_and_foreign_ledger_owner_refuse_preparation(self):
        for mode, reason in [('pending', 'preparation has pending tail'), ('owner', 'captured ledger owner')]:
            v, files, _, observed, current = preparing()
            if mode == 'pending': files['pending.accept'] = b'pending'
            else:
                state = j.peers.decode(files[j.PEERS]); state['owner'] = v.identities[1]; files[j.PEERS] = j.peers.frame(state)
            with self.subTest(mode=mode), patch.object(j.disk, 'current', return_value=current), \
                 self.assertRaisesRegex(ValueError, '^joining initialization '+reason+'$'):
                j.prepare(files, v.ballot, observed, set())

    def test_next_counter_respects_observed_promise_as_well_as_persisted_allocator(self):
        v, files, _, _, _ = preparing()
        promise = j.f.decode(files['grants.gsr'], 'records', 'PROMISE'); promise['ballot']['counter'] = 9
        files['grants.gsr'] = j.f.encode('records', 'PROMISE', promise)
        self.assertEqual(dict(v.ballot, counter=10), j.next_ballot(files))
        files['allocator.gsr'] = j.f.encode('records', 'ALLOCATOR', dict(root=v.cap['root'], node='node-1', counter=12))
        self.assertEqual(dict(v.ballot, counter=13), j.next_ballot(files))

    def test_exhausted_counter_is_not_wrapped(self):
        v, files, _, _, _ = preparing()
        files['allocator.gsr'] = j.f.encode('records', 'ALLOCATOR', dict(root=v.cap['root'], node='node-1', counter=2**63-2))
        with self.assertRaisesRegex(ValueError, '^joining initialization allocator exhausted$'): j.next_ballot(files)

    def test_aggregate_events_have_explicit_collection_bound(self):
        for rows in ({}, [None], [{}]*32768):
            with self.assertRaisesRegex(ValueError, '^joining initialization event collection bound$'): j.local_order(rows)
        with self.assertRaisesRegex(ValueError, '^joining initialization original lifecycle order$'): j.local_order([])

    def test_invalid_original_is_not_negative_evidence(self):
        with patch.object(j, 'validate', side_effect=ValueError('original failed')), patch.object(j.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^original failed$'): j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_prior_gate_failure_cannot_count_as_new_rejection(self):
        with patch.object(j, 'validate', return_value={}) as checked, patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.retirement, 'validate', side_effect=ValueError('prior gate failed')):
            with self.assertRaisesRegex(ValueError, '^prior gate failed$'): j.qualify(Path('/original'))
            self.assertEqual(1, checked.call_count)

    def test_unrelated_rejection_is_not_a_pass(self):
        with patch.object(j, 'validate', side_effect=[{}, ValueError('wrong reason')]), patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.retirement, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining unrelated initialization negative:'): j.qualify(Path('/original'))

    def test_accepted_mutation_is_a_failure(self):
        with patch.object(j, 'validate', return_value={}), patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.retirement, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining initialization mutation accepted:'): j.qualify(Path('/original'))


if __name__ == '__main__': unittest.main()
