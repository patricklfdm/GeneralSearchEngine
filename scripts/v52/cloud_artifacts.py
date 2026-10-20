"""Original shared-build artifact provenance and bounded read-only collection.

An authenticated CI/build input is not native provider or workload admission.
The fixed native entry accepts no injected transport, credentials or observation.
"""
import argparse
from copy import deepcopy
import io
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
import zipfile
from . import cloud_authority as a, cloud_ci as ci, cloud_inputs as inputs, cloud_credentials as credentials
from .evidence import need, encoded, digest, strict

MAX_ZIP = 288 << 20
MAX_JSON = 16 << 20
SCHEMA = 'gse-v52-build-provenance-v1'
BUILD_PREFIX = 'v51-verification-build-'
EXECUTION_FIELDS = ('name', 'run_id', 'head_sha', 'started_at', 'completed_at', 'status', 'conclusion', 'steps')
PHASES = ('source', 'full-ci', 'artifact-selection', 'build-producer', 'artifact-download',
          'artifact-bytes', 'final-ci', 'artifact-replay', 'final-source')
MAX_ATTEMPTS = 3
MAX_STDERR = 16384
READ_CODES = ('HTTP_REJECTED', 'TRANSPORT', 'PROCESS_FAILED', 'DEADLINE', 'BYTE_BOUND',
              'STDERR_BOUND', 'START_FAILED', 'CALL_BOUND', 'JSON_INVALID', 'INCOMPLETE')
REQUEST_KINDS = ('master', 'source', 'runs', 'run', 'attempt', 'jobs', 'artifacts', 'artifact', 'download')
STOPS = ('terminal', 'attempt-limit', 'deadline', 'call-limit')


class GitHubReadError(ValueError):
    """Closed diagnostics only: never retain CLI stderr, token or signed URL."""
    def __init__(self, reason, status=None):
        need(reason in READ_CODES, 'V5.2 GitHub error code')
        self.code = 'V52_GITHUB_'+reason
        self.http_status = status
        self.request = None
        detail = {'DEADLINE':'deadline', 'BYTE_BOUND':'byte bound'}.get(reason, 'failed')
        super().__init__('V5.2 GitHub original read '+detail+' ('+self.code+')')

    @property
    def retryable(self):
        return self.code == 'V52_GITHUB_TRANSPORT' or (
            self.code == 'V52_GITHUB_HTTP_REJECTED' and self.http_status in (500, 502, 503, 504))


def command_error(stderr, exit_code):
    # gh api emits its HTTP error with this suffix. Conflicting/unknown output
    # fails closed. Body/error strings are never used as validation evidence.
    statuses = re.findall(rb'^gh: (?:[^\r\n]* \()?HTTP ([1-5][0-9]{2})\)?\r?$', stderr, re.M)
    if len(statuses) == 1: return GitHubReadError('HTTP_REJECTED', int(statuses[0]))
    transport = (b'connection reset by peer', b'TLS handshake timeout', b'i/o timeout',
                 b'context deadline exceeded', b'unexpected EOF', b'no such host',
                 b'error connecting to api.github.com')
    if not statuses and exit_code == 1 and any(word in stderr for word in transport):
        return GitHubReadError('TRANSPORT')
    return GitHubReadError('PROCESS_FAILED')


def request_kind(path):
    if path == 'branches/master': return 'master'
    if path.startswith('contents/'): return 'source'
    part = path.split('?', 1)[0].rsplit('/', 1)[-1]
    if part in ('runs', 'jobs', 'artifacts'): return part
    if part == 'zip': return 'download'
    if path.startswith('actions/artifacts/'): return 'artifact'
    return 'attempt' if '/attempts/' in path else 'run'


def failure_details(error, phase):
    """Project the last owned check location, never exception text or locals."""
    value = dict(phase=phase, code='V52_PROVENANCE_'+phase.upper().replace('-', '_')+'_REJECTED')
    modules = (__name__, ci.__name__, inputs.__name__, inputs.build.__name__)
    trace = error.__traceback__
    while trace is not None:
        module = trace.tb_frame.f_globals.get('__name__')
        if module in modules: value['checkSite'] = dict(module=module, line=trace.tb_lineno)
        trace = trace.tb_next
    if isinstance(error, GitHubReadError):
        value['reasonCode'] = error.code
        if error.http_status is not None: value['httpStatus'] = error.http_status
        if error.request is not None: value['request'] = error.request
    return value


def public_failure(value):
    """Revalidate the private receipt before adding it to the public summary."""
    if type(value) is not dict or value.get('phase') not in PHASES: return None
    phase = value['phase']; code = 'V52_PROVENANCE_'+phase.upper().replace('-', '_')+'_REJECTED'
    if value.get('status') != 'FAIL' or value.get('code') != code: return None
    result = dict(phase=phase, code=code)
    site = value.get('checkSite')
    if type(site) is dict and site.get('module') in (__name__, ci.__name__, inputs.__name__, inputs.build.__name__) and \
            type(site.get('line')) is int and 0 < site['line'] <= 100000:
        result['checkSite'] = dict(module=site['module'], line=site['line'])
    if value.get('reasonCode') in tuple('V52_GITHUB_'+v for v in READ_CODES):
        result['reasonCode'] = value['reasonCode']
    status = value.get('httpStatus')
    if type(status) is int and 100 <= status <= 599: result['httpStatus'] = status
    row = value.get('request')
    if type(row) is dict and row.get('kind') in REQUEST_KINDS and row.get('stop') in STOPS and \
            type(row.get('attempts')) is int and 1 <= row['attempts'] <= MAX_ATTEMPTS and \
            type(row.get('ordinal')) is int and 1 <= row['ordinal'] <= 256:
        result['request'] = {key:row[key] for key in ('kind', 'stop', 'attempts', 'ordinal')}
    return result


def current_job(observation):
    rows = [job for job in observation['jobs'] if job['name'] == ci.BUILD]
    need(len(rows) == 1, 'V5.2 build job missing/duplicate'); return rows[0]


def producing_attempt(record, run):
    need(type(record['name']) is str, 'V5.2 build artifact name type')
    match = re.fullmatch(BUILD_PREFIX+run['head_sha']+r'-attempt-([1-9][0-9]{0,5})', record['name'])
    need(match is not None, 'V5.2 build artifact original attempt name')
    return a.integer(int(match[1]), 1, run['run_attempt'])


def metadata(record, observation, now):
    run = observation['run']; job = current_job(observation)
    attempt = producing_attempt(record, run); a.integer(record['id'], 1); a.integer(record['size_in_bytes'], 1, MAX_ZIP)
    need(record['expired'] is False and ci.stamp(record['expires_at']) > now, 'V5.2 artifact expired')
    origin = record['workflow_run']
    for key in ('id', 'repository_id', 'head_repository_id'): a.integer(origin[key], 1)
    need(origin['id'] == run['id'] and origin['repository_id'] == origin['head_repository_id'] == credentials.REPOSITORY_ID and
         origin['head_sha'] == run['head_sha'] and origin['head_branch'] == 'master', 'V5.2 artifact run/source/repository')
    sha = record['digest']; need(type(sha) is str and sha.startswith('sha256:'), 'V5.2 artifact digest missing')
    a.hex_value(sha[7:])
    step = next(s for s in job['steps'] if s['name'] == ci.BUILD_STEP)
    upload = next(s for s in job['steps'] if s['name'] == ci.UPLOAD_STEP)
    need(ci.stamp(job['started_at']) <= ci.stamp(step['completed_at']) <= ci.stamp(upload['started_at']) <=
         ci.stamp(record['created_at']) <= ci.stamp(record['updated_at']) <= ci.stamp(upload['completed_at']) <=
         ci.stamp(job['completed_at']) <= now, 'V5.2 artifact outside original upload')
    return attempt, sha[7:]


def select(rows, observation, now):
    run = observation['run']; job = current_job(observation)
    prefix = BUILD_PREFIX+run['head_sha']+'-attempt-'
    selected = [row for row in rows if type(row['name']) is str and row['name'].startswith(prefix) and
                ci.stamp(job['started_at']) <= ci.stamp(row['created_at']) <= ci.stamp(job['completed_at'])]
    need(len(selected) == 1, 'V5.2 original build artifact missing/ambiguous')
    metadata(selected[0], observation, now); return selected[0]


def producer(original_run, original, record, observation, shape, now):
    run = observation['run']; current = current_job(observation)
    attempt, _ = metadata(record, observation, now)
    ci.run_identity(original_run, run['head_sha'], green=False)
    need(original_run['id'] == run['id'] and original_run['run_attempt'] == attempt and
         all(original_run[key] == run[key] for key in ('workflow_id', 'event', 'path')), 'V5.2 original build run/attempt')
    ci.job_identity(original, original_run, now=now, required=shape['jobs'][ci.BUILD]['steps'])
    need(encoded({k: original[k] for k in EXECUTION_FIELDS}) == encoded({k: current[k] for k in EXECUTION_FIELDS}),
         'V5.2 original build execution replaced')
    if original['id'] != current['id']:
        need(attempt < run['run_attempt'] and type(original.get('runner_id')) is int and original['runner_id'] > 0 and
             original['runner_id'] == current.get('runner_id') and type(original.get('runner_name')) is str and
             original['runner_name'] and original['runner_name'] == current.get('runner_name') and
             ci.stamp(original['created_at']) <= ci.stamp(original['started_at']) and
             ci.stamp(current['created_at']) >= ci.stamp(original['completed_at']), 'V5.2 carried build execution not original')
    return dict(attempt=attempt, jobId=original['id'], acceptedJobId=current['id'])


def zip_contents(path, record, observation, now):
    _, sha = metadata(record, observation, now); raw = inputs.regular(path, MAX_ZIP)
    need(len(raw) == record['size_in_bytes'] and digest(raw) == sha, 'V5.2 original artifact ZIP bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist(); names = [row.filename for row in rows]
        need(len(rows) == 2 and set(names) == {'manifest.json', 'build.tar.gz'}, 'V5.2 original artifact ZIP inventory')
        for row in rows:
            mode = row.external_attr >> 16
            need(row.orig_filename == row.filename and not row.is_dir() and not row.flag_bits & 1 and
                 stat.S_IFMT(mode) in (0, stat.S_IFREG) and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                 0 < row.file_size <= (inputs.MAX_JSON if row.filename == 'manifest.json' else inputs.MAX_BYTES),
                 'V5.2 original artifact ZIP member')
        return {name: archive.read(name) for name in names}


def save(path, value):
    raw = encoded(value)+b'\n'; need(len(raw) <= MAX_JSON, 'V5.2 GitHub retained JSON bound')
    with Path(path).open('xb') as stream: stream.write(raw)


def read(path): return strict(inputs.regular(path, MAX_JSON))


def replay(directory, source, shape, binding, *, now):
    """Inspect retained original metadata and bytes; no freshness is inferred."""
    directory = Path(directory)
    need(not (directory/'failure.json').exists(), 'V5.2 original provenance collection failed')
    before, after = read(directory/'ci-before.json'), read(directory/'ci-after.json')
    first, last = [ci.validate(v, source, shape, now) for v in (before, after)]
    need(first == last, 'V5.2 accepted CI changed during artifact collection')
    record = read(directory/'artifact.json')
    need(encoded(record) == encoded(read(directory/'artifact-after.json')), 'V5.2 artifact metadata changed')
    for key in ('artifacts-before.json', 'artifacts-after.json'):
        rows = read(directory/key)['artifacts']
        need(type(rows) is list and 0 < len(rows) <= ci.MAX_ROWS and
             len({a.integer(row['id'], 1) for row in rows}) == len(rows), 'V5.2 artifact inventory')
        need(encoded(select(rows, before, now)) == encoded(record), 'V5.2 selected artifact changed')
    original_run, original_job = read(directory/'producer-run.json'), read(directory/'producer-job.json')
    original_jobs = read(directory/'producer-jobs.json')['jobs']
    need(type(original_jobs) is list and 0 < len(original_jobs) <= ci.MAX_ROWS and
         len({a.integer(job['id'], 1) for job in original_jobs}) == len(original_jobs), 'V5.2 original job inventory')
    need(encoded([job for job in original_jobs if job['name'] == ci.BUILD]) == encoded([original_job]),
         'V5.2 original build job observation changed')
    origin = producer(original_run, original_job, record, before, shape, now)
    files = zip_contents(directory/'build.zip', record, before, now)
    # Compare original ZIP members to retained outputs; existing local target
    # JARs or a copied receipt never substitute for these authenticated bytes.
    for name, raw in files.items(): need(inputs.regular(directory/'build'/name, inputs.MAX_BYTES) == raw, 'V5.2 extracted build bytes changed')
    need(binding['source'] == source, 'V5.2 separately observed build source')
    roots = [f'target/general-search-engine-{inputs.VERSION}.jar',
             f'{inputs.build.MODULE}/target/general-search-engine-replication-{inputs.VERSION}.jar', inputs.build.CLASSES, inputs.build.REPORTS]
    raw, _ = inputs.build_files(directory/'build', binding, roots)
    return dict(schema=SCHEMA, status='BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED', source=source, buildBinding=deepcopy(binding),
        ci=first, producer=origin, artifactId=record['id'], artifactSha256=record['digest'][7:],
        buildManifestSha256=digest(raw), paidAdmission=False, fullRemoteQualification=False)


def _collect(directory, source, shape, binding, client, wall, *, progress=None):
    directory = Path(directory); progress = {} if progress is None else progress
    progress['phase'] = 'full-ci'
    before = ci.observe(source, shape, client.get, wall); save(directory/'ci-before.json', before)
    progress['phase'] = 'artifact-selection'
    rows = ci.pages(client.get, f"actions/runs/{before['run']['id']}/artifacts", 'artifacts')
    save(directory/'artifacts-before.json', dict(artifacts=rows))
    record = select(rows, before, int(wall())); save(directory/'artifact.json', record)
    need(encoded(client.get('actions/artifacts/'+str(record['id']))) == encoded(record), 'V5.2 artifact metadata mismatch')
    progress['phase'] = 'build-producer'
    attempt = producing_attempt(record, before['run'])
    run = client.get(f"actions/runs/{before['run']['id']}/attempts/{attempt}"); save(directory/'producer-run.json', run)
    originals = ci.jobs(client.get, before['run'], attempt)
    save(directory/'producer-jobs.json', dict(jobs=originals))
    matches = [job for job in originals if job['name'] == ci.BUILD]
    need(len(matches) == 1, 'V5.2 original build job missing/duplicate')
    origin = matches[0]; producer(run, origin, record, before, shape, int(wall())); save(directory/'producer-job.json', origin)
    progress['phase'] = 'artifact-download'
    client.download(record['id'], directory/'build.zip', record['size_in_bytes'])
    progress['phase'] = 'artifact-bytes'
    files = zip_contents(directory/'build.zip', record, before, int(wall()))
    (directory/'build').mkdir()
    for name, raw in files.items():
        with (directory/'build'/name).open('xb') as stream: stream.write(raw)
    save(directory/'artifact-after.json', client.get('actions/artifacts/'+str(record['id'])))
    rows_after = ci.pages(client.get, f"actions/runs/{before['run']['id']}/artifacts", 'artifacts')
    save(directory/'artifacts-after.json', dict(artifacts=rows_after))
    progress['phase'] = 'final-ci'
    save(directory/'ci-after.json', ci.observe(source, shape, client.get, wall))
    progress['phase'] = 'artifact-replay'
    result = replay(directory, source, shape, binding, now=int(wall()))
    save(directory/'inspection.json', result); return result


def bounded_command(command, path, maximum, timeout):
    """Own and reap one read subprocess; bound bytes while streaming, not after."""
    process = None; success = False; end = time.monotonic()+timeout
    with Path(path).open('xb') as output:
        try:
            try:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True)
            except OSError: raise GitHubReadError('START_FAILED') from None
            total = 0; stderr = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                selector.register(process.stderr, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = end-time.monotonic()
                    if remaining <= 0: raise GitHubReadError('DEADLINE')
                    for key, _ in selector.select(min(1, remaining)):
                        diagnostic = key.fileobj is process.stderr
                        bound = MAX_STDERR-len(stderr) if diagnostic else maximum-total
                        raw = os.read(key.fd, min(65536, bound+1))
                        if not raw: selector.unregister(key.fileobj); continue
                        if len(raw) > bound: raise GitHubReadError('STDERR_BOUND' if diagnostic else 'BYTE_BOUND')
                        if diagnostic: stderr.extend(raw)
                        else: total += len(raw); output.write(raw)
            remaining = end-time.monotonic()
            if remaining <= 0: raise GitHubReadError('DEADLINE')
            try: status = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired: raise GitHubReadError('DEADLINE') from None
            if status != 0: raise command_error(stderr, status)
            success = True
        finally:
            if process is not None:
                if not success:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                if process.stdout is not None: process.stdout.close()
                if process.stderr is not None: process.stderr.close()
                process.wait()


def allowed_path(path):
    need(type(path) is str, 'V5.2 GitHub read path')
    number = r'[1-9][0-9]{0,19}'; page = r'[1-9][0-9]?'
    patterns = (r'branches/master', r'actions/workflows/ci\.yml/runs\?branch=master&head_sha=[0-9a-f]{40}&per_page=100&page='+page,
        r'actions/runs/'+number+r'(?:/attempts/'+number+r')?',
        r'actions/runs/'+number+r'/attempts/'+number+r'/jobs\?per_page=100&page='+page,
        r'actions/runs/'+number+r'/artifacts\?per_page=100&page='+page, r'actions/artifacts/'+number)
    contents = any(re.fullmatch(re.escape('contents/'+name)+r'\?ref=[0-9a-f]{40}', path) for name in ci.SOURCE_FILES)
    need(contents or any(re.fullmatch(pattern, path) for pattern in patterns), 'V5.2 GitHub read path outside scope')


class Network:
    """Fixed GitHub GET only. Does not discover/obtain any cloud credential."""
    def __init__(self, output):
        self.output = Path(output); self.output.mkdir(); self.calls = 0

    @staticmethod
    def command(path):
        return ['gh', 'api', '--hostname', 'github.com', '--method', 'GET',
                '-H', 'Accept: application/vnd.github+json', '-H', 'X-GitHub-Api-Version: 2022-11-28',
                'repos/'+credentials.REPOSITORY+'/'+path]

    def authorize_path(self, path): allowed_path(path)

    def _read(self, path, maximum, timeout, *, download=False):
        """Retry only failed GET exchanges, within one original deadline.

        Each physical attempt consumes the call bound and retains a distinct
        body/closed receipt. Validation and whole collections are never retried.
        """
        end = time.monotonic()+timeout
        for attempt in range(1, MAX_ATTEMPTS+1):
            if self.calls >= 256: raise GitHubReadError('CALL_BOUND')
            remaining = end-time.monotonic()
            if remaining <= 0: raise GitHubReadError('DEADLINE')
            self.calls += 1; ordinal = self.calls
            target = self.output/f'{ordinal:03}.{"zip" if download else "json"}'
            record = dict(method='GET', path=path, kind=request_kind(path), attempt=attempt, ordinal=ordinal)
            error = None
            try:
                bounded_command(self.command(path), target, maximum, remaining)
                if time.monotonic() >= end: raise GitHubReadError('DEADLINE')
            except GitHubReadError as failure:
                error = failure
            if error is None:
                save(self.output/f'{ordinal:03}-request.json', dict(record, status='PASS'))
                return target
            delay = attempt  # 1 second, then 2 seconds; never reset the deadline.
            if not error.retryable: stop = 'deadline' if error.code == 'V52_GITHUB_DEADLINE' else 'terminal'
            elif attempt == MAX_ATTEMPTS: stop = 'attempt-limit'
            elif self.calls >= 256: stop = 'call-limit'
            elif end-time.monotonic() <= delay: stop = 'deadline'
            else: stop = None
            detail = dict(record, status='FAIL', reasonCode=error.code, retry=stop is None, stop=stop)
            if error.http_status is not None: detail['httpStatus'] = error.http_status
            save(self.output/f'{ordinal:03}-request.json', detail)
            # Progress is intentionally closed and excludes request URLs/body.
            print(encoded({key:value for key,value in detail.items() if key not in ('path', 'method')}).decode(), flush=True)
            if stop is not None:
                error.request = dict(kind=record['kind'], attempts=attempt, ordinal=ordinal, stop=stop)
                raise error
            time.sleep(delay)

    def get(self, path):
        self.authorize_path(path)
        target = self._read(path, MAX_JSON, 30)
        try: return read(target)
        except ValueError: raise GitHubReadError('JSON_INVALID') from None

    def download(self, identity, output, size):
        a.integer(identity, 1); a.integer(size, 1, MAX_ZIP)
        output = Path(output)
        if output.exists() or output.is_symlink(): raise FileExistsError(output)
        target = self._read(f'actions/artifacts/{identity}/zip', size, 300, download=True)
        if target.stat().st_size != size: raise GitHubReadError('INCOMPLETE')
        os.link(target, output)  # Publish one complete response, never concatenate partial attempts or overwrite.


def collect_native(source, output):
    """Read current source/GitHub with fixed adapters; no provider capability."""
    output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 provenance output symlink')
    output.mkdir(parents=True, exist_ok=False)
    progress = dict(phase='source')
    try:
        bound = inputs.checkout(ci.ROOT, source); shape = ci.contract()
        result = _collect(output, source, shape, bound, Network(output/'requests'), time.time, progress=progress)
        progress['phase'] = 'final-source'
        need(inputs.checkout(ci.ROOT, source) == bound and ci.contract() == shape, 'V5.2 source changed during GitHub observation')
        receipt = dict(execution='native-v52-github-read-only', checkedAt=int(time.time()), **result)
        save(output/'receipt.json', receipt); return receipt
    except BaseException as error:
        try:
            save(output/'failure.json', dict(status='FAIL', **failure_details(error, progress['phase']),
                                            type=type(error).__name__, paidAdmission=False, fullRemoteQualification=False))
        except Exception: print('v52GitHubDiagnosticRetention=FAIL', flush=True)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--source', required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); print(encoded(collect_native(args.source, args.output)).decode())
