"""V5.1 source and provider observations. No paid admission, writes or cleanup."""
import argparse
import html
import math
import os
from pathlib import Path
import subprocess
import time
from . import cloud_authority as a, cloud_ci as ci, cloud_gcp as gcp, cloud_http
from . import performance_model as m, remote_command as c

CONFIG = ci.ROOT/ci.CONFIG_PATH
PENDING = ('dedicated observer WIF and effective IAM review',
           'V5.1 runner/cleanup WIF, IAM and environment qualification',
           'recent exact-source scheduled or manual V5.1 cleanup with retained PASS reconciliation',
           'native cloud adapter and all preset workload qualification',
           'immutable evidence retention and full sequence price review',
           'exact-request paid confirmation and user-triggered execution')


def configuration(value):
    m.need(type(value) is dict and set(value) == {'schema', 'provider', 'projectNumber', 'observerServiceAccount', 'observerWifProvider'} and
           value['schema'] == 'gse-v51-preflight-config-v1', 'preflight configuration fields')
    gcp.config(value['provider']); gcp.numeric(value['projectNumber'])
    m.need(value['observerServiceAccount'] == 'gse-v51-observer@'+value['provider']['project']+'.iam.gserviceaccount.com' and
           value['observerWifProvider'] == 'projects/'+value['projectNumber']+'/locations/global/workloadIdentityPools/gse-v51-observer/providers/github',
           'dedicated V5.1 observer identity')
    return m.sha(m.canonical(value))


def identity(value, env):
    configuration(value)
    expected = dict(GITHUB_REPOSITORY=ci.REPOSITORY, GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),
                    GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID), GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_REF='refs/heads/master', GITHUB_WORKFLOW_REF=ci.REPOSITORY+'/'+a.RUNNER_WORKFLOW+'@refs/heads/master')
    m.need(all(env.get(k) == v for k, v in expected.items()), 'dedicated master preflight dispatch required')
    a.digest(env['GITHUB_SHA'], 40)
    return dict(provider=value['observerWifProvider'], serviceAccount=value['observerServiceAccount'])


def queries(cfg):
    configuration(cfg); p = cfg['provider']; base = 'https://compute.googleapis.com/compute/v1/projects/'+p['project']
    return dict(project=base, region=base+'/regions/'+p['region'], zone=base+'/zones/'+p['zone'],
                machine=base+'/zones/'+p['zone']+'/machineTypes/'+p['machineType'],
                image='https://compute.googleapis.com/compute/v1/projects/'+p['imageProject']+'/global/images/'+p['imageName'],
                subnetwork=base+'/regions/'+p['region']+'/subnetworks/'+p['subnetwork'],
                bucket='https://storage.googleapis.com/storage/v1/b/'+p['bucket'])


def principal():
    result = subprocess.run(['gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'], capture_output=True, timeout=30)
    m.need(result.returncode == 0 and len(result.stdout) <= 4096, 'observer account query failed')
    return result.stdout.decode().strip()


def collect_provider(cfg, *, api=None, who=principal, wall=time.time):
    configuration(cfg); api = api or cloud_http.Api(); started = int(wall()); deadline = api.clock()+300
    observed = {}
    def capture(name, call):
        try: observed[name] = call()
        except Exception as error:
            observed[name] = dict(error=type(error).__name__)  # Never retain credentials or response bodies from errors.
            if isinstance(error, cloud_http.ApiError):observed[name]['httpStatus'] = error.status
    capture('principal', who)
    for label, url in queries(cfg).items():
        capture(label, lambda url=url: api.call('GET', url, deadline=deadline, maximum=1 << 20))
    store = gcp.Store(cfg['provider'], api)
    for label, key in (('lease', a.LEASE), ('ledger', a.LEDGER)):
        capture(label, lambda key=key: store.get(key))
    return dict(execution='offline-preflight-fixture' if api.offline else 'read-only-provider-observations',
                configurationSha256=configuration(cfg), startedAt=started, completedAt=int(wall()), observations=observed)


def quota(rows, expected):
    m.need(type(rows) is list and len({r['metric'] for r in rows}) == len(rows), 'quota metric inventory')
    index = {r['metric']: r for r in rows}
    for name, needed in expected.items():
        row = index[name]; values = (row['limit'], row['usage'])
        m.need(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values) and
               values[0]-values[1] >= needed, 'insufficient '+name+' quota')


def check_provider(cfg, evidence):
    p = cfg['provider']; o = evidence['observations']; checks = {}
    dependencies = dict(observerIdentity=('principal',), image=('image',), topology=('project','zone','machine','subnetwork'),
                        quota=('region','project'), storagePolicy=('bucket',), controlState=('ledger','lease'))
    def check(name, fn):
        try:
            for label in dependencies[name]:
                value = o[label]
                if isinstance(value, dict) and 'error' in value:
                    raise ValueError(label+' query failed: '+str(value['error'])+'; HTTP '+str(value.get('httpStatus', 'unavailable')))
            detail = fn(); checks[name] = dict(status='PASS', detail=detail)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            checks[name] = dict(status='BLOCKED', reason=str(error)[:300])
    check('observerIdentity', lambda: m.need(o['principal'] == cfg['observerServiceAccount'], 'wrong/missing observer account'))
    def image():
        v = o['image']
        m.need(v['id'] == p['imageId'] and v['name'] == p['imageName'] and v['status'] == 'READY' and
               v['architecture'] == 'X86_64' and not v.get('deprecated'), 'frozen image identity/status/architecture changed')
        return dict(name=v['name'], id=v['id'])
    check('image', image)
    def topology():
        m.need(o['project']['name'] == p['project'] and str(o['project']['id']) == cfg['projectNumber'], 'project identity')
        m.need(o['zone']['name'] == p['zone'] and o['zone']['status'] == 'UP', 'zone identity/status')
        m.need(o['machine']['name'] == p['machineType'] and o['machine']['guestCpus'] == 8 and o['machine']['memoryMb'] == 32768, 'machine shape')
        base = 'https://compute.googleapis.com/compute/v1/projects/'+p['project']
        subnet = o['subnetwork']
        m.need(subnet['name'] == p['subnetwork'] and gcp.link(subnet['network']) == base+'/global/networks/'+p['network'] and
               gcp.link(subnet['region']) == base+'/regions/'+p['region'] and subnet['privateIpGoogleAccess'] is True, 'private subnet/provider access')
        return dict(voters=3, vcpus=24, diskGiB=450)
    check('topology', topology)
    def capacity():
        m.need(o['region']['name'] == p['region'], 'quota region identity')
        quota(o['region']['quotas'], {'N2_CPUS': 24, 'CPUS': 24, 'SSD_TOTAL_GB': 450})
        quota(o['project']['quotas'], {'CPUS_ALL_REGIONS': 24, 'FIREWALLS': 4})
        return dict(allocationGuaranteed=False)
    check('quota', capacity)
    def storage():
        bucket = o['bucket']
        m.need(bucket['name'] == p['bucket'] and bucket['projectNumber'] == cfg['projectNumber'] and
               bucket['iamConfiguration']['uniformBucketLevelAccess']['enabled'] is True, 'bucket identity/access')
        # A bucket-wide retention lock/event hold would also freeze the mutable control ledger/lease.
        m.need(not bucket.get('retentionPolicy') and not bucket.get('defaultEventBasedHold'), 'shared bucket control replacement blocked by retention/hold')
        for rule in bucket.get('lifecycle', {}).get('rule', []):
            action = rule['action']['type']; m.need(action in ('Delete', 'SetStorageClass', 'AbortIncompleteMultipartUpload'), 'unreviewed storage lifecycle action')
            if action == 'Delete':a.integer(rule['condition']['age'], a.workload.load()['evidence']['retentionDays'])
        return dict(minimumEvidenceDays=30, immutableRetentionQualified=False)
    check('storagePolicy', storage)
    def control():
        ledger = o['ledger']; lease = o['lease']
        def entry(value):
            m.need(type(value) in (list, tuple) and len(value) == 2, 'control observation unavailable')
            a.integer(value[0], 1); return value[1]
        total, attempts = a.inspect_ledger(entry(ledger) if ledger is not None else a.empty_ledger())
        if lease is not None:a.validate_lease(entry(lease))
        m.need(lease is None, 'retained lease requires reconciliation; expiry does not authorize reset')
        m.need(not any(v['status'] == 'PENDING' for v in attempts.values()), 'unresolved ledger reservation')
        m.need(total < 100_000_000, 'suite budget exhausted')
        return dict(previousCostMicrousd=total, budgetMicrousd=100_000_000, leaseAbsent=True)
    check('controlState', control)
    return checks


def evaluate(cfg, source, github, provider, *, now, workflow=None):
    digest = configuration(cfg); a.digest(source, 40); a.integer(now, 1)
    workflow = workflow if workflow is not None else (ci.ROOT/ci.WORKFLOW).read_text()
    checks = {}
    try:
        m.need(github and 'observations' in github, 'GitHub observation collection did not complete')
        a.integer(github['startedAt'], 1); a.integer(github['completedAt'], 1)
        m.need(github['source'] == source and now-900 <= github['startedAt'] <= github['completedAt'] <= now, 'GitHub observation stale/future')
        m.need(github['observations']['configurationSha256'] == digest, 'configuration differs from protected source')
        checks['exactSourceCI'] = dict(status='PASS', detail=ci.check(github['observations'], source, now, workflow))
    except (ValueError, KeyError, TypeError, IndexError) as error:checks['exactSourceCI'] = dict(status='BLOCKED', reason=str(error)[:300])
    started = now
    try:
        m.need(provider and 'observations' in provider, 'provider observations missing; authentication or collection did not finish')
        a.integer(provider['startedAt'], 1); a.integer(provider['completedAt'], 1)
        m.need(provider['execution'] in ('read-only-provider-observations', 'offline-preflight-fixture') and
               provider['configurationSha256'] == digest and now-900 <= provider['startedAt'] <= provider['completedAt'] <= now,
               'provider observation identity/stale/future')
        started = min(provider['startedAt'], github.get('startedAt', now))
        m.need(now < started+900, 'preflight observation expired')
        checks.update(check_provider(cfg, provider))
    except (ValueError, KeyError, TypeError, IndexError) as error:checks['provider'] = dict(status='BLOCKED', reason=str(error)[:300])
    blockers = [k+': '+v['reason'] for k, v in checks.items() if v['status'] != 'PASS']
    return dict(schema='gse-v51-read-only-preflight-v1', source=source, configurationSha256=digest,
                workloadSha256=a.workload.PLAN_SHA256, observedAt=now, expiresAt=started+900,
                execution=provider.get('execution', 'read-only-preflight-incomplete'), status='BLOCKED' if blockers else 'OBSERVATIONS_READY',
                checks=checks, blockers=blockers, paidAdmission=False, paidCloud=False, resourcesCreated=False,
                fullRemoteQualification=False, pending=list(PENDING))


def summary(receipt, cfg):
    p = cfg['provider']
    def safe(value):return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ')
    lines = ['# V5.1 read-only preflight', '', '**'+receipt['status']+'** — paid admission remains closed.', '',
             '| Parameter | Value |', '| --- | --- |']
    for key, value in [('Source', receipt['source']), ('Project', p['project']), ('Zone', p['zone']), ('Machine', p['machineType']),
                       ('Topology', '3 voters / 24 vCPU / 450 GiB'), ('Image', p['imageName']+' / '+p['imageId']),
                       ('Bucket', p['bucket']), ('Suite budget (USD)', '100; reservations never reset'),
                       ('Observed at / expires (UTC epoch)', f'{receipt["observedAt"]} / {receipt["expiresAt"]}'),
                       ('Execution', receipt['execution'])]:lines.append('| '+safe(key)+' | '+safe(value)+' |')
    lines.extend(['', '| Check | Result | Detail |', '| --- | --- | --- |'])
    for name, v in receipt['checks'].items():lines.append('| '+safe(name)+' | '+safe(v['status'])+' | '+safe(v.get('reason', v.get('detail')))+' |')
    lines.extend(['', '## Remaining admission requirements', '', *('- '+safe(v) for v in receipt['pending']), ''])
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('action', choices=('identity', 'github', 'provider', 'report', 'foundation'))
    p.add_argument('--source', required=True);p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execution', choices=('plan', 'fake'), default='plan');p.add_argument('--github-step-summary', type=Path)
    args = p.parse_args();a.digest(args.source, 40);cfg = c.read(CONFIG);configuration(cfg)
    m.need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ci.ROOT, text=True).strip() == args.source, 'source must match checkout')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.action == 'identity':
        value = identity(cfg, os.environ);m.need(os.environ['GITHUB_SHA'] == args.source, 'dispatch source')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            for k, v in value.items():f.write(k+'='+v+'\n')
    elif args.action in ('github', 'provider'):
        start = int(time.time())
        try:
            value = (dict(source=args.source, startedAt=start, observations=ci.collect(args.source), completedAt=int(time.time()))
                     if args.action == 'github' else collect_provider(cfg))
        except Exception as error:value = dict(source=args.source, startedAt=start, completedAt=int(time.time()), error=type(error).__name__)
        c.write_once(args.output/(args.action+'.json'), value)
    elif args.action == 'foundation':
        from . import cloud_qualification
        value = dict(schema='gse-v51-foundation-workflow-v1', source=args.source, execution='offline-'+args.execution,
                     workload=a.workload.audit(a.workload.load()), provider=cfg['provider'], paidCloud=False, fullRemoteQualification=False)
        if args.execution == 'fake':value['qualification'] = cloud_qualification.run(args.output/'qualification')
        c.write_once(args.output/'foundation.json', value)
        text = '# V5.1 foundation\n\nExecution: **'+args.execution+'**; source: `'+args.source+'`.\n\n'+\
            '3 voters, 24 vCPU, 450 GiB; experiment 4 cells, failure-drill 12 cells, canonical 15 cells × 3 repetitions.\n\n'+\
            'Offline qualification only. No credentials, cloud resources, paid admission or engine performance claim.\n'
        if args.github_step_summary:
            with args.github_step_summary.open('a') as f:f.write(text)
    else:
        inputs = {k:c.read(args.output/(k+'.json')) if (args.output/(k+'.json')).exists() else {} for k in ('github', 'provider')}
        value = evaluate(cfg, args.source, **inputs, now=int(time.time()))
        c.write_once(args.output/'preflight.json', value)
        text = summary(value, cfg);(args.output/'summary.md').write_text(text)
        if args.github_step_summary:
            with args.github_step_summary.open('a') as f:f.write(text)
        print(m.canonical(dict(status=value['status'], blockers=value['blockers'], paidAdmission=False)).decode())
        if value['status'] == 'BLOCKED':raise SystemExit(2)


if __name__ == '__main__':main()
