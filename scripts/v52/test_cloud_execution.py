"""Control-flow tests with external native entry modeled; no guest workloads."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_execution as e


@contextmanager
def chdir(path):
    previous=Path.cwd()
    try:
        os.chdir(path);yield
    finally:os.chdir(previous)


class ExecutionTest(unittest.TestCase):
    def execute(self, failure=None, relative=False):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.output = Path(temp.name)/'execution'
        self.calls = []; calls = self.calls
        def record(name):
            calls.append(name)
            if failure == name: raise ValueError('synthetic original failure, never public detail')
        class Session:
            def __enter__(self): record('enter'); return self
            def run_member(self, key, output):
                self_case.assertEqual(self_case.output/'member',output);record('member')
            def retain_member(self, output):
                self_case.assertEqual(self_case.output/'retention',output);record('retention')
            def __exit__(self, *args): record('close')
        def opened(*args, **kw):
            self.assertEqual(self.output/'native',args[-1])
            record('open'); self.asserted = kw['prepare_workload']; return Session()
        def publish(session, output):
            record('seal'); output.mkdir(); (output/'member-seal.json').write_text('modeled public seal')
            return dict(status='ORIGINAL_MEMBER_CLOSED_NOT_QUALIFIED', requestSha256='a'*64)
        self_case=self
        with chdir(temp.name),patch.object(e.native, 'open_native', side_effect=opened), patch.object(e.seal, 'publish', side_effect=publish), \
             patch.object(e.member.Progress, 'report'):
            return e.run_native('a'*40, 'plan', 'approval', 'confirmation', 'package', 'private-key',
                                Path('execution') if relative else self.output)
    def test_direct_relative_entry_keeps_absolute_paths_through_retention_and_seal(self):
        self.execute(relative=True)
        self.assertEqual(['open','enter','member','retention','close','seal'],self.calls)
    def test_original_member_retention_close_then_public_seal_once(self):
        result = self.execute(); self.assertTrue(self.asserted)
        self.assertEqual(['open', 'enter', 'member', 'retention', 'close', 'seal'], self.calls)
        self.assertEqual('ORIGINAL_MEMBER_CLOSED_NOT_QUALIFIED', result['status'])
    def test_each_failure_stops_without_retry_and_cannot_publish_success(self):
        for failure in ('open', 'enter', 'member', 'retention', 'close', 'seal'):
            with self.subTest(failure=failure), self.assertRaisesRegex(ValueError, 'synthetic'): self.execute(failure)
            self.assertEqual(1, self.calls.count(failure)); self.assertFalse((self.output/'receipt.json').exists())
            self.assertFalse((self.output/'public').exists())
            receipt = e.native.artifacts.read(self.output/'failure.json')
            self.assertEqual('FAIL', receipt['status']); self.assertNotIn('synthetic original failure', str(receipt))
            if failure in ('member', 'retention'): self.assertIn('close', self.calls)
    def test_existing_or_symlink_output_does_not_open_native_entry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(e.native, 'open_native') as opened:
            root = Path(directory); (root/'link').symlink_to(root, target_is_directory=True)
            for output in (root, root/'link'/'new'):
                with self.assertRaises((ValueError, FileExistsError)):
                    e.run_native('a'*40, 'plan', 'approval', 'confirmation', 'package', 'key', output)
            opened.assert_not_called()


if __name__ == '__main__': unittest.main()
