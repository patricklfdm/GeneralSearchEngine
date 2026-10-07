"""Synthetic original CI archives and WIF exchanges; never real cloud evidence.

The tiny JAR/runtime fixtures cannot execute an engine and use explicit offline
control pins. The native entry never accepts those pins or these HTTP doubles.
"""
import argparse
import base64
from copy import deepcopy
from pathlib import Path
import tarfile
import zipfile
from . import cloud_runner_admission as r, cloud_runner_artifacts as artifacts
from . import test_cloud_runner_precheck as pre, test_cloud_package as packaged
from . import cloud_preflight_qualification as pq, cloud_cleanup_qualification as cleanup
from . import cloud_cleanup_auth_fake as auth, cloud_fake, cloud_http_fake
from . import cloud_experiment_resource_qualification as rq, cloud_native_authority as n
from . import performance_model as m
from .remote_command import read, write_once

COST = 10_000_000  # Synthetic quote, not a live price or permission to spend.


def fixture(root):
    root = Path(root); root.mkdir(parents=True, exist_ok=False)
    cfg, env, preflight, data = pre.fixture(root)
    github = read(preflight/'github.json'); obs = github['observations']
    for kind in artifacts.JOBS:
        job = next(j for j in obs['jobs'] if j['name'] == artifacts.JOBS[kind])
        job['steps'].append(dict(name=artifacts.STEPS[kind], status='completed', conclusion='success',
            started_at=pre.at(pq.NOW-290), completed_at=pre.at(pq.NOW-60)))
    (preflight/'github.json').write_bytes(m.canonical(github))
    before = r.p.report(cfg, pq.SOURCE, preflight, dict(env, GITHUB_JOB='observations'), now=pq.NOW)
    m.need(before['status'] == 'OBSERVATIONS_READY', 'synthetic original preflight')
    (preflight/'preflight.json').write_bytes(m.canonical(before))
    data.update(pq.github_api(github))
    config_bytes = m.canonical(cfg)
    data['contents/'+r.ci.CONFIG_PATH+'?ref='+pq.SOURCE] = dict(encoding='base64', size=len(config_bytes),
        content=base64.b64encode(config_bytes).decode())
    clock = cloud_fake.Clock(); clock.now = (pq.NOW+2-10000)*10**9
    binding = dict(source=pq.SOURCE, checkoutSha256='c'*64, java={
        'java.vendor': r.workload.load()['environment']['javaVendor'],
        'java.runtime.version': r.workload.load()['environment']['javaRuntime']})
    package = root/'guest'; manifest = packaged.fixture(package)
    build_tar = root/'build.tar.gz'
    with tarfile.open(build_tar, 'w:gz') as tar:
        for name in manifest['modes'][artifacts.package.MODES[2]]['jars']:
            prefix = 'general-search-engine-replication/target/' if 'replication' in name else 'target/'
            tar.add(package/name, arcname=prefix+Path(name).name, recursive=False)
    bm = read(package/'ci-build-manifest.json'); bm.update(schema=r.build.SCHEMA, binding=binding,
        archiveSha256=m.sha(build_tar.read_bytes()))
    (package/'ci-build-manifest.json').write_bytes(m.canonical(bm))
    (package/'workload.json').write_bytes(m.canonical(r.workload.load()))
    manifest.update(dirty=False, buildBinding=binding,
        buildManifestSha256=m.sha((package/'ci-build-manifest.json').read_bytes()),
        workloadSha256=m.sha((package/'workload.json').read_bytes()),
        jvmArguments=r.workload.load()['environment']['jvmArguments'], files=artifacts.package.inventory(package))
    (package/'manifest.json').write_bytes(m.canonical(manifest))
    raw = root/'originals'; raw.mkdir()
    with tarfile.open(raw/'guest.tar.gz', 'w:gz') as tar:
        for path in sorted(package.rglob('*')):
            if path.is_file(): tar.add(path, arcname=path.relative_to(package).as_posix(), recursive=False)
    archive = (raw/'guest.tar.gz').read_bytes()
    receipt = dict(schema='gse-v51-guest-build-v1', status='PASS', source=pq.SOURCE, dirty=False,
        buildManifestSha256=manifest['buildManifestSha256'], archiveSha256=m.sha(archive), archiveBytes=len(archive),
        payloadFiles=len(manifest['files']), payloadBytes=sum(v['size'] for v in manifest['files']),
        checks=[dict(mode=mode, status='PASS') for mode in artifacts.package.MODES],
        paidCloud=False, fullRemoteQualification=False, engineWorkloadExecuted=False)
    payloads = dict(build={'manifest.json':(package/'ci-build-manifest.json').read_bytes(), 'build.tar.gz':build_tar.read_bytes()}, package={
        'guest.tar.gz':archive, 'receipt.json':m.canonical(receipt), 'package/manifest.json':m.canonical(manifest)})
    records = {}
    for i, (kind, files) in enumerate(payloads.items(), 101):
        with zipfile.ZipFile(raw/(kind+'.zip'), 'w', zipfile.ZIP_DEFLATED) as zip:
            for name, content in files.items(): zip.writestr(name, content)
        content = (raw/(kind+'.zip')).read_bytes()
        records[kind] = dict(id=i, name=artifacts.name(kind, obs['run']), expired=False, size_in_bytes=len(content),
            digest='sha256:'+m.sha(content), created_at=pre.at(pq.NOW-50), updated_at=pre.at(pq.NOW-40),
            workflow_run=dict(id=12, head_sha=pq.SOURCE, head_branch='master',
                              repository_id=r.ci.REPOSITORY_ID, head_repository_id=r.ci.REPOSITORY_ID))
        data[f'actions/artifacts/{i}'] = deepcopy(records[kind])
    data['actions/runs/12/artifacts?per_page=100&page=1'] = dict(total_count=2, artifacts=list(records.values()))
    write_once(raw/'artifacts.json', records)
    write_once(raw/'build-job.json', next(j for j in obs['jobs'] if j['name'] == artifacts.JOBS['build']))
    controls = read(package/'published-controls.json')
    proof = artifacts.verify(raw, obs, binding, controls=controls)
    quote = dict(observedAt=pq.NOW, expiresAt=pq.NOW+86400, region='us-west4', machineType='n2-standard-8',
        diskType='pd-balanced', vmMicrousdPerHour=500000, diskMicrousdPerGiBHour=200,
        pricedThroughSeconds=19800, retentionDays=30,
        otherCostsMicrousd=dict(requests=10000, evidenceRetention=10000, network=10000, actions=10000, failureOverhang=100000),
        sources={k:'https://cloud.google.com/'+path for k, path in dict(compute='compute/all-pricing',
            disks='compute/disks-image-pricing', storage='storage/pricing', network='vpc/network-pricing').items()})
    quote['sources']['actions'] = 'https://docs.github.com/en/billing/concepts/product-billing/github-actions'
    guest = dict(attempt='b'*32, user='gse-'+'b'*24, publicKey=cleanup.KEY)
    value = r.plan(cfg, proof, guest, quote, None, sequence='d'*32, now=clock.wall(), maximum_cost=COST)
    approved = r.approval_template(value); approved['confirmed'] = True
    env['RUNNER_EXPERIMENT_CONFIRMATION'] = approved['planSha256']
    get = lambda path: deepcopy(data[path])
    r.precheck.bind(cfg, env, pq.SOURCE, pq.SOURCE, preflight, root/'identity', get=get, wall=clock.wall)
    pre.permission_files(cfg, env, root/'permissions', 'runner', clock.wall())
    result = r.precheck.finish(cfg, env, pq.SOURCE, pq.SOURCE, preflight, root, get=get, wall=clock.wall)
    m.need(result['status'] == 'PRECHECK_PASS', 'synthetic original runner precheck')
    identity = r.precheck.identity(cfg, env, pq.SOURCE, pq.SOURCE)
    env, descriptor = auth.inputs(identity, env)
    issuer = auth.Issuer(identity, clock); http = cloud_http_fake.Http(cfg['provider'])
    return dict(root=root, cfg=cfg, env=env, data=data, preflight=preflight, github=obs, clock=clock,
        binding=binding, originals=raw, controls=controls, value=value, approved=approved,
        issuer=issuer, descriptor=descriptor, http=http)


def inspect(f):
    return r.OfflineAdmission(f['cfg'], f['env'], pq.SOURCE, f['preflight'], f['root'], f['value'],
        f['approved'], f['originals'], f['binding'], transport=auth.Provider(f['http']), issuer=f['issuer'],
        descriptor=f['descriptor'], clock=f['clock'].seconds, wall=f['clock'].wall,
        get=lambda path:deepcopy(f['data'][path]), controls=f['controls'])


def qualify(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    f = fixture(output/'inputs'); before = cleanup.snapshot(f['http'])
    admitted = inspect(f); result = admitted.result
    m.need(result['status'] == 'REQUEST_BOUND' and result['credentialExchangeCompleted'] and
           cleanup.snapshot(f['http']) == before and all(v['method'] == 'GET' for v in f['http'].requests),
           'request inspection mutated control/provider state')
    write_once(output/'inspection.json', result); write_once(output/'inspection-http.json', admitted.api.requests)
    write_once(output/'credential-stages.json', f['issuer'].calls)
    value = result['resourcePlan']; clock = f['clock']; http = f['http']
    api = r.resources.OfflineApi(value, clock.wall(), transport=http, tokens=lambda _: 'offline-token', clock=clock.seconds)
    prepared = r.resources.prepare(value, api, output/'resources', now=clock.wall(), sleep=clock.sleep)
    m.need(prepared['status'] == 'RESOURCES_PREPARED' and http.inserts == 13, 'admitted offline resource preparation')
    saved = cleanup.snapshot(http)
    receipt, after, _ = rq.replay(api.cfg, pq.SOURCE, saved, output/'expired-manual', api.lease['expiresAt']+api.lease['graceSeconds'])
    m.need(receipt['status'] == 'PASS', 'admitted resource cleanup replay')
    _, restored, raw, _ = cleanup.restore(after); store = r.g.Store(api.cfg, raw, authority=n)
    cost, entries = n.inspect_ledger(store.get(n.LEDGER)[1])
    m.need(store.get(n.LEASE) is None and not restored.resources and cost == COST and
           all(v['status'] == 'FAIL' for v in entries.values()), 'admitted cleanup retained charge/result')
    summary = dict(schema='gse-v51-runner-admission-qualification-v1', status='PASS',
        execution='offline-runner-request-and-resource-lifecycle', paidCloud=False, syntheticArtifacts=True,
        cases=['original-artifacts-and-credentials', 'read-only-request-inspection', 'thirteen-resource-preparation',
               'independent-expired-manual-cleanup'], reservedCostMicrousd=cost, **r.FLAGS)
    write_once(output/'receipt.json', summary); print(m.canonical(summary).decode()); return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); qualify(parser.parse_args().output)
