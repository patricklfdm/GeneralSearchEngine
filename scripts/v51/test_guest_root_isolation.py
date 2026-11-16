"""Exercise the qualification launcher without performing mounts or chown."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from . import guest_root_isolation as isolation


class RootIsolationLauncherTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)/'rootfs'; self.root.mkdir()
        (self.root/'account').write_text('fixture')
        self.owner = self.root.stat().st_uid

    def launch(self, binary, returncode=0):
        events = []
        def run(argv, **kwargs):
            events.append(('run', argv, kwargs))
            if argv[0].endswith('/chroot'):
                if argv[0] != binary: raise FileNotFoundError(argv[0])
                return subprocess.CompletedProcess(argv, returncode)
            return subprocess.CompletedProcess(argv, 0)
        def chown(*args, **kwargs): events.append(('chown', args, kwargs))
        argv = ['isolation', str(self.root), 'parent-namespace', str(self.owner), str(os.getgid()),
                '/usr/bin/python3', '-I', '-c', 'raise SystemExit(0)']
        with patch.object(isolation.sys, 'argv', argv), \
                patch.object(isolation.os, 'getuid', return_value=0), \
                patch.object(isolation.os, 'readlink', return_value='isolated-namespace'), \
                patch.object(isolation.os, 'chown', side_effect=chown), \
                patch.object(isolation.ctypes, 'CDLL', return_value=Mock(syscall=Mock(return_value=0))), \
                patch.object(isolation.subprocess, 'run', side_effect=run), \
                patch('shutil.which', return_value=binary) as lookup, \
                patch.dict(os.environ, {'PATH':'/untrusted/workspace/bin'}):
            with self.assertRaises(SystemExit) as exited: isolation.main()
        self.assertEqual(returncode, exited.exception.code)
        lookup.assert_called_once_with('chroot', path='/usr/sbin:/usr/bin:/sbin:/bin')
        return events

    def test_bin_and_sbin_system_layouts_preserve_receiver_and_clean_environment(self):
        for binary in ('/usr/bin/chroot', '/usr/sbin/chroot'):
            with self.subTest(binary=binary):
                events = self.launch(binary)
                call = next(e for e in events if e[0]=='run' and e[1][0]==binary)
                self.assertEqual([binary, str(self.root), '/usr/bin/python3', '-I', '-c',
                                  'raise SystemExit(0)'], call[1])
                self.assertEqual(dict(PATH='/usr/bin:/bin', SUDO_USER='fixture', SUDO_UID='1001',
                                      SUDO_GID='1001'), call[2]['env'])
                mounts = [e[1][-1] for e in events if e[0]=='run' and e[1][0]=='mount']
                unmounts = [e[1][-1] for e in events if e[0]=='run' and e[1][0]=='umount']
                self.assertEqual(mounts[::-1], unmounts)

    def test_receiver_failure_is_not_turned_into_success_and_mounts_are_released(self):
        events = self.launch('/usr/bin/chroot', returncode=7)
        self.assertTrue(any(e[0]=='run' and e[1][0]=='umount' for e in events))

    def test_missing_system_chroot_fails_before_ownership_changes_or_mounts(self):
        argv = ['isolation',str(self.root),'parent',str(self.owner),str(os.getgid()),'/usr/bin/python3']
        with patch.object(isolation.sys,'argv',argv), \
                patch.object(isolation.os,'getuid',return_value=0), \
                patch.object(isolation.os,'readlink',return_value='isolated'), \
                patch.object(isolation.os,'chown') as chown, \
                patch.object(isolation.ctypes,'CDLL',return_value=Mock(syscall=Mock(return_value=0))), \
                patch.object(isolation.subprocess,'run') as run, \
                patch('shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'system chroot unavailable'): isolation.main()
        chown.assert_not_called(); run.assert_not_called()


if __name__ == '__main__': unittest.main()
