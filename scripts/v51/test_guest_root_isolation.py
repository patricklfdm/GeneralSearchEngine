"""System-tool discovery stays independent of an inherited operator PATH."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import guest_root_isolation as m


class GuestRootIsolationTest(unittest.TestCase):
    def test_bin_and_sbin_hosts_use_only_fixed_system_search_directories(self):
        for path in ('/usr/sbin/chroot','/usr/bin/chroot'):
            with self.subTest(path=path),patch.dict(os.environ,{'PATH':'/untrusted'}), \
                 patch.object(m.shutil,'which',return_value=path) as which:
                self.assertEqual(path,m.chroot_executable())
                which.assert_called_once_with('chroot',path='/usr/sbin:/usr/bin:/sbin:/bin')

    def test_missing_system_binary_fails_before_mount_or_chown(self):
        owner,group=os.getuid(),os.getgid()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'rootfs';root.mkdir()
            argv=['isolate',str(root),'parent',str(owner),str(group),'true']
            with patch.object(m.sys,'argv',argv),patch.object(m.os,'getuid',return_value=0), \
                 patch.object(m.os,'readlink',return_value='private'), \
                 patch.object(m.shutil,'which',return_value=None),patch.object(m.subprocess,'run') as run, \
                 patch.object(m.os,'chown') as chown:
                with self.assertRaisesRegex(ValueError,'system chroot executable missing'):m.main()
        run.assert_not_called();chown.assert_not_called()
