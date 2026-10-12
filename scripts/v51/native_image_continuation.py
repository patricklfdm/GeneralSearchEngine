"""One operator-authorized batch audit. No admission, ledger writes or workload replay.

Original records keep their source/sequence/request identity. Only the frozen
2026-10-12 exception can count two historical members toward this batch.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile
from . import cloud_authority as a, cloud_native_authority as n, cloud_ci as ci
from . import cloud_gcp as g, cloud_http as h, cloud_package as package
from . import native_preset_timing as timing, performance_model as m, remote_command as c

POLICY_PATH = 'docs/v5x/v5.1/native-image-continuation.json'
SCHEMA = 'gse-v51-image-continuation-v1'
REMAINING = ('canonical-3', 'experiment', 'failure-drill')
INHERITED = ('canonical-1', 'canonical-2')
RECORDS = ('completion.json', 'owned-experiment/evidence.json', 'owned-experiment/manifest.json')


def policy():
    value = c.read(ci.ROOT/POLICY_PATH)
    m.need(value['schema'] == SCHEMA and value['remaining'] == list(REMAINING) and
           set(value['inherited']) == set(INHERITED), 'continuation policy scope')
    a.digest(value['oldSource'], 40); a.digest(value['oldSequence'], 32); a.digest(value['sequence'], 32)
    m.need(value['oldSequence'] != value['sequence'], 'continuation needs distinct sequence')
    return value


def git(*args):
    return subprocess.run(['git', *args], cwd=ci.ROOT, check=True, capture_output=True, timeout=30).stdout


def source_compatible(source, frozen):
    """Exact paths and approved script bytes; all other tracked inputs unchanged."""
    a.digest(source, 40)
    m.need(source != frozen['oldSource'], 'continuation needs corrected source')
    git('merge-base', '--is-ancestor', frozen['oldSource'], source)
    changed = set(git('diff', '--name-only', '--no-renames', '-z', frozen['oldSource'], source, '--').decode().split('\0'))-{''}
    m.need(changed and changed <= set(frozen['allowedChanges']), 'continuation source changed outside image repair')
    for path, digest in frozen['approvedScripts'].items():
        m.need(m.sha(git('show', source+':'+path)) == digest, 'continuation approved script changed: '+path)
    m.need(m.strict_json(git('show', source+':'+POLICY_PATH)) == frozen, 'continuation source policy changed')
    return sorted(changed)


def payload(manifest, helper_raw):
    # CI metadata and the helper's source field bind the different checkout.
    # Keep every executable byte, including all embedded helper files, exact.
    helper = m.strict_json(helper_raw)
    m.need(set(helper) == {'schema', 'source', 'files'} and helper['schema'] == 'gse-v51-helper-payload-v1' and
           helper['source'] == manifest['source'] and m.canonical(helper) == helper_raw, 'continuation helper source/encoding')
    rows = [dict(v) for v in manifest['files'] if v['path'] != 'ci-build-manifest.json']
    helpers = [v for v in rows if v['path'] == 'startup-helper.json']
    m.need(len(helpers) == 1 and helpers[0]['sha256'] == m.sha(helper_raw) and
           helpers[0]['size'] == len(helper_raw), 'continuation helper inventory')
    normalized = m.canonical(dict(helper, source='0'*40))
    helpers[0].update(sha256=m.sha(normalized), size=len(normalized))
    return dict(files=rows,
                **{k: manifest[k] for k in ('adapterSources', 'modes', 'jvmArguments', 'workloadSha256')})


def prepared(root, frozen, source):
    root = Path(root); plan = c.read(root/'plan.json'); req = plan['resourcePlan']['request']
    n.validate_request(req); request_compatible(req, frozen, source)
    m.need(req['member'] in REMAINING, 'continuation prepared member')
    provider = plan['configuration']['provider']
    m.need(g.config(provider) == req['configurationSha256'] and
           all(provider[k] == x for k, x in frozen['image'].items()), 'continuation prepared image/configuration')
    proof = plan['artifacts']; archive = root/'originals/package.zip'
    m.need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size <= 288 << 20 and
           m.sha(archive.read_bytes()) == proof['artifacts']['package']['sha256'], 'continuation original package ZIP')
    with zipfile.ZipFile(archive) as z:
        rows = z.infolist()
        m.need(len(rows) <= 10000 and len({v.filename for v in rows}) == len(rows) and
               sum(v.file_size for v in rows) <= 288 << 20, 'continuation package ZIP bounds')
        raw = z.read('guest.tar.gz'); manifest_raw = z.read('package/manifest.json')
    m.need(m.sha(raw) == proof['archiveSha256'] == req['bundleSha256'] and
           m.sha(manifest_raw) == proof['packageManifestSha256'], 'continuation package archive/manifest binding')
    with tempfile.TemporaryDirectory(prefix='v51-continuation-') as tmp:
        path = Path(tmp); (path/'guest.tar.gz').write_bytes(raw)
        manifest = package.unpack(path/'guest.tar.gz', path/'unpacked', req['bundleSha256'], source)
        m.need((path/'unpacked/manifest.json').read_bytes() == manifest_raw and manifest['dirty'] is False and
               manifest['buildBinding'] == proof['buildBinding'] and proof['source'] == source and
               manifest['buildManifestSha256'] == proof['buildManifestSha256'], 'continuation original package identity')
        comparison = payload(manifest, (path/'unpacked/startup-helper.json').read_bytes())
        m.need(m.sha(m.canonical(comparison)) == frozen['payloadSha256'], 'continuation executable/workload payload changed')
    return plan


def request_compatible(req, frozen, source):
    n.validate_request(req)
    m.need(req['schema'] == timing.SOFT_REQUEST_SCHEMA and req['order'] == 'any-order' and
           all(req[k] == frozen[k] for k in ('configurationSha256', 'workloadSha256', 'timingPlanSha256')),
           'continuation frozen request policy changed')
    if req['member'] in INHERITED:
        pin = frozen['inherited'][req['member']]
        m.need(req['source'] == frozen['oldSource'] and req['sequence'] == frozen['oldSequence'] and
               n.validate_request(req) == pin['requestSha256'], 'continuation inherited request changed')
    else:
        m.need(req['member'] in REMAINING and req['source'] == source and req['sequence'] == frozen['sequence'],
               'continuation new member/source/sequence changed')


def select(ledger, frozen, source):
    total, attempts = n.inspect_ledger(ledger)
    m.need(not any(v['status'] == 'PENDING' for v in attempts.values()), 'continuation unresolved reservation')
    selected = {}
    for sha, value in attempts.items():
        req = value['request']
        if req['sequence'] not in (frozen['oldSequence'], frozen['sequence']): continue
        request_compatible(req, frozen, source)
        # An experiment/drill retry remains charged and retained; it cannot be
        # silently selected. A failed canonical already poisons its sequence.
        if value['status'] != 'PASS': continue
        m.need(req['member'] not in selected, 'continuation duplicate member')
        selected[req['member']] = req
    m.need(set(INHERITED) <= set(selected), 'continuation historical PASS missing')
    return total, selected


def record(value):
    a.integer(value['generation'], 1)
    raw = m.canonical(value['value'])
    m.need(value['bytes'] == len(raw) and value['sha256'] == m.sha(raw), 'continuation retained record hash/size')
    return value['value']


def member(req, rows, ledger, frozen, plan=None):
    sha = n.validate_request(req); name = req['member']
    m.need(set(rows) == set(RECORDS), 'continuation retained record inventory')
    completion, evidence, inventory = [record(rows[k]) for k in RECORDS]
    terminal = [v for v in ledger['entries'] if v['kind'] == 'FINISHED' and v['requestSha256'] == sha]
    m.need(len(terminal) == 1 and terminal[0]['status'] == 'PASS' and
           terminal[0]['completionSha256'] == rows[RECORDS[0]]['sha256'], 'continuation terminal ledger binding')
    m.need(completion['schema'] == n.COMPLETION_SCHEMA and completion['status'] == 'PASS' and
           completion['requestSha256'] == inventory['requestSha256'] == sha and completion['errors'] == [] and
           completion['evidence'] == evidence and completion['evidenceSha256'] == rows[RECORDS[1]]['sha256'] and
           completion['inventorySha256'] == rows[RECORDS[2]]['sha256'], 'continuation completion/evidence binding')
    for v in (completion, evidence):
        m.need(v['execution'] == n.EXECUTION and v['paidCloud'] is True and v['engineWorkloadExecuted'] is True and
               v['fullRemoteQualification'] is False and v['status'] == 'PASS', 'continuation native workload scope')
    allocation = timing.validate(req); preset = allocation['preset']
    scope = 'owned-complete-'+preset if preset != 'experiment' else 'owned-complete-experiment'
    m.need(evidence['physicalHistoryQualified'] is True and
           (preset == 'failure-drill' or evidence.get('backupRestoreQualified') is True) and
           evidence['errors'] == [] and evidence['cells'] == allocation['cells'] and
           evidence['scope'] == completion['qualificationScope'] == scope, 'continuation member qualification')
    if preset == 'canonical':
        m.need(evidence['repetition'] == allocation['repetition'] and evidence['aggregate']['calls'] == 1080 and
               evidence['aggregate']['status'] == 'PASS' and evidence['aggregate']['ownedCanonicalQualified'] is True and
               evidence['aggregate']['repetition'] == allocation['repetition'] and
               evidence['aggregate']['requestSha256'] == sha, 'continuation canonical repetition/binding')
    cleanup = completion['cleanup']; checks = cleanup['checks']
    m.need(cleanup['status'] == 'PASS' and cleanup['errors'] == [] and cleanup['leftovers'] == [] and
           len(checks) == 13 and {v['name'] for v in checks} == {v['name'] for v in n.resources(req)} and
           all(v['absent'] is True and v['observed'] is None and type(v['expectedId']) is str and
               v['expectedId'].isdigit() for v in checks), 'continuation exact cleanup incomplete')
    prefix = a.PREFIX+'attempts/'+sha+'/owned-experiment/'
    files = inventory['files']
    m.need(inventory['schema'] == 'gse-v51-native-owned-evidence-v2' and files and
           all(key.startswith(prefix) and '..' not in key.split('/') for key in files) and
           {prefix+'metadata/parts.json', prefix+'parts/parts.json', prefix+'evidence.json'} <= set(files) and
           files[prefix+'evidence.json'] == {k: rows[RECORDS[1]][k] for k in ('bytes', 'sha256')},
           'continuation retention inventory')
    for value in files.values(): a.digest(value['sha256']); a.integer(value['bytes'], 1)
    if name in INHERITED:
        pin = frozen['inherited'][name]
        m.need(all(rows[k]['sha256'] == pin['records'][k] for k in RECORDS), 'continuation pinned historical record changed')
    else:
        m.need(plan is not None and plan['resourcePlan']['request'] == req and
               m.sha(m.canonical(plan)) == completion['preparation']['planSha256'], 'continuation prepared plan binding')
    return dict(member=name, source=req['source'], sequence=req['sequence'], requestSha256=sha,
                inherited=name in INHERITED, records={k: rows[k]['sha256'] for k in RECORDS})


def review(observations, source, prepared_roots):
    frozen = policy(); changes = source_compatible(source, frozen)
    m.need(observations['schema'] == SCHEMA and observations['source'] == source and
           observations['policySha256'] == m.sha(m.canonical(frozen)) and observations['lease'] is None,
           'continuation observation source/policy/lease')
    a.integer(observations['ledgerGeneration'], 1)
    ledger = observations['ledger']; total, chosen = select(ledger, frozen, source)
    m.need(set(observations['members']) == set(chosen) and
           set(prepared_roots) == set(chosen)-set(INHERITED), 'continuation exact member/prepared inventory')
    results = []
    for name, req in chosen.items():
        plan = prepared(prepared_roots[name], frozen, source) if name in prepared_roots else None
        results.append(member(req, observations['members'][name], ledger, frozen, plan))
    missing = sorted(set(timing.MEMBERS)-set(chosen))
    return dict(schema=SCHEMA, status='PARTIAL' if missing else 'PASS', batchComplete=not missing,
                source=source, sequence=frozen['sequence'], policySha256=m.sha(m.canonical(frozen)),
                observationsSha256=m.sha(m.canonical(observations)), changedPaths=changes,
                members=results, missing=missing, recordedCostMicrousd=total,
                scope='one-batch-completion-audit', fullRemoteQualification=False, paidAdmission=False,
                workloadReplayed=False, ledgerModified=False)


def collect(source, output):
    """Current generation-pinned reads only. Never upload, list objects or reset."""
    frozen = policy(); source_compatible(source, frozen)
    cfg = c.read(ci.ROOT/'docs/v5x/v5.1/phase6-preflight-config.json')['provider']
    m.need(g.config(cfg) == frozen['configurationSha256'], 'continuation provider configuration')
    store = g.Store(cfg, h.Api(), authority=n)
    ledger = store.get(n.LEDGER); m.need(ledger is not None, 'continuation ledger absent')
    _, chosen = select(ledger[1], frozen, source); lease = store.get(n.LEASE)
    m.need(lease is None, 'continuation retained lease')
    members = {}
    for name, req in chosen.items():
        rows = {}
        for key in RECORDS:
            value = store.get(a.PREFIX+'attempts/'+n.validate_request(req)+'/'+key)
            m.need(value is not None, 'continuation retained record missing')
            generation, data = value; raw = data if type(data) is bytes else m.canonical(data)
            rows[key] = dict(generation=generation, bytes=len(raw), sha256=m.sha(raw), value=m.strict_json(raw))
        members[name] = rows
    m.need(store.get(n.LEDGER) == ledger and store.get(n.LEASE) is None, 'continuation control changed during observation')
    result = dict(schema=SCHEMA, source=source, policySha256=m.sha(m.canonical(frozen)), observedAt=int(time.time()),
                  ledgerGeneration=ledger[0], ledger=ledger[1], lease=lease, members=members)
    c.write_once(Path(output), result)
    return dict(status='COLLECTED', members=sorted(members), fullRemoteQualification=False)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='action', required=True)
    for action in ('source', 'prepared', 'collect', 'review'):
        command = sub.add_parser(action); command.add_argument('--source', required=True); command.add_argument('--output', required=True)
        if action == 'prepared': command.add_argument('--prepared', required=True)
        if action == 'review':
            command.add_argument('--observations', required=True); command.add_argument('--prepared', action='append', default=[])
    args = p.parse_args(); frozen = policy()
    if args.action == 'collect': result = collect(args.source, args.output)
    else:
        changes = source_compatible(args.source, frozen)
        if args.action == 'review':
            pairs = [v.split('=', 1) for v in args.prepared]
            m.need(all(len(v) == 2 for v in pairs) and len(dict(pairs)) == len(pairs), 'duplicate/malformed prepared argument')
            result = review(c.read(Path(args.observations)), args.source, dict(pairs))
        else:
            result = dict(schema=SCHEMA, status='COMPATIBLE', source=args.source, sequence=frozen['sequence'],
                          changedPaths=changes, paidAdmission=False, fullRemoteQualification=False)
            if args.action == 'prepared':
                plan = prepared(args.prepared, frozen, args.source)
                result['requestSha256'] = n.validate_request(plan['resourcePlan']['request'])
        c.write_once(Path(args.output), result)
    print(m.canonical(result).decode())


if __name__ == '__main__': main()
