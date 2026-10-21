"""GET-only provenance for an explicitly selected original Runner attempt.

Unlike current CI/admission, completed experiment evidence has no recency limit.
Never select the latest green run or replace a selected attempt with its rerun.
This internal collector remains closed until the protected workflow is present
in the exact clean source checkout. It cannot run or qualify a cloud workload.
"""
import io
from pathlib import Path
import re
import stat
import time
import zipfile
from scripts import ci_suites as yaml
from . import cloud_ci as ci, cloud_artifacts as artifacts, cloud_authority as a
from . import cloud_credentials as credentials, cloud_preflight as preflight, cloud_preflight_read as reads
from . import cloud_member_seal as seal
from .evidence import need, encoded, digest, strict

SCHEMA = 'gse-v52-original-runner-provenance-v1'
PATH = credentials.ROLES['runner'][1]
JOB = 'V5.2 replication runner'
IDENTITY = 'Bind V5.2 Runner identity'
AUTH = 'Authenticate V5.2 Runner identity'
EXECUTE = 'Execute selected V5.2 operation'
UPLOAD = 'Retain V5.2 Runner result'
REQUIRED = (IDENTITY, AUTH, EXECUTE, UPLOAD)
MAX_ZIP = 128 << 10
OBSERVATION_SECONDS = 900
# Runner step times and GitHub artifact service times use separate clocks and
# whole-second API timestamps. Bound only this correlation, never execution,
# expiry, source/attempt identity or the original artifact's immutable bytes.
UPLOAD_CLOCK_TOLERANCE_SECONDS = 5


def contract(root=ci.ROOT):
    """Inspect actual source, never infer deployed workflow bytes from a report."""
    source = artifacts.inputs.regular(Path(root)/PATH, 65536).decode()
    header = yaml.fields(source.split('\njobs:\n', 1)[0], 0)
    events = yaml.fields(header['on'][1], 2)
    need(not header['on'][0] and set(events) == {'workflow_dispatch'}, 'V5.2 Runner manual event contract')
    jobs = yaml.job_blocks(source); need(set(jobs) == {'runner'}, 'V5.2 Runner job inventory contract')
    job = yaml.fields(jobs['runner'], 4)
    need(yaml.scalar(job['name']) == JOB and yaml.scalar(job['environment']) == 'v52-cloud-benchmark' and
         yaml.scalar(job['if']) == "${{ github.ref == 'refs/heads/master' }}" and
         'continue-on-error' not in job and 'strategy' not in job, 'V5.2 Runner job identity contract')
    need(job['runs-on'] == ('[self-hosted, Linux, X64, gse-v52-cloud-d-wsl]', '') and
         yaml.scalar(job['timeout-minutes']) == '1380', 'V5.2 dedicated Runner routing/time contract')
    steps = yaml.steps(job['steps'])
    need(tuple(name for name in steps if name in REQUIRED) == REQUIRED, 'V5.2 Runner ordered required steps contract')
    need(all('if' not in steps[name] for name in REQUIRED), 'V5.2 Runner conditional required step')
    return source


def original(value):
    a.fields(value, 'runId runAttempt', 'selected original invocation')
    for key in value: a.integer(value[key], 1)
    return value


def name(chosen):
    original(chosen); return f"v52-runner-{chosen['runId']}-{chosen['runAttempt']}"


def run_identity(value, source, chosen):
    original(chosen)
    for key in ('id', 'run_attempt', 'workflow_id'): a.integer(value[key], 1)
    for key in ('repository', 'head_repository'):
        row = value[key]
        need(type(row['id']) is int and row['id'] == credentials.REPOSITORY_ID and row['full_name'] == credentials.REPOSITORY and
             type(row['owner']['id']) is int and row['owner']['id'] == credentials.OWNER_ID, 'V5.2 Runner repository identity')
    need(value['id'] == chosen['runId'] and value['run_attempt'] == chosen['runAttempt'] and
         value['head_sha'] == source and value['head_branch'] == 'master' and value['path'] == PATH and
         value['event'] == 'workflow_dispatch' and value['status'] == 'completed' and value['conclusion'] == 'success',
         'V5.2 Runner original attempt not exact-master completed success')
    return value


def job(rows, run, now):
    need(type(rows) is list and len(rows) == 1 and rows[0]['name'] == JOB, 'V5.2 Runner original job inventory')
    row = rows[0]; ci.job_identity(row, run, now=now, required=REQUIRED)
    times = {v['name']: (ci.stamp(v['started_at']), ci.stamp(v['completed_at'])) for v in row['steps'] if v['name'] in REQUIRED}
    need(all(times[left][1] <= times[right][0] for left, right in zip(REQUIRED, REQUIRED[1:])), 'V5.2 Runner steps out of order')
    return row, times


def metadata(record, run, chosen, times, now, *, artifact_name=None, maximum=MAX_ZIP):
    a.integer(record['id'], 1); a.integer(record['size_in_bytes'], 1, maximum)
    need(record['name'] == (name(chosen) if artifact_name is None else artifact_name) and record['expired'] is False and ci.stamp(record['expires_at']) > now,
         'V5.2 Runner original artifact name/expiry')
    origin = record['workflow_run']
    for key in ('id', 'repository_id', 'head_repository_id'): a.integer(origin[key], 1)
    need(origin['id'] == run['id'] and origin['repository_id'] == origin['head_repository_id'] == credentials.REPOSITORY_ID and
         origin['head_sha'] == run['head_sha'] and origin['head_branch'] == 'master', 'V5.2 Runner artifact original execution')
    sha = record['digest']; need(type(sha) is str and sha.startswith('sha256:'), 'V5.2 Runner artifact digest missing')
    a.hex_value(sha[7:])
    created, updated = ci.stamp(record['created_at']), ci.stamp(record['updated_at'])
    need(times[UPLOAD][0] - UPLOAD_CLOCK_TOLERANCE_SECONDS <= created <= updated <=
         min(now, times[UPLOAD][1] + UPLOAD_CLOCK_TOLERANCE_SECONDS),
         'V5.2 Runner artifact outside original upload')
    return sha[7:]


def select(rows, run, chosen, times, now, *, artifact_name=None, maximum=MAX_ZIP):
    need(type(rows) is list and len(rows) <= ci.MAX_ROWS and len({a.integer(r['id'], 1) for r in rows}) == len(rows),
         'V5.2 Runner artifact inventory')
    matches = [row for row in rows if row['name'] == (name(chosen) if artifact_name is None else artifact_name)]
    need(len(matches) == 1, 'V5.2 Runner original artifact missing/ambiguous')
    metadata(matches[0], run, chosen, times, now, artifact_name=artifact_name, maximum=maximum); return matches[0]


def contents(path, record, sha):
    raw = artifacts.inputs.regular(path, MAX_ZIP)
    need(len(raw) == record['size_in_bytes'] and digest(raw) == sha, 'V5.2 Runner original ZIP bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        need(len(rows) == 1, 'V5.2 Runner ZIP inventory')
        row = rows[0]; mode = row.external_attr >> 16
        need(row.filename == row.orig_filename == 'member-seal.json' and not row.is_dir() and not row.flag_bits & 1 and
             stat.S_IFMT(mode) in (0, stat.S_IFREG) and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
             0 < row.file_size <= seal.MAX_BYTES, 'V5.2 Runner ZIP member')
        return strict(archive.read(row))


def validate(value, cfg, source, request, chosen, archive, workflow, now):
    a.fields(value, 'schema source configurationSha256 selected startedAt completedAt masterBefore masterAfter '
             'run runAfter jobs jobsAfter artifact artifactAfter artifactsBefore artifactsAfter workflowContent', 'Runner observation')
    original(chosen)
    need(value['schema'] == SCHEMA and value['source'] == value['masterBefore'] == value['masterAfter'] == source['source'] and
         value['configurationSha256'] == preflight.configuration(cfg) and value['selected'] == chosen,
         'V5.2 Runner source/configuration/selection changed')
    a.integer(value['startedAt'], max(1, now-OBSERVATION_SECONDS), now)
    a.integer(value['completedAt'], value['startedAt'], now)
    run = run_identity(value['run'], source['source'], chosen)
    after = run_identity(value['runAfter'], source['source'], chosen)
    need(encoded(ci.run_key(run)) == encoded(ci.run_key(after)), 'V5.2 Runner original attempt changed')
    first, times = job(value['jobs'], run, now); last, _ = job(value['jobsAfter'], run, now)
    need(encoded(ci.job_key(first)) == encoded(ci.job_key(last)) and ci.stamp(first['completed_at']) <= value['startedAt'],
         'V5.2 Runner original job changed/future')
    ci.source_content(value['workflowContent'], PATH, workflow)
    record = value['artifact']; sha = metadata(record, run, chosen, times, now)
    for other in (value['artifactAfter'], select(value['artifactsBefore'], run, chosen, times, now),
                  select(value['artifactsAfter'], run, chosen, times, now)):
        need(encoded(record) == encoded(other), 'V5.2 Runner artifact changed')
    result = contents(archive, record, sha); seal.validate(result, cfg, source, request, now=now)
    own = result['credentialContext']
    need(own['runId'] == chosen['runId'] and own['runAttempt'] == chosen['runAttempt'] and
         times[EXECUTE][0] <= result['startedAt'] <= result['completedAt'] <= times[EXECUTE][1],
         'V5.2 Runner seal outside original execution')
    return dict(schema=SCHEMA, status='ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED', source=source, selected=chosen,
        artifactId=record['id'], artifactSha256=sha, seal=result, sealSha256=digest(encoded(result)),
        fullRemoteQualification=False, paidCloud=False)


def collect(directory, cfg, source, request, chosen, workflow, client, wall):
    original(chosen); directory = Path(directory); started = int(wall())
    master = client.get('branches/master')['commit']['sha']; need(master == source['source'], 'V5.2 Runner current master moved')
    path = f"actions/runs/{chosen['runId']}/attempts/{chosen['runAttempt']}"
    run = run_identity(client.get(path), source['source'], chosen)
    jobs = ci.jobs(client.get, run); _, times = job(jobs, run, int(wall()))
    listing = f"actions/runs/{chosen['runId']}/artifacts"
    records = ci.pages(client.get, listing, 'artifacts'); record = select(records, run, chosen, times, int(wall()))
    artifact_path = 'actions/artifacts/'+str(record['id'])
    need(encoded(client.get(artifact_path)) == encoded(record), 'V5.2 Runner original artifact metadata mismatch')
    client.download(record['id'], directory/'runner.zip', record['size_in_bytes'])
    value = dict(schema=SCHEMA, source=source['source'], configurationSha256=preflight.configuration(cfg), selected=chosen,
        startedAt=started, masterBefore=master, run=run, jobs=jobs, artifactsBefore=records, artifact=record,
        workflowContent=client.get('contents/'+PATH+'?ref='+source['source']), artifactAfter=client.get(artifact_path),
        artifactsAfter=ci.pages(client.get, listing, 'artifacts'), jobsAfter=ci.jobs(client.get, run), runAfter=client.get(path),
        masterAfter=client.get('branches/master')['commit']['sha'], completedAt=int(wall()))
    artifacts.save(directory/'observation.json', value)
    return validate(value, cfg, source, request, chosen, directory/'runner.zip', workflow, int(wall()))


class Network(artifacts.Network):
    def authorize_path(self, path):
        number = r'[1-9][0-9]{0,19}'; page = r'[1-9][0-9]?'
        patterns = (r'branches/master', r'actions/runs/'+number+r'/attempts/'+number,
            r'actions/runs/'+number+r'/attempts/'+number+r'/jobs\?per_page=100&page='+page,
            r'actions/runs/'+number+r'/artifacts\?per_page=100&page='+page, r'actions/artifacts/'+number,
            re.escape('contents/'+PATH)+r'\?ref=[0-9a-f]{40}')
        need(type(path) is str and any(re.fullmatch(v, path) for v in patterns), 'V5.2 Runner GitHub path outside scope')
    def download(self, identity, output, size):
        a.integer(size, 1, MAX_ZIP); return super().download(identity, output, size)


def collect_native(source, request, chosen, output):
    output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 Runner provenance output link')
    output.mkdir(parents=True, exist_ok=False)
    try:
        cfg = reads.source_configuration(source); bound = artifacts.inputs.checkout(ci.ROOT, source); workflow = contract()
        a.validate_request(request, domain='native')
        value = collect(output, cfg, bound, request, chosen, workflow, Network(output/'requests'), time.time)
        need(reads.source_configuration(source) == cfg and artifacts.inputs.checkout(ci.ROOT, source) == bound and contract() == workflow,
             'V5.2 Runner provenance source changed')
        artifacts.save(output/'receipt.json', value); return value
    except BaseException as error:
        artifacts.save(output/'failure.json', dict(status='FAIL', code='V52_ORIGINAL_RUNNER_PROVENANCE_REJECTED',
            errorType=type(error).__name__, fullRemoteQualification=False))
        raise
