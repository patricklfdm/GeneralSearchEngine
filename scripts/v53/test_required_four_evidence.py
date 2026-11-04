import copy
import itertools
from pathlib import Path
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from . import required_four_evidence as e


class RequiredFourEvidenceTest(unittest.TestCase):
    def phase(self):
        c = e.c; root = 'a'*64
        identities = {f'node-{i}': dict(node=f'node-{i}', storage=str(uuid.UUID(int=i)),
                       host='127.0.0.1', port=9000+i) for i in range(1, 7)}
        view = dict(generation=1, old=e.OLD, new=e.NEW, operation='f'*64)
        parent = dict(cut=dict(index=9, entry='b'*64, view=view))
        ballot = dict(counter=7, proposer='node-1', incarnation=identities['node-1']['storage'])
        authority = c.catalog.authority(root, view)
        selected = dict(root=root, view=authority, ballot=ballot, cut=parent['cut'], nextEntry=None,
            sources=[dict(voter=n, basisId=str(uuid.UUID(int=20+i)), basisDigest=f'{i+1:064x}')
                     for i, n in enumerate(e.JOINT_LIVE)])
        payload = c.f.canonical(dict(binding=view['operation']))
        entry = dict(root=root, authority=authority, index=10, previous=parent['cut']['entry'],
                     origin=ballot, kind='FINAL', payload=c.sha(payload))
        parts = dict(PAYLOAD=payload, ENTRY=c.f.encode('records', 'ENTRY', entry),
            SELECTED=c.f.encode('records', 'SELECTED', selected),
            PROMISE=c.f.encode('records', 'PROMISE', dict(root=root, view=authority, ballot=ballot,
                              basisId=str(uuid.UUID(int=20)))),
            SELECTOR=c.f.encode('records', 'SELECTOR', dict(root=root, node='node-1', generation='a', digest='0'*64)))
        accept = dict(root=root, authority=authority, ballot=ballot, index=10, entry=c.sha(parts['ENTRY']))
        parts['ACCEPT'] = c.f.encode('records', 'ACCEPT', accept)
        def witnesses(phase):
            return [dict(voter=n, incarnation=identities[n]['storage'], receipt=c.catalog.digest(dict(
                root=root, voter=n, incarnation=identities[n]['storage'], phase=phase, record=c.sha(parts[phase]))))
                for n in e.JOINT_LIVE]
        proof = dict(accept, accepts=witnesses('ACCEPT')); parts['PROOF'] = c.f.encode('records', 'PROOF', proof)
        parts['CERTIFICATE'] = c.f.encode('records', 'CERTIFICATE', dict(proof, proofs=witnesses('PROOF')))
        return parts, parent, identities, root

    def check(self, args):
        parts, parent, identities, root = args
        return e.c.phased_certificate(e.c.packed_phases(parts), parent, identities, root)

    def test_four_is_necessary_not_merely_a_four_voter_observation(self):
        args = self.phase(); self.check(args)
        refused = e.required_joint(args[1]['cut']['view'], e.JOINT_LIVE)
        self.assertEqual([list(v) for v in itertools.combinations(e.JOINT_LIVE, 3)], refused)
        overlapping = dict(args[1]['cut']['view'], new=['node-1', 'node-2', 'node-3', 'node-4', 'node-6'])
        with self.assertRaisesRegex(ValueError, '^required-four exact joint topology$'):
            e.required_joint(overlapping, e.JOINT_LIVE)

    def test_every_missing_proof_is_rejected_with_other_phase_bytes_intact(self):
        for node in e.JOINT_LIVE:
            with self.subTest(node=node):
                args = self.phase(); parts = args[0]
                cert = e.c.f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE')
                cert['proofs'] = [v for v in cert['proofs'] if v['voter'] != node]
                parts['CERTIFICATE'] = e.c.f.encode('records', 'CERTIFICATE', cert)
                with self.assertRaisesRegex(ValueError, '^both governing majorities$'): self.check(args)

    def test_duplicate_or_foreign_receipt_cannot_supply_the_fourth_vote(self):
        for mode in ('duplicate', 'foreign-incarnation', 'bad-receipt'):
            args = self.phase(); parts = args[0]; cert = e.c.f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE')
            if mode == 'duplicate': cert['proofs'][-1] = copy.deepcopy(cert['proofs'][0])
            else: cert['proofs'][-1]['incarnation' if mode == 'foreign-incarnation' else 'receipt'] = (
                str(uuid.UUID(int=99)) if mode == 'foreign-incarnation' else '0'*64)
            parts['CERTIFICATE'] = e.c.f.encode('records', 'CERTIFICATE', cert)
            reason = 'quorum identity/order' if mode == 'duplicate' else 'joining original phased receipt'
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^'+reason+'$'): self.check(args)

    def test_topology_override_is_explicit_and_narrow(self):
        self.assertEqual(e.NEW, e.c.target_nodes(5, 'REPLACE', True))
        self.assertEqual(['node-1', 'node-2', 'node-3', 'node-4', 'node-6'], e.c.target_nodes(5, 'REPLACE'))
        for size, kind, flag in [(3, 'ADD', True), (4, 'REPLACE', True), (5, 'REPLACE', 1)]:
            with self.assertRaisesRegex(ValueError, '^joining required-four profile$'):
                e.c.target_nodes(size, kind, flag)

    def test_departing_voter_cannot_supply_any_successor_endorsement(self):
        before = dict(cut=dict(view=dict(old=e.OLD, new=e.NEW)))
        after = dict(cut=dict(view=dict(old=e.NEW, new=e.NEW)))
        self.assertFalse(e.c.applied_voter(before, after, 'FINAL', 'node-3', {}))
        self.assertTrue(e.c.applied_voter(before, after, 'FINAL', 'node-6', {'ack.gsr': b'original'}))
        for node, files in [('node-3', {'ack.gsr': b'forged'}), ('node-6', {})]:
            with self.subTest(node=node), self.assertRaisesRegex(ValueError, '^joining applied end voting eligibility$'):
                e.c.applied_voter(before, after, 'FINAL', node, files)
        for name in ('parent-ack.gsr', 'ancestor-0-statement.gsr'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, '^joining departing ancestor endorsement$'):
                e.c.applied_voter(before, after, 'FINAL', 'node-3', {name: b'forged'})
        for kind, node in [('BARRIER', 'node-3'), ('FINAL', 'foreign')]:
            with self.subTest(kind=kind, node=node), self.assertRaisesRegex(ValueError, '^joining nonvoting FINAL owner$'):
                e.c.applied_voter(before, after, kind, node, {})

    def test_original_must_pass_before_any_negative_is_attempted(self):
        with patch.object(e.c.collection, 'inventory', return_value={}), \
             patch.object(e, 'validate', side_effect=ValueError('invalid original')), \
             patch.object(e.shutil, 'copytree') as copying:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): e.qualify(Path('/original'))
            copying.assert_not_called()

    def test_departing_force_sequence_has_no_checkpoint_ack_force(self):
        from . import joining_phase_evidence as phases
        parts, _, _, _ = self.phase()
        replay = SimpleNamespace(phases=[parts], old=e.OLD, joining='node-6', nonvoting={(1, 'node-3')})
        rows = [dict(node=node, event=event, **({'scope': 'continuation-owner'} if node == 'node-6' else {}))
                for node in e.JOINT_LIVE for event in phases.force_names(nonvoting=node == 'node-3')]
        self.assertEqual({(1, n) for n in e.JOINT_LIVE}, set(phases.blocks(rows, replay)))
        for mode in ('missing-nonvoting-force', 'forged-ack-force'):
            changed = copy.deepcopy(rows)
            at = next(i for i, r in enumerate(changed) if r['node'] == 'node-3' and r['event'] == 'APPLY_NONVOTING_DIRECTORY_FORCED')
            if mode == 'missing-nonvoting-force': changed.pop(at)
            else: changed.insert(at, dict(node='node-3', event='APPLY_ACK_FORCED'))
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^joining exact slot force order: node-3$'):
                phases.blocks(changed, replay)

    def test_departing_publication_requires_remote_successor_receipts(self):
        from . import joining_publication_evidence as publication
        from . import joining_transcript as transcript
        from .test_joining_publication_evidence import JoiningPublicationEvidenceTest
        for missing in (False, True):
            replay, _ = JoiningPublicationEvidenceTest().bridge()
            replay.states[9]['cut']['view'].update(old=['node-1', 'node-2', 'node-4'], new=['node-1', 'node-2', 'node-4'], operation=None)
            statement = e.c.f.encode('records', 'CHECKPOINT', replay.checkpoint(8, 9, 'RANGE'))
            replay.acks = {(e.c.sha(statement), node): e.c.f.encode('records', 'CHECKPOINT_ACK',
                dict(root=replay.root, voter=node, incarnation=identity['storage'], cut=replay.states[9]['cut'], statement=e.c.sha(statement)))
                for node, identity in e.c.catalog.identities(replay.states[9]['identities']).items() if node in ('node-1', 'node-2')}
            replay.nonvoting = {(9, 'node-3')}
            replay.owner = lambda *args: {'applied-end/statement.gsr': statement}
            transfers = [dict(kind='RECORD', raw=raw,
                offer=dict(sent=11, request=dict(sender=dict(node='node-3'), recipient=dict(node=node))),
                commit=dict(delivered=19)) for (_, node), raw in replay.acks.items()]
            if missing: transfers.pop()
            def fill(rows, *, contents): contents.extend(transfers); return {}
            with patch.object(e.c.collection, 'read_json', return_value=[]), patch.object(transcript, 'causal', return_value=[]), \
                 patch.object(transcript, 'transfers', side_effect=fill), patch.object(publication.phases, 'blocks',
                    return_value={(9, 'node-3'): dict(APPLY_BEFORE_RETURN=10, PUBLICATION_VALIDATED=20)}):
                if missing:
                    with self.assertRaisesRegex(ValueError, '^both governing majorities$'):
                        publication.CheckpointReceipts(Path('/original'), replay)
                else:
                    result = publication.CheckpointReceipts(Path('/original'), replay)
                    self.assertEqual(2, result.transfers)
                    self.assertEqual(list(replay.acks.values()), result.get('node-3', e.c.sha(statement)))

    def test_unrelated_failure_cannot_satisfy_a_negative(self):
        with patch.object(e.c.collection, 'inventory', return_value={}), \
             patch.object(e, 'validate', side_effect=[{}, ValueError('unrelated corruption')]), \
             patch.object(e.shutil, 'copytree'), patch.object(e, 'mutate'):
            with self.assertRaisesRegex(ValueError, '^required-four unrelated negative:'):
                e.qualify(Path('/original'))


if __name__ == '__main__': unittest.main()
