"""Portable mount-backing admission tests; no namespace or SSH execution claim."""
import os
from pathlib import Path
import tempfile
import unittest
from . import guest_isolation as isolation, guest_delivery_receiver as receiver


class BackingAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        # Exercise the real argv/backing builder without Linux namespace setup.
        self.views=isolation.Views.__new__(isolation.Views)
        self.views.root=self.root/'views';self.views.root.mkdir()
        self.views.cell=self.root/'mount';self.views.cell.mkdir(mode=0o700)
        self.views.prefix=['unshare'];self.views.parent_namespace='fixture-mount-namespace';self.views.sudo=True
        self.value=dict(binding=dict(attempt='a'*32,node='node-1'))
    def test_fresh_backing_meets_real_receiver_contract_under_common_umasks(self):
        for mask in (0o022,0o002):
            previous=os.umask(mask)
            try:
                for name in ('producer','node-1','node-2','node-3'):
                    with self.subTest(umask=oct(mask),member=name):
                        key=name+'-'+str(mask);argv=self.views.args(key,['/bin/true'])
                        backing=self.views.root/key
                        self.assertIn(str(backing),argv)
                        # Bind mounts expose this directory's permissions, not
                        # the covered mountpoint's existing 0700 permissions.
                        self.assertEqual(receiver.location(backing,self.value,os.getuid()),backing/('a'*32+'-node-1'))
            finally:os.umask(previous)
    def test_reconnect_preserves_existing_private_backing_and_claim(self):
        self.views.args('node-1',['/bin/true']);backing=self.views.root/'node-1'
        inode=backing.stat().st_ino;claim=backing/'claim';claim.write_bytes(b'consumed')
        self.views.args('node-1',['/bin/true'])
        receiver.location(backing,self.value,os.getuid())
        self.assertEqual(backing.stat().st_ino,inode);self.assertEqual(claim.read_bytes(),b'consumed')
    def test_changed_permissions_fail_without_repairing_existing_backing(self):
        backing=self.views.root/'node-1';backing.mkdir(mode=0o700);backing.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private'):self.views.args('node-1',['/bin/true'])
        self.assertEqual(backing.stat().st_mode & 0o777,0o755)
        with self.assertRaisesRegex(ValueError,'private parent'):receiver.location(backing,self.value,os.getuid())
    def test_linked_backing_is_rejected_without_touching_its_target(self):
        target=self.root/'foreign';target.mkdir(mode=0o700)
        (self.views.root/'node-1').symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):self.views.args('node-1',['/bin/true'])
        self.assertEqual(list(target.iterdir()),[])


if __name__=='__main__':unittest.main()
