"""V5.2 exact-master CI/build observations using the existing closed CI registry.

No workflow dispatch, rerun, configuration change or paid admission. Pure replay
is not a fresh observation; the native collector owns its fixed read-only client.
"""
import base64
from copy import deepcopy
from datetime import datetime
import hashlib
import itertools
from pathlib import Path
from scripts import ci_suites as suites
from . import cloud_authority as a, cloud_credentials as credentials, cloud_build_workflow as standalone
from .evidence import need, encoded, digest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = suites.WORKFLOW
EVENTS = ('push', 'workflow_dispatch', 'schedule')
SCHEMA = 'gse-v52-full-ci-observation-v1'
SOURCE_FILES = (WORKFLOW, standalone.WORKFLOW, suites.REGISTRY, '.github/workflows/release.yml',
                '.github/actions/v51-restore-build/action.yml', '.github/actions/v51-retain-build/action.yml')
BUILD = 'V5.1 verification build'
BUILD_STEP = 'Create exact-source V5.1 verification bundle'
UPLOAD_STEP = 'Publish V5.1 verification inputs'
MAX_ROWS = 1000
# Temporary V5.2 cloud-admission policy, explicitly authorized by the operator.
# Restore True to require the complete green job set again. No environment or
# dispatch input may change this policy; build/source provenance stays required.
REQUIRE_FULL_CI = False
RUN_FIELDS = ('id', 'run_attempt', 'workflow_id', 'head_sha', 'head_branch', 'event', 'path', 'status', 'conclusion',
              'repository', 'head_repository')
JOB_FIELDS = ('id', 'run_id', 'run_attempt', 'head_sha', 'name', 'status', 'conclusion', 'started_at', 'completed_at', 'steps')


def stamp(value):
    need(type(value) is str and len(value) <= 40, 'V5.2 GitHub timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(parsed.tzinfo is not None, 'V5.2 GitHub timestamp timezone')
    # Job/step timestamps commonly have only whole-second precision. Do not
    # claim a finer correlation with an artifact's fractional-second timestamp.
    return a.integer(int(parsed.timestamp()), 1)


def run_identity(value, source, *, green=True, allow_unfinished=False, allow_standalone=False):
    need(type(value) is dict, 'V5.2 CI run shape')
    for key in ('id', 'run_attempt', 'workflow_id'): a.integer(value[key], 1)
    for key in ('repository', 'head_repository'):
        row = value[key]
        need(type(row) is dict and type(row['id']) is int and row['id'] == credentials.REPOSITORY_ID and
             row['full_name'] == credentials.REPOSITORY and type(row['owner']['id']) is int and
             row['owner']['id'] == credentials.OWNER_ID, 'V5.2 CI repository identity')
    permitted = (value['path'] == WORKFLOW and value['event'] in EVENTS) or (
        allow_standalone and value['path'] == standalone.WORKFLOW and value['event'] == 'workflow_dispatch')
    need(value['head_sha'] == source and value['head_branch'] == 'master' and permitted, 'V5.2 CI source/workflow/event')
    if allow_unfinished:
        need(not green and ((value['status']=='completed' and type(value['conclusion']) is str and bool(value['conclusion'])) or
             (value['status'] in ('queued','in_progress','pending','waiting','requested') and value['conclusion'] is None)),
             'V5.2 CI run state')
    else:
        need(value['status'] == 'completed' and type(value['conclusion']) is str and
             (value['conclusion'] == 'success' if green else bool(value['conclusion'])), 'V5.2 CI not completed green')
    return value


def run_key(value):
    result = {key: deepcopy(value[key]) for key in RUN_FIELDS if key not in ('repository', 'head_repository')}
    for key in ('repository', 'head_repository'):
        row = value[key]
        result[key] = dict(id=row['id'], full_name=row['full_name'], owner=dict(id=row['owner']['id']))
    return result


def job_key(value):
    return {**{key: deepcopy(value[key]) for key in JOB_FIELDS},
            **{key: value.get(key) for key in ('created_at', 'runner_id', 'runner_name')}}


def admission_run_key(value, require_full):
    result=run_key(value)
    if not require_full:
        # Other jobs can finish during collection; identity/attempt cannot move.
        result.pop('status');result.pop('conclusion')
    return result


def build_name(run):
    need(run['path'] in (WORKFLOW, standalone.WORKFLOW), 'V5.2 build workflow')
    return BUILD if run['path'] == WORKFLOW else standalone.JOB


def build_contract(shape, run):
    key = 'jobs' if run['path'] == WORKFLOW else 'standaloneJobs'
    return shape[key][build_name(run)]


def admitted_jobs(rows, require_full, run):
    need(type(rows) is list and 0<len(rows)<=MAX_ROWS and
         len({a.integer(row['id'],1) for row in rows})==len(rows),'V5.2 CI duplicate/incomplete job inventory')
    return rows if require_full else [row for row in rows if row['name']==build_name(run)]


def contract(root=ROOT):
    """Use the existing source-controlled inventory, including fixed matrices."""
    registry = suites.check(root)
    workflow = suites.read(root, WORKFLOW); blocks = suites.job_blocks(workflow)
    by_id = {row['id']: row for row in registry['suites']}; jobs = {}
    for key, body in blocks.items():
        fields = suites.fields(body, 4); names = suites.steps(fields['steps'])
        # GitHub exposes the caller name for a composite action in the job API.
        # The source contract separately validates its expanded implementation.
        required = [name for name, values in names.items() if 'if' not in values or suites.scalar(values['if']) == suites.ALWAYS]
        for name, values in names.items():
            if 'run' in values and 'if' in values and suites.scalar(values['if']) != suites.ALWAYS:
                need(key == 'changes' and name == 'Validate documentation-only contract changes' and
                     suites.scalar(values['if']) == "${{ steps.scope.outputs.run_full_ci == 'false' }}",
                     'V5.2 CI unreviewed conditional verification')
        matrix = by_id[key]['matrix'] if key in by_id else None
        variants = [{}] if matrix is None else matrix.get('include')
        if variants is None: variants = [dict(zip(matrix, row)) for row in itertools.product(*matrix.values())]
        for variant in variants:
            name = suites.scalar(fields['name'])
            for axis, value in variant.items(): name = name.replace('${{ matrix.'+axis+' }}', str(value))
            need(name not in jobs and '${{' not in name, 'V5.2 CI expanded name')
            jobs[name] = dict(id=key, steps=required)
    need(set(jobs) == set(suites.expanded_names(registry)) and BUILD in jobs and
         {BUILD_STEP, UPLOAD_STEP} <= set(jobs[BUILD]['steps']), 'V5.2 CI complete contract')
    return dict(schema='gse-v52-full-ci-contract-v1', jobs=jobs, standaloneJobs=standalone.contract(root),
                sourceFiles={name: suites.read(root, name) for name in SOURCE_FILES})


def pages(get, path, key, *, limit=MAX_ROWS):
    """Complete bounded inventory, rejecting truncation, duplicates and drift."""
    rows = []; total = None
    for page in range(1, (limit+99)//100+1):
        value = get(path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
        need(type(value) is dict, 'V5.2 GitHub page shape')
        count = a.integer(value['total_count'], 0, limit); part = value[key]
        need(total in (None, count) and type(part) is list and len(part) == min(100, count-len(rows)),
             'V5.2 GitHub changed/truncated pagination')
        total = count; rows.extend(part)
        if len(rows) == total: break
    need(total is not None and len(rows) == total, 'V5.2 GitHub incomplete inventory')
    identities = [a.integer(row['id'], 1) for row in rows]
    need(len(identities) == len(set(identities)), 'V5.2 GitHub duplicate inventory ID')
    return rows


def latest(rows, source, *, require_full=True):
    if not require_full:
        dedicated = [row for row in rows if row['head_sha'] == source and row['head_branch'] == 'master' and
                     row['path'] == standalone.WORKFLOW and row['event'] == 'workflow_dispatch']
        # An explicit manual build supersedes CI for this source, even when
        # it fails or is pending. Never hide its failure with another producer.
        if dedicated: return max(dedicated, key=lambda row:a.integer(row['id'], 1))
    selected = [row for row in rows if row['head_sha'] == source and row['head_branch'] == 'master' and
                row['path'] == WORKFLOW and row['event'] in EVENTS]
    need(selected, 'V5.2 no exact-master CI run')
    # Include newer failed/pending runs; never search backward for a green one.
    return max(selected, key=lambda row: a.integer(row['id'], 1))


def listing(get, source, *, require_full=True):
    # GitHub caps filtered run searches at 1,000. Reject that boundary rather
    # than mistaking a capped response for a complete inventory.
    paths = [WORKFLOW] if require_full else [WORKFLOW, standalone.WORKFLOW]
    rows = []
    for path in paths:
        part = pages(get, 'actions/workflows/'+Path(path).name+'/runs?branch=master&head_sha='+source,
                     'workflow_runs', limit=999)
        need(all(row['path'] == path for row in part), 'V5.2 CI workflow listing identity')
        rows.extend(part)
    need(len(rows) < 1000 and len({row['id'] for row in rows}) == len(rows), 'V5.2 CI combined run inventory')
    return rows


def jobs(get, run, attempt=None):
    run_id = a.integer(run['id'], 1); number = a.integer(run['run_attempt'] if attempt is None else attempt, 1)
    return pages(get, f'actions/runs/{run_id}/attempts/{number}/jobs', 'jobs')


def job_identity(job, run, *, now, required):
    a.integer(job['id'], 1)
    need(type(job['run_id']) is int and type(job['run_attempt']) is int and job['run_id'] == run['id'] and
         job['run_attempt'] == run['run_attempt'] and job['head_sha'] == run['head_sha'] and
         job['status'] == 'completed' and job['conclusion'] == 'success', 'V5.2 CI failed/skipped/wrong-attempt job')
    start, end = stamp(job['started_at']), stamp(job['completed_at'])
    need(start <= end <= now, 'V5.2 CI job time')
    steps = job['steps']; need(type(steps) is list and 0 < len(steps) <= 1000, 'V5.2 CI steps inventory')
    numbers = [a.integer(step['number'], 1) for step in steps]
    need(len(numbers) == len(set(numbers)), 'V5.2 CI duplicate step number')
    for name in required:
        matches = [step for step in steps if step['name'] == name]
        need(len(matches) == 1, 'V5.2 CI required step missing/duplicate')
        step = matches[0]
        need(step['status'] == 'completed' and step['conclusion'] == 'success' and
             start <= stamp(step['started_at']) <= stamp(step['completed_at']) <= end,
             'V5.2 CI required step skipped/failed/outside job')


def source_content(value, path, expected):
    need(type(value) is dict and value['type'] == 'file' and value['path'] == path and value['encoding'] == 'base64',
         'V5.2 CI source content identity')
    a.integer(value['size'], 1, suites.LIMIT)
    need(type(value['content']) is str and len(value['content']) <= 2*suites.LIMIT, 'V5.2 CI source content bound')
    raw = base64.b64decode(value['content'].replace('\n', ''), validate=True)
    need(raw == expected.encode() and len(raw) == value['size'], 'V5.2 CI source bytes changed')
    blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    need(value['sha'] == blob, 'V5.2 CI source Git blob changed')
    return digest(raw)


def validate(value, source, shape, now, *, require_full=True):
    a.hex_value(source, 40); a.integer(now, 1)
    a.fields(value, 'schema source masterBefore masterAfter run runAttempt runAfter runsBefore runsAfter jobs jobsAfter sourceContents', 'CI observation')
    need(value['schema'] == SCHEMA and value['source'] == source and value['masterBefore'] == value['masterAfter'] == source,
         'V5.2 CI master/source moved')
    need(type(require_full) is bool,'V5.2 CI admission policy')
    run = run_identity(value['run'], source,green=require_full,allow_unfinished=not require_full,allow_standalone=not require_full)
    for key in ('runAttempt', 'runAfter'):
        run_identity(value[key], source,green=require_full,allow_unfinished=not require_full,allow_standalone=not require_full)
        need(encoded(admission_run_key(value[key],require_full)) == encoded(admission_run_key(run,require_full)), 'V5.2 CI run/attempt changed')
    for key in ('runsBefore', 'runsAfter'):
        rows = value[key]
        need(type(rows) is list and 0 < len(rows) < 1000 and
             len({a.integer(row['id'], 1) for row in rows}) == len(rows), 'V5.2 CI run inventory')
        chosen = latest(rows, source,require_full=require_full)
        run_identity(chosen, source,green=require_full,allow_unfinished=not require_full,allow_standalone=not require_full)
        need(encoded(admission_run_key(chosen,require_full)) == encoded(admission_run_key(run,require_full)), 'V5.2 CI latest run changed/not green')
    wanted = shape['jobs'] if require_full else {build_name(run):build_contract(shape,run)}
    rows = admitted_jobs(value['jobs'],require_full,run)
    need(type(rows) is list and len(rows) == len(wanted) and sorted(row['name'] for row in rows) == sorted(wanted),
         'V5.2 CI full job inventory')
    need(len({a.integer(row['id'], 1) for row in rows}) == len(rows), 'V5.2 CI duplicate job ID')
    for job in rows: job_identity(job, run, now=now, required=wanted[job['name']]['steps'])
    after = admitted_jobs(value['jobsAfter'],require_full,run)
    need(type(after) is list and len(after) == len(rows) and
         encoded(sorted((job_key(row) for row in after), key=lambda r:r['id'])) ==
         encoded(sorted((job_key(row) for row in rows), key=lambda r:r['id'])), 'V5.2 CI job execution changed')
    need(set(value['sourceContents']) == set(SOURCE_FILES) == set(shape['sourceFiles']), 'V5.2 CI source file inventory')
    hashes = {name: source_content(value['sourceContents'][name], name, raw) for name, raw in shape['sourceFiles'].items()}
    return dict(schema='gse-v52-full-ci-inspection-v1' if require_full else 'gse-v52-build-ci-inspection-v1',
        status='FULL_CI_VERIFIED_NOT_ADMITTED' if require_full else 'BUILD_CI_VERIFIED_NOT_ADMITTED',
        fullCiRequired=require_full, source=source, workflow=run['path'],
        runId=run['id'], attempt=run['run_attempt'], jobs=len(rows),
        jobSha256=digest(encoded(sorted((job_key(row) for row in rows), key=lambda r:r['id']))),
        contractSha256=digest(encoded(shape)), sourceFiles=hashes, paidAdmission=False, fullRemoteQualification=False)


def observe(source, shape, get, wall, *, require_full=True):
    a.hex_value(source, 40)
    before = get('branches/master')['commit']['sha']; need(before == source, 'V5.2 source is not current master')
    listings = listing(get, source,require_full=require_full); selected = latest(listings, source,require_full=require_full)
    run = get('actions/runs/'+str(selected['id']))
    run_identity(run, source,green=require_full,allow_unfinished=not require_full,allow_standalone=not require_full)
    need(encoded(admission_run_key(selected,require_full)) == encoded(admission_run_key(run,require_full)), 'V5.2 CI selection changed')
    attempt = get(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}")
    rows = jobs(get, run)
    contents = {name: get('contents/'+name+'?ref='+source) for name in SOURCE_FILES}
    rows_after = jobs(get, run); run_after = get('actions/runs/'+str(run['id']))
    listings_after = listing(get, source,require_full=require_full); after = get('branches/master')['commit']['sha']
    value = dict(schema=SCHEMA, source=source, masterBefore=before, masterAfter=after,
        run=run, runAttempt=attempt, runAfter=run_after, runsBefore=listings, runsAfter=listings_after,
        jobs=rows, jobsAfter=rows_after, sourceContents=contents)
    validate(value, source, shape, int(wall()),require_full=require_full); return value
