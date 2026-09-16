"""Public probe over three persistent private SSH streams; controller timestamps only."""
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import time
import zipfile
from .cloud_bundle import extract
from .cloud_common import ROOT, canonical, plan, read, require, save, sha
from .cloud_guest import BASE, ROOT as GUEST_ROOT
from .performance_evidence import inventory, validate
from .performance_model import summary


def now(): return time.monotonic_ns()


class Worker:
    def __init__(self, probe, instance):
        self.probe, self.instance = probe, instance
        self.path = probe.root / 'members' / ('node-' + str(instance['node']) + '.json')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stderr = self.path.with_suffix('.stderr').open('wb'); self.buffer = b''
        self.receipt = dict(schema='gse-v50-performance-member-v1', node='node-' + str(instance['node']),
            startedNanos=now(), exchanges=[], args=probe.args('worker', instance['node']), instanceId=instance['id'])
        args = probe.guest_args('worker', instance['node'])
        self.process = subprocess.Popen([*probe.backend.ssh_args(instance), '--command=' + shlex.join(args)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        probe.workers.append(self)
        save(self.path, self.receipt)
        ready = self.receive()
        require(ready['ready'] is True and ready['node'] == self.receipt['node'], 'remote worker readiness')
        self.receipt.update(ready=ready, pid=ready['identity']['pid'], readyNanos=now())
        # PID is remote, and may coincide with a PID on another VM. The VM ID and
        # boot ID in hosts.json provide its namespace; never compare remote clocks.
        self.receipt['linuxStartTicks'] = '0'  # Replaced with the actual retained guest receipt at collection.
        save(self.path, self.receipt)

    def receive(self):
        deadline = time.monotonic() + 40
        while b'\n' not in self.buffer:
            seconds = deadline - time.monotonic()
            require(seconds > 0 and select.select([self.process.stdout], [], [], max(0, seconds))[0], 'unreachable member/response timeout')
            data = os.read(self.process.stdout.fileno(), 65536)
            require(data, 'remote JVM/SSH stream exited'); self.buffer += data
            require(len(self.buffer) <= 4 << 20, 'guest response bound')
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def command(self, name, accepted=True, **values):
        request = dict(command=name, **values); exchange = dict(sentNanos=now(), request=request)
        self.receipt['exchanges'].append(exchange); save(self.path, self.receipt)
        self.process.stdin.write(canonical(request) + b'\n'); self.process.stdin.flush()
        result = self.receive(); exchange.update(receivedNanos=now(), response=result); save(self.path, self.receipt)
        require(result['command'] == name and result['accepted'] is accepted, 'public command failed: ' + name)
        return result

    def close(self, failed=False):
        if 'finishedNanos' in self.receipt: return
        try:
            if not failed and self.process.poll() is None: self.command('close')
            if failed and self.process.poll() is None: self.process.terminate()
            self.process.wait(timeout=10)
        finally:
            if self.process.poll() is None: self.process.kill(); self.process.wait(timeout=5)
            self.receipt.update(finishedNanos=now(), exitCode=self.process.returncode, cleanup='reaped', forced=failed)
            save(self.path, self.receipt)
            self.stderr.close(); self.process.stdin.close(); self.process.stdout.close()
        require(failed or self.process.returncode == 0, 'remote worker exit')


class Probe:
    def __init__(self, backend, bundle, workspace, content=None):
        self.backend, self.bundle = backend, Path(bundle)
        self.root = Path(workspace) / 'runtime'; self.root.mkdir(parents=True)
        self.plan = read(ROOT / backend.plan['workloadPlan']); self.workers = []; self.hosts = []
        self.started = now(); self.endpoints = ''; self.completed = False
        self.content = Path(content) if content else self.bundle.parent / 'bundle'
        self.manifest = read(self.content / 'bundle.json', 16 << 20)
        shutil.copyfile(self.content / 'workload.json', self.root / 'plan.json')
        (self.root / 'artifacts').mkdir()
        for name in ('core', 'replication', 'control'): shutil.copyfile(self.content / (name + '.jar'), self.root / 'artifacts' / (name + '.jar'))
        with zipfile.ZipFile(self.root / 'source-inputs.zip', 'w', zipfile.ZIP_DEFLATED) as stream:
            for name in self.manifest['inputs']: stream.write(self.content / 'source-inputs' / name, name)
        self.metadata = dict(head=backend.request['source'], dirty=self.manifest['dirty'], inputs=self.manifest['inputs'],
            execution='gcp-public-admission-probe-only', javaExecutable=str(BASE / 'jre/bin/java'),
            jars={n: dict(path=str(BASE / (n + '.jar')), sha256=self.manifest['jars'][n]) for n in ('core', 'replication', 'control')},
            maven=subprocess.check_output([str(ROOT / 'mvnw'), '--version'], text=True),
            runnerPlanSha256=sha(canonical(backend.plan)))

    def guest_args(self, action, node=0, **values):
        args = ['python3', str(BASE / 'guest.py'), action, '--node', str(node), '--owner', self.backend.request['owner'], '--endpoints', self.endpoints]
        for name, value in values.items():
            args += ['--' + name.replace('_', '-')] + ([] if value is True else [str(value)])
        return args

    def guest(self, instance, action, **values):
        return self.backend.ssh(instance, self.guest_args(action, instance['node'], **values))

    def args(self, role, node=0):
        # Same pure argument construction as the guest, without reading its filesystem.
        control = role in ('measure', 'restore')
        cp = [str(BASE / (n + '.jar')) for n in (('control',) if control else ('core', 'replication'))]
        cp.append(str(BASE / ('classes-control' if control else 'classes-candidate')))
        name = 'admission.V50PerformanceControl' if control else 'replication.V50PerformanceWorker'
        tail = [role, str(GUEST_ROOT), str(BASE / 'workload.json')] if control else [str(GUEST_ROOT), str(node), self.endpoints, str(BASE / 'workload.json'), 'volumes']
        return [str(BASE / 'jre/bin/java'), *self.plan['jvmArguments'], '-cp', ':'.join(cp), 'io.github.patricklfdm.generalsearch.' + name, *tail]

    def prepare(self, instance):
        deadline = time.monotonic() + 120
        while True:
            try:
                self.backend.ssh(instance, ['python3', '-c', 'print("{}")'], timeout=15); break
            except Exception:
                if time.monotonic() >= deadline: raise
                time.sleep(2)
        self.backend.copy(instance, self.bundle, '/tmp/gse-v50-bundle.tar.gz')
        self.backend.copy(instance, self.content / 'guest.py', '/tmp/gse-v50-guest.py')
        result = self.backend.ssh(instance, ['sudo', 'python3', '/tmp/gse-v50-guest.py', 'install', '--archive', '/tmp/gse-v50-bundle.tar.gz',
            '--sha256', self.backend.request['bundleSha256']])
        require(result['manifest'] == self.manifest, 'guest bundle identity')
        facts = self.guest(instance, 'facts')
        self.hosts.append(dict(instance=instance, facts=facts, distribution=result))

    def control(self, role):
        start = now(); receipt = self.guest(self.hosts[0]['instance'], role)
        receipt['process'].update(startedNanos=start, finishedNanos=now())
        label = 'control-' + role
        save(self.root / 'processes' / (label + '.json'), receipt['process'])
        save(self.root / 'processes' / (label + '.stdout'), receipt['result'])
        save(self.root / ('control.json' if role == 'measure' else 'restore.json'), receipt)
        return receipt

    def bootstrap(self, instance):
        self.endpoints = ','.join(h['instance']['observation']['networkInterfaces'][0]['networkIP'] + ':' + str(self.backend.plan['port']) for h in self.hosts)
        self.control_result = self.control('measure')
        for node in (1, 2, 3):
            mount = self.backend.ssh(instance, self.guest_args('mount', node, fresh=True))
            self.hosts[node - 1]['initialMount'] = mount
        self.guest(instance, 'bootstrap')

    def unmount(self, instance, disk):
        self.backend.ssh(instance, self.guest_args('unmount', disk['node']))

    def start(self, instance):
        if instance['node'] != 1: self.hosts[instance['node'] - 1]['runtimeMount'] = self.guest(instance, 'mount')
        self.hosts[instance['node'] - 1]['facts'] = self.guest(instance, 'facts')
        Worker(self, instance)

    def exercise(self):
        leader, second, third = self.workers
        leader.command('activate')
        measured = [leader.command('measure', window='warmup', firstCycle=0, cycles=1)['measurement']]
        cycle = 1
        for name in self.plan['localSmoke']['windows']:
            for worker in self.workers: worker.command('configure', window=name, enabled=name.startswith('instrumented'))
            measured.append(leader.command('measure', window=name, firstCycle=cycle, cycles=2)['measurement'])
            for worker in self.workers: worker.command('telemetry')
            cycle += 2
        for worker in self.workers: worker.command('configure', window='disabled', enabled=False)
        semantic = leader.command('semantic')['semantic']
        for peer in ('node-2', 'node-3'): leader.command('catchup', peer=peer)
        for worker in self.workers: worker.command('checkpoint')
        leader.command('backup'); second.close(); third.close()
        leader.command('no-quorum', accepted=False)
        require(leader.command('semantic')['semantic'] == semantic, 'failed write changed committed state')
        leader.close(); self.control('restore')
        save(self.root / 'measurements.json', summary(measured, self.control_result['result']['windows']))
        self.completed = True

    def stop(self, instance):
        worker = next((w for w in self.workers if w.instance['id'] == instance['id']), None)
        if worker is not None: worker.close(failed=not self.completed)
        result = self.guest(instance, 'stop')
        save(self.root / ('stop-' + str(instance['node']) + '.json'), result)

    def collect(self, instance, target):
        receipt = self.guest(instance, 'collect')
        require(0 < receipt['bytes'] <= 128 << 20, 'guest archive bound')
        archive = self.root / ('guest-' + str(instance['node']) + '.tar.gz')
        self.backend.copy(instance, receipt['archive'], archive, download=True)
        require(archive.stat().st_size == receipt['bytes'] and sha(archive.read_bytes()) == receipt['sha256'], 'guest evidence transfer')
        extract(archive, target); archive.unlink()
        node = instance['node']; retained = target / ('volume-' + str(node)) / ('node-' + str(node))
        if retained.exists(): shutil.copytree(retained, self.root / ('node-' + str(node)))
        if node == 1:
            for name in ('source', 'export'):
                if (target / name).exists(): shutil.copytree(target / name, self.root / name)
        member = self.root / 'members' / ('node-' + str(node) + '.json')
        if member.exists() and (target / 'worker.json').exists():
            record = read(member); guest = read(target / 'worker.json')
            require(record['pid'] == guest['pid'] and record['args'] == guest['args'], 'retained worker identity')
            record['linuxStartTicks'] = guest['startTicks']; save(member, record)

    def validate(self, workspace):
        require(self.completed and len(self.hosts) == 3, 'incomplete public cloud probe')
        self.metadata.update(bootId=self.hosts[0]['facts']['bootId'], filesystem=self.hosts[0]['initialMount'], sourceBackup=self.control_result['sourceBackup'])
        save(self.root / 'metadata.json', self.metadata)
        save(self.root / 'hosts.json', dict(schema='gse-v50-cloud-hosts-v1', plan=self.backend.plan, request=self.backend.request, hosts=self.hosts))
        save(self.root / 'set.json', dict(schema='gse-v50-cloud-probe-v1', execution='gcp-public-admission-probe-only',
            preset=self.backend.plan['preset'], protocol=self.plan['protocol'], planSha256=sha((self.root / 'plan.json').read_bytes()),
            startedNanos=self.started, finishedNanos=now(), members=['node-1', 'node-2', 'node-3'], files=inventory(self.root)))
        return validate(self.root, ROOT / self.backend.plan['workloadPlan'], cloud=True)
