"""Actual root receiver qualification with isolated filesystem and modeled cloud facts."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from . import guest_root as root, guest_root_admission as admission
from . import guest_delivery as delivery, guest_startup_fake as fake
from . import guest_root_isolation, performance_model as m, remote_command as c


class IsolatedEndpoint(root.Endpoint):
    offline = True

    def __init__(self, target, plan, output, allow_sudo=False):
        super().__init__(target, plan)
        self.output = Path(output); self.output.mkdir(mode=0o700)
        self.fs = self.output/'rootfs'; self.fs.mkdir(mode=0o700)
        for name in ('var', 'var/lib', 'usr', 'lib', 'lib64', 'proc', 'dev', 'etc'):
            (self.fs/name).mkdir(mode=0o755)
        (self.fs/'dev/null').touch(mode=0o600)
        (self.fs/'account').write_text(plan['access']['user'])
        (self.fs/'etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\n'+plan['access']['user']+':x:1001:1001:fixture:/nonexistent:/bin/false\n')
        (self.fs/'etc/group').write_text('root:x:0:\nfixture:x:1001:\n')
        self.parent_namespace = os.readlink('/proc/self/ns/mnt')
        self.prefix = ['unshare', '--user', '--map-root-user', '--mount', '--propagation', 'private']
        probe = subprocess.run([*self.prefix, 'true'], capture_output=True, timeout=10)
        self.sudo = probe.returncode != 0
        m.need(not self.sudo or allow_sudo, 'root qualification needs user namespace or explicit sudo option: '+probe.stderr.decode()[-500:])
        if self.sudo:
            self.prefix = ['sudo', '-n', 'unshare', '--mount', '--propagation', 'private']
            subprocess.run([*self.prefix, 'true'], check=True, timeout=10)
        self.metadata = dict(instanceId=plan['delivery']['instanceId'], sshKeys=plan['access']['user']+':'+plan['access']['publicKey'],
                             blockProjectSshKeys='TRUE', enableOslogin='FALSE')
        self.calls = []; self.kill_after_claim = False

    def argv(self, remote):
        m.need(remote[:10] == ['sudo', '-n', '-u', 'root', '-g', 'root', '--', 'python3', '-I', '-c'], 'qualification root argv')
        self.calls.append(remote[11])
        suffix = "sys.modules['trusted.guest_root_receiver'].main()\n"
        m.need(remote[10].endswith(suffix), 'trusted bootstrap entry')
        # Qualification changes elevation/routing and the metadata producer,
        # with one explicit SIGKILL injection immediately after durable admission.
        # UID/GID, NSS, ancestors, ownership, claims, bytes, clocks and helper run
        # remain the actual receiver implementation inside this private chroot.
        source = remote[10][:-len(suffix)]+"sys.modules['trusted.guest_root_receiver'].metadata=lambda deadline: "+repr(self.metadata)+"\n"
        if self.kill_after_claim:
            source += "sys.modules['trusted.guest_delivery_receiver'].install=lambda *a,**kw: __import__('os').kill(__import__('os').getpid(),9)\n"
        source += suffix
        return [*self.prefix, sys.executable, str(Path(guest_root_isolation.__file__).resolve()), str(self.fs),
                self.parent_namespace, str(os.getuid()) if self.sudo else '0', str(os.getgid()) if self.sudo else '0',
                '/usr/bin/python3', '-I', '-c', source, *remote[11:]]


def fixture(private):
    req, _, _, clock, _, store, provider, _ = fake.fixture(private/'key')
    from . import cloud_authority as a
    lease = a.lease(req, clock.wall())
    generation = store.put(a.LEASE, lease, 0)
    for row in lease['resources']:
        row['attempted'] = True
        generation = store.put(a.LEASE, lease, generation)
        row['id'] = provider.create(row['spec'], clock.nanos()+600*10**9)['id']
        generation = store.put(a.LEASE, lease, generation)
    facts = provider.guest_facts(lease, 1, deadline=clock.seconds()+600)
    helper = delivery.pack(Path(__file__).resolve().parents[2], req['source'])
    plan = admission.plan(req, lease, facts, provider.guest_access, helper)
    return plan, helper


def run(output, allow_sudo=False):
    output = Path(output).absolute(); output.mkdir(parents=True); rows = []
    cases = ('success', 'lost-receipt', 'metadata-drift', 'writable-parent', 'symlink-parent',
             'account-drift', 'partial-claim', 'claim-kill', 'payload-corruption', 'installed-corruption', 'renewed-ticket')
    with tempfile.TemporaryDirectory(prefix='v51-root-qualification-key-') as private:
        plan, helper = fixture(Path(private)); desc = plan['delivery']
        for case in cases:
            endpoint = IsolatedEndpoint(dict(instanceId=desc['instanceId'], user=plan['access']['user']), plan, output/case, allow_sudo)
            deadline = time.monotonic()+30
            destination = endpoint.fs/plan['destination'].lstrip('/')
            if case == 'metadata-drift': endpoint.metadata['instanceId'] = '999'
            elif case == 'writable-parent': (endpoint.fs/'var/lib').chmod(0o777)
            elif case == 'symlink-parent':
                (endpoint.fs/'var/lib/gse-v51-helper').symlink_to('/var')
            elif case == 'account-drift': (endpoint.fs/'etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\n')
            elif case == 'partial-claim':
                destination.parent.mkdir(mode=0o700); destination.with_name(destination.name+'.claim').mkdir(mode=0o700)
            elif case == 'claim-kill': endpoint.kill_after_claim = True
            elif case == 'lost-receipt':
                exchange = endpoint.exchange
                def lose(action, *args):
                    answer = exchange(action, *args)
                    if action == 'install': raise ConnectionError('qualification lost install response')
                    return answer
                endpoint.exchange = lose
            error = None
            try:
                if case == 'partial-claim':
                    answer = endpoint.exchange('install', desc, b'', deadline)
                    m.need(answer['state'] == 'UNCERTAIN' and not destination.exists(), 'partial claim reinstalled')
                elif case == 'claim-kill':
                    m.need(endpoint.exchange('query', desc, b'', deadline)['state'] == 'NOT_FOUND', 'initial claim not empty')
                    try: endpoint.exchange('install', desc, b'', deadline)
                    except ConnectionError: pass
                    else: raise ValueError('root claim crash did not occur')
                    m.need(endpoint.exchange('query', desc, b'', deadline)['state'] == 'UNCERTAIN' and
                           endpoint.exchange('install', desc, b'', deadline)['state'] == 'UNCERTAIN' and
                           (destination.with_name(destination.name+'.claim')/'admission.json').is_file() and not destination.exists(),
                           'killed admission reinstalled')
                elif case == 'payload-corruption':
                    answer = endpoint.exchange('install', desc, b'!'+helper[1:], deadline)
                    m.need(answer['state'] == 'FAILED', 'corrupt payload accepted')
                    m.need(endpoint.exchange('install', desc, b'', deadline) == answer and not (destination/'files').exists(), 'failed claim reused')
                else:
                    answer = delivery.deliver(endpoint, desc, helper, deadline)
                    m.need(answer['state'] == 'SUCCEEDED', 'root install receipt')
                    m.need(endpoint.exchange('check', desc, b'', deadline) == answer, 'root check receipt')
                    if case == 'installed-corruption':
                        (destination/'files/helper.py').write_text('raise Exception("must never execute")')
                        endpoint.exchange('check', desc, b'', deadline)
                    elif case == 'renewed-ticket':
                        endpoint.budget['expiresNanos'] += 1
                        endpoint.exchange('query', desc, b'', deadline)
            except (ValueError, ConnectionError) as failure: error = str(failure)
            expected_failure = case in ('metadata-drift', 'writable-parent', 'symlink-parent', 'account-drift', 'installed-corruption', 'renewed-ticket')
            m.need(bool(error) == expected_failure, 'root qualification outcome '+case+': '+str(error)+'; '+str(endpoint.failures))
            if expected_failure:
                reason = {'metadata-drift':'root metadata identity', 'writable-parent':'root ancestor ownership/mode',
                          'symlink-parent':'root private parent', 'account-drift':'root invoking account missing',
                          'installed-corruption':'delivery installed bytes changed', 'renewed-ticket':'root consumed admission identity'}[case]
                m.need(reason in str(endpoint.failures), 'unrelated failure cannot qualify '+case+': '+str(endpoint.failures))
            if case == 'lost-receipt': m.need(endpoint.calls == ['clock', 'install', 'query', 'check'], 'root install retry after response loss')
            if case in ('metadata-drift', 'writable-parent', 'symlink-parent', 'account-drift'):
                m.need(not destination.exists(), 'root context rejection wrote payload')
            row = dict(case=case, status='PASS', calls=endpoint.calls, rejection=error, sudoNamespace=endpoint.sudo,
                       plan=plan, deadline=endpoint.budget, observations=endpoint.observations, transportFailures=endpoint.failures)
            c.write_once(output/case/'receipt.json', row); rows.append(dict(case=case, status='PASS'))
            print(m.canonical(rows[-1]).decode(), flush=True)
    lifecycle = run_lifecycle(output/'lifecycle', allow_sudo)
    receipt = dict(schema='gse-v51-isolated-root-qualification-v1', status='PASS', cases=rows, lifecycle=lifecycle,
        execution='isolated-root-receiver', namespaceRootExecuted=True, metadataAndAccount='modeled-fixtures',
        realSshExecuted=False, paidCloud=False, realBlockDeviceWritten=False, nativeWritesEnabled=False, fullRemoteQualification=False,
        source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
        inputs={p.name:m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('guest_*.py'))})
    c.write_once(output/'receipt.json', receipt); return receipt


def run_lifecycle(output, allow_sudo):
    from . import cloud_authority as a, cloud_fake, cloud_runner, guest_startup
    output.mkdir(); rows = []
    for case in ('success', 'metadata-drift', 'lost-receipt'):
        folder = output/case; folder.mkdir(); (folder/'guests').mkdir()
        with tempfile.TemporaryDirectory(prefix='v51-root-controller-key-') as private:
            key = Path(private)/'key'
            req, pre, approval, clock, http, store, provider, volume = fake.fixture(key)
            # Use the host monotonic origin for actual subprocess deadlines;
            # modeled workload sleeps still advance only the fake clock.
            clock.now = start = time.monotonic_ns()
            clock.wall = lambda: 10001+(clock.now-start)//10**9
            def endpoint_factory(target, plan):
                endpoint = IsolatedEndpoint(target, plan, folder/'guests'/plan['delivery']['binding']['node'], allow_sudo)
                if plan['delivery']['binding']['node'] == 'node-2':
                    if case == 'metadata-drift': endpoint.metadata['instanceId'] = '999'
                    if case == 'lost-receipt':
                        exchange = endpoint.exchange
                        def lose(action, *args):
                            answer = exchange(action, *args)
                            if action == 'install': raise ConnectionError('qualification lost install response')
                            return answer
                        endpoint.exchange = lose
                return endpoint
            transport = root.Transport(provider, lambda:store.get(a.LEASE)[1], volume, endpoint_factory)
            startup = guest_startup.Prepare(provider, transport, key/'identity', folder/'startup')
            probe = cloud_fake.Probe(folder/'probe', clock)
            result = cloud_runner.Runner(store, provider, probe, folder/'run', clock=clock.nanos, wall=clock.wall,
                                         startup=startup).run(req, pre, approval)
            expected = 'FAIL' if case == 'metadata-drift' else 'PASS'
            m.need(result['status'] == expected and result['cleanup']['status'] == 'PASS' and result['leaseReleased'] and
                   result['retention'] == 'VERIFIED' and not http.resources, 'isolated root controller lifecycle '+str(result))
            formats = sum(b.formats for b in volume.blocks)
            m.need(formats == (1 if expected == 'FAIL' else 3) and (expected == 'PASS' or not probe.cells), 'root precedes model format/workload')
            total, _ = a.inspect_ledger(store.get(a.LEDGER)[1]); m.need(total == approval['maximumCostMicrousd'], 'root failure lost charge')
            retained = [key for key in http.objects if key.endswith('/startup/root-node-2.json')]
            m.need(len(retained) == 1, 'root startup diagnostics not retained')
            record = c.read(folder/'startup/root-node-2.json')
            if expected == 'FAIL': m.need('root metadata identity' in str(record['transportFailures']), 'unrelated lifecycle failure')
            if case == 'lost-receipt': m.need([o['action'] for o in record['observations']] == ['clock', 'install', 'query', 'check'], 'lifecycle repeated install')
            row = dict(case=case, status='PASS', observedOutcome=expected, cleanup='PASS', chargedMicrousd=total, modelFormats=formats)
            c.write_once(folder/'receipt.json', row); rows.append(row); print(m.canonical(dict(lifecycle=row)).decode(), flush=True)
    return rows


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output'); p.add_argument('--allow-sudo-namespace', action='store_true')
    args = p.parse_args(); run(args.output, args.allow_sudo_namespace)
