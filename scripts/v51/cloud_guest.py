"""Persistent per-voter guest service; closed commands, durable receipts, no cloud admission."""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from . import cloud_package as package, performance_model as m, remote_command as c
from . import remote_collection as collection, remote_schedule as schedule, remote_schedule_evidence as schedule_evidence
from .guest_jvm import Jvm

EXECUTION = 'local-guest-service-only'
FIELDS = {'schema', 'execution', 'binding', 'packageManifestSha256', 'root', 'mode', 'hosts', 'ports', 'groupId'}


def validate(config):
    m.need(type(config) is dict and set(config) == FIELDS and config['schema'] == 'gse-v51-guest-service-v1' and
           config['execution'] == EXECUTION, 'guest service configuration scope')
    c.validate_binding(config['binding'])
    m.need(re.fullmatch('[0-9a-f]{64}', config['packageManifestSha256']) and config['mode'] in package.MODES, 'guest package/mode')
    root = Path(config['root']); m.need(root.is_absolute() and str(root) == config['root'] and '..' not in root.parts, 'guest root')
    m.need(isinstance(config['hosts'], list) and len(config['hosts']) == 3 and isinstance(config['ports'], list) and len(config['ports']) == 3, 'guest members')
    networks = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8')]
    for host in config['hosts']:
        m.need(isinstance(host, str), 'guest numeric host text')
        address = ipaddress.IPv4Address(host); m.need(any(address in n for n in networks), 'guest host must be private/loopback')
    m.need(all(type(p) is int and 1024 <= p <= 65535 for p in config['ports']) and
           len(set(zip(config['hosts'], config['ports']))) == 3, 'guest distinct endpoints')
    m.need(str(uuid.UUID(config['groupId'])) == config['groupId'], 'guest group identity')
    return root/'agents'/config['binding']['node']


def socket_path(root):
    # Keep Unix paths below Linux's 108-byte limit, even with long retained CI paths.
    folder = Path('/tmp')/('gse-v51-agent-'+m.sha(str(root).encode())[:24])
    return folder/'rpc.sock'


def receive(stream):
    data = b''
    while b'\n' not in data:
        chunk = stream.recv(65536); m.need(chunk, 'guest RPC EOF'); data += chunk
        m.need(len(data) <= c.RESPONSE_BYTES, 'guest RPC byte bound')
    raw, tail = data.split(b'\n', 1); m.need(not tail, 'guest RPC trailing bytes')
    return m.strict_json(raw)


def rpc(root, value, seconds=10):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(seconds); sock.connect(str(socket_path(root)))
        sock.sendall(m.canonical(value)+b'\n'); return receive(sock)


def prepared_config(base, config):
    target = validate(config); manifest = package.verify(base, config['binding']['source'])
    m.need(m.sha((base/'manifest.json').read_bytes()) == config['packageManifestSha256'], 'guest package manifest changed')
    root = Path(config['root']); c.directory(root.parent)
    root.mkdir(exist_ok=True); c.directory(root)
    (root/'agents').mkdir(exist_ok=True); c.directory(root/'agents')
    if not target.exists():
        target.mkdir(mode=0o700); c.write_once(target/'config.json', config)
        c.CommandStore(target/'store', config['binding'], create=True)
    m.need(c.read(target/'config.json') == config, 'guest service configuration changed')
    c.directory(target)
    return target, manifest


def start(base, config):
    root, _ = prepared_config(base, config)
    claim = root/'launch.json'
    if claim.exists(): return dict(state='EXISTS', configSha256=m.sha(m.canonical(config)))
    c.write_once(claim, dict(configSha256=m.sha(m.canonical(config))))  # Claim before process creation.
    with (root/'service.stdout').open('xb') as out, (root/'service.stderr').open('xb') as err:
        proc = subprocess.Popen([sys.executable, '-I', str(base/'guest.py'), 'service', 'serve', str(root/'config.json')],
                                stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
    return dict(state='LAUNCHED', pid=proc.pid, configSha256=m.sha(m.canonical(config)))


class Service:
    def __init__(self, base, config):
        self.base, self.config = base, config
        self.root, _ = prepared_config(base, config)
        self.store = c.CommandStore(self.root/'store', config['binding'])
        self.cell = Path(config['root']); self.node = config['binding']['node']; self.jvm = None
        self.started = time.monotonic(); self.deadline = self.started+5400
        self.plan = base/'source-inputs/docs/v5x/v5.1/phase6-plan.json'
        self.active = None; self.answer = None; self.ack = threading.Event(); self.shutting_down = False

    def java(self, mode, *args): return package.command(self.base, mode, args=list(map(str, args)))

    def oneshot(self, label, args):
        with (self.root/(label+'.stdout')).open('xb') as out, (self.root/(label+'.stderr')).open('xb') as err:
            proc = subprocess.Popen(args, stdout=out, stderr=err)
            try:
                until = min(self.deadline, time.monotonic()+90)
                while proc.poll() is None:
                    m.need(not self.shutting_down and time.monotonic() < until, 'guest setup cancelled/deadline')
                    time.sleep(.05)
            finally:
                if proc.poll() is None: proc.kill(); proc.wait(timeout=5)
        m.need(proc.returncode == 0, 'guest setup process failed: '+label)

    def handler(self, name, payload, checkpoint):
        self.ack.set(); checkpoint(); m.need(not self.shutting_down, 'guest shutting down')
        if name == 'prepare-cell':
            m.need((not payload or payload == {'distribute': True}) and self.node == 'node-1' and self.jvm is None, 'guest prepare role/state')
            for file, text in [('hosts.txt', '\n'.join(self.config['hosts'])+'\n'),
                               ('ports.txt', '\n'.join(map(str, self.config['ports']))+'\n'), ('group-id.txt', self.config['groupId']+'\n')]:
                with (self.cell/file).open('x') as out: out.write(text); out.flush(); os.fsync(out.fileno())
            self.oneshot('seed', self.java(package.MODES[0], self.cell, 'prepare', self.plan, self.cell/'source'))
            if self.config['mode'] != package.MODES[0] and not payload:
                self.oneshot('bootstrap', self.java(self.config['mode'], self.cell, 'setup', self.plan, self.cell/'source'))
            if payload:
                from copy import deepcopy
                from . import guest_bootstrap
                output = self.root/'bootstrap'; output.mkdir()
                exports = []
                for n in range(1, 2 if self.config['mode'] == package.MODES[0] else 4):
                    config = deepcopy(self.config); config['binding']['node'] = 'node-'+str(n)
                    exports.append(guest_bootstrap.export(self.cell, output/config['binding']['node'], config))
                return dict(prepared=True, bootstrap=exports)
            return dict(prepared=True)
        if name == 'start-voter':
            m.need(not payload and self.jvm is None, 'guest voter already started/payload')
            from . import guest_bootstrap
            if (self.cell/guest_bootstrap.CLAIM).exists() or (self.cell/guest_bootstrap.READY).exists() or (self.cell/'.bootstrap-install').exists():
                guest_bootstrap.check_ready(self.cell, self.config, sealed=True)
            local = self.config['mode'] == package.MODES[0]
            m.need(not local or self.node == 'node-1', 'local control belongs to node 1')
            # Every host must use the identical sealed absolute cell path and endpoint bytes.
            m.need((self.cell/'hosts.txt').read_text().splitlines() == self.config['hosts'] and
                   (self.cell/'ports.txt').read_text().splitlines() == list(map(str, self.config['ports'])) and
                   (self.cell/'group-id.txt').read_text().strip() == self.config['groupId'], 'guest prepared topology mismatch')
            node = 'local' if local else self.node
            self.jvm = Jvm(self.java(self.config['mode'], self.cell, 'run' if local else self.node[-1], self.plan, self.cell/'source'),
                           self.cell, node, self.deadline)
            return self.jvm.ready
        if name == 'fault':
            # Only lifecycle control in this batch; no arbitrary argv or mutation replay.
            m.need(self.jvm is not None and set(payload) == {'action'} and payload['action'] in ('status', 'activate'), 'guest control action')
            m.need(payload['action'] != 'activate' or self.config['mode'] == package.MODES[1] and self.node == 'node-1', 'configured activation role')
            return self.jvm.command(payload['action'])
        if name == 'window':
            m.need(self.jvm is not None and set(payload) == {'cell', 'preset', 'window'}, 'guest window fields/state')
            m.need(payload['cell'] == 'healthy' or self.config['mode'] == package.MODES[2], 'guest mode/cell scope')
            specs = schedule.windows(payload['cell'], payload['preset'])
            spec = next((v for v in specs if v['window'] == payload['window']), None); m.need(spec is not None, 'guest frozen window')
            folder = self.root/('window-'+payload['cell']+'-'+payload['window']); folder.mkdir()
            self.jvm.command('configure', window=payload['window'])
            events, lock = [], threading.Lock()
            def emit(row):
                with lock:
                    events.append(row)
                    with (folder/'arrivals.jsonl').open('ab') as out: out.write(m.canonical(row)+b'\n')
            def operation(call):
                answer = self.jvm.command('call', **call)
                return dict(outcome=answer['call']['outcome'], opId=answer['opId'], resultSha256=m.sha(m.canonical(answer)))
            result = schedule.execute_window(payload['cell'], payload['preset'], payload['window'], operation, emit,
                                             lambda: self.shutting_down or self.store.cancelled(self.current))
            c.write_once(folder/'spec.json', spec); c.write_once(folder/'result.json', result)
            validation = schedule_evidence.validate(spec, events, result)
            m.need(result['status'] == 'PASS', 'guest window failed')
            return dict(window=payload['window'], calls=len(result['calls']), validation=validation)
        if name == 'stop-voter':
            m.need(set(payload) == {'forced'} and type(payload['forced']) is bool and self.jvm is not None, 'guest stop state')
            self.jvm.stop(payload['forced']); return dict(stopped=True)
        if name == 'collect':
            m.need(not payload and (self.jvm is None or self.jvm.closed), 'guest collection requires stopped JVM')
            # Only this guest's closed receipts and JVM streams, never a neighbour's authority.
            import shutil
            raw = self.root/'collection'; raw.mkdir()
            shutil.copytree(self.root/'store', raw/'store', ignore=shutil.ignore_patterns(self.current['commandId'], 'executor.lock'))
            if self.jvm is not None:
                for suffix in ('jvm.json', 'exchanges.json', 'stop.json', 'stderr.log'):
                    source = self.cell/(self.jvm.node+'-'+suffix)
                    if source.exists(): shutil.copyfile(source, raw/source.name)
                for source in self.cell.glob(self.jvm.node+'-*.jsonl.gz'):
                    m.need(re.fullmatch(re.escape(self.jvm.node)+r'-(results|trace|samples)(-part[0-9]{4})?\.jsonl\.gz', source.name),
                           'unexpected guest journal member')
                    m.need(source.is_file() and not source.is_symlink(), 'guest journal type')
                    shutil.copyfile(source, raw/source.name)
            for window in sorted(self.root.glob('window-*')): shutil.copytree(window, raw/window.name)
            parts = collection.pack(raw, self.root/'parts', m.sha(m.canonical(self.config['binding'])))
            return parts
        raise ValueError('unimplemented guest command')

    def execute(self, value):
        try: self.answer = self.store.execute(value, self.handler)
        finally: self.ack.set()

    def submit(self, value):
        c.validate_request(value, self.config['binding'])
        previous = self.store.query(value)
        if previous['state'] != 'NOT_FOUND': return previous
        if self.active is not None and self.active.is_alive(): return self.store.envelope(value, 'BUSY')
        self.current, self.answer = value, None; self.ack.clear()
        self.active = threading.Thread(target=self.execute, args=(value,), name='v51-guest-command')
        self.active.start(); m.need(self.ack.wait(5), 'guest claim acknowledgement deadline')
        return self.answer if self.answer is not None else self.store.query(value)

    def serve(self):
        path = socket_path(self.root); path.parent.mkdir(mode=0o700)
        c.directory(path.parent); m.need(path.parent.stat().st_uid == os.getuid(), 'guest socket owner')
        error = None
        with socket.socket(socket.AF_UNIX) as sock:
            sock.bind(str(path)); path.chmod(0o600); sock.listen(4); sock.settimeout(.2)
            c.write_once(self.root/'ready.json', dict(pid=os.getpid(), startTicks=Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                         bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), configSha256=m.sha(m.canonical(self.config))))
            try:
                while not (self.root/'shutdown.json').exists() and time.monotonic() < self.deadline:
                    try: connection, _ = sock.accept()
                    except socket.timeout: continue
                    with connection:
                        connection.settimeout(5)
                        try:
                            _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                            m.need(uid == os.getuid(), 'guest RPC user')
                            value = receive(connection); reply = self.submit(value)
                            connection.sendall(m.canonical(reply)+b'\n')
                        except (BrokenPipeError, ConnectionResetError): pass  # Durable handler outlives the caller.
                        except Exception as failure:
                            try: connection.sendall(m.canonical(dict(error=type(failure).__name__, message=str(failure)[:1000]))+b'\n')
                            except OSError: pass
            except BaseException as failure: error = failure
            finally:
                self.shutting_down = True
                if self.active is not None: self.active.join(timeout=15)
                if self.jvm is not None and not self.jvm.closed:
                    try: self.jvm.stop(forced=True)
                    except BaseException as failure: error = error or failure
                if self.active is not None: self.active.join(timeout=5)
                c.write_once(self.root/'closed.json', dict(status='PASS' if error is None and (self.active is None or not self.active.is_alive()) else 'FAIL',
                    error=str(error) if error else None, jvmStopped=self.jvm is None or self.jvm.closed))
                path.unlink(); path.parent.rmdir()
        if error: raise error


def main(base, argv):
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('start', 'serve', 'query', 'submit', 'cancel', 'shutdown', 'ready', 'part'))
    p.add_argument('config', nargs='?'); p.add_argument('--part'); args = p.parse_args(argv)
    if args.action == 'start': answer = start(base, m.strict_json(sys.stdin.buffer.read(c.REQUEST_BYTES+1)))
    else:
        config = c.read(Path(args.config)); root = validate(config)
        m.need(c.read(root/'config.json') == config, 'guest configuration path/identity')
        if args.action == 'serve':
            def terminate(*_): raise KeyboardInterrupt('guest service terminated')
            signal.signal(signal.SIGTERM, terminate); Service(base, config).serve(); return
        if args.action == 'ready':
            answer = dict(ready=c.read(root/'ready.json') if (root/'ready.json').exists() else None,
                          closed=c.read(root/'closed.json') if (root/'closed.json').exists() else None)
        elif args.action == 'shutdown':
            if not (root/'shutdown.json').exists(): c.write_once(root/'shutdown.json', dict(configSha256=m.sha(m.canonical(config))))
            answer = dict(shutdownRequested=True)
        elif args.action == 'part':
            manifest = c.read(root/'parts/parts.json'); collection.validate_manifest(manifest, m.sha(m.canonical(config['binding'])))
            part = next((v for v in manifest['parts'] if v['name'] == args.part), None); m.need(part is not None, 'guest part identity')
            path = root/'parts'/part['name']; m.need(path.is_file() and not path.is_symlink() and path.stat().st_size == part['bytes'], 'guest part type/size')
            raw = path.read_bytes(); m.need(m.sha(raw) == part['sha256'], 'guest part digest')
            sys.stdout.buffer.write(raw); return
        else:
            value = m.strict_json(sys.stdin.buffer.read(c.REQUEST_BYTES+1)); store = c.CommandStore(root/'store', config['binding'])
            answer = rpc(root, value) if args.action == 'submit' else getattr(store, args.action)(value)
    print(m.canonical(answer).decode(), flush=True)
