"""Retained owned-startup failures with fake HTTP/disks, no SSH or block writes."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from . import cloud_authority as a, cloud_fake, cloud_runner, guest_startup as startup, guest_startup_fake as fake, performance_model as m
from .remote_command import write_once

CASES = ('success', 'disk-id-drift', 'boot-device', 'used-disk', 'alias-drift', 'lost-format-reply', 'lost-mount-reply', 'wrong-mount', 'deadline')


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    for case in CASES:
        root = output/case; root.mkdir()
        # Real local key generation, kept outside retained artifacts and removed.
        with tempfile.TemporaryDirectory(prefix='v51-startup-key-') as private:
            key_dir = Path(private)/'access'
            req, pre, approval, clock, http, store, provider, transport = fake.fixture(key_dir, None if case == 'success' else case)
            bridge = startup.Prepare(provider, transport, key_dir/'identity', root/'startup')
            probe = cloud_fake.Probe(root/'probe', clock)
            result = cloud_runner.Runner(store, provider, probe, root/'run', clock=clock.nanos, wall=clock.wall, startup=bridge).run(req, pre, approval)
            expected = 'PASS' if case == 'success' else 'FAIL'
            m.need(result['status'] == expected and result['cleanup']['status'] == 'PASS' and not http.resources and result['leaseReleased'], 'startup lifecycle '+case)
            m.need(result['retention'] == 'VERIFIED' and (case == 'success' or not probe.cells), 'startup precedes workload/retains failure')
            m.need(all(b.formats <= 1 for b in transport.blocks), 'startup repeated format')
            total, _ = a.inspect_ledger(store.get(a.LEDGER)[1]); m.need(total == approval['maximumCostMicrousd'], 'startup lost charge')
            retained = [key for key in http.objects if '/startup/' in key]
            m.need(any(key.endswith('/receipt.json') for key in retained), 'startup diagnostic retention')
            write_once(root/'http.json', dict(requests=http.requests))
            write_once(root/'blocks.json', [dict(commands=b.commands, formats=b.formats, formatted=b.formatted, mounted=b.attached) for b in transport.blocks])
            row = dict(case=case, status='PASS', observedOutcome=expected, cleanup='PASS', chargedMicrousd=total,
                       formats=sum(b.formats for b in transport.blocks), retainedFiles=len(retained))
            rows.append(row); print(m.canonical(row).decode(), flush=True)
    inputs = [*Path(__file__).parent.glob('guest_*.py'), *Path(__file__).parent.glob('cloud_*.py')]
    receipt = dict(schema='gse-v51-startup-qualification-v1', status='PASS', execution='offline-startup-http-block-model',
        source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
        inputs={p.name:m.sha(p.read_bytes()) for p in sorted(inputs)}, cases=rows,
        paidCloud=False, realSshExecuted=False, realBlockDeviceWritten=False, fullRemoteQualification=False)
    write_once(output/'receipt.json', receipt); return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path); run(p.parse_args().output)
