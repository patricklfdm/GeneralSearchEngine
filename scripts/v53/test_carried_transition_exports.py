"""Carried ownership boundaries; mock fixtures never count as native evidence."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import carried_transition_exports as r


class CarriedTransitionExportsTest(unittest.TestCase):
    def test_invalid_kind_precedes_filesystem(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'exact kind'):r.validate('/unused','DATA')
        inventory.assert_not_called()

    def test_bad_original_prevents_exports_and_negative_credit(self):
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.network,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'bad original'):r.validate('/unused','INTENT')
        replay.assert_not_called()
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/unused','FINAL')
        negative.assert_not_called()

    def test_original_inventory_must_be_unchanged(self):
        with patch.object(r.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.network,'validate'),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/unused','FINAL')

    def test_worker_count_is_bounded_and_not_boolean(self):
        for workers in (0,5,True,1.2):
            with self.subTest(workers=workers),patch.object(r,'validate') as validate:
                with self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/unused','INTENT',workers=workers)
            validate.assert_not_called()

    def test_negative_requires_same_physical_inventory_valid_network_and_exact_reason(self):
        before=dict(files={'selector':'a'},directories=[])
        for after,network_error,export_error,reason in (
            (dict(files={'selector':'b'},directories=[]),None,None,'negative changed physical input'),
            (before,ValueError('broken transport'),None,'broken transport'),
            (before,None,ValueError('unrelated'),'unrelated negative'),
            (before,None,None,'mutation accepted')):
            with self.subTest(reason=reason),patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),\
                 patch.object(r.n.collection,'inventory',return_value=after),patch.object(r.network,'replay',side_effect=network_error),\
                 patch.object(r,'replay',side_effect=export_error):
                with self.assertRaisesRegex(ValueError,reason):r.negative('/unused','INTENT',before,'generation-alias')

    def timeline(self,indices):
        history=SimpleNamespace(phases=[dict(ENTRY=str(i).encode(),SELECTED=b's'+str(i).encode()) for i in indices])
        events=[]
        for parts,i in zip(history.phases,indices):
            events += [dict(event='ROUND_INSTALLED',record=r.sha(parts['SELECTED'])),
                       dict(event='DRIVER_APPLIED',index=i),dict(event='DRIVER_PUBLISHED',index=i)]
        return history,events

    def test_two_and_three_rounds_have_exact_original_snapshot_paths(self):
        for indices in ((5,6,7),(6,7)):
            history,events=self.timeline(indices)
            with patch.object(r.f,'decode',side_effect=lambda raw,*args:dict(index=int(raw))):actual=r.snapshots(events,history)
            expected=['before-network']
            for ordinal,i in enumerate(indices,1):expected += [f'installed-{ordinal}',f'applied-{i}',f'published-{i}']
            self.assertEqual(expected+['after-close'],[v[1] for v in actual])
            for change in ('missing','duplicate','reordered'):
                changed=list(events)
                if change=='missing':changed.pop(0)
                elif change=='duplicate':changed.append(events[0])
                else:changed[1],changed[2]=changed[2],changed[1]
                with self.subTest(indices=indices,change=change),patch.object(r.f,'decode',side_effect=lambda raw,*args:dict(index=int(raw))):
                    with self.assertRaisesRegex(ValueError,'snapshot timeline'):r.snapshots(changed,history)

    def test_final_generation_windows_use_six_and_seven_without_third_campaign(self):
        node='node-1';files={'g/generation.gsr':b'g','node.gsr':b'n'}
        history=SimpleNamespace(old=[node],installed={(1,node):files,(2,node):files},published={(1,node):files,(2,node):files})
        events=[dict(node=node,event=point) for point in ['INSTALL_SELECTOR_RENAMED','INSTALL_BEFORE_RETURN','INSTALL_SELECTOR_RENAMED','PUBLICATION_BEFORE_RETURN']*2]
        with patch.object(r.c,'inventory',return_value=files),patch.object(r.c,'current',return_value=('g/',{},{})),\
             patch.object(r.f,'decode',return_value=dict(identity=dict(node=node))):
            windows=r.shared.generation_windows(Path('/unused'),events,history,indices=(6,7))
        self.assertEqual(['before-network/node-1','installed-1/node-1','published-6/node-1','installed-2/node-1','published-7/node-1'],[v['path'] for v in windows])

    def source_windows(self,states,events):
        history=SimpleNamespace(old=['node-2'],phases=[])
        snapshots=[(-1,'before-network'),(1,'installed-1'),(3,'published-6'),(5,'installed-2'),(len(events),'after-close')]
        with patch.object(r.c,'inventory'),patch.object(r.process,'frozen_sources',side_effect=states):
            return r.process.source_windows(Path('/unused'),events,history,history,snapshots=snapshots)

    def test_pending_source_survives_publication_until_its_actual_retirement(self):
        source={'id':dict(node='node-2',basis=b'old')}
        events=[dict(node='node-2',event='other') for _ in range(7)]
        events[4]['event']='SOURCE_RETIREMENT_CREATED'
        windows=self.source_windows([source,source,source,{},{}],events)
        self.assertEqual([(-1,4)],[(v['start'],v['end']) for v in windows])
        # Removing a source early or resurrecting it cannot borrow that later event.
        for states,reason in (([source,{},source,{},{}],'retirement interval'),
                              ([source,source,source,{},source],'immutable source')):
            with self.assertRaisesRegex(ValueError,reason):self.source_windows(states,events)

    def test_snapshot_windows_cannot_be_reordered(self):
        history=SimpleNamespace(old=[],phases=[])
        with self.assertRaisesRegex(ValueError,'snapshot order'):
            r.process.source_windows(Path('/unused'),[{}]*4,history,history,
                                     snapshots=[(-1,'before-network'),(3,'later'),(1,'earlier'),(4,'after-close')])

    def test_retirement_negative_selects_retired_source_not_first_reply(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            events=[dict(node='node-1',event='NETWORK_SEND',request='q'),
                    dict(node='node-2',event='WIRE_RESPONSE',request='q',response='a'),
                    dict(node='node-2',event='SOURCE_RETIREMENT_CREATED'),dict(node='node-1',event='end')]
            (root/'events.json').write_bytes(r.f.canonical(events));(root/'wire.json').write_bytes(r.f.canonical([]))
            retained=dict(trace='retained',recipient=dict(node='node-4'),payload=dict(digest=r.sha(b'first')))
            retired=dict(trace='retired',recipient=dict(node='node-2'),payload=dict(digest=r.sha(b'second')))
            reader=SimpleNamespace(model=None,rows=[dict(request=retired,requestHash='q',responseHash='a')],
                groups=[[dict(raw=b'first',offer=dict(request=retained))],[dict(raw=b'second',offer=dict(request=retired))]],
                sources=[dict(node='node-4',basis=b'first',end=4),dict(node='node-2',basis=b'second',end=2)])
            with patch.object(r.e,'record_kind',return_value='BASIS'):r.e.mutate(root,'source-after-retirement',reader=reader)
            moved=r.n.collection.read_json(root,'events.json',r.n.collection.EVENT_BYTES)
            self.assertLess(next(i for i,v in enumerate(moved) if v['event']=='SOURCE_RETIREMENT_CREATED'),
                            min(i for i,v in enumerate(moved) if v.get('request')=='q'))

    def test_floor_scope_does_not_claim_ledger_process_public_or_phase_closure(self):
        reader=r.Replay.__new__(r.Replay);reader.kind='INTENT';reader.status_rows=[{}]
        with patch.object(reader,'exports',return_value={}),patch.object(reader,'statuses'),patch.object(reader,'floors',return_value={}):result=reader.run()
        self.assertTrue(result['observedExportAuthorityQualified']);self.assertTrue(result['completeCopyFloorLifetimesQualified'])
        for flag in ('retentionRevisionCompositionQualified','processDeathQualified','publicReady','phase3Complete'):self.assertFalse(result[flag])
        with self.assertRaisesRegex(ValueError,'unexpected direct fixture floor'):reader.direct({},0)
        reader.events=[];reader.expected_floor_counts=(7,0,17,10)
        with self.assertRaisesRegex(ValueError,'complete original floors'):reader.floors()


if __name__=='__main__':unittest.main()
