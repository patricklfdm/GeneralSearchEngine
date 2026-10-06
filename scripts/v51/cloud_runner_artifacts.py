"""Authenticate original exact-CI build and experiment-package artifacts.

GitHub reads and local bounded unpacking only; packaged programs are not run.
Metadata, original ZIP bytes and the checked package remain independently replayable.
"""
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile
from scripts import ci_v51_bundle as build
from . import cloud_authority as a, cloud_ci as ci, cloud_package as package
from . import cloud_workload_contract as workload, cloud_recent_cleanup as recent
from . import performance_model as m, remote_command as c

MAX_BYTES = 288 << 20
JOBS = {'build': 'V5.1 verification build', 'package': ci.OWNED_JOB}
STEPS = {'build': 'Create exact-source V5.1 verification bundle',
         'package': 'Build and relocate the V5.1 guest package without GCP'}


def name(kind, run):
    return (f"v51-verification-build-{run['head_sha']}-attempt-{run['run_attempt']}" if kind == 'build' else
            f"v51-experiment-package-{run['head_sha']}")


def producing_attempt(value, run):
    match = re.fullmatch(r'v51-verification-build-'+run['head_sha']+r'-attempt-([1-9][0-9]{0,5})', value['name'])
    m.need(match is not None, 'Runner build artifact name')
    return a.integer(int(match[1]), 1, run['run_attempt'])


def check_build_job(value, record, github):
    """Bind the original execution, including GitHub's carried check-run copy."""
    attempt = producing_attempt(record, github['run'])
    jobs = [j for j in github['jobs'] if j['name'] == JOBS['build']]
    m.need(len(jobs) == 1 and value['run_attempt'] == attempt, 'Runner build producing attempt')
    fields = ('name','run_id','head_sha','started_at','completed_at','status','conclusion','steps')
    m.need(all(value[k] == jobs[0][k] for k in fields), 'Runner build producing job changed')
    a.integer(value['id'], 1); current = jobs[0]
    if value['id'] != current['id']:
        # GitHub may allocate a new check-run ID for a carried successful job.
        # Its creation follows the already completed original execution; a new
        # execution has new start/end/step times and cannot satisfy this binding.
        m.need(attempt < github['run']['run_attempt'] and value.get('created_at') and current.get('created_at') and
               type(value.get('runner_id')) is int and value['runner_id'] > 0 and
               value['runner_id'] == current.get('runner_id') and value.get('runner_name') and
               value['runner_name'] == current.get('runner_name') and
               ci.timestamp(value['created_at']) <= ci.timestamp(value['started_at']) and
               ci.timestamp(current['created_at']) >= ci.timestamp(value['completed_at']), 'Runner build producing job changed')
    return value


def collect_build_job(record, github, get):
    run = github['run']; attempt = producing_attempt(record, run); rows = []; total = None
    for page in range(1, 4):
        value = get(f"actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100&page={page}")
        count = a.integer(value['total_count'], 1, 300)
        m.need(total in (None, count) and 0 < len(value['jobs']) <= 100, 'Runner producing job pagination'); total = count
        rows.extend(value['jobs'])
        if len(rows) >= total: break
    m.need(len(rows) == total and len({v['id'] for v in rows}) == total, 'Runner producing job inventory')
    selected = [v for v in rows if v['name'] == JOBS['build']]
    m.need(len(selected) == 1, 'Runner original producing job missing/duplicate')
    return check_build_job(selected[0], record, github)


def metadata(kind, value, github):
    run = github['run']; a.integer(value['id'], 1); a.integer(value['size_in_bytes'], 1, MAX_BYTES)
    if kind == 'build': producing_attempt(value, run)
    else: m.need(value['name'] == name(kind, run), 'Runner artifact name')
    m.need(value['expired'] is False, 'Runner artifact expiry')
    origin = value['workflow_run']
    m.need(origin['id'] == run['id'] and origin['head_sha'] == run['head_sha'] and origin['head_branch'] == 'master' and
           origin['repository_id'] == origin['head_repository_id'] == ci.REPOSITORY_ID, 'Runner artifact origin')
    jobs = [j for j in github['jobs'] if j['name'] == JOBS[kind]]
    m.need(len(jobs) == 1, 'Runner artifact producing job'); job = jobs[0]
    m.need(job['run_id'] == run['id'] and job['run_attempt'] == run['run_attempt'] and
           job['head_sha'] == run['head_sha'] and job['status'] == 'completed' and job['conclusion'] == 'success',
           'Runner artifact producing attempt')
    steps = [s for s in job['steps'] if s['name'] == STEPS[kind]]
    m.need(len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success', 'Runner artifact build step')
    m.need(ci.timestamp(job['started_at']) <= ci.timestamp(steps[0]['started_at']) <=
           ci.timestamp(steps[0]['completed_at']) <= ci.timestamp(value['created_at']) <=
           ci.timestamp(value['updated_at']) <= ci.timestamp(job['completed_at']), 'Runner artifact outside producing job')
    digest = value['digest']
    m.need(type(digest) is str and digest.startswith('sha256:'), 'Runner artifact missing digest')
    return a.digest(digest[7:])


def files(path, record, github, kind):
    path = Path(path)
    m.need(path.is_file() and not path.is_symlink() and path.stat().st_size == record['size_in_bytes'] <= MAX_BYTES,
           'Runner original archive size/type')
    m.need(m.sha(path.read_bytes()) == metadata(kind, record, github), 'Runner original ZIP digest')
    wanted = {'manifest.json', 'build.tar.gz'} if kind == 'build' else {'guest.tar.gz', 'receipt.json', 'package/manifest.json'}
    with zipfile.ZipFile(path) as archive:
        rows = archive.infolist(); names = [v.filename for v in rows]
        m.need(0 < len(rows) <= 10000 and len(names) == len(set(names)) and
               sum(v.file_size for v in rows) <= MAX_BYTES and not any(n.endswith('failure.json') for n in names),
               'Runner artifact inventory/failure')
        for row in rows:
            raw = row.filename[:-1] if row.is_dir() else row.filename
            p = PurePosixPath(raw); mode = row.external_attr >> 16
            m.need(row.orig_filename == row.filename and raw == p.as_posix() and raw not in ('', '.') and not p.is_absolute() and '..' not in p.parts and
                   '\\' not in raw and not stat.S_ISLNK(mode) and not row.flag_bits & 1 and
                   (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)), 'Runner unsafe ZIP member')
        m.need(wanted <= set(names), 'Runner artifact required file missing')
        for key in wanted:
            m.need(not archive.getinfo(key).is_dir() and archive.getinfo(key).file_size <=
                   (package.MAX_BYTES if key.endswith('.tar.gz') else 4 << 20), 'Runner artifact member bound')
        return {key: archive.read(key) for key in wanted}


def verify(root, github, binding, *, controls=None):
    """Replay original metadata/ZIPs against a separately trusted checkout binding."""
    root = Path(root); records = c.read(root/'artifacts.json'); source = binding['source']
    m.need(set(records) == {'build', 'package'} and github['run']['head_sha'] == source, 'Runner artifacts source/inventory')
    bf = files(root/'build.zip', records['build'], github, 'build')
    origin = check_build_job(c.read(root/'build-job.json'), records['build'], github)
    pf = files(root/'package.zip', records['package'], github, 'package')
    bm = m.strict_json(bf['manifest.json']); receipt = m.strict_json(pf['receipt.json'])
    env = workload.load()['environment']
    m.need(bm['schema'] == build.SCHEMA and bm['binding'] == binding and
           bm['archiveSha256'] == m.sha(bf['build.tar.gz']) and
           binding['java'] == {'java.vendor': env['javaVendor'], 'java.runtime.version': env['javaRuntime']},
           'Runner original build/source/toolchain mismatch')
    a.digest(binding['checkoutSha256']); a.digest(source, 40)
    m.need(receipt['schema'] == 'gse-v51-guest-build-v1' and receipt['status'] == 'PASS' and receipt['dirty'] is False and
           receipt['source'] == source and receipt['buildManifestSha256'] == m.sha(bf['manifest.json']) and
           receipt['archiveSha256'] == m.sha(pf['guest.tar.gz']) and receipt['archiveBytes'] == len(pf['guest.tar.gz']) and
           receipt['checks'] == [dict(mode=mode, status='PASS') for mode in package.MODES] and
           all(receipt[k] is False for k in ('paidCloud', 'fullRemoteQualification', 'engineWorkloadExecuted')), 'Runner package receipt')
    # Authenticate the whole tar before parsing it. Execute neither its verifier
    # nor its Java launcher; use the source-controlled verifier in this checkout.
    with tempfile.TemporaryDirectory(prefix='v51-admission-package-') as temporary:
        tmp = Path(temporary); archive = tmp/'guest.tar.gz'; archive.write_bytes(pf['guest.tar.gz'])
        unpacked = tmp/'package'; manifest = package.unpack(archive, unpacked, receipt['archiveSha256'], source)
        m.need((unpacked/'manifest.json').read_bytes() == pf['package/manifest.json'] and
               (unpacked/'ci-build-manifest.json').read_bytes() == bf['manifest.json'], 'Runner package original manifest mismatch')
        m.need(manifest['dirty'] is False and manifest['buildBinding'] == binding and
               manifest['jvmArguments'] == env['jvmArguments'] and receipt['payloadFiles'] == len(manifest['files']) and
               receipt['payloadBytes'] == sum(v['size'] for v in manifest['files']), 'Runner package payload profile')
        workload.validate(package.read(unpacked/'workload.json'))
        pins = c.read(ci.ROOT/'docs/v5x/v5.1/published-controls.json') if controls is None else controls
        m.need(package.read(unpacked/'published-controls.json') == pins,
               'Runner published controls changed')
    return dict(schema='gse-v51-runner-artifacts-v1', source=source, ciRun=github['run']['id'], ciAttempt=github['run']['run_attempt'],
        artifacts={k: dict(id=v['id'], sha256=metadata(k, v, github)) for k, v in records.items()}, buildBinding=binding,
        buildProducer=dict(attempt=origin['run_attempt'], jobId=origin['id'],
                           acceptedJobId=next(j['id'] for j in github['jobs'] if j['name'] == JOBS['build'])),
        buildManifestSha256=m.sha(bf['manifest.json']), packageManifestSha256=m.sha(pf['package/manifest.json']),
        archiveSha256=receipt['archiveSha256'], workloadSha256=workload.PLAN_SHA256)


def collect(root, github, *, get=ci.github, fetch=recent.download):
    """Pin one artifact per producing attempt and recheck metadata after download."""
    root = Path(root); root.mkdir(parents=True, exist_ok=False)
    run = github['run']; rows = []; total = None
    for page in range(1, 5):
        result = get(f"actions/runs/{run['id']}/artifacts?per_page=100&page={page}")
        count = a.integer(result['total_count'], 1, 400)
        m.need(total in (None, count) and 0 < len(result['artifacts']) <= 100, 'Runner artifact pagination'); total = count
        rows.extend(result['artifacts'])
        if len(rows) >= total: break
    m.need(len(rows) == total and len({v['id'] for v in rows}) == total, 'Runner artifact listing incomplete/duplicate')
    records = {}
    for kind in JOBS:
        if kind == 'build':
            # Old artifacts from replaced jobs cannot be selected by a green
            # historical attempt. Only the currently accepted job's time window
            # is eligible, then its original attempt must prove the same execution.
            job = next(j for j in github['jobs'] if j['name'] == JOBS[kind])
            selected = [v for v in rows if v['name'].startswith('v51-verification-build-'+run['head_sha']+'-attempt-') and
                        ci.timestamp(job['started_at']) <= ci.timestamp(v['created_at']) <= ci.timestamp(job['completed_at'])]
        else: selected = [v for v in rows if v['name'] == name(kind, run)]
        m.need(len(selected) == 1, 'Runner attempt artifact missing/duplicate')
        record = selected[0]; metadata(kind, record, github); records[kind] = record
        fetch(record['id'], root/(kind+'.zip'))
        files(root/(kind+'.zip'), record, github, kind)
        m.need(get(f"actions/artifacts/{record['id']}") == record, 'Runner artifact changed during download')
    c.write_once(root/'artifacts.json', records)
    c.write_once(root/'build-job.json', collect_build_job(records['build'], github, get))
    return records
