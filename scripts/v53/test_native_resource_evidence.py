"""Original owner/event binding, complete closure and physical preconditions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import native_resource_evidence as r
from . import native_resource_negatives as negatives
from .test_resource_transitions import trace,row,charge


class NativeResourceEvidenceTest(unittest.TestCase):
    def original(self,count=3):
        identities={f'node-{i}':dict(node=f'node-{i}',storage=f'00000000-0000-0000-0000-{i:012d}',host='127.0.0.1',port=12000+i)
                    for i in range(1,count+1)}
        events=[];boundaries=[];owners=[];traces={}
        for node,identity in identities.items():
            value=charge('SOURCE','original',20)
            traces[node]=trace([row('START'),row('RESERVE',added=[value],metadata=20,staging=20,counts={'SOURCE':1}),row('RELEASE',[value])])
            owners.append(dict(identity=identity,path=node+'.json',sha256='unused',registeredAt=len(events)))
            for seq,point in ((1,'OPEN'),(2,'CLOSE')):
                boundaries.append(dict(eventIndex=len(events),node=node,sequence=seq,usage=copy.deepcopy(traces[node]['changes'][seq]['usage'])))
                events.append(dict(node=node,event=point))
        index=dict(schema='gse-v53-resource-capture-index-v1',root='a'*64,owners=owners,eventsSha256='unused',boundariesSha256='unused')
        return index,traces,boundaries,events,identities,'a'*64

    def write(self,root,data):
        index,traces,boundaries,events,*_=copy.deepcopy(data);directory=root/r.DIRECTORY;directory.mkdir(exist_ok=True)
        def save(path,value):
            raw=r.collection.snapshot.f.canonical(value);path.write_bytes(raw);return r.collection.digest(raw)
        index['eventsSha256']=save(root/'events.json',events)
        index['boundariesSha256']=save(directory/'boundaries.json',boundaries)
        for owner in index['owners']:owner['sha256']=save(directory/owner['path'],traces[owner['identity']['node']])
        save(directory/'index.json',index)

    def test_complete_old_and_joining_budgets_bind_without_physical_peak_claim(self):
        for count in (3,6):
            with self.subTest(owners=count):
                result=r.replay(*self.original(count))
                self.assertEqual(count,len(result['owners']));self.assertEqual(count*2,result['eventBoundaries'])
                self.assertTrue(result['nativeBudgetAccountingQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_missing_offline_or_joining_owner_is_refused(self):
        for node in ('node-4','node-6'):
            data=self.original(6);data[0]['owners']=[v for v in data[0]['owners'] if v['identity']['node']!=node];del data[1][node]
            with self.assertRaisesRegex(ValueError,'complete identities'):r.replay(*data)

    def test_foreign_storage_endpoint_root_or_duplicate_owner_is_refused(self):
        for field,value in (('storage','foreign'),('host','192.0.2.1'),('port',12002)):
            data=self.original();data[0]['owners'][0]['identity']=dict(data[0]['owners'][0]['identity'],**{field:value})
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'complete identities'):r.replay(*data)
        data=self.original();data[0]['root']='b'*64
        with self.assertRaisesRegex(ValueError,'complete identities'):r.replay(*data)
        data=self.original();data[0]['owners'].append(data[0]['owners'][0])
        with self.assertRaisesRegex(ValueError,'complete identities'):r.replay(*data)

    def test_event_boundary_omission_swap_duplicate_and_wrong_owner_are_refused(self):
        for mode in ('omit','swap','duplicate','owner','boolean'):
            data=self.original();boundaries=data[2]
            if mode=='omit':boundaries.pop()
            elif mode=='swap':boundaries[0],boundaries[1]=boundaries[1],boundaries[0]
            elif mode=='duplicate':boundaries[1]=copy.deepcopy(boundaries[0])
            elif mode=='owner':boundaries[0]['node']='node-2'
            else:boundaries[0]['eventIndex']=False
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_sequence_range_backwards_and_usage_mismatch_are_refused(self):
        for value in (-1,3,True):
            data=self.original();data[2][0]['sequence']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact event sequence'):r.replay(*data)
        data=self.original();data[2][1]['sequence']=0
        with self.assertRaisesRegex(ValueError,'exact event sequence'):r.replay(*data)
        data=self.original();data[2][0]['usage']['staging']=19
        with self.assertRaisesRegex(ValueError,'derived usage'):r.replay(*data)

    def test_registration_after_first_event_and_unobserved_lifetime_are_refused(self):
        data=self.original();data[0]['owners'][0]['registeredAt']=1
        with self.assertRaisesRegex(ValueError,'exact event sequence'):r.replay(*data)
        data=self.original();data[1]['node-1']=trace([row('START')])
        with self.assertRaisesRegex(ValueError,'unobserved budget lifetime'):r.replay(*data)

    def test_partial_trace_nonzero_close_and_changed_limit_are_refused(self):
        for flag in ('failed','truncated'):
            data=self.original();data[1]['node-1'][flag]=True
            with self.subTest(flag=flag),self.assertRaisesRegex(ValueError,'incomplete observation'):r.replay(*data)
        data=self.original();value=data[1]['node-1'];value['changes'].pop();value['transitions']-=1;value['current']=value['changes'][-1]['usage']
        with self.assertRaisesRegex(ValueError,'outstanding charges'):r.replay(*data)
        data=self.original();data[1]['node-1']['stagingLimit']+=1
        with self.assertRaisesRegex(ValueError,'original limits'):r.replay(*data)

    def test_loader_preserves_exact_original_hashes_and_refuses_extra_files(self):
        data=self.original()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.write(root,data);loaded=r.load(root)
            self.assertEqual(6,r.replay(*loaded,*data[4:])['eventBoundaries'])
            directory=root/r.DIRECTORY;(directory/'unobserved.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'unobserved member'):r.load(root)

    def test_loader_rejects_changed_event_boundary_trace_and_links(self):
        for name in ('events.json',r.DIRECTORY+'/boundaries.json',r.DIRECTORY+'/node-1.json','link'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);data=self.original();self.write(root,data)
                if name=='link':
                    path=root/r.DIRECTORY/'node-1.json';path.unlink();path.symlink_to(root/r.DIRECTORY/'node-2.json')
                else:
                    path=root/name;value=json.loads(path.read_bytes())
                    if name.endswith('node-1.json'):value['changes'][1]['added'][0]['owner']='changed'
                    else:value[0]['node']='node-2'
                    path.write_bytes(r.collection.snapshot.f.canonical(value))
                with self.assertRaises(ValueError):r.load(root)

    def test_loader_rejects_noncanonical_duplicate_keys_and_path_escape(self):
        for mode in ('noncanonical','duplicate','path'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);data=self.original();self.write(root,data);directory=root/r.DIRECTORY
                if mode=='path':
                    index=json.loads((directory/'index.json').read_bytes());index['owners'][0]['path']='../node-1.json'
                    (directory/'index.json').write_bytes(r.collection.snapshot.f.canonical(index))
                else:
                    path=directory/'node-1.json';raw=path.read_bytes()
                    path.write_bytes(raw+b'\n' if mode=='noncanonical' else b'{"schema":"duplicate",'+raw[1:])
                with self.assertRaises(ValueError):r.load(root)

    def test_publication_link_uses_storage_only_but_requires_exact_owner(self):
        data=self.original();boundary=data[2][0];observed=r.publication.usage(boundary['usage'])
        transactions=[[dict(eventIndex=0,node='node-1',storage=observed)]]
        self.assertEqual(1,r.bind_publications(transactions,data[2]))
        boundary['usage']['queued']=8;boundary['usage']['counts']['CONTROL']=1;boundary['usage']['leases']+=1
        self.assertEqual(1,r.bind_publications(transactions,data[2]))
        boundary['usage']['staging']-=1
        with self.assertRaisesRegex(ValueError,'publication storage boundary'):r.bind_publications(transactions,data[2])

    def test_full_entry_requires_original_physical_validation_before_accounting(self):
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.publication,'validate',side_effect=ValueError('bad original')), \
             patch.object(r,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad original'):r.validate('/unused')
        load.assert_not_called()

    def test_required_four_resources_cannot_bypass_complete_ledger_admission(self):
        from . import required_four_ledgers as ledgers
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.publication,'validate',return_value={'status':'PASS'}), \
             patch.object(ledgers,'validate',side_effect=ValueError('bad ledger')),patch.object(r,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad ledger'):r.validate('/unused','5-REPLACE-required-four')
        load.assert_not_called()

    def test_native_extra_inventory_requires_explicit_opt_in(self):
        native=r.publication.native
        for enabled in (False,True):
            with patch.object(native.b.selection,'layout',side_effect=ValueError('layout checked')) as layout:
                with self.assertRaisesRegex(ValueError,'layout checked'):native.validate('/unused',resource_transitions=enabled)
            self.assertEqual(enabled,r.DIRECTORY in layout.call_args.args[1])

    def test_all_negatives_reject_their_own_error_on_three_and_six_original_owners(self):
        for count in (3,6):
            data=self.original(count)
            results=negatives.replay(data[:4],*data[4:])
            self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in results])
            self.assertTrue(all(v['status']=='REJECTED' for v in results))

    def test_invalid_original_cannot_be_counted_as_successful_negatives(self):
        data=self.original();data[1]['node-1']['truncated']=True
        with patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'incomplete observation'):negatives.replay(data[:4],*data[4:])
        mutate.assert_not_called()

    def test_long_encoded_journal_is_not_one_protocol_message(self):
        source=charge('CONTROL','message',8);rows=[row('START')]
        for _ in range(1500):rows.extend([row('RESERVE',added=[source],queued=8,counts={'CONTROL':1}),row('RELEASE',[source])])
        value=trace(rows)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'long.json';path.write_bytes(r.collection.snapshot.f.canonical(value))
            with self.assertRaisesRegex(ValueError,'parser depth/node budget'):r.collection.read_json(path.parent,path.name,128*r.transitions.MIB)
            self.assertEqual(3001,r.transitions.validate(path)['transitions'])


if __name__=='__main__':unittest.main()
