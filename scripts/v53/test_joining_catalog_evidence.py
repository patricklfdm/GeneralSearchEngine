import base64
from pathlib import Path
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from . import joining_catalog_evidence as j


class JoiningCatalogEvidenceTest(unittest.TestCase):
    def test_bootstrap_source_is_explicit_and_defaults_to_empty(self):
        # A mismatched seed must fail in original admission, before any catalog
        # can be obtained from the producer's history or claimed outcome.
        for options,backup in (({},False),({'bootstrap_source':'EMPTY'},False),
                               ({'bootstrap_source':'VERIFIED_DURABLE_BACKUP'},True)):
            with self.subTest(options=options), patch.object(j.bootstrap,'original',side_effect=ValueError('source mismatch')) as original:
                with self.assertRaisesRegex(ValueError,'^source mismatch$'):
                    j.Replay(Path('/unused'),size=5,kind='REPLACE',**options)
                original.assert_called_once_with(Path('/unused'),5,backup)

    def test_unknown_or_truthy_bootstrap_profile_cannot_read_originals(self):
        for source in (None,True,1,[],{},'backup','empty','VERIFIED_DURABLE_BACKUP '):
            with self.subTest(source=source), patch.object(j.bootstrap,'original') as original:
                with self.assertRaisesRegex(ValueError,'^joining explicit bootstrap source$'):
                    j.Replay(Path('/unused'),bootstrap_source=source)
                original.assert_not_called()

    def phase(self, joint=False, voters=None):
        root = 'a' * 64
        identities = {f'node-{i}': dict(node=f'node-{i}', storage=str(uuid.UUID(int=i)), host='127.0.0.1', port=9000+i)
                      for i in range(1, 5)}
        view = dict(generation=0, old=['node-1', 'node-2', 'node-3'],
                    new=['node-1', 'node-2', 'node-3', 'node-4'] if joint else ['node-1', 'node-2', 'node-3'],
                    operation='f' * 64 if joint else None)
        parent = dict(cut=dict(index=8, entry='b' * 64, view=view))
        ballot = dict(counter=5, proposer='node-1', incarnation=identities['node-1']['storage'])
        authority = j.catalog.authority(root, view)
        voters = voters or (['node-1', 'node-2', 'node-4'] if joint else ['node-1', 'node-2'])
        selected = dict(root=root, view=authority, ballot=ballot, cut=parent['cut'], nextEntry=None,
                        sources=[dict(voter=n, basisId=str(uuid.UUID(int=20+i)), basisDigest=f'{i+1:064x}') for i, n in enumerate(voters)])
        payload = j.f.canonical(dict(binding=view['operation'])) if joint else b''
        entry = dict(root=root, authority=authority, index=9, previous=parent['cut']['entry'], origin=ballot,
                     kind='FINAL' if joint else 'BARRIER', payload=j.sha(payload))
        parts = dict(PAYLOAD=payload, ENTRY=j.f.encode('records', 'ENTRY', entry), SELECTED=j.f.encode('records', 'SELECTED', selected),
            PROMISE=j.f.encode('records', 'PROMISE', dict(root=root, view=authority, ballot=ballot, basisId=str(uuid.UUID(int=20)))),
            SELECTOR=j.f.encode('records', 'SELECTOR', dict(root=root, node='node-1', generation='a', digest='0' * 64)))
        accept = dict(root=root, authority=authority, ballot=ballot, index=9, entry=j.sha(parts['ENTRY']))
        parts['ACCEPT'] = j.f.encode('records', 'ACCEPT', accept)
        def witnesses(phase):
            return [dict(voter=n, incarnation=identities[n]['storage'], receipt=j.catalog.digest(dict(
                root=root, voter=n, incarnation=identities[n]['storage'], phase=phase, record=j.sha(parts[phase])))) for n in voters]
        proof = dict(accept, accepts=witnesses('ACCEPT')); parts['PROOF'] = j.f.encode('records', 'PROOF', proof)
        parts['CERTIFICATE'] = j.f.encode('records', 'CERTIFICATE', dict(proof, proofs=witnesses('PROOF')))
        return parts, parent, identities, root

    def check(self, values):
        parts, parent, identities, root = values
        return j.phased_certificate(j.packed_phases(parts), parent, identities, root)

    def test_distinct_phases_require_both_original_joint_majorities(self):
        for joint in (False, True):
            parts, values = self.check(self.phase(joint)); self.assertEqual(9, values['CERTIFICATE']['index'])
        with self.assertRaisesRegex(ValueError, '^both governing majorities$'):
            self.check(self.phase(True, ['node-1', 'node-2']))
        with self.assertRaisesRegex(ValueError, '^quorum identity/order$'):
            self.check(self.phase(False, ['node-1', 'node-2', 'node-4']))

    def test_duplicate_voters_cannot_increase_the_majority(self):
        with self.assertRaisesRegex(ValueError, '^quorum identity/order$'):
            self.check(self.phase(True, ['node-1', 'node-1', 'node-2']))

    def test_receipts_bind_phase_bytes_and_permanent_storage(self):
        for field, value in [('receipt', '0' * 64), ('incarnation', str(uuid.UUID(int=99)))]:
            args = self.phase(); parts = args[0]
            cert = j.f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE'); cert['proofs'][0][field] = value
            parts['CERTIFICATE'] = j.f.encode('records', 'CERTIFICATE', cert)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^joining original phased receipt$'):
                self.check(args)

    def test_parent_and_ballot_are_not_inferred_from_claimed_end(self):
        for field, value, reason in [('previous', '0' * 64, 'joining original governing entry'),
                                    ('origin', dict(counter=6, proposer='node-4', incarnation=str(uuid.UUID(int=4))), 'joining original ballot identity')]:
            args = self.phase(); parts = args[0]; entry = j.f.decode(parts['ENTRY'], 'records', 'ENTRY'); entry[field] = value
            parts['ENTRY'] = j.f.encode('records', 'ENTRY', entry)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^' + reason + '$'): self.check(args)

    def test_selection_cannot_name_a_different_phase_set_or_future_cut(self):
        for mode in ('future', 'voters', 'carried'):
            args = self.phase(); parts = args[0]; selected = j.f.decode(parts['SELECTED'], 'records', 'SELECTED')
            if mode == 'future': selected['cut']['index'] = 10
            elif mode == 'carried': selected['nextEntry'] = 'f' * 64
            else: selected['sources'][1]['voter'] = 'node-3'
            parts['SELECTED'] = j.f.encode('records', 'SELECTED', selected)
            reason = 'joining selected phase owners' if mode == 'voters' else 'joining original selection'
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^' + reason + '$'): self.check(args)

    def test_invalid_original_cannot_count_as_negative_qualification(self):
        with patch.object(j, 'validate', side_effect=ValueError('invalid original')), patch.object(j.shutil, 'copytree') as copytree:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): j.qualify(Path('/original'))
            copytree.assert_not_called()

    def test_readiness_without_an_original_barrier_completion_is_refused(self):
        raw = b'uncompleted'; row = dict(node='node-1', event='JOINING_ROUND_BEFORE_READY',
            record=j.sha(raw), bytes=base64.b64encode(raw).decode())
        replay = SimpleNamespace(selections={}, entries=[dict(kind='BARRIER')])
        with patch.object(j.collection, 'read_json', return_value=[row]):
            with self.assertRaisesRegex(ValueError, '^joining readiness before stable barrier$'):
                j.lifecycle(Path('/original'), replay)
        with patch.object(j.collection, 'read_json', return_value=[]):
            with self.assertRaisesRegex(ValueError, '^joining complete round lifecycle$'):
                j.lifecycle(Path('/original'), replay)

    def test_round_claims_require_the_exact_record_hash_and_owner(self):
        raw = b'original'; row = dict(node='node-1', event='JOINING_ROUND_INSTALLED',
            record='0' * 64, bytes=base64.b64encode(raw).decode())
        with patch.object(j.collection, 'read_json', return_value=[row]):
            with self.assertRaisesRegex(ValueError, '^joining original round record$'):
                j.lifecycle(Path('/original'), SimpleNamespace())
            row['node'] = 'node-4'
            with self.assertRaisesRegex(ValueError, '^joining original round owner$'):
                j.lifecycle(Path('/original'), SimpleNamespace())

    def test_unrelated_negative_failure_is_not_accepted(self):
        with patch.object(j, 'validate', side_effect=[{}, ValueError('unrelated corruption')]), \
             patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'):
            with self.assertRaisesRegex(ValueError, '^joining unrelated negative:'): j.qualify(Path('/original'))

    def test_missing_or_linked_original_cannot_reach_bootstrap_replay(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(j, 'Replay') as replay:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, '^joining complete consecutive applied history$'): j.validate(root)
            (root / 'linked').symlink_to('/absent')
            with self.assertRaisesRegex(ValueError, '^collection linked member$'): j.validate(root)
            replay.assert_not_called()


if __name__ == '__main__': unittest.main()
