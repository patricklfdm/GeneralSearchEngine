"""Reject incomplete original histories and falsely successful negative qualifications."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import generation_copy_evidence as q


class GenerationCopyEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_be_counted_as_negative_success(self):
        with patch.object(q,'validate',side_effect=ValueError('original failed')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):q.qualify('missing')
            copied.assert_not_called()

    def test_original_history_precedes_network_and_floor_validation(self):
        with (patch.object(q.b.selection,'layout'),patch.object(q.b,'original',side_effect=ValueError('original source')),
              patch.object(q,'sessions') as network,patch.object(q.floor,'transaction') as floor):
            with self.assertRaisesRegex(ValueError,'original source'):q.case('raw',3,False)
            network.assert_not_called();floor.assert_not_called()

    def test_incomplete_size_or_source_matrix_is_rejected_before_cases(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(q,'case') as case:
            root=Path(temp);(root/'receipt.json').write_text('{}')
            for size,backup in q.PROFILES[:-1]:(root/q.profile(size,backup)).mkdir()
            with self.assertRaisesRegex(ValueError,'generation matrix'):q.validate(root)
            case.assert_not_called()

    def test_accepted_mutation_cannot_pass_qualification(self):
        with (patch.object(q,'validate',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),patch.object(q,'case',return_value={})):
            with self.assertRaisesRegex(ValueError,'accepted mutation'):q.qualify('missing')

    def test_unrelated_failure_cannot_pass_qualification(self):
        with (patch.object(q,'validate',return_value={}),patch.object(q.shutil,'copytree'),patch.object(q,'mutate'),patch.object(q,'case',side_effect=ValueError('wrong failure'))):
            with self.assertRaisesRegex(ValueError,'unrelated negative'):q.qualify('missing')

    def test_changed_or_excess_original_retries_are_rejected(self):
        row=dict(request='original request',response='original response')
        with patch.object(q.t.t,'wire',return_value=('CHUNK',dict(sequence=1))):
            self.assertEqual([row],q.attempts([row,dict(row),dict(row)]))
            with self.assertRaisesRegex(ValueError,'retry limit'):q.attempts([row]*4)
            with self.assertRaisesRegex(ValueError,'changed retry'):q.attempts([row,dict(row,response='changed')])

    def test_reordered_or_missing_requests_are_not_silently_sorted(self):
        def decode(value):return 'CHUNK',dict(sequence=value)
        with patch.object(q.t.t,'wire',side_effect=decode):
            with self.assertRaisesRegex(ValueError,'request sequence'):q.attempts([dict(request=2,response='r')])
            with self.assertRaisesRegex(ValueError,'request sequence'):
                q.attempts([dict(request=1,response='r'),dict(request=2,response='r'),dict(request=1,response='r')])

    def test_prefix_and_generation_cannot_share_one_session(self):
        with patch.object(q.t.t,'wire',return_value=('CHUNK',dict(trace='same'))):
            with self.assertRaisesRegex(ValueError,'complete sessions'):q.sessions([dict(request='q',response='r')])

    def test_duplicate_or_foreign_contact_cannot_replace_missing_peer(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'wire.json'
            for rows in ([dict(node='node-2',exchanges=[])]*2,
                         [dict(node=node,exchanges=[]) for node in ('node-2','node-4')],
                         [dict(node='node-2',exchanges=[])],
                         {'node-2':[]}):
                path.write_bytes(q.e.f.canonical(rows))
                with self.assertRaisesRegex(ValueError,'generation contacted peers'):
                    q.peer_transcripts(path,['node-2','node-3'])
            rows=[dict(node=node,exchanges=[]) for node in ('node-2','node-3')]
            path.write_bytes(q.e.f.canonical(rows))
            self.assertEqual({'node-2':[],'node-3':[]},q.peer_transcripts(path,['node-2','node-3']))


if __name__=='__main__':unittest.main()
