"""One fail-closed retry for the explicitly reviewed CI Maven build commands."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time

# No test profiles, qualification scripts, install/deploy or arbitrary shell commands.
COMMANDS = {
    ('./mvnw', '-f', 'reactor/pom.xml', 'package'),
    ('./mvnw', '-f', 'reactor/pom.xml', 'clean', 'package'),
    ('./mvnw', '-DskipTests', 'package'),
    ('./mvnw', '-q', 'clean', '-DskipTests', 'package'),
}
ATTEMPTS, BACKOFF_SECONDS = 2, 15
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
TEST_STARTED = re.compile(
    r'--- (?:maven-)?(?:surefire|failsafe)(?:-plugin)?:[^\n]*:(?:test|integration-test|verify)\b'
    r'|\bTests run:\s*\d+|^\[INFO\]\s+Running\s+\S+', re.MULTILINE)
VETO = re.compile(
    r'COMPILATION (?:ERROR|FAILURE)|cannot find symbol|incompatible types|package .+ does not exist'
    r'|\b(?:Failures|Errors):\s*[1-9]\d*|There (?:are|were) test failures|SurefireBooterForkException'
    r'|AssertionError|AssertionFailedError|AutomaticReplicationException|QUORUM_UNAVAILABLE'
    r'|STALE_EPOCH|INTEGRITY_FAILURE|CAPACITY_EXCEEDED'
    r'|(?:election|protocol|recovery|evidence|linearizability|compatibility|version alignment|release validation|schema|format contract)[^\n]*(?:fail|error|violation)'
    r'|(?:checksum|hash|signature|reproducibility)[^\n]*(?:mismatch|fail|invalid)'
    r'|corrupt[^\n]*(?:artifact|evidence)|(?:malformed|non-parseable|invalid)[^\n]*(?:pom|coordinates)'
    r'|Could not find artifact|Failure to find |Maven Enforcer|maven-enforcer-plugin'
    r'|unauthorized|forbidden|not found|authentication|authorization|access denied'
    r'|PKIX|certificate|SSLHandshakeException'
    r'|(?:HTTP(?:/\d(?:\.\d)?)?\s+|status code\s*[:=]?\s*|return code is:\s*)(?:401|403|404)\b'
    r'|was cached in the local repository|resolution (?:is|will) not (?:be )?reattempted', re.IGNORECASE)
TRANSFER = re.compile(r'Could not transfer (?:artifact|metadata)\s+\S+\s+from/to\s+\S+\s+\(https?://[^\s)]+\):\s*(.+)', re.IGNORECASE)
TRANSIENT = re.compile(
    r'(?:HTTP(?:/\d(?:\.\d)?)?\s+|status code\s*[:=]?\s*|return code is:\s*)(?:429|500|502|503|504)\b'
    r'|\bToo Many Requests\b|\bConnection reset(?: by peer)?\b'
    r'|\b(?:Connection|Connect|Read) timed out\b|\bConnection closed prematurely\b'
    r'|\bTemporary failure in name resolution\b', re.IGNORECASE)
DIAGNOSIS = re.compile(r'^(?:Failed to execute goal .+|Plugin .+ could not be resolved: .+)$')
BOILERPLATE = re.compile(
    r'^(?:$|-> \[Help \d+\]|To see the full stack trace .+|Re-run Maven using the -X switch .+'
    r'|For more information about the errors .+|\[Help \d+\] https?://\S+'
    r'|After correcting the problems, you can resume the build with the command'
    r'|mvn <args> -rf :\S+)$')


def classify(output: str) -> str | None:
    """Require every ERROR diagnosis to bind a transient cause to a remote transfer.

    Never combine an unrelated timeout/HTTP message with a resolution exception.
    Unknown/multiline errors and test execution fail closed, even after passing tests.
    """
    return classify_lines(output.splitlines())


def classify_lines(lines):
    causes = []
    for raw in lines:
        line = ANSI.sub('', raw.rstrip('\r\n'))
        if TEST_STARTED.search(line) or VETO.search(line):
            return None
        if not line.startswith('[ERROR]'):
            continue
        error = line[len('[ERROR]'):].strip()
        if BOILERPLATE.fullmatch(error):
            continue
        if not DIAGNOSIS.fullmatch(error):
            return None
        transfers = list(TRANSFER.finditer(error))
        if error.lower().count('could not transfer ') != 1 or not transfers or not all(TRANSIENT.search(t.group(1)) for t in transfers):
            return None
        causes.append(error)
    return '\n'.join(causes) if causes else None


class Cancelled(Exception):
    def __init__(self, signum):
        self.signum = signum


def run(command, *, log_root=None, sleep=time.sleep, output=None):
    if tuple(command) not in COMMANDS:
        print('Unsupported Maven command; review the CI build allowlist first.', file=sys.stderr)
        return 2
    output = sys.stdout.buffer if output is None else output
    # A quiet/custom environment could hide test-start or correctness diagnostics.
    env_args = os.environ.get('MAVEN_ARGS', '')
    retry_enabled = env_args in ('', '--batch-mode --no-transfer-progress -Dstyle.color=never')
    root = Path(log_root) if log_root else Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'gse-maven-infra-retry'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run.', dir=root))
    records = []
    child = None

    def message(text):
        output.write((text + '\n').encode()); output.flush()

    def stop(signum, _frame):
        raise Cancelled(signum)

    handlers = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        message(f'Maven infrastructure logs: {directory}')
        for attempt in range(1, ATTEMPTS + 1):
            path = directory / f'attempt-{attempt}.log'
            message(f'Maven attempt {attempt}/{ATTEMPTS}: {shlex.join(command)}')
            with path.open('wb') as log:
                child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while chunk := child.stdout.read1(65536):
                        log.write(chunk); log.flush()
                        output.write(chunk); output.flush()
                    code = child.wait()
                finally:
                    child.stdout.close()
            # Maven normally reports 1. Signals and other exit statuses are not retryable.
            with path.open(errors='replace') as retained:
                reason = classify_lines(retained) if code == 1 and retry_enabled else None
            code = 128 - code if code < 0 else code
            records.append({'attempt': attempt, 'exitCode': code, 'log': path.name, 'infraReason': reason})
            (directory / 'attempts.json').write_text(json.dumps({'command': command, 'attempts': records}, indent=2) + '\n')
            if code == 0:
                if attempt > 1:
                    message('Maven recovered after one infrastructure retry; first failure is retained.')
                return 0
            if reason is None:
                message('Failure is not classified as transient infrastructure. No retry will be attempted.')
                return code
            if attempt == ATTEMPTS:
                message('Infrastructure retry exhausted; preserving the final Maven exit code.')
                return code
            message(f'Transient Maven infrastructure failure detected:\n{reason}\nRetrying in {BACKOFF_SECONDS} seconds...')
            sleep(BACKOFF_SECONDS)
    except Cancelled as cancelled:
        message(f'Maven retry cancelled by signal {cancelled.signum}; no further attempt.')
        if child is not None and child.poll() is None:
            # Forward cancellation to the live owned Maven session.
            try:
                os.killpg(child.pid, cancelled.signum)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
        return 128 + cancelled.signum
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
