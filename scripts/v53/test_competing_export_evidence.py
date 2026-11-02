"""Capability boundaries; synthetic fixtures are not native fault evidence."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import competing_export_evidence as m
from . import test_joining_export_evidence as fixtures


def partial():
    fixture=fixtures.JoiningExportEvidenceTest();windows,q=fixture.inputs();raw=b'original selection'
    q['payload']={'digest':m.sha(raw)}
    value=dict(offer=dict(request=q,received=10,offered=11),through=13,raw=raw,kind='RECORD')
    records=[dict(node='node-2',start=5,end=40,reference=m.sha(raw),raw=raw,ballot=None,view=None,family='journal')]
    return value,windows,records


class CompetingExportEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_capability_interpretation(self):
        with patch.object(m.activation,'Replay') as gate,patch.object(m,'generation_windows') as windows:
            gate.return_value.run.side_effect=ValueError('invalid original')
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.Replay('/original').run()
            windows.assert_not_called()

    def test_incomplete_bytes_are_authorized_without_a_synthetic_commit(self):
        value,windows,records=partial();before=copy.deepcopy(value)
        self.assertEqual('journal',m.e.authorize_record_interval(value,windows,records,value['through']))
        self.assertEqual(before,value);self.assertNotIn('commit',value)
        complete=dict(value,commit={'offered':value['through']})
        self.assertEqual('journal',m.e.authorize_record([complete],windows,records))

    def test_partial_selection_requires_actual_force_and_retirement_interval(self):
        for received,through in ((5,13),(10,40),(40,41)):
            value,windows,records=partial();value['offer']['received']=received
            with self.subTest(received=received,through=through),self.assertRaisesRegex(ValueError,'unavailable original record'):
                m.e.authorize_record_interval(value,windows,records,through)

    def test_partial_transfer_cannot_claim_later_completed_lifetime(self):
        value,windows,records=partial()
        self.assertEqual('journal',m.e.authorize_record_interval(value,windows,records,39))
        with self.assertRaisesRegex(ValueError,'unavailable original record'):
            m.e.authorize_record([dict(value,commit={'offered':40})],windows,records)

    def test_partial_transfer_needs_exact_bytes_and_original_owner(self):
        for kind in ('bytes','owner','view'):
            value,windows,records=partial();q=value['offer']['request']
            if kind=='bytes':value['raw']=b'another selection';reason='exact live record'
            elif kind=='owner':q['sender'],q['recipient']=q['recipient'],q['sender'];reason='unavailable original record'
            else:q['view']='f'*64;reason='record original context'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,reason):
                m.e.authorize_record_interval(value,windows,records,value['through'])

    def test_higher_ballot_does_not_cancel_a_retained_journal_capability(self):
        value,windows,records=partial();value['offer']['request']['ballot']['counter']+=1
        self.assertEqual('journal',m.e.authorize_record_interval(value,windows,records,value['through']))

    def test_generation_replacement_and_inverted_interval_refuse_partial_export(self):
        value,windows,records=partial()
        for through in (9,100):
            with self.assertRaisesRegex(ValueError,'inactive current generation'):
                m.e.authorize_record_interval(value,windows,records,through)

    def test_losing_selected_pair_does_not_invent_a_remote_durable_selection(self):
        schema=m.f.catalog();selected=m.f.sample(schema['records']['SELECTED']['schema'],schema['types'])
        raw=m.f.encode('records','SELECTED',selected);digest=m.sha(raw)
        # Both voters appear in the decision, but only one stores it.
        own=selected['sources'][0]['voter'];peer=selected['sources'][1]['voter']
        replay=SimpleNamespace(root=Path('/original'),events=[],bindings=[dict(node=own,selection=digest,forced=10)],
                               selections={digest:dict(raw=raw)})
        history=SimpleNamespace(selected=selected,initial={own:{},peer:{}},proposer=own,
            snapshots={f'slot-{i}-applied':{own:{'pending.accept':b'pending'}} for i in (1,2)})
        sources=[dict(node=node,start=1,end=30,value=dict(ballot=selected['ballot'])) for node in (own,peer)]
        with patch.object(m.disk,'pending',return_value=({},{})),patch.object(m.e,'record_windows',return_value=[]) as shared:
            result=m.record_windows(replay,history,[],sources)
            self.assertEqual([(own,raw,10,30)],[(v['node'],v['raw'],v['start'],v['end']) for v in result])
            self.assertEqual((),shared.call_args.kwargs['nodes'])
            self.assertEqual([],shared.call_args.kwargs['selection_records'])
            sources[0]['end']=10
            with self.assertRaisesRegex(ValueError,'original durable selection lifetime'):
                m.record_windows(replay,history,[],sources)

    def test_generation_windows_require_every_selector_and_completed_return(self):
        windows,q=fixtures.JoiningExportEvidenceTest().inputs();node=q['recipient']['node'];own=windows[1]
        files={'node.gsr':m.f.encode('records','NODE',dict(root=q['root'],identity=own['identity'])),
               'generation.gsr':own['manifest']}
        history=SimpleNamespace(initial={node:files},voters=[node],installed={node:files},
            snapshots={f'slot-{i}-published':{node:files} for i in (1,2)})
        events=[dict(node=node,event=name) for name in ('INSTALL_SELECTOR_RENAMED','INSTALL_BEFORE_RETURN',
            'INSTALL_SELECTOR_RENAMED','PUBLICATION_BEFORE_RETURN','INSTALL_SELECTOR_RENAMED','PUBLICATION_BEFORE_RETURN')]+[{}]
        with patch.object(m.disk,'current',return_value=('',own['members'],own['packet'])):
            result=m.generation_windows(events,history)
            self.assertEqual([(-1,0),(1,2),(3,4),(5,7)],[(v['start'],v['end']) for v in result])
            for at in (0,1,2,3,4,5):
                with self.subTest(at=at),self.assertRaisesRegex(ValueError,'inactive current generation'):
                    m.e.current(result,node,at,at)
            with self.assertRaisesRegex(ValueError,'complete generation timeline'):
                m.generation_windows(events[:-2],history)
            wrong=copy.deepcopy(events);wrong[0],wrong[1]=wrong[1],wrong[0]
            with self.assertRaisesRegex(ValueError,'selector completion order'):m.generation_windows(wrong,history)

    def test_unselected_owner_keeps_only_its_original_generation_window(self):
        windows,q=fixtures.JoiningExportEvidenceTest().inputs();node=q['recipient']['node'];own=windows[1]
        files={'node.gsr':m.f.encode('records','NODE',dict(root=q['root'],identity=own['identity'])),
               'generation.gsr':own['manifest']}
        history=SimpleNamespace(initial={node:files},voters=[])
        with patch.object(m.disk,'current',return_value=('',own['members'],own['packet'])):
            result=m.generation_windows([{}]*20,history)
            self.assertEqual([(-1,20)],[(v['start'],v['end']) for v in result])
            with self.assertRaisesRegex(ValueError,'complete generation timeline'):
                m.generation_windows([dict(node=node,event='INSTALL_BEFORE_RETURN')],history)

    def test_invalid_original_never_qualifies_capability_negatives(self):
        with patch.object(m.activation.publication.preceding.prefix.collection.h,'inventory',return_value={}), \
                patch.object(m.Replay,'run',side_effect=ValueError('original')),patch.object(m,'negative_claim') as negative:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            negative.assert_not_called()

    def test_negative_requires_exact_rejection_not_an_unrelated_failure(self):
        for error,reason in ((ValueError('other'),'unrelated competing export negative'),(None,'mutation accepted')):
            with self.subTest(error=error),patch.object(m.activation.publication.preceding.prefix.collection.h,'inventory',return_value={}), \
                    patch.object(m.Replay,'run',return_value={}),patch.object(m,'negative_claim',side_effect=error):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')

    def test_unknown_capability_family_cannot_be_dropped(self):
        value,windows,records=partial();value['raw']=b'foreign record';value['offer']['request']['payload']['digest']=m.sha(value['raw'])
        with self.assertRaisesRegex(ValueError,'unavailable original record'):
            m.authorize_session([dict(value,commit={'offered':13})],windows,[],records)


if __name__=='__main__':unittest.main()
