"""Synthetic disk/trace binding checks; no native history qualification credit."""
import copy
from pathlib import Path
import tempfile
import unittest

from . import queue_pressure_storage as m
from .test_queue_completion_run import pressure_storage


class QueuePressureStorageTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.original={'generations':None,'generations/g':None,'generations/g/state.image':b'image',
                       'generations/g/metadata':b'metadata','sources':None,'sources/s':None,
                       'sources/s/state.image':b'image','sources/s/metadata':b'packet'}
        self.storage=m.publication.baseline(self.original)
        usage=dict(self.storage,queued=50*1024**2)
        self.trace={'changes':[dict(usage=copy.deepcopy(usage)) for _ in range(6)]}
        self.markers={name:dict(sequence=i*3,eventIndex=i+10,queued=usage['queued']) for i,name in enumerate(m.names())}
        self.points=[dict(event=name,node='node-1',eventIndex=marker['eventIndex'],beforeSequence=marker['sequence'],
                          afterSequence=marker['sequence']+2,files=m.file_rows(m.describe(self.original)['files'])) for name,marker in self.markers.items()]
        self.directory=self.root/m.DIRECTORY;self.directory.mkdir()
        for name in m.names():
            for relative,data in self.original.items():
                p=self.directory/name/relative
                if data is None:p.mkdir(parents=True,exist_ok=True)
                else:p.write_bytes(data)
        self.index={'schema':'gse-v53-queue-storage-captures-v1','points':self.points};self.save()

    def save(self):
        (self.directory/'index.json').write_bytes(m.publication.f.canonical(self.index))

    def value(self):
        return m.load(self.root,self.original)

    def test_same_owner_bytes_and_each_resource_transition_are_replayed(self):
        value=self.value();before=copy.deepcopy(value);result=m.replay(value,self.markers,self.trace);m.check_result(result)
        self.assertEqual(before,value)
        self.assertEqual([50*1024**2]*2,[p['queuedBytes'] for p in result['points']])
        self.assertEqual([2,2],[p['imageCopies'] for p in result['points']])
        self.assertEqual([10,10],[p['physicalApplicationBytes'] for p in result['points']])
        self.assertFalse(result['combinedMaximumQualified']);self.assertFalse(result['phase3Complete'])

    def test_equal_image_contents_count_as_distinct_physical_copies(self):
        result=m.describe(self.original)
        self.assertEqual(2,result['imageCopies']);self.assertEqual(10,result['physicalApplicationBytes'])

    def test_changed_snapshot_bytes_cannot_use_producer_hashes_as_authority(self):
        (self.directory/m.names()[0]/'generations/g/state.image').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'differs from original joint authority'):self.value()

    def test_missing_or_extra_capture_directory_is_rejected(self):
        p=self.directory/m.names()[0];p.rename(self.directory/'wrong')
        with self.assertRaisesRegex(ValueError,'complete captures'):self.value()

    def test_extra_empty_storage_directory_is_not_hidden_by_file_only_hashes(self):
        (self.directory/m.names()[0]/'unowned').mkdir()
        with self.assertRaisesRegex(ValueError,'differs from original joint authority'):self.value()

    def test_symlinked_storage_or_index_is_rejected(self):
        p=self.directory/m.names()[0]/'generations/g/state.image';p.unlink();p.symlink_to(self.directory/m.names()[1]/'generations/g/state.image')
        with self.assertRaises(ValueError):self.value()
        p.unlink();p.write_bytes(b'image')
        index=self.directory/'index.json';index.rename(self.root/'index.json');index.symlink_to(self.root/'index.json')
        with self.assertRaises(ValueError):self.value()

    def test_missing_reordered_and_rehearsal_points_are_rejected(self):
        for points in (self.points[:1],list(reversed(self.points)),[dict(self.points[0],event='EIGHTH_SEND_DELIVERED'),self.points[1]]):
            self.index['points']=points;self.save()
            with self.subTest(points=points),self.assertRaisesRegex(ValueError,'exact index'):self.value()

    def test_foreign_owner_or_unrelated_queue_event_is_rejected(self):
        for field,changed,reason in (('node','node-2','original owner'),('eventIndex',999,'exact resource interval')):
            value=self.value();value['points'][0][field]=changed
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):m.replay(value,self.markers,self.trace)

    def test_moved_truncated_and_boolean_resource_sequences_are_rejected(self):
        for field,changed in (('beforeSequence',1),('beforeSequence',True),('afterSequence',6),('afterSequence',-1)):
            value=self.value();value['points'][0][field]=changed
            with self.subTest(field=field,changed=changed),self.assertRaisesRegex(ValueError,'exact resource interval'):
                m.replay(value,self.markers,self.trace)

    def test_changed_file_inventory_is_rejected(self):
        value=self.value();value['points'][0]['files']={}
        with self.assertRaisesRegex(ValueError,'original inventory'):m.replay(value,self.markers,self.trace)

    def test_physical_paths_require_ordered_unique_value_rows(self):
        for mode in ('object-keys','reordered','duplicate'):
            value=self.value();files=value['points'][0]['files']
            if mode=='object-keys':value['points'][0]['files']=m.describe(self.original)['files']
            elif mode=='reordered':files.reverse()
            else:files.append(files[0])
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original inventory'):
                m.replay(value,self.markers,self.trace)

    def test_transient_storage_growth_cannot_be_hidden_by_equal_endpoints(self):
        self.trace['changes'][1]['usage']['metadata']+=1
        with self.assertRaisesRegex(ValueError,'original reservations'):m.replay(self.value(),self.markers,self.trace)

    def test_queue_only_transitions_do_not_change_physical_storage(self):
        usage=self.trace['changes'][1]['usage'];usage['counts']['CONTROL']=1;usage['leases']+=1;usage['queued']+=1024
        m.check_result(m.replay(self.value(),self.markers,self.trace))

    def test_original_baseline_cannot_be_replaced_by_writer_reserved_bytes(self):
        value=self.value();value['storage']['staging']+=1
        with self.assertRaisesRegex(ValueError,'original reservations'):m.replay(value,self.markers,self.trace)

    def test_summary_cannot_claim_maximum_images_or_full_qualification(self):
        result=pressure_storage();m.check_result(result)
        with self.assertRaisesRegex(ValueError,'maximum original images'):m.check_result(result,image_bytes=64*1024**2)
        for field in ('phase3Complete','combinedMaximumQualified'):
            bad=copy.deepcopy(result);bad[field]=True
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'result scope'):m.check_result(bad)
        for field,changed in (('imageCopies',True),('queuedBytes',0),('reservedStagingBytes',0),('inventorySha256','0'*64)):
            bad=copy.deepcopy(result);bad['points'][0][field]=changed
            with self.subTest(field=field),self.assertRaises(ValueError):m.check_result(bad)


if __name__=='__main__':unittest.main()
