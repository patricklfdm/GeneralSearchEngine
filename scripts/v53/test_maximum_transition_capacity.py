"""No experiment starts from a guest-volume estimate or insufficient capacity."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_transition_capacity as m


class MaximumTransitionCapacityTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for target,value in (('platform.system','Linux'),('platform.release','6.8.0-generic'),
                ('shutil.disk_usage',SimpleNamespace(free=300*m.GIB)),('Path.read_text','MemAvailable: 10000000 kB\n')):
            mocked=patch.object(m.Path,'read_text',return_value=value) if target=='Path.read_text' else patch('scripts.v53.maximum_transition_capacity.'+target,return_value=value)
            mocked.start();self.addCleanup(mocked.stop)

    def test_execute_and_verify_have_independent_fixed_capacity(self):
        for stage,minimum in m.FREE_BY_STAGE.items():
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=minimum)):
                value=m.check(self.root,stage);self.assertEqual(minimum,value['minimumFreeBytes']);self.assertFalse(value['runtimeBudgetsChanged'])
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=minimum-1)):
                with self.assertRaisesRegex(ValueError,'insufficient disk'):m.check(self.root,stage)
        for stage in ('prepare','diagnostic','',False):
            with self.assertRaisesRegex(ValueError,'capacity stage'):m.check(self.root,stage)

    def test_memory_shortage_and_missing_ambiguous_or_wrong_units_fail_closed(self):
        for record in ('MemAvailable: 1 kB\n','','MemAvailable: 10000000 MB\n',
                       'MemAvailable: 10000000 kB\nMemAvailable: 10000000 kB\n'):
            with patch.object(m.Path,'read_text',return_value=record),self.assertRaises(ValueError):m.check(self.root)

    def test_wsl_or_non_linux_never_relies_on_sparse_guest_free_space(self):
        for system,release in [('Windows','11'),('Darwin','24'),('Linux','6.6.87.2-microsoft-standard-WSL2'),('Linux','WSL')]:
            with patch.object(m.platform,'system',return_value=system),patch.object(m.platform,'release',return_value=release),patch.object(m.shutil,'disk_usage') as disk:
                with self.assertRaisesRegex(ValueError,'native Linux'):m.check(self.root)
                disk.assert_not_called()

    def test_workspace_must_exist_and_be_a_directory(self):
        with self.assertRaises(FileNotFoundError):m.check(self.root/'absent')
        path=self.root/'file';path.write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'workspace directory'):m.check(path)


if __name__=='__main__':unittest.main()
