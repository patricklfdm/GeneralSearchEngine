"""The preparation probe cannot omit a stronger existing admission gate."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import large_runner_readiness as r


class LargeRunnerReadinessTest(unittest.TestCase):
    def test_every_real_stage_is_checked_on_the_same_workspace(self):
        workspace = Path('/synthetic/actual-workspace')
        with patch.object(r.direct, 'check', return_value={'direct': True}) as direct, \
                patch.object(r.hosted, 'check', return_value={'hosted': True}) as hosted, \
                patch.object(r.final, 'capacity', return_value={'final': True}) as final:
            result = r.inspect(workspace)
        direct.assert_called_once_with(workspace, 'execute')
        self.assertEqual([((workspace, s), {}) for s in ('execute', 'verify-download', 'verify')], hosted.call_args_list)
        final.assert_called_once_with(workspace)
        self.assertEqual('PASS', result['status'])
        self.assertEqual(5, len(result['checks']))
        self.assertTrue(result['hardwareOnly'])
        self.assertTrue(result['inputsPresentNotVerified'])
        self.assertFalse(result['phase3Complete'])

    def test_a_failed_gate_does_not_hide_remaining_blockers_or_write_files(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            with patch.object(r.direct, 'check', side_effect=ValueError('native Linux required')), \
                    patch.object(r.hosted, 'check', side_effect=[{'ok': True}, OSError('disk unavailable'), {'ok': True}]), \
                    patch.object(r.final, 'capacity', side_effect=ValueError('448 GiB required')):
                result = r.inspect(workspace)
            self.assertEqual([], list(workspace.iterdir()))
        self.assertEqual('BLOCKED', result['status'])
        self.assertEqual(['BLOCKED', 'PASS', 'BLOCKED', 'PASS', 'BLOCKED'], [v['status'] for v in result['checks']])

    def test_programming_errors_are_not_reclassified_as_host_capacity(self):
        with patch.object(r.direct, 'check', side_effect=TypeError('bug')):
            with self.assertRaises(TypeError): r.inspect('/unused')


if __name__ == '__main__':
    unittest.main()
