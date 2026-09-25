"""Retained no-network qualification through real provider request adapters."""
import argparse
from pathlib import Path
import subprocess
from . import cloud_authority as a, cloud_fake, cloud_http_fake as fake, cloud_runner as runner, performance_model as m
from .remote_command import write_once

CASES = ('success', 'lost-insert', 'pending-insert', 'delete-denied', 'image-drift')


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    for case in CASES:
        root = output/case; root.mkdir()
        req, pre, approval, clock, http, store, provider = fake.fixture(None if case == 'success' else case)
        probe = cloud_fake.Probe(root/'guest', clock)
        result = runner.Runner(store, provider, probe, root/'run', clock=clock.nanos, wall=clock.wall).run(req, pre, approval)
        expected = 'PASS' if case == 'success' else 'FAIL'
        m.need(result['status'] == expected, 'HTTP lifecycle outcome: '+case)
        held = store.get(a.LEASE) is not None
        if held:
            waiting = runner.reconcile(store, provider, root/'manual-active', trigger='manual', now=clock.wall())
            m.need(waiting['status'] == 'WAITING', 'HTTP cleanup bypassed lease/grace')
        if case == 'lost-insert': m.need(http.inserts == 3 and not http.resources and not held, 'lost insert resolution')
        if case in ('pending-insert', 'delete-denied', 'image-drift'): m.need(held, 'unresolved HTTP state released lease')
        total, _ = a.inspect_ledger(store.get(a.LEDGER)[1]); m.need(total == approval['maximumCostMicrousd'], 'HTTP ledger lost charge')
        write_once(root/'http.json', dict(requests=http.requests, operations=http.operations, resources=http.resources))
        write_once(root/'store.json', {key: dict(generation=gen, size=len(raw), sha256=m.sha(raw), contentType=content)
                   for key, (gen, raw, content) in http.objects.items()})
        row = dict(case=case, status='PASS', observedOutcome=expected, cleanup=result['cleanup']['status'],
                   inserts=http.inserts, leaseRetained=held, chargedMicrousd=total)
        rows.append(row); print(m.canonical(row).decode(), flush=True)
    receipt = dict(schema='gse-v51-provider-qualification-v1', status='PASS', execution='offline-provider-http',
        source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
        inputs={p.name: m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('cloud_*.py'))},
        paidCloud=False, engineWorkloadExecuted=False, fullRemoteQualification=False, cases=rows)
    write_once(output/'receipt.json', receipt); return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path); run(p.parse_args().output)
