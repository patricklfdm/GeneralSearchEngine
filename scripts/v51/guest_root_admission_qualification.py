"""Offline root observations inside the owned lifecycle; no privileged execution."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from . import cloud_authority as a, cloud_fake, cloud_runner, guest_delivery
from . import guest_root_admission as admission, guest_startup, guest_startup_fake as fake
from . import performance_model as m, remote_command as c

CASES = ('success', 'nonroot', 'metadata-drift', 'writable-parent', 'expired', 'partial-claim')
ROOT = Path(__file__).resolve().parents[2]


class Transport(fake.Transport):
    def __init__(self, clock, provider, store, case):
        super().__init__(clock)
        self.provider, self.store, self.case = provider, store, case
        self.helper = guest_delivery.pack(ROOT, provider.req['source'])

    def prepare(self, facts, target, output, deadline, *, recheck):
        recheck()
        value = admission.plan(self.provider.req, self.store.get(a.LEASE)[1], facts,
                               self.provider.guest_access, self.helper)
        now = self.clock.nanos(); access = value['access']; desc = value['delivery']
        budget = dict(schema='gse-v51-helper-deadline-v1', sample=dict(schema='gse-v51-helper-clock-v1',
            requestSha256=m.sha(m.canonical(desc)), nonce='f'*32, bootId='12345678-1234-1234-1234-123456789abc',
            sampledNanos=now), expiresNanos=int(deadline*10**9))
        account = dict(user=access['user'], uid=1001, gid=1001)
        observed = dict(planSha256=m.sha(m.canonical(value)), bootId=budget['sample']['bootId'],
            ids=dict(uid=0, euid=0, gid=0, egid=0), account=account, invoker=dict(account),
            metadata=dict(instanceId=desc['instanceId'], sshKeys=access['user']+':'+access['publicKey'],
                          blockProjectSshKeys='TRUE', enableOslogin='FALSE'),
            ancestors=[dict(path=p, kind='directory', uid=0, mode=0o755) for p in ('/', '/var', '/var/lib')],
            parent=dict(exists=False), claim=dict(state='ABSENT', planSha256=None, deadlineSha256=None))
        if facts['provider']['node'] == 2:
            if self.case == 'nonroot': observed['ids']['uid'] = 1001
            elif self.case == 'metadata-drift': observed['metadata']['instanceId'] = '999'
            elif self.case == 'writable-parent': observed['ancestors'][2]['mode'] = 0o777
            elif self.case == 'expired': now = budget['expiresNanos']
            elif self.case == 'partial-claim':
                observed['parent'] = dict(exists=True, kind='directory', uid=0, mode=0o700)
                observed['claim']['state'] = 'PARTIAL'
        record = dict(execution=admission.EXECUTION, plan=value, observation=observed, deadline=budget,
                      nowNanos=now, status='FAIL', paidCloud=False, privilegedExecution=False)
        try:
            result = admission.assess(value, observed, budget, now); record['assessment'] = result
            m.need(result['decision'] == 'INSTALL_ONCE', 'root model refuses ambiguous installation')
            record['status'] = 'PASS'
        except Exception as error:
            record['failure'] = dict(type=type(error).__name__, message=str(error)[:2000]); raise
        finally:
            c.write_once(Path(output).with_name('root-'+Path(output).name+'.json'), record)
        # Only the historical fake block backend follows this modeled decision.
        return super().prepare(facts, target, output, deadline, recheck=recheck)


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    for case in CASES:
        directory = output/case; directory.mkdir()
        with tempfile.TemporaryDirectory(prefix='v51-root-model-key-') as private:
            req, pre, approval, clock, http, store, provider, _ = fake.fixture(Path(private)/'key')
            transport = Transport(clock, provider, store, case)
            startup = guest_startup.Prepare(provider, transport, Path(private)/'key/identity', directory/'startup')
            probe = cloud_fake.Probe(directory/'probe', clock)
            result = cloud_runner.Runner(store, provider, probe, directory/'run',
                clock=clock.nanos, wall=clock.wall, startup=startup).run(req, pre, approval)
            expected = 'PASS' if case == 'success' else 'FAIL'
            m.need(result['status'] == expected and result['cleanup']['status'] == 'PASS' and
                   not http.resources and result['leaseReleased'] and result['retention'] == 'VERIFIED', 'root model lifecycle')
            m.need(sum(b.formats for b in transport.blocks) == (3 if case == 'success' else 1) and
                   (case == 'success' or not probe.cells), 'root rejection precedes affected-node format/workload')
            total, _ = a.inspect_ledger(store.get(a.LEDGER)[1])
            m.need(total == approval['maximumCostMicrousd'], 'root model failure lost charge')
            m.need(any(key.endswith('/startup/root-node-2.json') for key in http.objects), 'root admission retention')
            row = dict(case=case, status='PASS', observedOutcome=expected, cleanup='PASS', chargedMicrousd=total,
                       modelFormats=sum(b.formats for b in transport.blocks))
            rows.append(row); print(m.canonical(row).decode(), flush=True)
    result = dict(schema='gse-v51-root-admission-qualification-v1', status='PASS', execution=admission.EXECUTION,
        source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
        inputs={p.name:m.sha(p.read_bytes()) for p in sorted((ROOT/'scripts/v51').glob('guest_*.py'))}, cases=rows,
        paidCloud=False, privilegedExecution=False, realSshExecuted=False, realBlockDeviceWritten=False,
        fullRemoteQualification=False)
    c.write_once(output/'receipt.json', result); return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path); run(p.parse_args().output)
