"""Focused lifetime guards; retained native histories supply execution evidence."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_carried_application_exports as x
from . import native_carried_application_maintenance as m
from . import native_carried_application_retention as r
from .test_native_carried_transition_physical import sample
from . import test_native_carried_transition_retention as retention_fixtures


class NativeCarriedApplicationOwnershipTest(unittest.TestCase):
    def interrupted(self,change=None):
        selected=sample('SELECTED');selected['sources']=[dict(selected['sources'][0],voter=node) for node in ('node-1','node-2')]
        selected_raw=x.f.encode('records','SELECTED',selected)
        frames=dict(ENTRY=b'entry',PROOF=b'original proof',CERTIFICATE=b'original certificate')
        events=[dict(event='unused') for _ in range(12)]
        for at,node,name in ((2,'node-1','PROOF_BEFORE_RETURN'),(4,'node-2','PROOF_BEFORE_RETURN'),
                             (6,'node-1','CERTIFICATE_BEFORE_RETURN'),(8,'node-2','PROMISE_FORCED')):
            events[at]=dict(node=node,event=name)
        if change=='missing-force':events[4]=dict(event='unused')
        elif change=='duplicate-return':events[5]=dict(node='node-2',event='PROOF_BEFORE_RETURN')
        elif change=='peer-certificate':events[7]=dict(node='node-2',event='CERTIFICATE_BEFORE_RETURN')
        history=SimpleNamespace(ranges=[dict(kind='interrupted',start=0,stop=10,before='installed')])
        def pending(files):
            result=dict(frames)
            if files=='node-2' and change=='foreign-proof':result['PROOF']=b'foreign proof'
            if change=='foreign-entry':result['ENTRY']=b'foreign entry'
            return result,()
        def owner(windows,node,start,stop):return dict(end=30,identity=dict(storage='storage-'+node))
        with patch.object(x.exports,'interrupted_records',return_value=[]),patch.object(Path,'read_bytes',return_value=selected_raw),\
             patch.object(x.c,'inventory',side_effect=lambda path:path.name),patch.object(x.p.data,'pending',side_effect=pending),\
             patch.object(x.e,'current',side_effect=owner):
            return x.interrupted_records(Path('/original'),events,history,[],SimpleNamespace(phases=[dict(ENTRY=b'entry')]))

    def test_proof_receipts_begin_at_return_and_end_at_promise_or_death(self):
        records=self.interrupted();receipts=[v for v in records if v['family']=='native-vote-receipt']
        self.assertEqual([('node-1',2,10),('node-2',4,8)],[(v['node'],v['start'],v['end']) for v in receipts])
        for row in receipts:
            body=x.json.loads(row['raw']);self.assertEqual('PROOF',body['phase'])
            self.assertEqual(row['node'],body['voter']);self.assertEqual('storage-'+row['node'],body['incarnation'])
            self.assertEqual(x.sha(b'original proof'),body['record'])
            self.assertEqual(x.sha(x.f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=x.sha(row['raw'])))),row['reference'])
        certs=[v for v in records if v['raw']==b'original certificate']
        self.assertEqual([('node-1',6,10)],[(v['node'],v['start'],v['end']) for v in certs])
        self.assertEqual({'pending-record','native-vote-receipt'},{v['family'] for v in records})

    def test_interrupted_exports_cannot_invent_completion_or_peer_application(self):
        for change in ('missing-force','duplicate-return','peer-certificate'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'interrupted completion boundary'):self.interrupted(change)
        with self.assertRaisesRegex(ValueError,'exact original PROOF'):self.interrupted('foreign-proof')
        with self.assertRaisesRegex(ValueError,'original interrupted certificate'):self.interrupted('foreign-entry')

    def boundaries(self):
        before={'b':dict(members={'source.gscp':b'b','image':b'large'}),'a':dict(members={'source.gscp':b'a'})}
        events=[dict(event='unrelated')];starts=[]
        for source in sorted(before):
            starts.append(len(events))
            names=['SOURCE_RETIREMENT_CREATED','SOURCE_RETIREMENT_WRITTEN','SOURCE_RETIREMENT_FORCED',
                   'SOURCE_RETIREMENT_PARENT_FORCED','SOURCE_RETIREMENT_JOURNAL_PRUNED']
            names+=['SOURCE_RETIREMENT_FILE_DELETED']*len(before[source]['members'])
            names+=['SOURCE_RETIREMENT_DIRECTORY_DELETED','SOURCE_RETIREMENT_CLEARED','SOURCE_RETIREMENT_BEFORE_RETURN']
            events += [dict(node='node-1',event=name) for name in names]
        return before,events,starts

    def test_multiple_removed_sources_keep_distinct_sorted_retirement_ends(self):
        before,events,starts=self.boundaries()
        self.assertEqual(dict(zip(('a','b'),starts)),x.retirement_boundaries(events,'node-1',before,{},0,len(events),starts))
        for changed in (starts[:1],list(reversed(starts)),[starts[0],starts[0]]):
            with self.assertRaisesRegex(ValueError,'exact source retirement count'):
                x.retirement_boundaries(events,'node-1',before,{},0,len(events),changed)

    def test_missing_duplicate_or_misbound_source_deletion_is_rejected(self):
        before,events,starts=self.boundaries()
        for index in range(1,len(events)):
            if events[index]['event']=='SOURCE_RETIREMENT_CREATED':continue
            changed=copy.deepcopy(events);changed[index]['event']='unrelated'
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'complete per-source retirement'):
                x.retirement_boundaries(changed,'node-1',before,{},0,len(changed),starts)
        altered=copy.deepcopy(before);altered['a']['members']['foreign.image']=b'wrong'
        with self.assertRaisesRegex(ValueError,'complete per-source retirement'):
            x.retirement_boundaries(events,'node-1',altered,{},0,len(events),starts)

    def test_campaign_defers_staged_owner_and_interrupted_slot_maintains_all_voters(self):
        before={'node-1':{'applied-end':None},'node-2':{}};voters=list(before)
        with patch.object(m.protocol,'pin_current',return_value=False) as pin:
            current,eligible,annotations=m.stage_projector(before,copy.deepcopy(before),voters,dict(kind='campaign'),voters,m.protocol.application.CUT)
            self.assertEqual(['node-2'],eligible);self.assertIn('applied-end',current['node-1']);pin.assert_called_once_with(current,'node-2')
        before={node:{} for node in voters}
        with patch.object(m.protocol,'pin_current',return_value=True):
            current,eligible,annotations=m.stage_projector(before,copy.deepcopy(before),[],dict(kind='interrupted'),voters,m.protocol.application.CUT)
            self.assertEqual(voters,eligible);self.assertTrue(all(v['pinned'] for v in annotations.values()))

    def test_slot_retires_old_end_under_original_authority_before_floor(self):
        before={'node-1':{'applied-end':None,'pending.accept':b'old'}}
        current={'node-1':{'applied-end':None,'pending.accept':b'new'}}
        with patch.object(m.p.data,'pending',return_value=(dict(ENTRY=b'entry',PAYLOAD=b'payload'),())),\
             patch.object(m.protocol.application,'retire') as retire,patch.object(m.protocol,'pin_current',return_value=False):
            result,eligible,_=m.stage_projector(before,current,['node-1'],dict(kind='slot'),['node-1'],m.protocol.application.CUT)
            retire.assert_called_once_with(before['node-1'],b'entry',b'payload')
            self.assertEqual({'pending.accept':b'new'},result['node-1']);self.assertIn('applied-end',before['node-1'])
        with self.assertRaisesRegex(ValueError,'original cut'):m.stage_projector({}, {},[],dict(kind='campaign'),[],'ACCEPT_RENAMED')

    def test_floor_callbacks_use_derived_pinning_not_the_observed_event_list(self):
        reader=m.Replay.__new__(m.Replay);reader.expected={(3,'node-1'):dict(pinned=True)}
        with patch.object(reader,'stage',return_value=(3,{})),patch.object(m.maintenance.maintenance,'floor_events',return_value=[]) as floor:
            reader.expected_events({'original':'bytes'},dict(node='node-1'),True,12,30)
            floor.assert_called_once_with({'original':'bytes'},'node-1',True,pinned=True)

    def test_certificate_recovery_keeps_the_original_ledger_reseals(self):
        base=retention_fixtures.NativeCarriedTransitionRetentionTest().opens()
        for row in base.events:
            if row.get('event')=='ACCEPT_ACTIVE_PARENT_FORCED':row['event']='CERTIFICATE_ACTIVE_PARENT_FORCED'
        with self.assertRaisesRegex(ValueError,'original open recovery interval'):r.retention.open_reseals(base)
        base.recovery_phases=m.Replay.recovery_phases
        self.assertEqual(4,len(r.retention.open_reseals(base)))
        base.events[2]['event']='missing'
        with self.assertRaisesRegex(ValueError,'exact open reseal order'):r.retention.open_reseals(base)

    def test_each_new_layer_requires_the_complete_preceding_reader(self):
        for module,preceding in ((x,x.protocol),(m,m.exports),(r,r.maintenance)):
            with self.subTest(module=module.__name__),patch.object(module.p.process.collection,'inventory',return_value={}),\
                 patch.object(preceding,'validate',side_effect=ValueError('original rejected')),patch.object(module,'replay') as replay,\
                 patch.object(module.shutil,'copytree') as copytree:
                with self.assertRaisesRegex(ValueError,'original rejected'):module.qualify('/original')
                replay.assert_not_called();copytree.assert_not_called()

    def test_each_reader_rejects_mutation_of_original_during_replay(self):
        for module,preceding,value in ((x,x.protocol,dict(original=dict(physical=dict(kind='FINAL')))),
                (m,m.exports,dict(exports=dict(kind='FINAL'))),(r,r.maintenance,dict(maintenance=dict(kind='FINAL')))):
            with self.subTest(module=module.__name__),patch.object(module.p.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                 patch.object(preceding,'validate',return_value=value),patch.object(module,'replay',return_value={}):
                with self.assertRaisesRegex(ValueError,'original changed'):module.validate('/original')

    def test_negatives_cannot_change_storage_or_unrelated_observations(self):
        original=dict(files={'pending.accept':'original'},directories=[]);changed=dict(files={'pending.accept':'changed'},directories=[])
        for module,preceding,value in ((x,x.exports,dict(exports=dict(kind='FINAL'))),
                (m,m.maintenance,dict(maintenance=dict(kind='FINAL'))),(r,r.retention,dict(retention=dict(kind='FINAL')))):
            with self.subTest(module=module.__name__),patch.object(module.p.process.collection,'inventory',side_effect=[original,changed]),\
                 patch.object(module,'validate',return_value=value),patch.object(preceding,'mutate'),patch.object(module.shutil,'copytree'),\
                 patch.object(module,'NEGATIVES',{'peers':{'one':'reason'}} if module is r else {'one':'reason'}):
                with self.assertRaisesRegex(ValueError,'negative changed'):module.qualify('/original')


if __name__=='__main__':unittest.main()
