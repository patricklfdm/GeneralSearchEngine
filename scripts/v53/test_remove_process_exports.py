"""Fail-closed temporal boundaries; synthetic fixtures are not native evidence."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import remove_process_exports as r


class RemoveProcessExportsTest(unittest.TestCase):
    def events(self):
        return [dict(node='node-1',event='PROCESS_OPEN',value='kill'),dict(node='node-1',event='NETWORK_SEND'),
            dict(node='node-1',event='PROCESS_CUT'),dict(node='node-1',event='STORE'),
            dict(node='node-1',event='PROCESS_OPEN',value='resume'),dict(node='node-1',event='NETWORK_REQUEST'),
            dict(node='node-1',event='PROCESS_CLOSED',value='resume')]

    def test_network_is_bound_to_two_separate_process_lifetimes(self):
        events=self.events();self.assertEqual([(0,2),(4,6)],r.lifetimes(events,dict(mode='kill')))
        events[3]=dict(node='node-1',event='NETWORK_SEND')
        with self.assertRaisesRegex(ValueError,'^REMOVE process network outside owner lifetime$'):r.lifetimes(events,dict(mode='kill'))

    def test_missing_extra_reordered_or_foreign_owner_markers_refuse(self):
        for change in ('missing','extra','reordered','foreign'):
            events=self.events()
            if change=='missing':events.pop(2)
            elif change=='extra':events.append(events[0])
            elif change=='reordered':events[2],events[4]=events[4],events[2]
            else:events[4]=dict(events[4],value='kill')
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'REMOVE process export owner'):r.lifetimes(events,dict(mode='kill'))

    def test_generation_authority_cannot_span_owner_death(self):
        history=SimpleNamespace(old=('node-1',),installed={},published={});activation=SimpleNamespace(installed={(1,'node-1'):{'g/generation.gsr':b'g','node.gsr':b'n'}})
        events=[dict(node='node-1',event='other') for _ in range(20)]
        events[6]['event']='INSTALL_SELECTOR_RENAMED';events[7]['event']='INSTALL_BEFORE_RETURN'
        with patch.object(r.c,'inventory',return_value={'g/generation.gsr':b'g','node.gsr':b'n'}),\
             patch.object(r.c,'current',return_value=('g/',{},{})),patch.object(r.f,'decode',return_value=dict(identity=dict(node='node-1'))):
            windows=r.generation_windows(Path('/unused'),events,history,activation,dict(mode='kill'),[(1,8),(12,18)])
        self.assertEqual([(1,6),(7,8),(12,18)],[(v['start'],v['end']) for v in windows])
        for lower,upper in ((8,12),(7.5,12.5),(9,10)):
            with self.assertRaisesRegex(ValueError,'inactive current generation'):r.e.current(windows,'node-1',lower,upper)

    def test_missing_generation_rename_is_not_reconstructed_from_snapshot(self):
        history=SimpleNamespace(old=('node-1',),installed={},published={});activation=SimpleNamespace(installed={(1,'node-1'):{}})
        with self.assertRaisesRegex(ValueError,'complete generation timeline'):
            r.generation_windows(Path('/unused'),[dict(node='node-1',event='INSTALL_BEFORE_RETURN')],history,activation,dict(mode='kill'),[(0,2)])

    def sources(self,states,events):
        history=SimpleNamespace(old=('node-2',));activation=SimpleNamespace(phases=[])
        with patch.object(r.c,'inventory'),patch.object(r,'frozen_sources',side_effect=states):
            return r.source_windows(Path('/unused'),events,history,activation)

    def test_actual_source_retirement_ends_its_export_window(self):
        before={'id':dict(node='node-2',basis=b'b')}
        events=[dict(node='node-2',event='SOURCE_RETIREMENT_CREATED'),dict(node='node-1',event='PROCESS_SNAPSHOT',value='next')]
        result=self.sources([before,{},{}],events)
        self.assertEqual([(-1,0)],[(v['start'],v['end']) for v in result])

    def test_missing_source_retirement_cannot_be_inferred_from_final_absence(self):
        events=[dict(node='node-1',event='PROCESS_SNAPSHOT',value='next')]
        with self.assertRaisesRegex(ValueError,'original source retirement interval'):
            self.sources([{'id':dict(node='node-2',basis=b'b')},{}],events)

    def test_spurious_retirement_and_changed_frozen_source_refuse(self):
        before={'id':dict(node='node-2',basis=b'b')}
        for events,states,reason in (
            ([dict(node='node-2',event='SOURCE_RETIREMENT_CREATED')],[before,before],'retirement without removed source'),
            ([],[before,{'id':dict(node='node-2',basis=b'changed')}],'immutable source'),
            ([],[{},before],'source without grant')):
            with self.assertRaisesRegex(ValueError,reason):self.sources(states,events)

    def test_interrupted_selection_is_a_journal_record_without_a_completed_slot(self):
        records=[b'first',b'second'];model=SimpleNamespace(phases=[dict(SELECTED=b'second')]);events=[dict(node='node-1',event='SELECTED_FORCED')]*2
        sources=[dict(node='node-1',start=-1,end=5,promise=b'promise',value=dict(ballot=v)) for v in records]
        with patch.object(r.e.f,'decode',side_effect=lambda raw,*args:dict(sources=[dict(voter='node-1')],ballot=raw)),\
             patch.object(r.e.n.phase,'blocks',return_value={}):
            with self.assertRaisesRegex(ValueError,'journal selection timeline'):
                r.e.record_windows('/unused',events,model,[],sources,nodes=['node-1'])
            result=r.e.record_windows('/unused',events,model,[],sources,nodes=['node-1'],selection_records=records)
        self.assertEqual(records,[v['raw'] for v in result if v['raw'] in records])

    def test_bad_network_prevents_all_export_claims(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.n,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.validate('/original')
        replay.assert_not_called()

    def test_expiry_negative_never_moves_killed_child_output_into_resumed_lifetime(self):
        def group(raw,start,end):return [dict(raw=raw,offer=dict(sent=start,request=dict(recipient=dict(node='node-2'),payload=dict(digest=r.sha(raw)))),commit=dict(delivered=end))]
        first,second=group(b'first',1,2),group(b'second',11,12)
        reader=SimpleNamespace(groups=[first,second],sources=[dict(node='node-2',basis=b'first',end=13),dict(node='node-2',basis=b'second',end=15)],live=[(0,5),(10,20)])
        with patch.object(r.e,'record_kind',return_value='BASIS'):
            self.assertEqual((second,15),r.movable_source(reader));reader.groups=[first]
            with self.assertRaisesRegex(ValueError,'same-lifetime source retirement'):r.movable_source(reader)

    def test_original_failure_or_invalid_worker_count_prevents_mutations(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()
        for workers in (0,5,True,1.2):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/original',workers=workers)
            validate.assert_not_called()

    def test_negative_requires_unchanged_physical_files_valid_network_and_exact_reason(self):
        before=dict(files={'owner/selector':'a'},directories=[])
        for after,network_error,export_error,reason in (
            (dict(files={'owner/selector':'b'},directories=[]),None,None,'negative changed physical inputs'),
            (before,ValueError('bad network'),None,'bad network'),
            (before,None,ValueError('different'),'unrelated export negative'),
            (before,None,None,'mutation accepted')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
                 patch.object(r.n,'validate',side_effect=network_error),patch.object(r,'replay',side_effect=export_error):
                with self.assertRaisesRegex(ValueError,reason):r.negative('/original',{},before,'generation-alias')


if __name__=='__main__':unittest.main()
