"""Fail-closed original-first replay of the unequal-cut network qualification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_ancestry_evidence as q


class NativeAncestryEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_a_successful_negative(self):
        with patch.object(q,'validate',side_effect=ValueError('original failed')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):q.qualify('missing')
            copied.assert_not_called()

    def test_original_proofs_are_checked_before_selected_sources_or_wire(self):
        with (patch.object(q.b.selection,'layout'),patch.object(q,'original',side_effect=ValueError('original proof')),
              patch.object(q,'installation') as installed,patch.object(q,'network') as network):
            with self.assertRaisesRegex(ValueError,'original proof'):q.case('raw',3,False,1)
            installed.assert_not_called();network.assert_not_called()

    def test_incomplete_size_backup_or_lower_peer_matrix_is_not_qualified(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(q,'case') as case:
            root=Path(temp)
            for profile in q.PROFILES[:-1]:(root/q.name(*profile)).mkdir()
            with self.assertRaisesRegex(ValueError,'native ancestry profiles inventory'):q.validate(root)
            case.assert_not_called()

    def test_reusing_the_same_history_across_profiles_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for profile in q.PROFILES:(root/q.name(*profile)).mkdir()
            with patch.object(q,'case',return_value={'history':'reused'}):
                with self.assertRaisesRegex(ValueError,'distinct histories'):q.validate(root)

    def test_partial_publication_requires_both_actual_majorities(self):
        cap={'capsule':{'cut':{'view':{'old':['node-1','node-2','node-3'],'new':['node-1','node-4','node-5']}}}}
        with patch.object(q.c,'current',return_value=(None,None,cap)):
            with self.assertRaisesRegex(ValueError,'quorum'):
                q.partial_publication(Path('raw'),{'node-1':{},'node-2':{},'node-3':{}},None,[],'node-1')

    def test_linked_raw_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'actual').write_text('{}');(root/'alias').symlink_to(root/'actual')
            with self.assertRaises(ValueError):q.read(root/'alias')

    def test_unrelated_exception_cannot_count_as_intended_negative(self):
        with (patch.object(q,'validate',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),
              patch.object(q,'case',side_effect=ValueError('unrelated failure'))):
            with self.assertRaisesRegex(ValueError,'unrelated negative'):q.qualify('missing')

    def test_accepted_mutation_is_rejected(self):
        with (patch.object(q,'validate',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),
              patch.object(q,'case',return_value={})):
            with self.assertRaisesRegex(ValueError,'accepted negative'):q.qualify('missing')

    def test_tail_negative_replay_requires_both_unchanged_originals_first(self):
        with patch.object(q,'validate_tails',side_effect=ValueError('original tail failed')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original tail failed'):q.qualify_tails('missing')
            copied.assert_not_called()

    def test_tail_matrix_cannot_omit_the_local_longest_direction(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(q,'case') as case:
            root=Path(temp);(root/q.name(*q.TAIL_PROFILES[0])).mkdir()
            with self.assertRaisesRegex(ValueError,'tail profiles inventory'):q.validate_tails(root)
            case.assert_not_called()

    def test_tail_negative_cannot_pass_on_an_unrelated_failure(self):
        with (patch.object(q,'validate_tails',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),
              patch.object(q,'case',side_effect=ValueError('unrelated failure'))):
            with self.assertRaisesRegex(ValueError,'unrelated tail negative'):q.qualify_tails('missing')

    def test_tail_accepted_mutation_is_rejected(self):
        with (patch.object(q,'validate_tails',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),
              patch.object(q,'case',return_value={})):
            with self.assertRaisesRegex(ValueError,'accepted tail negative'):q.qualify_tails('missing')

    def test_control_retries_require_identical_request_and_response_within_limit(self):
        row={'request':'exact request','response':'exact response'}
        with patch.object(q.p.t,'wire',return_value=('SELECTED',{'sequence':1})):
            self.assertEqual([row],q.control_attempts([row,dict(row),dict(row)]))
            with self.assertRaisesRegex(ValueError,'control retry limit'):q.control_attempts([row]*4)
            with self.assertRaisesRegex(ValueError,'changed control retry'):
                q.control_attempts([row,dict(row,response='changed reply')])
            with self.assertRaisesRegex(ValueError,'changed control retry'):
                q.control_attempts([row,dict(row,request='changed request')])


if __name__=='__main__':unittest.main()
