"""Exact-master, exact-attempt GitHub CI observations; no dispatch or mutation."""
import base64
from datetime import datetime
from pathlib import Path
import re
import subprocess
from . import cloud_authority as a, performance_model as m

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'patricklfdm/GeneralSearchEngine'
REPOSITORY_ID = 1341513206
OWNER_ID = 147357093
WORKFLOW = '.github/workflows/ci.yml'
CONFIG_PATH = 'docs/v5x/v5.1/phase6-preflight-config.json'
OWNED_JOB = 'V5.1 owned experiment (no GCP)'
OWNED_STEP = 'Qualify V5.1 owned complete experiment history and backup restore without GCP'
SHARDS = ('published-controls', 'automatic-healthy', 'automatic-concurrent')
CANONICAL_TAPES = (
    ('v44-healthy', 'published-v4.4-local', 'healthy'),
    ('v50-healthy', 'published-v5.0-configured', 'healthy'),
    ('automatic-healthy', 'candidate-v5.1-automatic', 'healthy'),
    ('automatic-read-heavy', 'candidate-v5.1-automatic', 'read-heavy'),
    ('automatic-sustained', 'candidate-v5.1-automatic', 'sustained'),
)


def expected_jobs(text):
    """Closed parser for this repository's explicit names and reviewed matrices."""
    blocks = re.split(r'^  ([\w-]+):\n', text.split('\njobs:\n', 1)[1], flags=re.M)
    result = []
    for key, body in zip(blocks[1::2], blocks[2::2]):
        names = re.findall(r'^    name: (.+)$', body, re.M)
        m.need(len(names) == 1, 'CI explicit job name')
        name = names[0]
        if key == 'v51-remote-rich-shards':
            m.need(name == 'V5.1 rich workload (${{ matrix.shard }}, no GCP)' and
                   re.findall(r'^        shard: \[(.+)\]$', body, re.M) == [', '.join(SHARDS)], 'CI rich matrix changed')
            result.extend(name.replace('${{ matrix.shard }}', shard) for shard in SHARDS)
        elif key == 'v51-owned-canonical-tapes':
            expected='      fail-fast: false\n      matrix:\n        include:\n'+''.join(
                f'          - tape: {tape}\n            mode: {mode}\n            cell: {cell}\n'
                for tape,mode,cell in CANONICAL_TAPES)
            strategy=re.findall(r'^    strategy:\n(.*?)^    env:\n',body,re.M|re.S)
            m.need(name=='V5.1 owned canonical tape (${{ matrix.tape }}, no GCP)' and strategy==[expected],
                   'CI owned canonical matrix changed')
            result.extend(name.replace('${{ matrix.tape }}',tape) for tape,_,_ in CANONICAL_TAPES)
        else:
            m.need('${{' not in name and '    strategy:' not in body, 'unreviewed CI matrix')
            result.append(name)
    m.need(len(result) == len(set(result)) and OWNED_JOB in result and 'Required' in result, 'CI job inventory')
    return result


def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    m.need(dt.tzinfo is not None, 'GitHub timestamp zone')
    return int(dt.timestamp())


def check(value, source, now, workflow):
    a.digest(source, 40); a.integer(now, 1)
    m.need(value['masterBefore'] == value['masterAfter'] == source, 'master moved or source is not master')
    run = value['run']; after = value['runAfter']
    keys = ('id', 'run_attempt', 'head_sha', 'head_branch', 'event', 'path', 'status', 'conclusion')
    m.need(all(run[k] == after[k] for k in keys), 'CI changed during observation')
    a.integer(run['id'], 1); a.integer(run['run_attempt'], 1)
    m.need(all(r['repository']['id'] == REPOSITORY_ID and r['repository']['full_name'] == REPOSITORY and
               r['repository']['owner']['id'] == OWNER_ID for r in (run, after)), 'CI repository identity')
    m.need(run['head_sha'] == source and run['head_branch'] == 'master' and run['event'] in ('push', 'workflow_dispatch') and
           run['path'] == WORKFLOW and run['status'] == 'completed' and run['conclusion'] == 'success', 'exact-source CI not green')
    m.need(value['workflowSha256'] == m.sha(workflow.encode()), 'CI workflow bytes changed')
    jobs = value['jobs']; wanted = expected_jobs(workflow)
    m.need(len(jobs) == len(wanted) and sorted(j['name'] for j in jobs) == sorted(wanted), 'CI missing/duplicate jobs')
    m.need(len({j['id'] for j in jobs}) == len(jobs), 'CI duplicate job ID')
    for job in jobs:
        m.need(job['run_id'] == run['id'] and job['run_attempt'] == run['run_attempt'] and job['head_sha'] == source and
               job['status'] == 'completed' and job['conclusion'] == 'success', 'CI skipped/failed/wrong-attempt job')
        m.need(0 < timestamp(job['started_at']) <= timestamp(job['completed_at']) <= now, 'CI job time')
    job = next(j for j in jobs if j['name'] == OWNED_JOB)
    steps = [s for s in job['steps'] if s['name'] == OWNED_STEP]
    m.need(len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success' and
           timestamp(job['started_at']) <= timestamp(steps[0]['started_at']) <= timestamp(steps[0]['completed_at']) <= timestamp(job['completed_at']),
           'owned complete experiment did not execute')
    return dict(runId=run['id'], attempt=run['run_attempt'], jobs=len(jobs), ownedExperiment=True,
                fullRemoteQualification=False, url=f'https://github.com/{REPOSITORY}/actions/runs/{run["id"]}')


def github(path):
    m.need(isinstance(path, str) and not path.startswith('/') and '..' not in path, 'GitHub read path')
    result = subprocess.run(['gh', 'api', '--method', 'GET', 'repos/'+REPOSITORY+'/'+path], capture_output=True, timeout=30)
    m.need(result.returncode == 0 and len(result.stdout) <= 16 << 20, 'GitHub read failed or oversized')
    return m.strict_json(result.stdout)


def collect(source, get=github):
    a.digest(source, 40)
    before = get('branches/master')['commit']['sha']
    def latest():
        runs = get('actions/workflows/ci.yml/runs?branch=master&head_sha='+source+'&per_page=100')['workflow_runs']
        m.need(type(runs) is list and len(runs) <= 100, 'CI run listing bound')
        candidates = [r for r in runs if r['head_sha'] == source and r['head_branch'] == 'master' and
                      r['event'] in ('push', 'workflow_dispatch') and r['path'] == WORKFLOW]
        m.need(candidates, 'no exact-master CI run')
        # Include pending/failed reruns; never cherry-pick green history.
        return max(candidates, key=lambda r: r['id'])
    selected = latest()
    run = get('actions/runs/'+str(selected['id'])); a.integer(run['run_attempt'], 1)
    jobs = []; total = None
    for page in range(1, 4):
        response = get(f'actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs?per_page=100&page={page}')
        count = response['total_count']; a.integer(count, 1, 300)
        m.need(total is None or total == count, 'CI pagination changed'); total = count
        m.need(response['jobs'] and len(response['jobs']) <= 100, 'CI pagination truncated')
        jobs.extend(response['jobs'])
        if len(jobs) >= total:break
    m.need(len(jobs) == total, 'CI pagination count')
    def contents(path):
        content = get('contents/'+path+'?ref='+source)
        m.need(content['encoding'] == 'base64' and 0 < content['size'] <= 256 << 10, 'source content')
        raw = base64.b64decode(content['content'].replace('\n', ''), validate=True)
        m.need(len(raw) == content['size'], 'source content byte count')
        return raw
    raw = contents(WORKFLOW)
    configuration_sha = m.sha(m.canonical(m.strict_json(contents(CONFIG_PATH))))
    m.need(latest()['id'] == selected['id'], 'new CI run appeared during observation')
    return dict(masterBefore=before, masterAfter=get('branches/master')['commit']['sha'], run=run,
                runAfter=get('actions/runs/'+str(run['id'])), jobs=jobs, workflowSha256=m.sha(raw), configurationSha256=configuration_sha)
