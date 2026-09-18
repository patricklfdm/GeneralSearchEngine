"""Owned guest operations for the full workload; no cloud credentials on the guest."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time

# The offline bundle contains the exact reviewed Python inputs as well as Java.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'source-inputs'))
from scripts.v50.cloud_common import canonical, read, require, save
from scripts.v50.cloud_workload_io import inventory, pack, sha_file
from scripts.v50.cloud_collection import archive_parts
from scripts.v50.cloud_workload_plan import PLAN_SHA256, read_plan
from scripts.v50 import cloud_guest, runtime_format, admission_format

SCHEMA = 'gse-v50-remote-workload-bundle-v1'
EXECUTION = 'remote-workload-adapter-only'
PACKAGE = 'io.github.patricklfdm.generalsearch.'


def process_ticks(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def alive(receipt):
    path = Path(f'/proc/{receipt["pid"]}/stat')
    if not path.exists(): return False
    fields = path.read_text().rsplit(')', 1)[1].split()
    require(fields[19] == receipt['startTicks'], 'refusing reused guest PID')
    return fields[0] != 'Z'


class Guest:
    def __init__(self, base, root, owner, *, qualification=False):
        self.base, self.root, self.owner = Path(base).resolve(), Path(root).resolve(), owner
        require(re.fullmatch('gse-v50-[0-9a-f]{12}', owner), 'guest owner identity')
        require(qualification or (self.base == cloud_guest.BASE and self.root == cloud_guest.ROOT), 'guest path boundary')
        self.manifest = read(self.base / 'bundle.json', 16 << 20)
        require(self.manifest['schema'] == SCHEMA and self.manifest['execution'] == EXECUTION and
                self.manifest['workloadPlanSha256'] == PLAN_SHA256, 'remote workload bundle required')
        self.plan = read_plan(self.base / 'workload.json')
        self.qualification = qualification

    def args(self, role, node, endpoints, profile, generation=0, source=0):
        require(profile in ('experiment', 'failure-drill', 'canonical') or
                self.qualification and profile == 'local-qualification', 'guest workload profile')
        require(node in (0, 1, 2, 3), 'guest node')
        control = role in ('measure', 'restore')
        jars = ('control',) if control else ('core', 'replication')
        cp = [self.base / (n + '.jar') for n in jars]
        cp.append(self.base / ('classes-control' if control else 'classes-candidate'))
        name = 'admission.V50CloudWorkloadControl' if control else (
            'replication.V50CloudWorkloadWorker' if role == 'worker' else 'admission.V50CloudWorkloadConsumer')
        args = [str(self.base / 'jre/bin/java'), *self.plan['jvmArguments'], '-cp', ':'.join(map(str, cp)), PACKAGE + name]
        if control: return args + [role, str(self.root), str(self.base / 'workload.json'), profile]
        require(len(endpoints.split(',')) == 3, 'three peer endpoints')
        if role == 'worker':
            require(node in (1, 2, 3) and 1 <= generation <= 32, 'worker generation')
            tail = [str(self.root / 'streams' / f'node-{node}-{generation}')]
        else:
            require(role in ('bootstrap', 'replace'), 'offline operation')
            tail = [role]
            if role == 'replace':
                require((node, source) in ((3, 1), (1, 2)), 'replacement authority source')
                tail += [str(node), str(source)]
        return args + [str(self.root), str(node if role == 'worker' else 0), endpoints,
                       str(self.base / 'workload.json'), *tail, 'volumes']

    def receipt_path(self, node, generation):
        require(node in (1, 2, 3) and 1 <= generation <= 32, 'worker identity')
        return self.root / 'workers' / f'node-{node}-{generation}.json'

    def receipt(self, node, generation):
        value = read(self.receipt_path(node, generation))
        require(value['owner'] == self.owner and value['node'] == node and value['generation'] == generation and
                value['bootId'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'guest process namespace')
        return value

    def worker(self, node, generation, endpoints, profile):
        path = self.receipt_path(node, generation)
        require(not path.exists(), 'worker generation already used')
        self.quiescent(node)
        args = self.args('worker', node, endpoints, profile, generation)
        require(not (self.root / 'streams' / f'node-{node}-{generation}').exists(), 'stream generation already used')
        save(path, dict(owner=self.owner, node=node, generation=generation, pid=os.getpid(),
                        startTicks=process_ticks(os.getpid()), args=args,
                        bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
        os.execv(args[0], args)

    def stop(self, node, generation, barrier=None):
        receipt = self.receipt(node, generation)
        if barrier:
            require(barrier in ('AFTER_ENTRY_QUORUM', 'AFTER_PROOF_QUORUM', 'AFTER_PUBLIC_BACKUP'), 'kill barrier')
            marker = self.root / 'streams' / f'node-{node}-{generation}' / 'barrier'
            deadline = time.monotonic() + 20
            while not marker.exists() and alive(receipt) and time.monotonic() < deadline: time.sleep(.02)
            require(marker.exists() and marker.read_text().splitlines() == [str(receipt['pid']), barrier], 'owned fault barrier')
        killed = alive(receipt)
        if killed: os.kill(receipt['pid'], signal.SIGKILL)
        deadline = time.monotonic() + 10
        while alive(receipt) and time.monotonic() < deadline: time.sleep(.02)
        require(not alive(receipt), 'owned guest process still alive')
        result = dict(receipt, status='KILLED' if killed else 'EXITED', barrier=barrier)
        path=self.root / 'stops' / f'node-{node}-{generation}.json'
        if not path.exists() or killed:save(path, result)
        return result

    def quiescent(self, node):
        for path in (self.root / 'workers').glob(f'node-{node}-*.json'):
            value = read(path)
            require(value['owner'] == self.owner and not alive(value), 'guest worker still running')

    def oneshot(self, role, node, endpoints, profile, source=0):
        self.quiescent(node if role == 'replace' else 1)
        args = self.args(role, node, endpoints, profile, source=source)
        maximum = 900 if role == 'measure' else 120
        directory = self.root / 'guest-processes'; directory.mkdir(exist_ok=True)
        label = role + ('-' + str(node) if role == 'replace' else '')
        out, err = directory / (label + '.stdout'), directory / (label + '.stderr')
        require(not out.exists(), 'oneshot already executed')
        with out.open('xb') as stdout, err.open('xb') as stderr:
            proc = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            try: proc.wait(timeout=maximum)
            finally:
                if proc.poll() is None: proc.kill(); proc.wait(timeout=10)
        require(proc.returncode == 0 and out.stat().st_size <= 4 << 20, 'guest public operation failed: ' + err.read_text()[-2000:])
        result = dict(process=dict(pid=proc.pid, args=args, exitCode=proc.returncode), result=read(out))
        if role == 'measure': result['sourceBackup'] = inventory(self.root / 'source')
        return result

    def capture(self, node, label):
        # Capacity captures run while the command-driven writer is idle between
        # acknowledged operations; other captures require every owned JVM stopped.
        if not label.startswith('capacity-'):self.quiescent(node)
        require(label in ('entry-cut', 'proof-cut', 'lost') or
                node == 1 and re.fullmatch('capacity-(before-[0-2]|after-rejection)', label), 'capture label')
        source = self.root / f'volume-{node}/node-{node}'
        if label == 'lost': target = self.root / f'lost-node-{node}'
        elif label.startswith('capacity-'): target = self.root / 'capacity-sources' / label.removeprefix('capacity-')
        else: target = self.root / 'cuts' / label / f'node-{node}'
        require(not target.exists(), 'capture already exists')
        inventory(source, logical=True); shutil.copytree(source, target)
        return dict(path=target.relative_to(self.root).as_posix(), files=inventory(target, logical=True),
                    report=runtime_format.inspect(target, torn=True))

    def collect(self, node, output):
        self.quiescent(node)
        output = Path(output); require(not output.exists(), 'fresh guest collection')
        selected = [self.root / f'volume-{node}/node-{node}', self.root / f'lost-node-{node}']
        for directory in ('workers', 'stops', 'streams'):
            selected += list((self.root / directory).glob(f'node-{node}-*'))
        selected += list((self.root / 'cuts').glob(f'*/node-{node}'))
        if node == 1:
            selected += [self.root / n for n in ('source', 'export', 'published-after-cut', 'operation',
                'capacity-sources', 'control-streams', 'restore-streams', 'control-measure', 'control-restore')]
        staging = output.with_name(output.name + '-raw'); require(not staging.exists(), 'fresh collection staging'); staging.mkdir(parents=True)
        try:
            for path in selected:
                if not path.exists(): continue
                require(not path.is_symlink(), 'guest evidence symlink')
                dest = staging / path.relative_to(self.root); dest.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir(): inventory(path, logical=True); shutil.copytree(path, dest)
                else: shutil.copyfile(path, dest)
            manifest = pack(staging, output)
            archive = archive_parts(output, output.with_suffix('.zip'))
            return dict(directory=str(output), manifest=manifest, manifestSha256=sha_file(output / 'parts.json'), archive=archive)
        finally: shutil.rmtree(staging)

    def replay(self, endpoints):
        from scripts.v50.cloud_workload_io import rows
        request = next(r['request'] for r in rows(self.root / 'streams/node-1-1/ledger') if r['type'] == 'APPEND')
        ordinal = int(request['recipient'].split('-')[1]); host, port = endpoints.split(',')[ordinal-1].split(':')
        def exact(connection, count):
            value = b''
            while len(value) < count:
                part = connection.recv(count-len(value)); require(part, 'truncated fencing reply'); value += part
            return value
        with socket.create_connection((host, int(port)), timeout=5) as connection:
            connection.sendall(admission_format.framed(admission_format.TYPES.index(request['type'])+1,
                admission_format.canonical(request), magic=b'GSRP'))
            header = exact(connection, 48); length = struct.unpack_from('>i', header, 12)[0]
            require(0 < length <= 1 << 20, 'fencing response bound'); raw = header + exact(connection, length)
        authority = self.root / 'volume-1/node-1'
        genesis = admission_format.genesis((authority / 'genesis.gsr').read_bytes())
        manifest = admission_format.manifest((authority / 'manifest.gsr').read_bytes(), genesis)
        admission_format.wire(raw, manifest)
        response = admission_format.json_value(raw[48:])
        require(response['type'] == 'REJECT' and response['payload']['reason'] == 'STALE_EPOCH', 'stale incarnation accepted')
        return dict(staleRequest=request, staleResponse=response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('worker', 'receipt', 'stop', 'bootstrap', 'replace', 'measure', 'restore',
        'capture', 'collect', 'replay', 'mount', 'unmount', 'facts'))
    parser.add_argument('--base', type=Path, default=cloud_guest.BASE); parser.add_argument('--root', type=Path, default=cloud_guest.ROOT)
    parser.add_argument('--qualification', action='store_true'); parser.add_argument('--owner', required=True)
    parser.add_argument('--node', type=int, default=0); parser.add_argument('--generation', type=int, default=0)
    parser.add_argument('--source', type=int, default=0); parser.add_argument('--endpoints', default='')
    parser.add_argument('--profile', default='canonical'); parser.add_argument('--label'); parser.add_argument('--barrier')
    parser.add_argument('--fresh', action='store_true')
    a = parser.parse_args(); guest = Guest(a.base, a.root, a.owner, qualification=a.qualification)
    if a.action == 'worker': guest.worker(a.node, a.generation, a.endpoints, a.profile); return
    if a.action == 'receipt': result = guest.receipt(a.node, a.generation)
    elif a.action == 'stop': result = guest.stop(a.node, a.generation, a.barrier)
    elif a.action in ('bootstrap', 'replace', 'measure', 'restore'):
        result = guest.oneshot(a.action, a.node, a.endpoints, a.profile, a.source)
    elif a.action == 'capture': result = guest.capture(a.node, a.label)
    elif a.action == 'collect': result = guest.collect(a.node, guest.root / f'collection-{a.node}')
    elif a.action == 'replay': result = guest.replay(a.endpoints)
    elif a.action == 'mount':
        require(not a.qualification, 'qualification has no mount authority'); result = cloud_guest.mount(a.node, a.owner, a.fresh)
    elif a.action == 'unmount':
        require(not a.qualification and a.node in (1, 2, 3), 'unmount ordinal')
        guest.quiescent(a.node); cloud_guest.execute(['sudo', 'umount', guest.root / f'volume-{a.node}']); result = dict(unmounted=a.node)
    else:
        result = dict(bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            java=cloud_guest.execute([guest.base / 'jre/bin/java', '--version']), bundle=guest.manifest,
            qualification=a.qualification)
    sys.stdout.buffer.write(canonical(result) + b'\n')


if __name__ == '__main__': main()
