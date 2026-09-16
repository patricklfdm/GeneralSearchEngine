"""Self-contained offline guest helper. Only used inside a freshly owned VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

BASE = Path('/opt/gse-v50')
ROOT = Path('/mnt/gse-v50')
PACKAGE = 'io.github.patricklfdm.generalsearch.'


def check(ok, message):
    if not ok: raise ValueError(message)


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def execute(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=60)
    check(result.returncode == 0, 'guest operation failed: ' + result.stderr[-2000:])
    return result.stdout


def install(archive, expected):
    check(not BASE.exists() and digest(archive) == expected, 'bundle digest/freshness')
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers(); names = [m.name for m in members]
        check(len(names) <= 2000 and len(set(names)) == len(names) and sum(m.size for m in members) <= 128 << 20, 'bundle expansion bound')
        check(all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members), 'unsafe bundle path')
        BASE.mkdir(); stream.extractall(BASE, members=members, filter='data')
    manifest = json.loads((BASE / 'bundle.json').read_bytes())
    check(manifest['schema'] == 'gse-v50-cloud-bundle-v1' and 'execution' not in manifest, 'admission-probe bundle required')
    actual = {str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()} - {'bundle.json'}
    check(actual == set(manifest['files']), 'bundle member set')
    for name, record in manifest['files'].items():
        path = BASE / name
        check(path.stat().st_size == record['bytes'] and digest(path) == record['sha256'], 'bundle member digest')
    ROOT.mkdir(parents=True)
    uid, gid = int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID'])
    os.chown(ROOT, uid, gid)
    return dict(installed=True, bundleSha256=expected, manifest=manifest)


def mount(node, owner, fresh=False):
    check(node in (1, 2, 3), 'disk ordinal')
    device = Path('/dev/disk/by-id/google-gse-data-' + str(node))
    check(device.exists(), 'owned data disk missing')
    target = ROOT / ('volume-' + str(node)); target.mkdir(exist_ok=True)
    label = 'gse' + owner.removeprefix('gse-v50-')
    if fresh:
        result = subprocess.run(['sudo', 'blkid', str(device)], capture_output=True, timeout=10)
        check(result.returncode == 2, 'refusing to format a nonempty or unreadable disk')
        execute(['sudo', 'mkfs.ext4', '-q', '-L', label, device])
    check(execute(['sudo', 'blkid', '-s', 'LABEL', '-o', 'value', device]).strip() == label, 'disk owner label')
    check(execute(['sudo', 'blkid', '-s', 'TYPE', '-o', 'value', device]).strip() == 'ext4', 'filesystem type')
    execute(['sudo', 'mount', '-o', 'defaults', device, target])
    execute(['sudo', 'chown', str(os.getuid()) + ':' + str(os.getgid()), target])
    return json.loads(execute(['findmnt', '-J', '-T', target, '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS,SIZE']))


def java_args(role, node, endpoints):
    workload = json.loads((BASE / 'workload.json').read_bytes())
    control = role in ('measure', 'restore')
    cp = [BASE / ('control.jar' if control else 'core.jar')]
    if not control: cp.append(BASE / 'replication.jar')
    cp.append(BASE / ('classes-control' if control else 'classes-candidate'))
    name = 'admission.V50PerformanceControl' if control else 'admission.V50PerformanceConsumer' if role == 'bootstrap' else 'replication.V50PerformanceWorker'
    args = [str(BASE / 'jre/bin/java'), *workload['jvmArguments'], '-cp', ':'.join(map(str, cp)), PACKAGE + name]
    return args + ([role, str(ROOT), str(BASE / 'workload.json')] if control else [str(ROOT), str(node), endpoints, str(BASE / 'workload.json'), 'volumes'])


def oneshot(role, endpoints):
    args = java_args(role, 0, endpoints)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output, error = proc.communicate(timeout=90)
    finally:
        if proc.poll() is None: proc.kill(); proc.wait(timeout=5)
    check(proc.returncode == 0 and len(output) <= 4 << 20, 'public process failed: ' + error.decode(errors='replace')[-2000:])
    result = dict(result=json.loads(output), process=dict(pid=proc.pid, args=args, exitCode=proc.returncode))
    if role == 'measure':
        result['sourceBackup'] = {str(p.relative_to(ROOT / 'source')): dict(bytes=p.stat().st_size, sha256=digest(p))
                                  for p in sorted((ROOT / 'source').rglob('*')) if p.is_file()}
    return result


def ticks(pid): return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def stop():
    path = ROOT / 'worker.json'
    if not path.exists(): return dict(status='NOT_STARTED')
    receipt = json.loads(path.read_bytes()); pid = receipt['pid']
    if not Path(f'/proc/{pid}').exists(): return dict(status='EXITED', **receipt)
    check(ticks(pid) == receipt['startTicks'], 'refusing reused PID')
    os.kill(pid, signal.SIGKILL)
    return dict(status='KILLED', **receipt)


def collect(node):
    selected = [ROOT / ('volume-' + str(node)) / ('node-' + str(node))]
    if node == 1: selected += [ROOT / 'source', ROOT / 'export', ROOT / 'operation']
    selected += [p for p in ROOT.iterdir() if p.is_file()]
    files = []
    for path in selected:
        if path.is_dir(): files += [p for p in path.rglob('*') if p.is_file()]
        elif path.is_file(): files.append(path)
    check(not any(p.is_symlink() for p in files) and len(files) <= 2000 and
          sum(p.stat().st_size for p in files) <= 128 << 20 and all(p.stat().st_size <= 16 << 20 for p in files), 'guest evidence bound')
    archive = Path('/tmp/gse-v50-evidence.tar.gz')
    with tarfile.open(archive, 'w:gz') as stream:
        for path in sorted(files): stream.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    return dict(archive=str(archive), bytes=archive.stat().st_size, sha256=digest(archive))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'mount', 'unmount', 'facts', 'bootstrap', 'measure', 'restore', 'worker', 'stop', 'collect'])
    parser.add_argument('--node', type=int, default=0); parser.add_argument('--owner'); parser.add_argument('--endpoints', default='')
    parser.add_argument('--archive', type=Path); parser.add_argument('--sha256'); parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    if args.action == 'install': result = install(args.archive, args.sha256)
    elif args.action == 'mount': result = mount(args.node, args.owner, args.fresh)
    elif args.action == 'unmount':
        execute(['sudo', 'umount', ROOT / ('volume-' + str(args.node))]); result = dict(unmounted=args.node)
    elif args.action in ('bootstrap', 'measure', 'restore'): result = oneshot(args.action, args.endpoints)
    elif args.action == 'stop': result = stop()
    elif args.action == 'collect': result = collect(args.node)
    elif args.action == 'facts':
        result = dict(bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            kernel=execute(['uname', '-a']), java=execute([BASE / 'jre/bin/java', '--version']),
            disks=json.loads(execute(['lsblk', '-J', '-b', '-o', 'NAME,SIZE,TYPE,MOUNTPOINTS'])),
            bundle=json.loads((BASE / 'bundle.json').read_bytes()))
        write(ROOT / 'facts.json', result)
    else:
        check(not (ROOT / 'worker.json').exists(), 'worker already started')
        cmd = java_args('worker', args.node, args.endpoints)
        write(ROOT / 'worker.json', dict(pid=os.getpid(), startTicks=ticks(os.getpid()), args=cmd))
        os.execv(cmd[0], cmd)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
