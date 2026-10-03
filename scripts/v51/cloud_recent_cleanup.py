"""Read-only, exact-attempt cleanup evidence. Manual is sufficient; no dispatch.

GitHub metadata and the downloaded archive are retained for independent replay.
A recent PASS is an observation, not paid admission or a deletion/IAM audit.
"""
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time
import zipfile
from . import cloud_authority as a, cloud_native_authority as n, cloud_ci as ci
from . import cloud_cleanup_entry as entry, cloud_cleanup_observation as observation
from . import cloud_permissions as permissions, cloud_preflight as preflight, performance_model as m
from .remote_command import read, write_once

MAX_ARCHIVE = 8 << 20
FILES = ('identity/binding.json', 'reconciliation/binding.json', 'reconciliation/receipt.json',
         'permissions/binding.json', 'permissions/observations.json', 'permissions/receipt.json')


def context(cfg, source, trigger, run):
    a.digest(source, 40); m.need(trigger in entry.TRIGGERS, 'cleanup trigger')
    a.integer(run['id'], 1); a.integer(run['run_attempt'], 1)
    chosen = entry.identities.proposal(cfg)['identities'][trigger]
    return dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=ci.REPOSITORY,
                GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID), GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),
                GITHUB_EVENT_NAME=chosen['claims']['event_name'], GITHUB_REF='refs/heads/master',
                GITHUB_WORKFLOW_REF=chosen['claims']['workflow_ref'], GITHUB_WORKFLOW_SHA=source,
                GITHUB_SHA=source, GITHUB_JOB='cleanup', CLEANUP_ENVIRONMENT=chosen['environment'],
                GITHUB_RUN_ID=str(run['id']), GITHUB_RUN_ATTEMPT=str(run['run_attempt']))


def latest(value, source):
    rows = value['workflow_runs']
    m.need(type(rows) is list and value['total_count'] == len(rows) and 0 < len(rows) <= 100,
           'no complete exact-source cleanup inventory; run manual cleanup on this master source')
    m.need(all(r['head_sha'] == source for r in rows), 'cleanup source inventory')
    m.need(len({a.integer(r['id'], 1) for r in rows}) == len(rows), 'duplicate cleanup runs')
    # Never search backwards for a green run when a newer run failed/is waiting.
    return max(rows, key=lambda row: row['id'])


def artifact_check(value, binding):
    a.integer(value['id'], 1); a.integer(value['size_in_bytes'], 1, MAX_ARCHIVE)
    expected = f"v51-cleanup-{binding['trigger']}-{binding['runId']}-{binding['runAttempt']}"
    m.need(value['name'] == expected and value['expired'] is False, 'cleanup artifact name/expiry')
    run = value['workflow_run']
    m.need(run['id'] == binding['runId'] and run['head_sha'] == binding['source'] and run['head_branch'] == 'master' and
           run['repository_id'] == run['head_repository_id'] == ci.REPOSITORY_ID, 'cleanup artifact source/run')
    digest = value['digest']; m.need(isinstance(digest, str) and digest.startswith('sha256:'), 'cleanup artifact digest missing')
    a.digest(digest[7:]); return digest[7:]


def download(artifact_id, path):
    a.integer(artifact_id, 1)
    # Fixed repository/API path, no user URL, shell or external credentials.
    with Path(path).open('xb') as output:
        result = subprocess.run(['gh', 'api', '--method', 'GET',
            f'repos/{ci.REPOSITORY}/actions/artifacts/{artifact_id}/zip'], stdout=output,
            stderr=subprocess.DEVNULL, timeout=60)
    m.need(result.returncode == 0, 'cleanup artifact download failed')


def contents(path, expected_sha):
    path = Path(path); m.need(0 < path.stat().st_size <= MAX_ARCHIVE, 'cleanup archive size')
    m.need(m.sha(path.read_bytes()) == expected_sha, 'cleanup archive digest mismatch')
    with zipfile.ZipFile(path) as archive:
        rows = archive.infolist(); names = [r.filename for r in rows]
        m.need(len(rows) <= 100 and len(names) == len(set(names)) and
               sum(r.file_size for r in rows) <= MAX_ARCHIVE, 'cleanup archive inventory/bound')
        for row in rows:
            name = PurePosixPath(row.filename); mode = row.external_attr >> 16
            m.need(not name.is_absolute() and '..' not in name.parts and '\\' not in row.filename and
                   row.filename == name.as_posix() and not stat.S_ISLNK(mode) and not row.flag_bits & 1,
                   'unsafe cleanup archive member')
        m.need(set(FILES) <= set(names), 'cleanup archive missing evidence')
        # Do not extract arbitrary archive paths. Only parse bounded required JSON.
        return {name: m.strict_json(archive.read(name)) for name in FILES}


def validate(cfg, source, value, archive, *, now):
    a.integer(now, 1)
    m.need(value['schema'] == 'gse-v51-recent-cleanup-v1' and value['source'] == source and
           value['configurationSha256'] == preflight.configuration(cfg) and 'failure' not in value, 'cleanup observation scope/collection')
    a.integer(value['startedAt'], 1); a.integer(value['completedAt'], 1)
    m.need(now-900 < value['startedAt'] <= value['completedAt'] <= now, 'cleanup observations stale/future')
    before = latest(value['runsBefore'], source); after = latest(value['runsAfter'], source)
    m.need((before['id'], before['run_attempt']) == (after['id'], after['run_attempt']), 'cleanup changed during collection')
    trigger = value['trigger']; env = context(cfg, source, trigger, before)
    binding = entry.identity(cfg, env, trigger=trigger, source=source, checkout=source)
    for run in (before, after): observation.completed_run(binding, run)
    start, end = observation.check_run(binding, value['run'])
    m.need(0 < start <= end <= value['startedAt'] and now-7200 < end, 'cleanup completion stale/future')
    digest = artifact_check(value['artifact'], binding)
    m.need(Path(archive).stat().st_size == value['artifact']['size_in_bytes'], 'cleanup artifact size mismatch')
    files = contents(archive, digest)
    m.need(files['identity/binding.json'] == files['reconciliation/binding.json'] == binding, 'cleanup artifact binding')
    receipt = files['reconciliation/receipt.json']; a.integer(receipt['checkedAt'], 1)
    m.need(start <= receipt['checkedAt'] <= end and all(receipt.get(k) == v for k, v in binding.items()) and
           receipt['status'] == 'PASS' and receipt['execution'] == 'gcp-native-cleanup-entry' and
           receipt['credentialExchangeCompleted'] is True and receipt['effectiveIamQualified'] is False and
           'failure' not in receipt, 'cleanup receipt not native PASS')
    inner = receipt['reconciliation']
    m.need(inner['trigger'] == trigger and inner['execution'] == n.CLEANUP_EXECUTION and
           inner['status'] == 'PASS' and 'failure' not in inner, 'cleanup reconciliation failed/offline')
    if inner.get('activeLease') is not False:
        outcome = inner['cleanup']
        m.need(inner['leaseReleased'] is True and outcome['status'] == 'PASS' and
               outcome['errors'] == outcome['leftovers'] == [], 'cleanup release/absence failed')
        checks = outcome['checks']; m.need(type(checks) is list, 'cleanup absence checks')
        m.need(all(v['absent'] is True and v['observed'] is None for v in checks), 'cleanup resource remains')
    pb = permissions.identity(cfg, env, role=trigger, source=source, checkout=source)
    obs = files['permissions/observations.json']; pr = files['permissions/receipt.json']
    m.need(files['permissions/binding.json'] == pb and
           start <= obs['startedAt'] <= obs['completedAt'] <= pr['observedAt'] <= receipt['checkedAt'],
           'cleanup permissions outside original run')
    m.need(pr == permissions.evaluate(cfg, pb, obs, now=pr['observedAt']) and pr['status'] == 'PRECHECK_PASS' and
           pr['execution'] == 'workflow-permission-probes', 'cleanup permissions incomplete/offline')
    return dict(status='PASS', detail=dict(trigger=trigger, runId=binding['runId'], runAttempt=binding['runAttempt'],
                completedAt=end, expiresAt=min(value['startedAt']+900,end+7200),
                artifactId=value['artifact']['id'], artifactSha256=digest,
                scheduleRequired=False, paidAdmission=False, fullRemoteQualification=False))


def check_saved(cfg, source, output, *, now):
    try:
        root = Path(output)
        return validate(cfg, source, read(root/'observations.json'), root/'cleanup.zip', now=now)
    except Exception as error:
        # No API/auth exception text. Missing/failed collection remains actionable.
        reason = (str(error)[:180] if isinstance(error, ValueError) else 'missing or invalid retained cleanup evidence')
        return dict(status='BLOCKED', reason=reason+'; complete a recent manual PASS on the exact master source')


def collect(cfg, source, output, *, trigger='manual', get=ci.github, fetch=download, wall=time.time):
    a.digest(source, 40); m.need(trigger in entry.TRIGGERS, 'cleanup trigger')
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    value = dict(schema='gse-v51-recent-cleanup-v1', source=source, trigger=trigger,
                 configurationSha256=preflight.configuration(cfg), startedAt=int(wall()))
    try:
        workflow = 'v51-manual-cleanup.yml' if trigger == 'manual' else 'v51-expired-cleanup.yml'
        path = f'actions/workflows/{workflow}/runs?branch=master&head_sha={source}&per_page=100'
        value['runsBefore'] = get(path); run = latest(value['runsBefore'], source)
        env = context(cfg, source, trigger, run)
        binding = entry.identity(cfg, env, trigger=trigger, source=source, checkout=source)
        observation.completed_run(binding, run)
        value['run'] = observation.collect_run(binding, get); observation.check_run(binding, value['run'])
        rows = get(f"actions/runs/{run['id']}/artifacts?per_page=100")
        m.need(rows['total_count'] == len(rows['artifacts']) <= 100, 'cleanup artifacts incomplete')
        name = f"v51-cleanup-{trigger}-{run['id']}-{run['run_attempt']}"
        matches = [r for r in rows['artifacts'] if r['name'] == name]
        m.need(len(matches) == 1, 'cleanup attempt artifact missing/duplicate')
        value['artifact'] = matches[0]; artifact_check(matches[0], binding)
        fetch(matches[0]['id'], root/'cleanup.zip')
        m.need(get(f"actions/artifacts/{matches[0]['id']}") == matches[0], 'cleanup artifact changed during download')
        value['runsAfter'] = get(path)
        # The latest-run endpoint is checked again after download as well.
        value['run']['after'] = get(f"actions/runs/{run['id']}")
    except Exception as error:
        value['failure'] = dict(type=type(error).__name__)
    value['completedAt'] = int(wall()); write_once(root/'observations.json', value)
    result = check_saved(cfg, source, root, now=int(wall()))
    write_once(root/'check.json', result)
    return result
