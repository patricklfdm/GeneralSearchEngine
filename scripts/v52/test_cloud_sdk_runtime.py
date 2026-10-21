"""Real bounded local helper processes; fake SDK, no cloud or credential access."""
import os
from pathlib import Path
import shlex
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_sdk_runtime as s


class SdkRuntimeTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def sdk(self, code):
        path=self.root/'gcloud'
        path.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,'-I','-S','-c',code])+' "$@"\n')
        path.chmod(0o700)
        return patch.object(s,'executable',return_value=str(path))

    def test_relocated_runtime_prefix_overrides_stale_build_time_and_ambient_paths(self):
        prefix=self.root/'relocated';(prefix/'lib').mkdir(parents=True)
        with patch.object(sys,'base_prefix',str(prefix)),patch.object(sysconfig,'get_config_var',return_value='/stale/lib'), \
             patch.dict(os.environ,{'LD_LIBRARY_PATH':'/untrusted/lib','LD_PRELOAD':'/untrusted/inject',
                 'PYTHONPATH':'private-python','GH_TOKEN':'private-github','GOOGLE_APPLICATION_CREDENTIALS':'private-cloud'}):
            env=s.environment(self.root)
        self.assertEqual(str(prefix/'lib'),env['LD_LIBRARY_PATH'])
        self.assertEqual(sys.executable,env['CLOUDSDK_PYTHON'])
        self.assertEqual(str(self.root),env['CLOUDSDK_CONFIG'])
        self.assertNotIn('private',str(env));self.assertNotIn('/untrusted',str(env));self.assertNotIn('/stale',str(env))
        self.assertEqual('true',env['CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK'])

    def test_invalid_runtime_prefix_and_library_search_separator_reject(self):
        for prefix in (str(self.root/'absent'),'relative',str(self.root/'colon:prefix')):
            if prefix.endswith('colon:prefix'):(Path(prefix)/'lib').mkdir(parents=True)
            with patch.object(sys,'base_prefix',prefix),self.assertRaisesRegex(s.SdkError,'PYTHON_ENVIRONMENT'):
                s.environment(self.root)

    def test_missing_sdk_is_terminal_before_any_child(self):
        with patch.object(s.shutil,'which',return_value=None),patch.object(s.transport,'process') as child:
            with self.assertRaisesRegex(s.SdkError,'EXECUTABLE_UNAVAILABLE'):s.check()
        child.assert_not_called()

    def test_real_helper_observes_exact_credential_free_environment_and_only_version(self):
        record=self.root/'config-path'
        code='''import json,os,sys
from pathlib import Path
assert sys.argv[1:]==['version','--format=json','--quiet']
config=Path(os.environ['CLOUDSDK_CONFIG'])
assert config.is_dir() and config.stat().st_mode & 0o077==0
assert not list(config.iterdir())
for name in ('GOOGLE_APPLICATION_CREDENTIALS','GH_TOKEN','V52_SSH_KEY','PYTHONPATH','LD_PRELOAD'):
 assert name not in os.environ
assert os.environ['LD_LIBRARY_PATH']==str(Path(sys.base_prefix).resolve()/'lib')
Path(RECORD).write_text(str(config))
print(json.dumps({'Google Cloud SDK':'582.0.0'}))
'''.replace('RECORD',repr(str(record)))
        with self.sdk(code):result=s.check()
        self.assertEqual('PASS',result['status']);self.assertEqual('582.0.0',result['sdkVersion'])
        self.assertFalse(result['cloudOperationExecuted']);self.assertFalse(result['credentialEnvironmentInherited'])
        self.assertFalse(Path(record.read_text()).exists())

    def test_python_launch_failure_prevents_sdk_launch_and_projects_only_closed_code(self):
        with patch.object(s,'executable',return_value='/sdk/gcloud'), \
             patch.object(s.transport,'process',side_effect=OSError('secret-loader-output')) as child:
            with self.assertRaises(s.SdkError) as raised:s.check()
        child.assert_called_once()
        self.assertEqual({'sdkCode':'V52_SDK_PYTHON_START_FAILED'},s.failure(raised.exception))
        self.assertNotIn('secret',str(raised.exception))
        self.assertEqual({},s.public_failure({'sdkCode':'private-error'}))

    def test_sdk_exit_does_not_publish_stderr_or_retry(self):
        with self.sdk('import sys;print("private-token-output",file=sys.stderr);sys.exit(4)'):
            with self.assertRaisesRegex(s.SdkError,'SDK_START_FAILED') as raised:s.check()
        self.assertNotIn('private-token-output',str(raised.exception))

    def test_bad_version_missing_version_and_extra_stdout_reject(self):
        for text in ('{"Google Cloud SDK":"unknown"}', '{}','private diagnostic\n{"Google Cloud SDK":"582.0.0"}'):
            with self.sdk('print('+repr(text)+')'),self.assertRaisesRegex(s.SdkError,'SDK_RESPONSE'):s.check()

    def test_excessive_output_is_bounded(self):
        with self.sdk('print("x"*70000)'),self.assertRaisesRegex(s.SdkError,'SDK_RESPONSE'):s.check()

    def test_local_startup_timeout_reaps_process_without_retry(self):
        record=self.root/'pid'
        code='import os,time;from pathlib import Path;Path('+repr(str(record))+').write_text(str(os.getpid()));time.sleep(10)'
        with self.sdk(code),patch.object(s,'CHECK_SECONDS',.5),self.assertRaisesRegex(s.SdkError,'SDK_TIMEOUT'):s.check()
        if record.exists():
            with self.assertRaises(ProcessLookupError):os.kill(int(record.read_text()),0)


if __name__=='__main__':unittest.main()
