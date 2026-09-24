from __future__ import annotations

import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from scripts import maven_infra_retry as retry

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ['./mvnw', '-f', 'reactor/pom.xml', 'package']
PLUGIN = ('[ERROR] Plugin org.apache.maven.plugins:maven-jar-plugin:3.5.1 or one of its dependencies '
          'could not be resolved: The following artifacts could not be resolved: '
          'org.apache.maven.plugins:maven-jar-plugin:pom:3.5.1 (absent): Could not transfer artifact '
          'org.apache.maven.plugins:maven-jar-plugin:pom:3.5.1 from/to central '
          '(https://repo.maven.apache.org/maven2): ')
DEPENDENCY = ('[ERROR] Failed to execute goal on project core: Could not resolve dependencies for project '
              'example:core:jar:1.0: Could not transfer artifact example:dep:jar:1.0 from/to central '
              '(https://repo.maven.apache.org/maven2): ')
THROTTLED = PLUGIN + 'status code: 429, reason phrase: Too Many Requests (429) -> [Help 1]\n'
FOOTER = '''[ERROR]
[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] https://cwiki.apache.org/confluence/display/MAVEN/PluginResolutionException
'''


class ClassificationTest(unittest.TestCase):
    def test_supported_http_and_transport_causes(self):
        for cause in ('HTTP 429', 'HTTP/1.1 500', 'status code: 502', 'status code: 503',
                      'Return code is: 504', 'Too Many Requests', 'Connection reset by peer',
                      'Connection reset', 'Read timed out', 'Connect timed out', 'Connection timed out',
                      'Connection closed prematurely', 'Temporary failure in name resolution'):
            for prefix in (PLUGIN, DEPENDENCY):
                with self.subTest(cause=cause, prefix=prefix):
                    self.assertIsNotNone(retry.classify(prefix + cause + '\n' + FOOTER))

    def test_requires_remote_transfer_and_bound_cause(self):
        for text in ('HTTP 429', '[ERROR] DependencyResolutionException: HTTP 503',
                     '[ERROR] PluginResolutionException: Connection reset',
                     PLUGIN + 'unexplained failure\n[WARNING] HTTP 429',
                     THROTTLED.replace('https://repo.maven.apache.org/maven2', 'file:/tmp/cache'),
                     THROTTLED + '[ERROR] unrelated failure\n',
                     PLUGIN + 'Connection refused', PLUGIN + 'UnknownHostException',
                     PLUGIN + 'SocketTimeoutException', PLUGIN + 'EOFException',
                     PLUGIN + 'SSL handshake interrupted', PLUGIN + 'status code: 501',
                     PLUGIN + '\n[ERROR] Read timed out',
                     THROTTLED.replace('[ERROR]', '[WARNING]')):
            with self.subTest(text=text):
                self.assertIsNone(retry.classify(text))

    def test_correctness_veto_overrides_transfer_even_in_mixed_logs(self):
        failures = ('COMPILATION ERROR', 'cannot find symbol', 'incompatible types',
                    'package org.example does not exist', 'Tests run: 1, Failures: 1, Errors: 0',
                    'Tests run: 1, Failures: 0, Errors: 1', 'There are test failures',
                    'SurefireBooterForkException', 'java.lang.AssertionError',
                    'org.opentest4j.AssertionFailedError',
                    'AutomaticReplicationException: automatic runtime QUORUM_UNAVAILABLE',
                    'election failure', 'protocol assertion failure', 'recovery invariant failure',
                    'evidence validation failure', 'history/linearizability failure',
                    'API compatibility failure', 'artifact compatibility failure', 'version alignment failure',
                    'release validation failure', 'evidence validator failure', 'schema/format contract failure',
                    'checksum mismatch', 'hash mismatch', 'signature mismatch', 'reproducibility mismatch',
                    'corrupt artifact evidence', 'malformed POM', 'invalid Maven coordinates',
                    'Maven Enforcer failure', 'PKIX path building failed',
                    'SSLHandshakeException', 'certificate error', 'authentication failure',
                    'authorization failure', 'Could not find artifact example:missing:jar:1')
        for failure in failures:
            for text in (THROTTLED + failure, failure + '\n' + THROTTLED):
                with self.subTest(failure=failure):
                    self.assertIsNone(retry.classify(text))

    def test_any_test_start_including_success_disables_retry(self):
        for marker in ('[INFO] --- surefire:3.5.6:test (default-test) @ core ---',
                       '[INFO] --- maven-surefire-plugin:3.5.6:test (default-test) @ core ---',
                       '[INFO] --- failsafe:3.5.6:integration-test (default) @ core ---',
                       '[INFO] Running example.Test', 'Tests run: 20, Failures: 0, Errors: 0'):
            with self.subTest(marker=marker):
                self.assertIsNone(retry.classify(marker + '\n' + THROTTLED))

    def test_permanent_http_and_cached_failures_override_retry(self):
        for cause in ('HTTP 401', 'HTTP 403', 'HTTP 404', 'status code: 403',
                      'Return code is: 404', 'resolution is not reattempted until the update interval',
                      'was cached in the local repository'):
            with self.subTest(cause=cause):
                self.assertIsNone(retry.classify(THROTTLED + DEPENDENCY + cause))

    def test_multiple_diagnostics_must_all_qualify(self):
        self.assertIsNotNone(retry.classify(THROTTLED + DEPENDENCY + 'HTTP 503'))
        self.assertIsNone(retry.classify(THROTTLED + DEPENDENCY + 'HTTP 501'))
        self.assertIsNone(retry.classify(THROTTLED.rstrip() + '; ' + DEPENDENCY + 'HTTP 501'))

    def test_ansi_and_crlf(self):
        self.assertIsNotNone(retry.classify('\x1b[31m' + THROTTLED.replace('\n', '\x1b[0m\r\n')))


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        old = Path.cwd(); os.chdir(self.directory)
        self.addCleanup(os.chdir, old)
        env = patch.dict(os.environ, MAVEN_ARGS='', RUNNER_TEMP=str(self.directory / 'runner'))
        env.start(); self.addCleanup(env.stop)
        self.sleep = Mock()
        self.output = io.BytesIO()
        self.fake = self.directory / 'mvnw'
        self.fake.write_text('#!' + sys.executable + '''
import json, pathlib, sys
p=pathlib.Path('count'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1))
pathlib.Path('argv').write_text(json.dumps(sys.argv[1:]))
steps=json.loads(pathlib.Path('steps.json').read_text()); row=steps[min(n,len(steps)-1)]
sys.stdout.write(row['out']); sys.stdout.flush()
sys.stderr.write(row.get('err','')); sys.stderr.flush()
sys.exit(row['code'])
''')
        self.fake.chmod(0o755)

    def execute(self, steps, command=None):
        (self.directory / 'steps.json').write_text(json.dumps(steps))
        code = retry.run(command or COMMAND, sleep=self.sleep, output=self.output)
        count = int((self.directory / 'count').read_text())
        logs = list((self.directory / 'runner/gse-maven-infra-retry').glob('run.*'))
        return code, count, logs[-1]

    def test_transient_then_success_exactly_twice(self):
        for cause in ('HTTP 429', 'HTTP 503', 'Connection reset by peer', 'Read timed out', 'Connect timed out'):
            with self.subTest(cause=cause):
                (self.directory / 'count').unlink(missing_ok=True); self.sleep.reset_mock()
                code, count, _ = self.execute([{'code': 1, 'out': PLUGIN + cause}, {'code': 0, 'out': 'BUILD SUCCESS\n'}])
                self.assertEqual((0, 2), (code, count)); self.sleep.assert_called_once_with(15)

    def test_success_is_once_and_original_argv_unchanged(self):
        code, count, _ = self.execute([{'code': 0, 'out': 'BUILD SUCCESS\n'}])
        self.assertEqual((0, 1), (code, count)); self.sleep.assert_not_called()
        self.assertEqual(COMMAND[1:], json.loads((self.directory / 'argv').read_text()))

    def test_all_failed_attempts_retained_and_bounded(self):
        code, count, log = self.execute([{'code': 1, 'out': THROTTLED, 'err': 'stderr marker\n'}])
        self.assertEqual((1, 2), (code, count)); self.sleep.assert_called_once_with(15)
        for n in (1, 2):
            self.assertEqual(THROTTLED + 'stderr marker\n', (log / f'attempt-{n}.log').read_text())
        self.assertEqual(2, self.output.getvalue().count(b'stderr marker'))
        self.assertEqual([1, 1], [r['exitCode'] for r in json.loads((log / 'attempts.json').read_text())['attempts']])

    def test_second_attempt_correctness_failure_is_not_retried(self):
        code, count, _ = self.execute([{'code': 1, 'out': THROTTLED}, {'code': 7, 'out': 'AssertionError\n'}])
        self.assertEqual((7, 2), (code, count))

    def test_nonretryable_failures_execute_once_and_preserve_exit(self):
        for text in ('COMPILATION ERROR', 'AssertionError', 'AutomaticReplicationException: QUORUM_UNAVAILABLE',
                     'checksum mismatch', PLUGIN + 'HTTP 404', PLUGIN + 'HTTP 401', PLUGIN + 'HTTP 403',
                     'unknown failure', THROTTLED + 'Tests run: 1, Failures: 1, Errors: 0'):
            with self.subTest(text=text):
                (self.directory / 'count').unlink(missing_ok=True); self.sleep.reset_mock()
                code, count, _ = self.execute([{'code': 1, 'out': text}])
                self.assertEqual((1, 1), (code, count)); self.sleep.assert_not_called()

    def test_non_maven_exit_status_and_signal_are_not_retried(self):
        for code in (2, 137, 143):
            (self.directory / 'count').unlink(missing_ok=True)
            self.assertEqual((code, 1), self.execute([{'code': code, 'out': THROTTLED}])[:2])
        self.sleep.assert_not_called()

    def test_hidden_output_environment_disables_retry(self):
        with patch.dict(os.environ, MAVEN_ARGS='--quiet'):
            self.assertEqual((1, 1), self.execute([{'code': 1, 'out': THROTTLED}])[:2])
        self.sleep.assert_not_called()

    def test_unsupported_command_cannot_execute(self):
        for command in (['./mvnw', 'deploy'], ['./mvnw', '-Prelease', 'verify'], ['bash', '-c', 'exit 0'],
                        ['./mvnw', '-q', '-f', 'reactor/pom.xml', 'package'],
                        ['scripts/verify-v51-phase5-hardening.sh']):
            self.assertEqual(2, retry.run(command, output=self.output))
        self.assertFalse((self.directory / 'count').exists())

    def test_cancellation_during_backoff_never_restarts(self):
        self.sleep.side_effect = retry.Cancelled(signal.SIGTERM)
        self.assertEqual((143, 1), self.execute([{'code': 1, 'out': THROTTLED}])[:2])

    def test_shell_entry_point_success(self):
        (self.directory / 'steps.json').write_text(json.dumps([{'code': 0, 'out': 'shell success\n'}]))
        result = subprocess.run([ROOT / 'scripts/run-maven-with-infra-retry.sh', *COMMAND], capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(b'shell success', result.stdout)

    def test_sigterm_stops_owned_maven_without_retry(self):
        self.fake.write_text('#!' + sys.executable + '''
import os, pathlib, time
pathlib.Path('ready').write_text(str(os.getpid()))
print('owned Maven waiting', flush=True)
while True: time.sleep(1)
''')
        proc = subprocess.Popen([ROOT / 'scripts/run-maven-with-infra-retry.sh', *COMMAND], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.directory / 'ready').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.directory / 'ready').exists())
            pid = int((self.directory / 'ready').read_text())
            proc.terminate(); out, err = proc.communicate(timeout=10)
            self.assertEqual(143, proc.returncode, err)
            self.assertNotIn(b'Maven attempt 2/', out)
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            proc.stdout.close(); proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
