"""Bounded subprocess/SSH envelope transport. Submit once; reconnect only to query."""
import os
from pathlib import Path
import re
import selectors
import shlex
import signal
import subprocess
import sys
import time
from . import cloud_guest as guest, performance_model as m, remote_command as c


def process(args, data, deadline, maximum=c.RESPONSE_BYTES):
    m.need(isinstance(data, bytes) and len(data) <= c.REQUEST_BYTES and time.monotonic() < deadline, 'guest transport request/deadline')
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    out, err, cursor = bytearray(), bytearray(), 0
    succeeded = False
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (proc.stdin, proc.stdout, proc.stderr): os.set_blocking(stream.fileno(), False)
            if data: selector.register(proc.stdin, selectors.EVENT_WRITE, 'input')
            else: proc.stdin.close()
            selector.register(proc.stdout, selectors.EVENT_READ, 'output'); selector.register(proc.stderr, selectors.EVENT_READ, 'error')
            while selector.get_map():
                left = deadline-time.monotonic()
                if left <= 0: raise TimeoutError('guest transport original deadline')
                events = selector.select(min(left, .5))
                for key, _ in events:
                    if key.data == 'input':
                        cursor += os.write(key.fileobj.fileno(), data[cursor:cursor+16384])
                        if cursor == len(data): selector.unregister(key.fileobj); key.fileobj.close()
                    else:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk: selector.unregister(key.fileobj); key.fileobj.close(); continue
                        target = out if key.data == 'output' else err; target.extend(chunk)
                        m.need(len(target) <= (maximum if target is out else 65536), 'guest transport response/diagnostic bound')
            proc.wait(timeout=max(.001, deadline-time.monotonic()))
            if proc.returncode: raise ConnectionError('guest transport failed; inspect retained guest receipts: '+err.decode(errors='replace')[-1500:])
            m.need(time.monotonic() <= deadline, 'late guest transport result')
            succeeded = True
            return bytes(out)
    finally:
        if not succeeded:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        if proc.poll() is None: proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if not stream.closed: stream.close()


class Local:
    """Actual packaged CLI over a fresh process connection for each control envelope."""
    offline = True
    def __init__(self, base, config): self.base, self.config = Path(base), config; self.root = guest.validate(config)
    def args(self, action, *tail):
        return [sys.executable, '-I', str(self.base/'guest.py'), 'service', action,
                *([] if action == 'start' else [str(self.root/'config.json')]), *tail]
    def exchange(self, action, value, deadline, *tail, binary=False, maximum=c.RESPONSE_BYTES):
        data = m.canonical(value) if value is not None else b''
        raw = process(self.args(action, *tail), data, deadline, maximum)
        return raw if binary else m.strict_json(raw)
    def start(self, deadline): return self.exchange('start', self.config, deadline)
    def submit(self, value, deadline): return self.exchange('submit', value, deadline)
    def query(self, value, deadline): return self.exchange('query', value, deadline)
    def cancel(self, value, deadline): return self.exchange('cancel', value, deadline)
    def ready(self, deadline): return self.exchange('ready', None, deadline)
    def shutdown(self, deadline): return self.exchange('shutdown', None, deadline)
    def part(self, name, maximum, deadline): return self.exchange('part', None, deadline, '--part', name, binary=True, maximum=maximum)


def ssh_args(target, remote):
    m.need(set(target) == {'project', 'zone', 'instance', 'instanceId', 'user', 'key', 'knownHosts'}, 'SSH target fields')
    for name in ('project', 'zone', 'instance', 'user'):
        m.need(isinstance(target[name], str) and re.fullmatch('[a-z][a-z0-9-]{0,62}', target[name]), 'SSH target '+name)
    m.need(re.fullmatch('[1-9][0-9]{0,19}', target['instanceId']), 'SSH exact instance ID')
    key, known = Path(target['key']), Path(target['knownHosts'])
    for path in (key, known):
        m.need(path.is_absolute() and path.is_file() and not path.is_symlink() and
               path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0, 'SSH owned credential file')
    alias = 'gse-v51-'+target['instanceId']
    pins = known.read_text().strip().splitlines()
    m.need(len(pins) == 1 and re.fullmatch(re.escape(alias)+r' ssh-ed25519 [A-Za-z0-9+/]+={0,2}', pins[0]), 'SSH exact pinned host key')
    proxy = shlex.join(['gcloud', 'compute', 'start-iap-tunnel', target['instance'], '22', '--listen-on-stdin',
                        '--project='+target['project'], '--zone='+target['zone'], '--verbosity=error'])
    return ['ssh', '-F', '/dev/null', '-T', '-i', str(key), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile='+str(known), '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'HostKeyAlias='+alias, '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
            '-o', 'ProxyCommand='+proxy, target['user']+'@'+target['instance'], shlex.join(remote)]


class Ssh(Local):
    offline = False
    def __init__(self, base, config, target): super().__init__(base, config); self.target = target
    def args(self, action, *tail):
        local = super().args(action, *tail)
        return ssh_args(self.target, ['python3', *local[1:]])
    def exchange(self, *args, **kwargs):
        raise ValueError('live SSH execution disabled pending trusted host setup and paid admission')
