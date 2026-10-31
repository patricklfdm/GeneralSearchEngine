import copy
import os
from pathlib import Path
import tempfile
import unittest
from . import joining_snapshot as j


class JoiningSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'copied';self.root.mkdir()
        self.rows=[]
        for name in sorted(j.ROOTS):
            row=dict(name=name,path=dict(path='/unmounted-original/'+name,parentRealPath='/unmounted-original',
                parentFileKey='parent',fileStoreName='original-store',fileStoreType='ext4'),present=name in j.REQUIRED)
            if row['present']:
                (self.root/name).mkdir();(self.root/name/'record').write_bytes(b'original')
                row['files']=[dict(name='.',identity=dict(directory=True,key=name+'-dir')),
                              dict(name='record',identity=dict(key=name+'-file',size=8,sha256=j.s.digest(b'original')))]
            self.rows.append(row)
        self.save()
    def save(self):
        (self.root/'inventory.json').write_bytes(j.f.canonical(self.rows))
    def row(self,name='replica'):
        return next(v for v in self.rows if v['name']==name)
    def reject(self,reason):
        with self.assertRaisesRegex(ValueError,reason):j.read(self.root)
    def test_portable_original_paths_are_data_and_success_is_partial(self):
        self.assertEqual('PARTIAL',j.validate(self.root)['status'])
        snapshot=j.read(self.root);self.assertEqual(b'original',snapshot.member('replica','record'))
        self.assertFalse(j.validate(self.root)['nativeHistoryQualified'])
    def test_tampered_copied_bytes_are_rejected_and_rechecked_on_read(self):
        snapshot=j.read(self.root);(self.root/'replica/record').write_bytes(b'changed!')
        self.reject('joining snapshot original bytes')
        with self.assertRaisesRegex(ValueError,'joining snapshot original bytes'):snapshot.member('replica','record')
    def test_unlisted_file_or_missing_root_is_rejected(self):
        (self.root/'replica/extra').write_bytes(b'extra');self.reject('joining snapshot copied inventory')
        (self.root/'replica/extra').unlink();(self.root/'materialization').mkdir();self.reject('joining snapshot layout')
    def test_symlink_and_hardlink_copies_are_not_regular_evidence(self):
        path=self.root/'replica/record';original=self.root.parent/'external';original.write_bytes(b'original');path.unlink();path.symlink_to(original)
        self.reject('joining snapshot copied member');path.unlink();os.link(original,path);self.reject('learner snapshot regular member')
    def test_recorded_inode_alias_or_overlapping_roots_are_rejected(self):
        self.row()['files'][1]['identity']['key']=self.row('operation')['files'][1]['identity']['key'];self.save();self.reject('joining snapshot original inode alias')
        self.row()['files'][1]['identity']['key']='replica-file';self.row()['path']=copy.deepcopy(self.row('operation')['path']);self.save();self.reject('joining snapshot overlapping roots')
    def test_relative_member_traversal_and_wrong_path_parent_are_rejected(self):
        self.row()['path']['parentRealPath']='/different';self.save();self.reject('joining snapshot path binding')
        for name in ('../record','/record','x/../../record','x//record'):
            with self.assertRaisesRegex(ValueError,'joining snapshot member path'):j.relative(name)
    def test_duplicate_roots_or_members_are_rejected(self):
        self.rows[-1]=copy.deepcopy(self.rows[0]);self.save();self.reject('joining snapshot roots')
    def test_directory_identity_and_boolean_sizes_are_rejected(self):
        self.row()['files'][0]['identity']['directory']=False;self.save();self.reject('joining snapshot directory identity')
        self.row()['files'][0]['identity']['directory']=True;self.row()['files'][1]['identity']['size']=True;self.save();self.reject('joining snapshot file identity')
    def test_missing_required_root_and_noncanonical_inventory_are_rejected(self):
        (self.root/'inventory.json').write_bytes((self.root/'inventory.json').read_bytes()+b'\n');self.reject('noncanonical evidence')
        self.row()['present']=False;del self.row()['files'];self.save();self.reject('joining snapshot required roots')
    def test_absent_family_cannot_be_read(self):
        with self.assertRaisesRegex(ValueError,'joining snapshot absent family'):j.read(self.root).member('materialization','record')
    def test_placed_stage_is_explicit_and_cannot_pass_as_native(self):
        import shutil
        with self.assertRaisesRegex(ValueError,'joining snapshot premature native roots'):j.read(self.root,stage='placed')
        for name in ('nativeOwner','retirement'):
            shutil.rmtree(self.root/name);row=self.row(name);row['present']=False;del row['files']
        self.save();self.assertEqual('placed',j.validate(self.root,stage='placed')['stage']);self.reject('joining snapshot required roots')
    def test_pending_snapshot_cannot_be_promoted_to_placed_or_native(self):
        import shutil
        for row in self.rows:
            if row['present']:shutil.rmtree(self.root/row['name']);row.pop('files')
            row['present']=row['name'] in j.PENDING
            if row['present']:
                name=row['name'];(self.root/name).mkdir()
                row['files']=[dict(name='.',identity=dict(directory=True,key=name+'-dir'))]
        self.save();self.assertEqual('pending',j.validate(self.root,stage='pending')['stage'])
        for stage in ('placed','native'):
            with self.subTest(stage=stage),self.assertRaisesRegex(ValueError,'joining snapshot required roots'):j.read(self.root,stage=stage)
        row=self.row('nativeOwner');row['present']=True
        (self.root/'nativeOwner').mkdir();row['files']=[dict(name='.',identity=dict(directory=True,key='native-owner'))]
        self.save()
        with self.assertRaisesRegex(ValueError,'joining snapshot premature placement roots'):j.read(self.root,stage='pending')

    def test_duplicate_member_name_is_rejected(self):
        self.row()['files'].append(copy.deepcopy(self.row()['files'][1]));self.save();self.reject('joining snapshot ordered members')


if __name__=='__main__':unittest.main()
