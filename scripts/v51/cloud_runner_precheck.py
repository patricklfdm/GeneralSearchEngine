"""Same-run observer evidence gate for optional runner permission diagnostics.

This module emits an identity or a diagnostic receipt, never a paid request.
No resource, control-object or IAM mutation is available here.
"""
import argparse
import html
import os
from pathlib import Path
import subprocess
import time
from . import cloud_authority as a, cloud_ci as ci, cloud_preflight as p
from . import cloud_permissions as permissions, cloud_cleanup_entry as entry, performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-runner-precheck-v1'
OBSERVER_STEPS = ('Collect exact-source CI and owned experiment status',
                  'Collect recent manual cleanup evidence (schedule optional)',
                  'Check actual observer permissions without cloud mutations',
                  'Report all readiness checks and remaining admission requirements',
                  'Retain observations including blocked admission')


def identity(cfg, env, source, checkout):
    m.need(env.get('RUNNER_PERMISSION_PRECHECK') == 'true', 'runner permission precheck must be explicitly selected')
    return permissions.identity(cfg, env, role='runner', source=source, checkout=checkout)


def observer_job(binding, value, *, now):
    jobs = value['jobs']; a.integer(value['total_count'], 1, 100)
    m.need(len(jobs) == value['total_count'], 'runner precheck job inventory incomplete')
    rows = [job for job in jobs if job['name'] == 'observations']
    m.need(len(rows) == 1, 'same-run observer job missing/duplicate')
    job = rows[0]
    m.need(job['run_id'] == binding['runId'] and job['run_attempt'] == binding['runAttempt'] and
           job['head_sha'] == binding['source'] and job['status'] == 'completed' and job['conclusion'] == 'success',
           'same-run observer job not successful')
    for name in OBSERVER_STEPS:
        steps = [v for v in job['steps'] if v['name'] == name]
        m.need(len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success',
               'observer prerequisite missing/skipped/failed')
    start, end = ci.timestamp(job['started_at']), ci.timestamp(job['completed_at'])
    m.need(0 < start <= end <= now, 'observer job time')
    return start, end


def prerequisites(cfg, env, binding, path, jobs, *, now):
    """Reject old attempts and forged/stale reports; replay original raw evidence."""
    root = Path(path); source = binding['source']; receipt = read(root/'preflight.json')
    start, end = observer_job(binding, jobs, now=now)
    a.integer(receipt['observedAt'], 1); a.integer(receipt['expiresAt'], 1)
    m.need(receipt['source'] == source and start <= receipt['observedAt'] <= end and
           receipt['observedAt'] <= now < receipt['expiresAt'], 'same-run observer evidence expired or wrong source')
    observer_env = dict(env, GITHUB_JOB='observations')
    original = p.report(cfg, source, root, observer_env, now=receipt['observedAt'])
    m.need(original == receipt and receipt['status'] == 'OBSERVATIONS_READY' and
           receipt['execution'] == 'read-only-provider-observations', 'observer receipt changed, blocked or offline')
    fresh = p.report(cfg, source, root, observer_env, now=now)
    m.need(fresh['status'] == 'OBSERVATIONS_READY', 'observer observations expired or blocked')
    return dict(preflightSha256=m.sha(m.canonical(receipt)), expiresAt=min(receipt['expiresAt'], fresh['expiresAt']),
                cleanup=fresh['checks']['recentCleanup']['detail'], source=source,
                runId=binding['runId'], runAttempt=binding['runAttempt'])


def collect_jobs(binding, get=ci.github):
    entry.collect_run(binding, get)
    jobs = get(f"actions/runs/{binding['runId']}/attempts/{binding['runAttempt']}/jobs?per_page=100")
    entry.collect_run(binding, get)
    return jobs


def bind(cfg, env, source, checkout, preflight, output, *, get=ci.github, wall=time.time):
    binding = identity(cfg, env, source, checkout)
    jobs = collect_jobs(binding, get)
    admitted = prerequisites(cfg, env, binding, preflight, jobs, now=int(wall()))
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_once(output/'binding.json', binding); write_once(output/'observer-jobs.json', jobs)
    value = dict(schema=SCHEMA, status='BOUND', binding=binding, prerequisites=admitted,
                 **permissions.BOUNDARY)
    write_once(output/'receipt.json', value)
    return value


def finish(cfg, env, source, checkout, preflight, root, *, get=ci.github, wall=time.time):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    value = dict(schema=SCHEMA, source=source, status='BLOCKED', execution='runner-permission-diagnostics',
                 **permissions.BOUNDARY)
    phase = 'identity'
    try:
        binding = identity(cfg, env, source, checkout); value['binding'] = binding
        bound = read(root/'identity/receipt.json')
        m.need(bound['schema'] == SCHEMA and bound['status'] == 'BOUND' and bound['binding'] == binding and
               read(root/'identity/binding.json') == binding and
               all(bound[k] is False for k in permissions.BOUNDARY), 'runner precheck binding changed/missing')
        phase = 'observer-preflight'; jobs = collect_jobs(binding, get)
        admitted = prerequisites(cfg, env, binding, preflight, jobs, now=int(wall()))
        m.need(admitted == bound['prerequisites'], 'runner precheck prerequisites changed')
        phase = 'runner-permissions'
        permission = permissions.check_saved(cfg, binding, root/'permissions', now=int(wall()))
        entry.collect_run(binding, get)
        m.need(int(wall()) < admitted['expiresAt'], 'runner precheck completed after original evidence expiry')
        value.update(status='PRECHECK_PASS', prerequisites=admitted, permission=permission)
    except Exception as error:
        value['failure'] = dict(phase=phase, type=type(error).__name__)
    value['checkedAt'] = int(wall()); write_once(root/'receipt.json', value)
    (root/'summary.md').write_text(summary(value))
    return value


def summary(value):
    def safe(v):return html.escape(str(v)).replace('|', '&#124;').replace('\n', ' ')
    binding = value.get('binding', {}); before = value.get('prerequisites', {})
    rows = [('Status', value['status']), ('Source', value['source']),
            *[(k, binding[k]) for k in ('runId','runAttempt','serviceAccount','provider','environment') if k in binding],
            ('Observer preflight SHA-256', before.get('preflightSha256','unavailable')),
            ('Evidence expires (UTC epoch)', before.get('expiresAt','unavailable')),
            ('Manual cleanup', before.get('cleanup', {}).get('runId','unavailable')),
            ('Failure', value.get('failure','none')), ('Paid admission', False)]
    return '# V5.1 runner permission precheck\n\n| Parameter | Value |\n| --- | --- |\n'+\
        ''.join('| '+safe(k)+' | '+safe(v)+' |\n' for k,v in rows)+\
        '\nDiagnostic project/bucket queries only. Object conditions, resource/IAP access, native workload integration, retention and exact paid approval remain required. Schedule is optional.\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('identity','report'))
    parser.add_argument('--source',required=True);parser.add_argument('--preflight',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--github-step-summary',type=Path)
    args = parser.parse_args();cfg = read(p.CONFIG)
    checkout = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
    if args.action == 'identity':
        value = bind(cfg,os.environ,args.source,checkout,args.preflight,args.output)
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:
            for key in ('provider','serviceAccount'):out.write(key+'='+value['binding'][key]+'\n')
    else:
        value = finish(cfg,os.environ,args.source,checkout,args.preflight,args.output)
        if args.github_step_summary:
            with args.github_step_summary.open('a') as out:out.write(summary(value))
        print(m.canonical(dict(status=value['status'],failure=value.get('failure'),paidAdmission=False)).decode())
        if value['status'] != 'PRECHECK_PASS':raise SystemExit(2)


if __name__ == '__main__':main()
