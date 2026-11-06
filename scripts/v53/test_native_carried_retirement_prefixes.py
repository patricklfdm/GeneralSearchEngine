import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_retirement_prefixes as p
from . import test_remove_retirement_prefixes as fixtures


class NativeCarriedRetirementPrefixesTest(unittest.TestCase):
    def fixture(self,base,empty_first=False):
        original,captured,files=fixtures.RemoveRetirementPrefixesTest().fixture(base)
        root=base/'observed';root.mkdir();original.rename(root/'history')
        retirement=base/'retirement';retirement.mkdir();expected=[]
        events=json.loads((root/'history/events.json').read_bytes())
        for life in (1,2):
            sidecar=retirement/f'life-{life}';shutil.copytree(captured,sidecar)
            resource=root/f'resources/life-{life}';resource.mkdir(parents=True)
            local=[] if life==1 and empty_first else [dict(node='node-1',event='NODE_OPEN',incarnation=life)]+[dict(v,incarnation=life) for v in events]
            encoded=p.f.canonical(local);(resource/'events.json').write_bytes(encoded)
            index=dict(root='a'*64,life=life,pid=100+life,terminal='CUT_PREFIX' if life==1 else 'CLOSED',eventsSha256=p.shared.sha(encoded))
            (resource/'index.json').write_bytes(p.f.canonical(index))
            if not local:
                for item in sidecar.glob('capture-*.json'):item.unlink()
                for item in (sidecar/'objects').iterdir():item.unlink()
            else:
                for item in sorted(sidecar.glob('capture-*.json')):
                    value=json.loads(item.read_bytes());value['eventIndex']+=1;item.write_bytes(p.f.canonical(value))
                    expected.append(dict(life=life,eventIndex=value['eventIndex'],node='node-1',kind='generation',
                                         point=value['point'],files=p.shared.r.physical(files)))
            header=dict(index,schema=p.SCHEMA,captures=2 if local else 0,
                storedBytes=sum(v.stat().st_size for v in sidecar.rglob('*') if v.is_file() and v.name!='collection.json'))
            (sidecar/'collection.json').write_bytes(p.f.canonical(header))
        shutil.rmtree(captured)
        return root,retirement,expected

    def test_distinct_lifetimes_share_callback_numbers_without_aliasing(self):
        with tempfile.TemporaryDirectory() as temp:
            root,retirement,expected=self.fixture(Path(temp));result=p.replay(root,retirement,expected)
            self.assertEqual(4,result['capturedPrefixes']);self.assertEqual([101,102],[v['pid'] for v in result['lifetimes']])
            self.assertTrue(result['transientRetirementBytesQualified']);self.assertFalse(result['fullTransientBytesQualified'])
            self.assertFalse(result['phase3Complete'])

    def test_pre_retirement_crash_requires_exact_empty_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root,retirement,expected=self.fixture(Path(temp),True)
            self.assertEqual(0,p.replay(root,retirement,expected)['lifetimes'][0]['capturedPrefixes'])
            expected.append(dict(expected[0],life=1))
            with self.assertRaisesRegex(ValueError,'^carried prefix exact original callback coverage$'):p.replay(root,retirement,expected)

    def test_header_cannot_substitute_identity_terminal_or_original_events(self):
        for name in ('process-pid','process-life','process-root','process-terminal','process-events','boolean-pid'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,retirement,expected=self.fixture(Path(temp));p.mutate(retirement,name)
                with self.assertRaisesRegex(ValueError,'^'+p.NEGATIVES[name]+'$'):p.replay(root,retirement,expected)

    def test_missing_callbacks_lifetimes_and_decoder_corruption_refuse_exactly(self):
        names=('missing-callback','missing-lifetime','missing-copy','duplicate-index','wrong-callback','missing-object',
               'altered-object','extra-object','boolean-size','wrong-owner')
        for name in names:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,retirement,expected=self.fixture(Path(temp));p.mutate(retirement,name)
                with self.assertRaisesRegex(ValueError,'^'+p.NEGATIVES[name]+'$'):p.replay(root,retirement,expected)

    def test_captured_bytes_do_not_supply_expected_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root,retirement,expected=self.fixture(Path(temp));expected[0]['files']['retirement/images.json']['sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'^carried prefix exact original state: RETIREMENT_OLD_FILES_FORCED$'):
                p.replay(root,retirement,expected)

    def test_complete_coverage_rejects_duplicate_and_extra_derived_indices(self):
        for duplicate in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                root,retirement,expected=self.fixture(Path(temp));extra=copy.deepcopy(expected[0])
                if not duplicate:extra['eventIndex']=0
                expected.append(extra)
                with self.assertRaisesRegex(ValueError,'^carried prefix exact original callback coverage$'):p.replay(root,retirement,expected)

    def test_record_binding_requires_original_owner_kind_and_point(self):
        for key,value in (('node','node-2'),('kind','source'),('point','RETIREMENT_RESERVED')):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as temp:
                root,retirement,expected=self.fixture(Path(temp));expected[0][key]=value
                with self.assertRaisesRegex(ValueError,'^carried prefix original transaction binding$'):p.replay(root,retirement,expected)

    def test_event_bytes_remain_bound_to_resource_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root,retirement,expected=self.fixture(Path(temp));(root/'resources/life-2/events.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'^carried resource original file digest: events.json$'):p.replay(root,retirement,expected)

    def test_original_fails_before_prefix_replay_or_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.observed,'validate',side_effect=ValueError('original failed')),patch.object(p,'replay') as replay,patch.object(p,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify(temp)
            replay.assert_not_called();mutate.assert_not_called()

    def test_original_inventory_change_during_validation_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                    patch.object(p.observed,'validate',return_value={}),patch.object(p,'replay',return_value={}):
                with self.assertRaisesRegex(ValueError,'^carried prefix original changed$'):p.validate(temp)

    def test_unrelated_failure_cannot_earn_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            _,_,expected=self.fixture(Path(temp))
            with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                    patch.object(p,'NEGATIVES',{'missing-copy':'expected refusal'}),\
                    patch.object(p,'replay',side_effect=ValueError('unrelated failure')):
                with self.assertRaisesRegex(ValueError,'^carried prefix unrelated negative: missing-copy: unrelated failure$'):p.qualify(temp)

    def test_negative_replay_cannot_change_original_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root,_,expected=self.fixture(Path(temp))
            def corrupt(*args):
                (root/'history/before-network/node-1/node.gsr').write_bytes(b'changed original')
                raise ValueError('expected refusal')
            with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                    patch.object(p,'NEGATIVES',{'missing-copy':'expected refusal'}),patch.object(p,'replay',side_effect=corrupt):
                with self.assertRaisesRegex(ValueError,'^carried prefix qualification changed original$'):p.qualify(temp)

    def test_plan_is_derived_from_original_process_kind_cut_and_force_oracle(self):
        with patch.object(p.forces.process,'read',return_value=dict(carriedKind='FINAL',cut='PROOF_RENAMED')),\
                patch.object(p.forces,'replay') as oracle:
            self.assertEqual([],p.plans('/original'))
            oracle.assert_called_once_with(Path('/original/history'),'FINAL','PROOF_RENAMED',prefixes=[])


if __name__=='__main__':unittest.main()
