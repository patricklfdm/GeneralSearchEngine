"""No credentials: qualify V5.1 controller decisions with retained local diagnostics."""
import argparse
import subprocess
from pathlib import Path
from . import cloud_authority as a, cloud_fake as fake, cloud_runner as runner, performance_model as m
from .remote_command import write_once

CASES = ('success', 'lost-submit', 'query-reconnect', 'partial-create', 'unresolved-create', 'startup-failure',
         'unreachable', 'cancel', 'collection-failure', 'upload-failure', 'readback-failure',
         'completion-failure', 'delete-failure', 'false-delete', 'foreign-owner', 'reused-id',
         'operation-read-failure', 'preparation-overrun', 'cell-overrun')


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True))
    inputs = {path.name: m.sha(path.read_bytes()) for path in sorted(Path(__file__).parent.glob('cloud_*.py'))}
    results = []
    for index, case in enumerate(CASES, 1):
        root = output/case; root.mkdir()
        clock = fake.Clock(); store = fake.Store(case); provider = fake.Provider(store, case)
        probe = fake.Probe(root/'guest', clock, case)
        req, preflight, approval = fake.fixture(source=source, attempt=f'{index:032x}')
        result = runner.Runner(store, provider, probe, root/'run', clock=clock.nanos, wall=clock.wall).run(req, preflight, approval)
        expected = 'PASS' if case in ('success', 'lost-submit', 'query-reconnect') else 'FAIL'
        m.need(result['status'] == expected, 'unexpected controller result: '+case)
        m.need(probe.stopped and probe.submits == (probe.handlers if case != 'unreachable' else 1), 'stop/replay invariant: '+case)
        total, attempts = a.inspect_ledger(store.get(a.LEDGER)[1])
        m.need(total == approval['maximumCostMicrousd'] and len(attempts) == 1, 'lost failed-attempt charge')
        held = store.get(a.LEASE) is not None
        if held:
            waiting = runner.reconcile(store, provider, root/'active-manual', trigger='manual', now=clock.wall())
            m.need(waiting['status'] == 'WAITING', 'manual cleanup bypassed expiry')
        write_once(root/'provider.json', dict(events=provider.events, objects=provider.objects, operations=provider.operations))
        write_once(root/'store.json', {k: (v[0], dict(bytes=len(v[1]), sha256=m.sha(v[1])))
                   if isinstance(v[1], bytes) else v for k, v in store.objects.items()})
        results.append(dict(case=case, expectedOutcome=expected, status='PASS', leaseRetained=held,
                            chargedMicrousd=total, handlers=probe.handlers, submits=probe.submits, queries=probe.queries))
    receipt = dict(schema='gse-v51-cloud-control-qualification-v1', execution=a.EXECUTION, status='PASS',
                   source=source, dirty=dirty, inputs=inputs,
                   engineWorkloadExecuted=False, fullRemoteQualification=False, paidCloud=False, cases=results)
    write_once(output/'receipt.json', receipt)
    print(m.canonical(receipt).decode())
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
