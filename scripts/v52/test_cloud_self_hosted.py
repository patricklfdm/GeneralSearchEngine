"""Local Runner admission and preservation; no registration or cloud execution."""
import json
import io
import os
from pathlib import Path
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import cloud_self_hosted as h


class HostTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.cfg = dict(name=h.LABEL, workspaceRoot=str(root/'work'), archiveRoot=str(root/'archives'), stateRoot=str(root/'state'))
        for key in ('workspaceRoot', 'archiveRoot', 'stateRoot'): Path(self.cfg[key]).mkdir(mode=0o700)
        self.workspace = Path(self.cfg['workspaceRoot'])/'GeneralSearchEngine/GeneralSearchEngine'
        self.workspace.mkdir(parents=True)
        self.env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=h.REPOSITORY, GITHUB_EVENT_NAME='workflow_dispatch',
                        GITHUB_REF='refs/heads/master', GITHUB_WORKFLOW_REF=h.WORKFLOW, GITHUB_JOB='runner',
                        RUNNER_NAME=h.LABEL, RUNNER_OS='Linux', RUNNER_ARCH='X64', RUNNER_ENVIRONMENT='self-hosted',
                        GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_WORKSPACE=str(self.workspace))
        self.bound = h.context(self.env, self.cfg)

    def start(self):
        with patch.object(h, 'check', return_value=self.bound): h.started(self.env, self.cfg)

    def evidence(self):
        root = self.workspace/'target/v52-runner'; root.mkdir(parents=True, mode=0o700)
        (root/'failure.json').write_text('{"status":"FAIL"}\n')
        return root

    def test_only_exact_manual_master_runner_context_is_accepted(self):
        for key, value in (('GITHUB_EVENT_NAME','pull_request'), ('GITHUB_EVENT_NAME','push'),
                           ('GITHUB_REF','refs/heads/feature'), ('GITHUB_WORKFLOW_REF',h.WORKFLOW.replace('v52-', 'v51-')),
                           ('GITHUB_JOB','other'), ('GITHUB_REPOSITORY','fork/GeneralSearchEngine'),
                           ('RUNNER_ENVIRONMENT','github-hosted'), ('RUNNER_NAME','other'),
                           ('RUNNER_OS','Windows'), ('RUNNER_ARCH','ARM64'), ('GITHUB_RUN_ID','../123'),
                           ('GITHUB_RUN_ATTEMPT','0'), ('GITHUB_WORKSPACE',str(self.workspace.parent))):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): h.context(dict(self.env, **{key:value}), self.cfg)

    def test_completion_moves_failed_evidence_without_copy_or_delete(self):
        self.start(); source = self.evidence(); original = (source/'failure.json').stat().st_ino
        h.completed(self.env, self.cfg)
        target = Path(self.cfg['archiveRoot'])/'123-1/evidence/failure.json'
        self.assertEqual(original, target.stat().st_ino); self.assertIn('FAIL', target.read_text())
        self.assertFalse(source.exists()); self.assertFalse((Path(self.cfg['stateRoot'])/'active.json').exists())
        self.start()  # next checkout can proceed; retained evidence still exists
        self.assertTrue(target.exists())

    def test_unpreserved_output_or_active_marker_prevents_next_checkout(self):
        source = self.evidence()
        with self.assertRaises(ValueError): self.start()
        self.assertTrue((source/'failure.json').exists())
        source.rename(source.with_name('manually-preserved'))
        self.start()
        with self.assertRaises(ValueError): self.start()

    def test_wrong_attempt_and_existing_archive_never_overwrite_evidence(self):
        self.start(); source = self.evidence()
        with self.assertRaises(ValueError): h.completed(dict(self.env, GITHUB_RUN_ATTEMPT='2'), self.cfg)
        target = Path(self.cfg['archiveRoot'])/'123-1'; target.mkdir(); (target/'keep').write_text('original')
        with self.assertRaises(FileExistsError): h.completed(self.env, self.cfg)
        self.assertEqual('original', (target/'keep').read_text()); self.assertTrue(source.exists())

    def test_linked_or_public_directory_is_rejected(self):
        self.start(); source = self.evidence(); actual = source.with_name('actual'); source.rename(actual); source.symlink_to(actual)
        with self.assertRaises(ValueError): h.completed(self.env, self.cfg)
        self.assertTrue((actual/'failure.json').exists())
        actual.chmod(0o755)
        with self.assertRaises(ValueError): h.private(actual)

    def test_failure_before_operation_is_preserved_as_empty_local_receipt(self):
        self.start(); h.completed(self.env, self.cfg)
        value = json.loads((Path(self.cfg['archiveRoot'])/'123-1/local-receipt.json').read_text())
        self.assertFalse(value['evidencePreserved']); self.assertNotIn('status', value)

    def test_low_disk_is_advisory_and_does_not_change_operator_result(self):
        from . import cloud_operator
        with patch.object(h,'configuration',return_value=self.cfg), patch.object(h,'check'), \
             patch.object(h.shutil,'disk_usage',return_value=type('Usage',(),{'free':1})()), \
             patch.object(cloud_operator,'execute_native',return_value={'original':'result'}) as execute:
            self.assertEqual(0.0,h.space(self.cfg['workspaceRoot'])['linuxFreeGiB'])
            self.assertEqual({'original':'result'},h.execute('a'*40,Path('target/v52-runner')))
            execute.assert_called_once()

    def test_operator_error_propagates_without_replay(self):
        from . import cloud_operator
        with patch.object(h,'configuration',return_value=self.cfg), patch.object(h,'check'), \
             patch.object(cloud_operator,'execute_native',side_effect=ConnectionError('original')) as execute:
            with self.assertRaises(ConnectionError): h.execute('a'*40,Path('target/v52-runner'))
            execute.assert_called_once()

    def test_cli_does_not_export_private_exception_or_retry(self):
        output = io.StringIO()
        with patch.object(h,'execute',side_effect=ValueError('private credential body')) as execute, patch('sys.stdout',output):
            self.assertEqual(2,h.main(['execute','--source','a'*40,'--output','target/v52-runner']))
        execute.assert_called_once(); self.assertNotIn('private credential',output.getvalue())
        self.assertNotIn('Traceback',output.getvalue())

    def test_host_check_requires_monitor_but_low_space_is_advisory_and_stat_has_no_secrets(self):
        with patch.object(Path,'read_text',return_value='ID=ubuntu\nVERSION_ID="24.04"\n'), \
             patch.object(h.subprocess,'check_output',return_value='ext2/ext3\n') as stat_call, \
             patch.object(h,'space',return_value={'hostSpace':'CURRENT','hostFreeGiB':1,'linuxFreeGiB':1}) as space, \
             patch.dict(os.environ,{'V52_SSH_KEY':'private','GH_TOKEN':'private'}):
            self.cfg['backingStore']='D:\\GSE-Runner\\Ubuntu'
            self.assertEqual(self.bound,h.check(self.env,self.cfg))
            self.assertEqual({'PATH':'/usr/bin:/bin','LC_ALL':'C'},stat_call.call_args.kwargs['env'])
            space.return_value={'hostSpace':'UNAVAILABLE'}
            with self.assertRaises(ValueError):h.check(self.env,self.cfg)

    def test_host_space_uses_actual_d_drive_and_rejects_stale_or_invalid_values(self):
        path=Path(self.temp.name)/'space.json'
        valid=dict(drive='D:',freeBytes=15<<30,totalBytes=200<<30,checkedAt=1000)
        info=SimpleNamespace(st_uid=0,st_mode=stat.S_IFREG|0o644,st_size=200)
        with patch.object(h,'HOST_SPACE',path), patch.object(Path,'stat',return_value=info), patch.object(h.time,'time',return_value=1001):
            path.write_text(json.dumps(valid)); value=h.space(self.cfg['workspaceRoot'])
            self.assertEqual('CURRENT',value['hostSpace']); self.assertEqual(15,value['hostFreeGiB'])
            for change in (dict(checkedAt=0),dict(checkedAt=1002),dict(drive='C:'),dict(freeBytes=-1),dict(freeBytes=201<<30),dict(extra='private')):
                path.write_text(json.dumps(dict(valid,**change)))
                self.assertEqual('UNAVAILABLE',h.space(self.cfg['workspaceRoot'])['hostSpace'])
            path.write_text(json.dumps(valid)); info.st_uid=1000
            self.assertEqual('UNAVAILABLE',h.space(self.cfg['workspaceRoot'])['hostSpace'])


if __name__ == '__main__': unittest.main()
