"""Scratch oracle unit cases; synthetic records never qualify native histories."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import process_joint_scratch as m

SOURCE='source-12345678-1234-1234-1234-123456789abc'
IMAGE='ab'*32+'.image'
CHARGES=[('JOURNAL',32*m.MIB),('MISC',2*m.MIB),('GENERATION',9),('APPLICATION',7),('SOURCE',13)]


def inventory():return {'owner.json':b'marker','scope.lock':b'',SOURCE:None,SOURCE+'/source.gscp':b'abc',SOURCE+'/'+IMAGE:b'de'}


def write_tree(path,files):
    path.mkdir(parents=True)
    for key,value in sorted(files.items()):
        if value is None:(path/key).mkdir(parents=True,exist_ok=True)
        else:(path/key).parent.mkdir(parents=True,exist_ok=True);(path/key).write_bytes(value)


def sample(area):
    original={'incoming':{'owner.json':b'in','scope.lock':b''},'outgoing':inventory()}
    rows=[];discarded={};authority=[dict(path='original',sha256='aa'*32)]
    for role in ('INCOMING','OUTGOING'):
        expected,discarded[role]=m.interval(original[role.lower()],CHARGES)
        for row in expected:
            state=f'{len(rows):03d}';write_tree(area/'states'/state,row['files'])
            rows.append(dict(event=row['event'],role=role,state=state,eventCount=2,
                             usage=row['usage'],authority=copy.deepcopy(authority)))
    return dict(rows=rows,discarded=discarded),original,authority


class ProcessJointScratchTest(unittest.TestCase):
    def test_cold_storage_charges_derive_from_bytes_including_empty_partial_copy(self):
        floor='floor-copies/'+'ff'*32
        files={'generations':None,'generations/a':None,'generations/a/generation.gsr':b'1234',
               'generations/a/'+IMAGE:b'1234567','sources':None,'sources/id':None,'sources/id/source.gscp':b'abc',
               'sources/id/'+IMAGE:b'x','floor-copies':None,floor:None,'pending.accept':b'x'*12}
        self.assertEqual(dict(metadata=34*m.MIB+8,staging=12,queued=0,leases=7,
            counts=dict(JOURNAL=1,MISC=1,GENERATION=1,APPLICATION=2,SOURCE=2)),m.usage(m.baseline(files)))
        # A partial floor image consumes one lease/byte even before its payload.
        files[floor+'/'+IMAGE]=b'';after=m.usage(m.baseline(files))
        self.assertEqual(13,after['staging']);self.assertEqual(3,after['counts']['APPLICATION'])
        files['applied-end']=None
        with self.assertRaisesRegex(ValueError,'unexpected live storage'):m.baseline(files)

    def test_combined_count_and_byte_limits_are_checked_without_boolean_integers(self):
        for charges in ([('SOURCE',1)]*7,[('APPLICATION',1)]*8,[('JOURNAL',32*m.MIB+1)],
                        [('CONTROL',8*m.MIB)]*9,[('SOURCE',True)],[('UNKNOWN',1)]):
            with self.subTest(charges=charges),self.assertRaises(ValueError):m.usage(charges)
        self.assertEqual(6,m.usage([('SOURCE',1)]*6)['leases'])

    def test_recovery_charges_all_files_before_deleting_and_keeps_owner_until_close(self):
        rows,discarded=m.interval(inventory(),CHARGES)
        self.assertEqual(['BEFORE_OPEN','OWNER_FORCED','RECOVERY_VALIDATED','FILE_REMOVED','FILE_REMOVAL_FORCED',
            'FILE_REMOVED','FILE_REMOVAL_FORCED','DIRECTORY_REMOVED','DIRECTORY_REMOVAL_FORCED','RECOVERY_COMPLETE','OPEN_RETURN','CLOSED'],[r['event'] for r in rows])
        self.assertEqual(34*m.MIB+25,rows[2]['usage']['metadata'])
        self.assertEqual(25,rows[2]['usage']['staging']);self.assertEqual(32768,rows[2]['usage']['queued'])
        self.assertEqual(8,rows[2]['usage']['leases']);self.assertEqual(23,rows[3]['usage']['staging'])
        self.assertEqual(20,rows[5]['usage']['staging']);self.assertEqual(32768,rows[-2]['usage']['queued'])
        self.assertEqual(m.usage(CHARGES),rows[-1]['usage'])
        self.assertEqual([dict(path=SOURCE+'/'+IMAGE,directory=False,bytes=2),dict(path=SOURCE+'/source.gscp',directory=False,bytes=3),
                          dict(path=SOURCE,directory=True,bytes=0)],discarded)

    def test_empty_scope_still_owns_its_marker_during_recovery(self):
        rows,discarded=m.interval({'owner.json':b'm','scope.lock':b''},CHARGES)
        self.assertEqual(['BEFORE_OPEN','OWNER_FORCED','RECOVERY_VALIDATED','RECOVERY_COMPLETE','OPEN_RETURN','CLOSED'],[r['event'] for r in rows])
        self.assertEqual([],discarded);self.assertEqual(32768,rows[2]['usage']['queued'])

    def test_live_writer_keeps_receivers_until_complete_copy_handoff(self):
        order=['node-6','node-1','node-3','node-2']
        copies={node:{'generation.gsr':b'1234','source.gscp':b'abc',IMAGE:b'12'} for node in order}
        first=m.usage(m.writer_charges(copies,order,CHARGES,1,0))
        self.assertEqual(5,first['counts']['SOURCE']);self.assertEqual(2,first['counts']['APPLICATION'])
        self.assertEqual(9,first['counts']['CONTROL']);self.assertEqual(81932,first['queued'])
        handed=m.usage(m.writer_charges(copies,order,CHARGES,1,1))
        self.assertEqual(4,handed['counts']['SOURCE']);self.assertEqual(first['staging']-3,handed['staging'])
        self.assertEqual(first['queued']-4100,handed['queued'])
        last=m.usage(m.writer_charges(copies,order,CHARGES,4,3))
        self.assertEqual(5,last['counts']['SOURCE']);self.assertEqual(5,last['counts']['APPLICATION'])
        self.assertEqual(3,last['counts']['CONTROL']);self.assertEqual(69632,last['queued'])
        with self.assertRaisesRegex(ValueError,'overlap position'):m.writer_charges(copies,order,CHARGES,3,0)

    def test_resume_borrows_only_a_complete_original_copy_and_retains_partial_charges(self):
        copy_files={'generation.gsr':b'1234','source.gscp':b'abc',IMAGE:b'12','promise.gsr':b'p'}
        cold={'generations':None,'generations/a':None,'generations/a/generation.gsr':b'12345',
              'generations/a/'+IMAGE:b'1234567','sources':None,'pending.accept':b'x'*12,'floor-copies':None}
        prefix='floor-copies/'+'ff'*32+'/'
        common=[('CONTROL',32768),('CONTROL',32768),('CONTROL',4096)]
        for missing in (None,'source.gscp','promise.gsr',IMAGE,'generation.gsr'):
            with self.subTest(missing=missing):
                before=dict(cold,**{prefix[:-1]:None},**{prefix+k:v for k,v in copy_files.items() if k!=missing})
                preserved=copy.deepcopy(before)
                after,charges,borrowed=m.resume_charges(before,prefix,copy_files,True,common)
                self.assertEqual(before,preserved);self.assertEqual(missing is None,borrowed)
                self.assertEqual(copy_files,{k[len(prefix):]:v for k,v in after.items() if k.startswith(prefix)})
                actual=m.usage(charges);self.assertEqual(1+(missing is not None),actual['counts']['SOURCE'])
                self.assertEqual(2,actual['counts']['APPLICATION'])
                self.assertEqual(34*m.MIB+13+(3 if missing else 0),actual['metadata'])
                self.assertEqual(17+(3 if missing else 0),actual['staging'])
                self.assertEqual(69637+(4096 if missing else 0),actual['queued'])

    def test_original_marker_binds_role_identity_path_and_parent(self):
        spec=dict(root=dict(digest='aa'*32),identity=dict(node='node-2'),paths=dict(scratch='/original/scratch'))
        value=dict(schema='gse-v53-derived-scratch-v1',root='aa'*32,identity=spec['identity'],role='OUTGOING',directoryKey='inode-2',
                   parent=dict(path='/original/scratch/outgoing',parentRealPath='/original/scratch',fileStoreName='fs',fileStoreType='ext4',parentFileKey='inode-1'))
        files={'scope.lock':b'','owner.json':m.f.canonical(value)};self.assertEqual(value,m.marker(files,spec,'OUTGOING'))
        for field,replacement,reason in [('role','INCOMING','owner binding'),('root','bb'*32,'owner binding'),
                                        ('identity',dict(node='node-1'),'owner binding'),('directoryKey','','path binding')]:
            changed=copy.deepcopy(value);changed[field]=replacement
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):
                m.marker(dict(files,**{'owner.json':m.f.canonical(changed)}),spec,'OUTGOING')
        changed=copy.deepcopy(value);changed['parent']['path']='/relocated/outgoing'
        with self.assertRaisesRegex(ValueError,'path binding'):m.marker(dict(files,**{'owner.json':m.f.canonical(changed)}),spec,'OUTGOING')

    def test_replay_requires_every_snapshot_force_charge_and_authority(self):
        for variant,reason in [(None,None),('usage','resource accounting'),('boolean','resource accounting'),
                               ('force','ordered recovery forces'),('authority','preserved authority'),
                               ('anchor','event bounds'),('request','before new requests'),('discard','discard list')]:
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as tmp:
                area=Path(tmp);receipt,original,authority=sample(area);row=receipt['rows'][8];events=[{},{}]
                if variant=='usage':row['usage']['metadata']-=1
                if variant=='boolean':row['usage']['leases']=True
                if variant=='force':row['event']='REMOVED_FORCE'
                if variant=='authority':row['authority'][0]['sha256']='bb'*32
                if variant=='anchor':row['eventCount']=3
                if variant=='request':events[0]=dict(node='node-2',request='r')
                if variant=='discard':receipt['discarded']['OUTGOING'].pop()
                if reason:
                    with self.assertRaisesRegex(ValueError,reason):m.replay(area,receipt,original,CHARGES,authority,0,2,events)
                else:
                    result=m.replay(area,receipt,original,CHARGES,authority,0,2,events)
                    self.assertEqual(18,result['callbacks']);self.assertEqual(2,result['discardedFiles'])

    def test_changed_or_unlisted_physical_state_is_rejected(self):
        for variant,reason in [('bytes','exact deletion snapshot'),('extra','exact state inventory')]:
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as tmp:
                area=Path(tmp);receipt,original,authority=sample(area)
                if variant=='bytes':(area/'states/008'/SOURCE/'source.gscp').write_bytes(b'foreign')
                else:(area/'states/extra').mkdir()
                with self.assertRaisesRegex(ValueError,reason):m.replay(area,receipt,original,CHARGES,authority,0,2,[{},{}])

    def test_historical_v1_cannot_qualify_new_scratch_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'joint-floor-recovery').mkdir();case='4,FLOOR_MEMBER_FORCED,kill'
            m.h.save(root/'joint-floor-recovery/receipt.json',m.p.scope(case))
            with self.assertRaisesRegex(ValueError,'requires v2'):m.validate(root)

    def test_invalid_original_never_runs_negative_mutations(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.p,'inspect',side_effect=ValueError('invalid original')),patch.object(m,'negative') as negative:
            root=Path(tmp);(root/'joint-floor-recovery').mkdir()
            m.h.save(root/'joint-floor-recovery/receipt.json',m.p.scope('1,FLOOR_COPY_CREATED,kill',scratch_recovery=True))
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.qualify(root)
            negative.assert_not_called()

    def test_negative_requires_exact_error_and_preserves_all_other_bytes(self):
        for error in (None,ValueError('unrelated'),ValueError('joint scratch recovery receipt scope')):
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'changed').write_bytes(b'original');(root/'protected').write_bytes(b'keep');before=m.h.inventory(root)
                def mutate(raw,name):(raw/'changed').write_bytes(b'changed');return 'changed'
                with patch.object(m,'mutate',side_effect=mutate),patch.object(m,'validate',side_effect=error):
                    if error and str(error)=='joint scratch recovery receipt scope':self.assertEqual('REJECTED',m.negative(root,'receipt-path',before)['status'])
                    else:
                        with self.assertRaisesRegex(ValueError,'unrelated rejection' if error else 'accepted mutation'):m.negative(root,'receipt-path',before)
                self.assertEqual(before,m.h.inventory(root))


if __name__=='__main__':unittest.main()
