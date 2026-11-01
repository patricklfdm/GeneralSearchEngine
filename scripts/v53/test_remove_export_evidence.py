"""Original-first REMOVE authority composition and adversarial replay guards."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import remove_export_evidence as r


class RemoveExportEvidenceTest(unittest.TestCase):
    def test_invalid_profile_precedes_filesystem(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^REMOVE export profile$'):r.validate('/unused','3-REMOVE')
        inventory.assert_not_called()

    def test_failed_original_network_prevents_export_authority(self):
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.n,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'bad original'):r.validate('/unused','4-REMOVE')
        replay.assert_not_called()

    def test_changed_original_is_not_qualified(self):
        with patch.object(r.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.n,'validate',return_value={}),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/unused','5-REMOVE')

    def test_failed_original_prevents_negative_mutation(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/unused','4-REMOVE')
        mutate.assert_not_called()

    def test_changed_physical_copy_cannot_count_as_export_negative(self):
        before=dict(files={'original':'a'},directories=[]);after=dict(files={'original':'b'},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',return_value={}),patch.object(r.n.collection,'inventory',side_effect=[before,after]),patch.object(r,'mutate'),patch.object(r.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'negative changed physical input'):r.qualify(temp,'4-REMOVE')
        network.assert_not_called()

    def test_broken_transport_is_not_an_export_authority_rejection(self):
        original=dict(files={},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',return_value={}),patch.object(r.n.collection,'inventory',return_value=original),patch.object(r,'mutate'),patch.object(r.n,'network',side_effect=ValueError('bad network')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad network$'):r.qualify(temp,'4-REMOVE')
        replay.assert_not_called()

    def test_unrelated_rejection_is_not_counted(self):
        original=dict(files={},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',return_value={}),patch.object(r.n.collection,'inventory',return_value=original),patch.object(r,'mutate'),patch.object(r.n,'network'),patch.object(r,'replay',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated export negative: generation-alias: unrelated'):r.qualify(temp,'4-REMOVE')

    def test_accepted_mutation_fails_qualification(self):
        original=dict(files={},directories=[])
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',return_value={}),patch.object(r.n.collection,'inventory',return_value=original),patch.object(r,'mutate'),patch.object(r.n,'network'),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'mutation accepted: generation-alias'):r.qualify(temp,'4-REMOVE')

    def test_unactivated_voter_remains_on_its_original_generation(self):
        history=SimpleNamespace(old=('node-4',),installed={},published={})
        files={'g/generation.gsr':b'manifest','node.gsr':b'identity'}
        with patch.object(r.c,'inventory',return_value=files),patch.object(r.c,'current',return_value=('g/',{},{})),patch.object(r.f,'decode',return_value=dict(identity=dict(node='node-4'))):
            windows=r.generation_windows(Path('/unused'),[dict(node='node-1',event='other')],history)
        self.assertEqual([('node-4',-1,1,'before-network/node-4')],[(v['node'],v['start'],v['end'],v['path']) for v in windows])

    def test_missing_selector_rename_cannot_invent_a_generation(self):
        history=SimpleNamespace(old=('node-1',),installed={(1,'node-1'):{}},published={(1,'node-1'):{}})
        with self.assertRaisesRegex(ValueError,'complete generation timeline'):
            r.generation_windows(Path('/unused'),[dict(node='node-1',event='INSTALL_BEFORE_RETURN'),dict(node='node-1',event='PUBLICATION_BEFORE_RETURN')],history)

    def test_original_generation_must_belong_to_its_node(self):
        history=SimpleNamespace(old=('node-4',),installed={},published={})
        with patch.object(r.c,'inventory',return_value={'g/generation.gsr':b'm','node.gsr':b'n'}),patch.object(r.c,'current',return_value=('g/',{},{})),patch.object(r.f,'decode',return_value=dict(identity=dict(node='node-3'))):
            with self.assertRaisesRegex(ValueError,'generation owner'):r.generation_windows(Path('/unused'),[],history)

    def test_remove_never_counts_direct_fixture_copies_as_network_floor(self):
        reader=r.Replay.__new__(r.Replay)
        with self.assertRaisesRegex(ValueError,'unexpected direct fixture floor'):reader.direct({},0)

    def test_complete_floor_omission_is_not_success(self):
        reader=r.Replay.__new__(r.Replay);reader.events=[];reader.expected_floor_counts=(13,0,35,22)
        with self.assertRaisesRegex(ValueError,'complete original floors'):reader.floors()

    def test_retirement_mutation_uses_exact_lifetime_not_first_equal_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);point=dict(node='node-2',event='SOURCE_RETIREMENT_CREATED')
            events=[dict(point),dict(node='node-1',event='NETWORK_SEND',request='q'),
                dict(node='node-2',event='WIRE_RESPONSE',request='q',response='a'),dict(point),dict(node='node-2',event='end')]
            (root/'events.json').write_bytes(r.f.canonical(events));(root/'wire.json').write_bytes(r.f.canonical([]))
            q=dict(trace='trace',recipient=dict(node='node-2'),payload=dict(digest=r.sha(b'basis')))
            reader=SimpleNamespace(model=None,rows=[dict(request=q,requestHash='q',responseHash='a')],
                groups=[[dict(raw=b'basis',offer=dict(request=q))]],sources=[dict(node='node-2',basis=b'basis',end=3)])
            with patch.object(r.e,'record_kind',return_value='BASIS'):r.e.mutate(root,'source-after-retirement',reader=reader)
            moved=r.n.collection.read_json(root,'events.json',r.n.collection.EVENT_BYTES)
            self.assertLess(max(i for i,v in enumerate(moved) if v['event']=='SOURCE_RETIREMENT_CREATED'),
                            min(i for i,v in enumerate(moved) if v.get('request')=='q'))


if __name__=='__main__':unittest.main()
