import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_completion_prefixes as p
from . import test_native_carried_vote_prefixes as fixture


class NativeCarriedCompletionPrefixesTest(unittest.TestCase):
    def fixture(self,base):
        previous=base/'previous';previous.mkdir()
        root,old,expected=fixture.NativeCarriedVotePrefixesTest().fixture(previous)
        completion=base/'completion';old.rename(completion)
        renamed={'ACCEPT_VALIDATED':'APPLY_VALIDATED','ACCEPT_CANDIDATE_CREATED':'APPLY_PLAN_CREATED'}
        for life in (1,2):
            resource=root/f'resources/life-{life}';path=resource/'events.json';events=json.loads(path.read_bytes())
            for row in events:row['event']=renamed.get(row['event'],row['event'])
            encoded=p.f.canonical(events);path.write_bytes(encoded)
            index=json.loads((resource/'index.json').read_bytes());index['eventsSha256']=p.shared.sha(encoded)
            (resource/'index.json').write_bytes(p.f.canonical(index))
            directory=completion/f'life-{life}'
            for path in directory.glob('capture-*.json'):
                value=json.loads(path.read_bytes());value.update(schema=p.CAPTURE_SCHEMA,kind='application',point=renamed[value['point']]);path.write_bytes(p.f.canonical(value))
            path=directory/'collection.json';header=json.loads(path.read_bytes());header.update(schema=p.SCHEMA,eventsSha256=index['eventsSha256'])
            header['storedBytes']=sum(v.stat().st_size for v in directory.rglob('*') if v.is_file() and v!=path);path.write_bytes(p.f.canonical(header))
        for row in expected:row.update(kind='application',point=renamed[row['point']])
        return root,completion,expected

    def test_exact_lifetimes_and_partial_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root,completion,expected=self.fixture(Path(temp));result=p.replay(root,completion,expected)
            self.assertEqual(4,result['capturedPrefixes']);self.assertEqual(['CUT_PREFIX','CLOSED'],[v['terminal'] for v in result['lifetimes']])
            self.assertTrue(result['applicationPublicationBytesQualified']);self.assertFalse(result['phase3Complete']);self.assertFalse(result['postCutTailObserved'])

    def test_generic_identity_and_inventory_negatives_reject_exactly(self):
        for name,reason in p.NEGATIVES.items():
            if name in p.PHYSICAL:continue
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,completion,expected=self.fixture(Path(temp));p.mutate(completion,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(root,completion,expected)

    def test_campaign_schema_and_wrong_phase_cannot_relabel_vote_bytes(self):
        for changed in ('schema','kind'):
            with tempfile.TemporaryDirectory() as temp:
                root,completion,expected=self.fixture(Path(temp));path=completion/'life-2/capture-0001.json'
                value=json.loads(path.read_bytes());value[changed]=p.prerequisite.CAPTURE_SCHEMA if changed=='schema' else 'publication';path.write_bytes(p.f.canonical(value))
                with self.assertRaises(ValueError):p.replay(root,completion,expected)

    def test_original_chain_must_pass_before_any_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.prerequisite,'validate',side_effect=ValueError('original failed')),patch.object(p,'replay') as replay,patch.object(p,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify(temp)
            replay.assert_not_called();mutate.assert_not_called()

    def test_unrelated_negative_failure_gets_no_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,expected=self.fixture(Path(temp))
            with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                    patch.object(p,'NEGATIVES',{'missing-copy':'expected'}),patch.object(p,'replay',side_effect=ValueError('unrelated')):
                with self.assertRaisesRegex(ValueError,'^carried completion unrelated negative: missing-copy: unrelated$'):p.qualify(temp)

    def test_plan_does_not_consume_captured_bytes(self):
        with patch.object(p.r.forces.process,'read',return_value=dict(carriedKind='FINAL',cut='PROOF_RENAMED')),patch.object(p.r.forces,'replay') as oracle:
            self.assertEqual([],p.plans('/original'))
        oracle.assert_called_once_with(Path('/original/history'),'FINAL','PROOF_RENAMED',completion_prefixes=[])


if __name__=='__main__':unittest.main()
