import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_campaign_prefixes as p
from . import test_native_carried_floor_prefixes as fixture


class NativeCarriedCampaignPrefixesTest(unittest.TestCase):
    def fixture(self,base,empty_first=False):
        maintenance=base/'maintenance';maintenance.mkdir();root,retirement,expected=fixture.NativeCarriedFloorPrefixesTest().fixture(maintenance,empty_first)
        campaigns=base/'campaigns';retirement.rename(campaigns);retirement.mkdir()
        renamed={'FLOOR_RESERVED':'PROMISE_BEFORE_WRITE','FLOOR_DIRECTORY_CREATED':'PROMISE_WRITTEN'}
        for life in (1,2):
            resource=root/f'resources/life-{life}';path=resource/'events.json';events=json.loads(path.read_bytes())
            for row in events:row['event']=renamed.get(row['event'],row['event'])
            encoded=p.f.canonical(events);path.write_bytes(encoded)
            index=json.loads((resource/'index.json').read_bytes());index['eventsSha256']=p.shared.sha(encoded)
            (resource/'index.json').write_bytes(p.f.canonical(index))
            directory=campaigns/f'life-{life}'
            for path in directory.glob('capture-*.json'):
                value=json.loads(path.read_bytes());value.update(schema=p.CAPTURE_SCHEMA,kind='grant',point=renamed[value['point']]);path.write_bytes(p.f.canonical(value))
            path=directory/'collection.json';header=json.loads(path.read_bytes());header.update(schema=p.SCHEMA,eventsSha256=index['eventsSha256'])
            header['storedBytes']=sum(v.stat().st_size for v in directory.rglob('*') if v.is_file() and v!=path);path.write_bytes(p.f.canonical(header))
        for row in expected:row.update(kind='grant',point=renamed[row['point']])
        return root,campaigns,expected

    def test_campaign_files_keep_distinct_lifetimes_and_partial_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root,campaigns,expected=self.fixture(Path(temp));value=p.replay(root,campaigns,expected)
            self.assertEqual(4,value['capturedPrefixes']);self.assertEqual([101,102],[v['pid'] for v in value['lifetimes']])
            self.assertTrue(value['transientCampaignBytesQualified']);self.assertFalse(value['fullTransientBytesQualified'])
            self.assertFalse(value['phase3Complete'])

    def test_empty_crash_prefix_must_equal_empty_derived_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root,campaigns,expected=self.fixture(Path(temp),True)
            self.assertEqual(0,p.replay(root,campaigns,expected)['lifetimes'][0]['capturedPrefixes'])
            expected.append(dict(expected[0],life=1))
            with self.assertRaisesRegex(ValueError,'^carried prefix exact original callback coverage$'):p.replay(root,campaigns,expected)

    def test_header_callback_and_object_mutations_preserve_exact_refusal(self):
        for name,reason in p.NEGATIVES.items():
            if name in p.PHYSICAL:continue
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,campaigns,expected=self.fixture(Path(temp));p.mutate(campaigns,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(root,campaigns,expected)

    def test_old_retirement_schema_cannot_relabel_campaign_collection(self):
        for header in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                root,campaigns,expected=self.fixture(Path(temp));path=campaigns/'life-2'/('collection.json' if header else 'capture-0001.json')
                value=json.loads(path.read_bytes());value['schema']=p.r.SCHEMA if header else p.shared.SCHEMA;path.write_bytes(p.f.canonical(value))
                reason='carried prefix original lifetime binding' if header else 'REMOVE prefix metadata shape/index'
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(root,campaigns,expected)

    def test_exact_whole_inventory_and_transaction_kind_are_required(self):
        for kind in (False,True):
            with tempfile.TemporaryDirectory() as temp:
                root,campaigns,expected=self.fixture(Path(temp))
                if kind:expected[0]['kind']='selected';reason='carried prefix original transaction binding'
                else:expected[0]['files']['root.gsr']['sha256']='b'*64;reason='carried prefix exact original state: PROMISE_BEFORE_WRITE'
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(root,campaigns,expected)

    def test_full_retirement_prerequisite_precedes_replay_and_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.prerequisite,'validate',side_effect=ValueError('original failed')),patch.object(p,'replay') as replay,patch.object(p,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify(temp)
            replay.assert_not_called();mutate.assert_not_called()

    def test_validation_refuses_original_inventory_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.prerequisite,'validate',return_value={}),patch.object(p,'replay',return_value={}),\
                    patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]):
                with self.assertRaisesRegex(ValueError,'^carried campaign original changed$'):p.validate(temp)

    def test_plan_uses_only_original_kind_cut_and_force_model(self):
        with patch.object(p.r.forces.process,'read',return_value=dict(carriedKind='INTENT',cut='ACCEPT_RENAMED')),\
                patch.object(p.r.forces,'replay') as oracle:
            self.assertEqual([],p.plans('/original'))
            oracle.assert_called_once_with(Path('/original/history'),'INTENT','ACCEPT_RENAMED',campaign_prefixes=[])

    def test_unrelated_failure_cannot_earn_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,expected=self.fixture(Path(temp))
            with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                    patch.object(p,'NEGATIVES',{'missing-copy':'expected refusal'}),patch.object(p,'replay',side_effect=ValueError('unrelated')):
                with self.assertRaisesRegex(ValueError,'^carried campaign unrelated negative: missing-copy: unrelated$'):p.qualify(temp)

    def test_negative_replay_cannot_modify_original_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root,_,expected=self.fixture(Path(temp))
            def corrupt(*args):
                (root/'history/before-network/node-1/node.gsr').write_bytes(b'changed original');raise ValueError('expected refusal')
            with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                    patch.object(p,'NEGATIVES',{'missing-copy':'expected refusal'}),patch.object(p,'replay',side_effect=corrupt):
                with self.assertRaisesRegex(ValueError,'^carried campaign qualification changed original$'):p.qualify(temp)


if __name__=='__main__':unittest.main()
