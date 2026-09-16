"""Phase 6B plan/fake/read-only preparation and exact-confirmation execution entry."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from .cloud_common import ROOT, canonical, inventory, plan, read, request, require, resources, save, sha
from .cloud_bundle import build, extract
from .cloud_fake import Fake, FakeProbe
from .cloud_gcp import Api, Gcp
from .cloud_preflight import admission, collect
from .cloud_runner import LEASE, Runner, reconcile
from .performance_harness import source_inputs


def exact_checkout(source):
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == source and
            not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'clean exact checkout required')


def fake_matrix(root):
    p = plan(); results = []
    faults = [None, 'partial-create', 'startup-failure', 'unreachable', 'upload-failure', 'cancel',
              'delete-failure', 'foreign-owner', 'reused-id', 'forbidden-read', 'unresolved-create']
    for index, fault in enumerate(faults, 1):
        backend = Fake(p, request('a' * 40, index, 1, 'b' * 64), fault)
        state = Runner(backend, FakeProbe(backend), Path(root) / (fault or 'success')).run()
        require(state['status'] == ('PASS' if fault is None else 'FAIL'), 'fake expected outcome: ' + str(fault))
        results.append(dict(case=fault or 'success', expectedFailure=fault is not None, status='PASS',
                            cleanup=state.get('cleanup'), leaseRetained=LEASE in backend.objects))
    report = dict(schema='gse-v50-cloud-fake-matrix-v1', execution='fake-owned-runner-only', status='PASS', cases=results)
    save(Path(root) / 'matrix.json', report); return report


def prepare(output, source, control, run_id, attempt):
    exact_checkout(source)
    subprocess.run([str(ROOT / 'mvnw'), '-f', 'reactor/pom.xml', 'clean', 'package'], cwd=ROOT, check=True, timeout=1200)
    subprocess.run([str(ROOT / 'scripts/verify-v50-phase6-performance.sh'), '--skip-build'], cwd=ROOT, check=True, timeout=260,
                   env=dict(os.environ, GSE_V50_CONTROL_JAR=str(Path(control).resolve())))
    bundle = build(Path(output) / 'artifacts', control)
    exact_checkout(source)
    req = request(source, run_id, attempt, sha(bundle.read_bytes()))
    save(Path(output) / 'request.json', req)
    receipt = collect(plan(), source)
    save(Path(output) / 'preflight.json', receipt)
    result = dict(status=receipt['status'], blockers=receipt['blockers'], requestSha256=sha(canonical(req)),
                  preflightSha256=sha(canonical(receipt)), expiresAt=receipt['expiresAt'])
    save(Path(output) / 'review.json', result); return result


def execute(prepared, output, approval_path, confirmation):
    p = plan(); prepared = Path(prepared)
    req, receipt, approval = (read(prepared / 'request.json'), read(prepared / 'preflight.json'), read(approval_path))
    require(confirmation == sha(canonical(req)), 'explicit confirmation must be the exact reviewed request SHA-256')
    expected = request(req['source'], req['runId'], req['attempt'], req['bundleSha256'], req['nonce'])
    expected['createdAt'] = req['createdAt']; require(req == expected, 'invalid run identity/profile')
    exact_checkout(req['source']); admission(p, receipt, req, approval)
    archive = prepared / 'artifacts/bundle.tar.gz'
    require(archive.stat().st_size <= p['maximumBundleBytes'] and sha(archive.read_bytes()) == req['bundleSha256'], 'admitted bundle checksum')
    # Discard no existing directory. Extraction always uses a fresh temporary location.
    with tempfile.TemporaryDirectory(prefix='gse-v50-execute-') as temporary:
        content = Path(temporary) / 'bundle'; extract(archive, content)
        manifest = read(content / 'bundle.json', 16 << 20)
        require(manifest['schema'] == 'gse-v50-cloud-bundle-v1' and 'execution' not in manifest,
                'paid execution requires the admission-probe bundle schema')
        actual = inventory(content); actual.pop('bundle.json')
        require(actual == manifest['files'], 'bundle inventory')
        inputs = source_inputs(); inputs['docs/v5x/v5.0/phase6-runner-plan.json'] = sha((ROOT / 'docs/v5x/v5.0/phase6-runner-plan.json').read_bytes())
        require(manifest['source'] == req['source'] and manifest['dirty'] is False and manifest['inputs'] == inputs and
                manifest['planSha256'] == sha(canonical(p)), 'bundle exact build/probe inputs')
        require(json.loads(subprocess.check_output(['gcloud', 'version', '--format=json']))['Google Cloud SDK'] == p['gcloudVersion'], 'gcloud version pin')
        # Fresh read-only observations immediately before the first mutation.
        fresh = collect(p, req['source']); require(fresh['status'] == 'READY_FOR_PAID_REVIEW', 'preflight changed: ' + str(fresh['blockers']))
        admission(p, receipt, req, approval)  # Refresh/transfer time cannot extend expiry.
        key = Path(temporary) / 'ssh-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True, timeout=10)
        backend = Gcp(p, req, output, ssh_key=key)
        runner = Runner(backend, None, output, approval=approval)
        for name, value in [('request', req), ('preflight', receipt), ('fresh-preflight', fresh), ('approval', approval)]:
            save(Path(output) / (name + '.json'), value)
        from .cloud_probe import Probe
        runner.probe = Probe(backend, archive, output, content)
        signal.alarm(p['maximumTopologySeconds'] - p['cleanupReserveSeconds'])
        return runner.run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan', 'fake', 'prepare', 'run', 'reconcile', 'expired-cleanup', 'validate'])
    parser.add_argument('--output', required=True, type=Path); parser.add_argument('--source')
    parser.add_argument('--control-jar', type=Path); parser.add_argument('--run-id'); parser.add_argument('--attempt', default='1')
    parser.add_argument('--prepared', type=Path); parser.add_argument('--approval', type=Path); parser.add_argument('--confirm-request')
    parser.add_argument('--profile', choices=['admission-probe', 'experiment', 'failure-drill', 'canonical'], default='admission-probe')
    args = parser.parse_args(); p = plan()
    require(args.profile == 'admission-probe' or args.mode in ('plan', 'fake'),
            'full workload presets currently support plan/fake qualification only')
    if args.mode == 'plan':
        if args.profile != 'admission-probe':
            from .cloud_presets import preset
            p = preset(args.profile)
        result = dict(plan=p, paidResourcesCreated=False, execution='plan-only'); save(args.output / 'plan.json', result)
    elif args.mode == 'fake':
        if args.profile == 'admission-probe': result = fake_matrix(args.output)
        else:
            from .cloud_preset_fake import matrix
            result = matrix(args.output, args.profile)
    elif args.mode == 'prepare':
        require(args.source and args.control_jar and args.run_id, 'prepare requires source, control JAR and run ID')
        result = prepare(args.output, args.source, args.control_jar, args.run_id, args.attempt)
    elif args.mode == 'run':
        require(args.prepared and args.approval and args.confirm_request, 'run requires prepared evidence and exact paid confirmation')
        result = execute(args.prepared, args.output, args.approval, args.confirm_request)
    elif args.mode in ('reconcile', 'expired-cleanup'):
        stored = Gcp(p, {}, args.output, api=Api()).get_object(LEASE)
        if args.mode == 'expired-cleanup':
            require(os.environ.get('GITHUB_EVENT_NAME') == 'schedule' and os.environ.get('GITHUB_REF') == p['ref'], 'scheduled protected-master cleanup only')
            if stored is None:
                save(args.output / 'cleanup.json', dict(status='PASS', activeLease=False)); return 0
        require(stored is not None, 'no active lease'); lease = json.loads(stored[1])
        req = lease['request']; expected = request(req['source'], req['runId'], req['attempt'], req['bundleSha256'], req['nonce'])
        expected['createdAt'] = req['createdAt']; require(req == expected, 'invalid retained request')
        if args.mode == 'reconcile': require(args.confirm_request == sha(canonical(req)), 'explicit cleanup must identify the retained request')
        elif int(time.time()) <= lease['expiresAt'] + p['commandTimeoutSeconds']:
            save(args.output / 'cleanup.json', dict(status='WAITING', activeLease=True)); return 0
        result = reconcile(Gcp(p, lease['request'], args.output), args.output)
    else:
        from .cloud_evidence import validate
        result = validate(args.output)
    print(json.dumps({k: result[k] for k in ('status', 'execution', 'blockers', 'requestSha256') if k in result}, sort_keys=True))
    return 0 if result.get('status', 'PASS') in ('PASS', 'READY_FOR_PAID_REVIEW') else 2


if __name__ == '__main__':
    def interrupted(signum, frame): raise RuntimeError('runner interrupted: ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    raise SystemExit(main())
