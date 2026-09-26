"""Real loopback OpenSSH helper delivery; no GCP, sudo, host configuration or disks."""
import argparse
import os
from pathlib import Path
import pwd
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from . import guest_delivery as d, guest_delivery_receiver as r, guest_setup as setup
from . import performance_model as m, remote_command as c
from .guest_transport import ssh_args

ROOT = Path(__file__).resolve().parents[2]


class Server:
    def __init__(self, private, output):
        self.private, self.output = Path(private), Path(output)
        self.process = None; self.log = None
    def __enter__(self):
        self.access = setup.generate(self.private/'client', 'c'*32)
        self.host = setup.generate(self.private/'host', 'd'*32)
        self.user = pwd.getpwuid(os.getuid()).pw_name
        self.known = self.private/'known'; setup.pin(self.known, '123', self.host['publicKey'])
        self.authorized = self.private/'authorized'
        self.authorized.write_text('restrict '+self.access['publicKey']+'\n'); self.authorized.chmod(0o600)
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        # Do not read global sshd_config, edit ~/.ssh, use passwords, or open a public listener.
        config = self.private/'sshd_config'
        config.write_text('\n'.join([
            'ListenAddress 127.0.0.1', 'Port '+str(self.port), 'HostKey '+str(self.private/'host/identity'),
            'PidFile '+str(self.private/'pid'), 'AuthorizedKeysFile '+str(self.authorized),
            'AllowUsers '+self.user, 'AuthenticationMethods publickey', 'PasswordAuthentication no',
            'KbdInteractiveAuthentication no', 'UsePAM no', 'StrictModes yes', 'PermitUserRC no',
            'DisableForwarding yes', 'PermitTTY no', 'PrintMotd no', 'LogLevel VERBOSE'])+'\n')
        daemon = shutil.which('sshd') or '/usr/sbin/sshd'
        self.versions = {}
        for name, executable in (('ssh', 'ssh'), ('sshd', daemon)):
            # Older sshd has no -V. Retain that probe's status, then require the
            # real config check and authenticated exchanges below to succeed.
            version = subprocess.run([executable, '-V'], capture_output=True, timeout=10)
            binary = Path(shutil.which(executable) or executable)
            self.versions[name] = dict(returncode=version.returncode,
                output=(version.stdout+version.stderr).decode().strip()[:1000], binarySha256=m.sha(binary.read_bytes()))
        subprocess.run([daemon, '-t', '-f', str(config)], check=True, capture_output=True, timeout=10)
        self.log = (self.output/'sshd.log').open('xb')
        self.process = subprocess.Popen([daemon, '-D', '-e', '-f', str(config)], stdin=subprocess.DEVNULL,
                                        stdout=self.log, stderr=self.log, start_new_session=True)
        try:
            until = time.monotonic()+10
            while True:
                m.need(self.process.poll() is None, 'qualification sshd exited; inspect sshd.log')
                try:
                    with socket.create_connection(('127.0.0.1', self.port), timeout=.1): break
                except OSError:
                    m.need(time.monotonic() < until, 'qualification sshd startup deadline'); time.sleep(.05)
            return self
        except BaseException:
            self.__exit__(None, None, None); raise
    def __exit__(self, *_):
        if self.process is not None:
            try: os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL); self.process.wait(timeout=5)
        if self.log is not None: self.log.close()
    def endpoint(self, parent, *, clock_offset_nanos=0):
        server = self
        class Loopback(d.Endpoint):
            offline = True
            def argv(self, remote):
                if clock_offset_nanos:
                    # Qualification-only independent epoch, with native Linux boot
                    # identity and unchanged clock rate. No application timer changes.
                    prefix = ('import time\n_original_ns = time.monotonic_ns\n_original = time.monotonic\n'
                              'time.monotonic_ns = lambda: _original_ns() + '+str(clock_offset_nanos)+'\n'
                              'time.monotonic = lambda: _original() + '+repr(clock_offset_nanos/10**9)+'\n')
                    remote = [*remote[:3], prefix+remote[3], *remote[4:]]
                argv = ssh_args(self.target, remote)
                argv = [v if not v.startswith('ProxyCommand=') else 'ProxyCommand=none' for v in argv]
                return [*argv[:-2], '-o', 'Hostname=127.0.0.1', '-p', str(server.port), *argv[-2:]]
        target = dict(project='test-project', zone='us-west4-a', instance='gse-v51-fixture',
                      instanceId='123', user=self.user, key=str(self.private/'client/identity'), knownHosts=str(self.known))
        return Loopback(target, parent, os.getuid())


def run(output):
    output = Path(output).absolute(); output.mkdir(parents=True, exist_ok=False)
    cases = []; source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    raw = d.pack(ROOT, source); (output/'helper.json').write_bytes(raw)
    receipt = dict(schema='gse-v51-ssh-delivery-qualification-v1', status='FAIL', source=source,
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
        helperSha256=m.sha(raw), cases=cases, execution='loopback-openssh-helper-delivery',
        paidCloud=False, realSshExecuted=True, privilegedExecution=False,
        realBlockDeviceWritten=False, fullRemoteQualification=False)
    try:
        # Client/host private keys are outside the artifact tree and always removed.
        with tempfile.TemporaryDirectory(prefix='v51-delivery-keys-', dir=ROOT/'target') as private, Server(private, output) as server:
            receipt['tools'] = server.versions
            binding = c.binding(source, 'b'*64, 'c'*32, 'node-1')
            provider = dict(instanceId='123', diskId='456', attempt='c'*32, node=1)
            value = d.describe(raw, binding, provider, server.access)
            c.write_once(output/'descriptor.json', value)
            def endpoint(name):
                parent = output/name; parent.mkdir(mode=0o700); return server.endpoint(parent)
            good = endpoint('success'); deadline = time.monotonic()+30
            answer = d.deliver(good, value, raw, deadline)
            m.need(answer['state'] == 'SUCCEEDED', 'SSH install failed: '+str(answer))
            m.need(good.exchange('check', value, b'', deadline) == answer, 'installed helper import/check')
            m.need(good.exchange('query', value, b'', deadline) == answer, 'SSH original receipt')
            cases.append(dict(case='success', status='PASS', files=answer['inventory']['files']))
            root = r.location(good.parent,value,os.getuid()); (root/'files/helper.py').write_text('raise RuntimeError("must not execute")\n')
            try: good.exchange('check', value, b'', deadline)
            except ConnectionError as error:
                m.need('delivery installed bytes changed' in str(error), 'changed-helper failure had another cause: '+str(error))
            else: raise ValueError('altered installed helper accepted')
            cases.append(dict(case='changed-installed-helper', status='PASS'))
            for name, offset in (('future-clock-epoch', 10**15), ('earlier-clock-epoch', -time.monotonic_ns()//2)):
                parent = output/name; parent.mkdir(mode=0o700)
                shifted = server.endpoint(parent, clock_offset_nanos=offset); until = time.monotonic()+30
                shifted_answer = d.deliver(shifted, value, raw, until)
                m.need(shifted_answer['state'] == 'SUCCEEDED' and
                       shifted.exchange('query', value, b'', until) == shifted_answer, 'SSH independent clock epoch')
                try: shifted.exchange('query', value, b'', until+1)
                except ValueError as error: m.need('changed' in str(error), 'deadline refusal reason')
                else: raise ValueError('SSH controller deadline renewed')
                cases.append(dict(case=name, status='PASS', clockOffsetNanos=offset, deadline=shifted.budget))
            lost = endpoint('lost-reply'); counts = dict(install=0, query=0)
            class Lost:
                offline = True
                def exchange(self, action, *args):
                    counts[action] += 1
                    result = lost.exchange(action, *args)
                    if action == 'install': raise ConnectionError('injected lost authenticated install reply')
                    return result
            m.need(d.deliver(Lost(), value, raw, time.monotonic()+30)['state'] == 'SUCCEEDED' and
                   counts == dict(install=1, query=1), 'SSH reconnect replayed install')
            cases.append(dict(case='lost-reply', status='PASS', **counts))
            broken = endpoint('truncated')
            broken_deadline = time.monotonic()+30
            answer = broken.exchange('install', value, raw[:-1], broken_deadline)
            m.need(answer['state'] == 'FAILED', 'truncated SSH delivery accepted')
            m.need(broken.exchange('install', value, raw, broken_deadline) == answer, 'partial install retried')
            cases.append(dict(case='truncated-no-reinstall', status='PASS'))
            wrong = endpoint('wrong-host-key')
            pin = Path(private)/'wrong-known'; setup.pin(pin, '123', server.access['publicKey'])
            wrong.target = dict(wrong.target, knownHosts=str(pin))
            try: wrong.exchange('install', value, raw, time.monotonic()+15)
            except ConnectionError as error:
                m.need('Host key verification failed' in str(error), 'wrong-pin failure had another cause: '+str(error))
            else: raise ValueError('wrong SSH host key accepted')
            m.need(not list(Path(wrong.parent).iterdir()), 'wrong pin reached installer')
            cases.append(dict(case='wrong-host-key', status='PASS'))
            unauthorized = endpoint('wrong-client-key')
            unauthorized.target = dict(unauthorized.target, key=str(Path(private)/'host/identity'))
            try: unauthorized.exchange('install', value, raw, time.monotonic()+15)
            except ConnectionError as error:
                m.need('Permission denied (publickey)' in str(error), 'wrong-client failure had another cause: '+str(error))
            else: raise ValueError('unauthorized SSH client accepted')
            m.need(not list(Path(unauthorized.parent).iterdir()), 'wrong client reached installer')
            cases.append(dict(case='wrong-client-key', status='PASS'))
            altered = endpoint('altered-payload')
            bad = raw[:-1]+b' '
            answer = altered.exchange('install', value, bad, time.monotonic()+30)
            m.need(answer['state'] == 'FAILED' and not (r.location(altered.parent,value,os.getuid())/'files').exists(), 'altered payload executed')
            cases.append(dict(case='altered-payload', status='PASS'))
            expired = endpoint('expired')
            try: d.deliver(expired,value,raw,time.monotonic()-1)
            except ValueError: pass
            else: raise ValueError('expired delivery accepted')
            m.need(not list(Path(expired.parent).iterdir()), 'expired delivery reached receiver')
            cases.append(dict(case='expired', status='PASS'))
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error)[:2000]); raise
    finally:
        c.write_once(output/'receipt.json', receipt)
    print(m.canonical(receipt).decode(), flush=True); return receipt


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('output', type=Path); a=p.parse_args()
    def terminate(*_): raise TimeoutError('SSH qualification terminated')
    signal.signal(signal.SIGTERM, terminate); run(a.output)
