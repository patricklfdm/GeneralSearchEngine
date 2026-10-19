"""Original synthetic build bytes, exclusive staging and offline controls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_staging as s,controls
from . import test_cloud_inputs as fixture


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.case=fixture.InputsTest();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root/'checkout';self.root.mkdir();self.expected=self.case.verify();self.serial=0
        for name,obj,value in (('checkout',s.inputs,fixture.binding()),('controls',s.inputs,(self.case.controls_raw,self.case.pins)),
                               ('layout',s.inputs.build,fixture.roots())):
            mock=patch.object(obj,name,return_value=value);mock.start();self.addCleanup(mock.stop)
    def stage(self):
        self.serial+=1
        obj=s.stage(self.root,'a'*40,self.case.build,self.case.archive,self.case.root/f'stage-{self.serial}',expected=self.expected)
        self.addCleanup(obj.close);return obj
    def test_exact_five_original_jars_and_reuse_without_build_or_network(self):
        first=self.stage();self.assertEqual(self.expected,first.check());self.assertEqual(5,len(first.files))
        self.assertEqual(set(s.paths()),{p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file()})
        before={n:(self.root/n).stat() for n in first.files}
        second=self.stage();self.assertTrue(all(r['reused'] for r in second.receipt['files'].values()))
        self.assertEqual(before,{n:(self.root/n).stat() for n in first.files})
        self.assertFalse(second.receipt['paidAdmission']);self.assertFalse(second.receipt['fullRemoteQualification'])
    def test_normal_read_access_time_update_is_not_input_drift(self):
        obj=self.stage();path=self.root/s.paths()[0];before=path.stat()
        os.utime(path,ns=(1,before.st_mtime_ns))
        self.assertEqual(self.expected,obj.check())
        self.assertEqual(1,path.stat().st_nlink)
    def test_late_conflicting_destination_prevents_all_earlier_writes(self):
        name=s.paths()[-1];path=self.root/name;path.parent.mkdir(parents=True);path.write_bytes(b'conflict')
        with self.assertRaisesRegex(ValueError,'type/size|bytes changed'):self.stage()
        self.assertEqual([path],list(p for p in self.root.rglob('*') if p.is_file()))
    def test_symlink_parent_and_linked_files_are_never_followed(self):
        other=self.case.root/'outside';other.mkdir();(self.root/'target').symlink_to(other,target_is_directory=True)
        with self.assertRaises(OSError):self.stage()
        self.assertEqual([],list(other.iterdir()));(self.root/'target').unlink()
        obj=self.stage();name=s.paths()[0];path=self.root/name;raw=path.read_bytes();path.unlink()
        outside=other/'jar';outside.write_bytes(raw);path.symlink_to(outside)
        with self.assertRaises(OSError):obj.check()
        path.unlink();os.link(outside,path)
        with self.assertRaisesRegex(ValueError,'type/size'):obj.check()
    def test_fifo_and_shared_writable_directory_reject_without_waiting(self):
        path=self.root/s.paths()[0];path.parent.mkdir();os.mkfifo(path)
        with self.assertRaisesRegex(ValueError,'type/size'):self.stage()
        path.unlink();path.parent.chmod(0o777)
        with self.assertRaisesRegex(ValueError,'directory owner/mode'):self.stage()
    def test_missing_changed_or_retargeted_staging_cannot_be_used(self):
        obj=self.stage();name=s.paths()[0];path=self.root/name;raw=path.read_bytes()
        path.write_bytes(b'x'*len(raw))
        with self.assertRaisesRegex(ValueError,'bytes changed'):obj.check()
        path.unlink()
        with self.assertRaisesRegex(ValueError,'input missing'):obj.check()
        self.root.rename(self.root.with_name('original'));self.root.mkdir()
        with self.assertRaisesRegex(ValueError,'root changed'):obj.check()
    def test_approval_proof_and_package_are_reverified_before_output(self):
        self.expected=deepcopy(self.expected);self.expected['packageSha256']='f'*64
        with self.assertRaisesRegex(ValueError,'inspection changed'):self.stage()
        self.assertEqual([],list(self.root.iterdir()))
        self.expected=self.case.verify();self.case.archive.write_bytes(b'corrupt')
        with self.assertRaises(Exception):self.stage()
        self.assertEqual([],list(self.root.iterdir()))
    def test_failed_exclusive_write_stays_consumed_without_overwrite(self):
        original=s.os.fsync;failed=False
        def sync(fd):
            nonlocal failed
            if not failed and (self.root/s.paths()[0]).exists():failed=True;raise OSError('original fsync failed')
            return original(fd)
        with patch.object(s.os,'fsync',side_effect=sync),self.assertRaisesRegex(OSError,'fsync failed'):self.stage()
        self.assertTrue((self.root/s.paths()[0]).exists())
        # Fully written original bytes can be independently verified on a new
        # admission, but a partial byte sequence is never repaired by staging.
        (self.root/s.paths()[0]).write_bytes(b'partial')
        with self.assertRaisesRegex(ValueError,'type/size'):self.stage()
        self.assertEqual(b'partial',(self.root/s.paths()[0]).read_bytes())
    def test_drift_during_inspection_and_closed_handle_reject(self):
        obj=self.stage();obj.close()
        with self.assertRaisesRegex(ValueError,'closed'):obj.check()
        with patch.object(s.inputs,'checkout',return_value=dict(fixture.binding(),source='c'*40)):
            with self.assertRaisesRegex(ValueError,'binding/layout'):self.stage()
    def test_offline_controls_never_download_or_write_a_receipt(self):
        root=self.case.root/'controls-root';doc=root/'docs/v5x/v5.2';doc.mkdir(parents=True)
        entries=[];out=self.case.root/'controls';out.mkdir()
        for name,raw in self.case.published.items():
            artifact,version=name[:-4].rsplit('-',1)
            entries.append(dict(artifact=artifact,version=version,sha256=s.digest(raw)));(out/name).write_bytes(raw)
        (doc/'published-controls.json').write_text(json.dumps(dict(artifacts=entries)))
        with patch.object(controls,'ROOT',root),patch.object(controls.urllib.request,'urlopen') as fetch:
            self.assertEqual('PASS',controls.resolve(out,allow_download=False)['status'])
            self.assertFalse((out/'receipt.json').exists());(out/name).unlink()
            with self.assertRaisesRegex(ValueError,'missing from original staging'):controls.resolve(out,allow_download=False)
            fetch.assert_not_called()


if __name__=='__main__':unittest.main()
