"""Private, foreground OpenSSH master for one already pinned guest.

Each channel is submitted once. A broken master cannot silently fall back to a
new network connection; the caller may reconnect only for its next operation.
"""
import os
from pathlib import Path
import signal
import stat
import subprocess
import time
from . import guest_transport as transport, performance_model as m


class Master:
    def __init__(self, args, root, deadline, env, *, connect_deadline=None):
        self.path = Path(root)/'socket'
        self.deadline, self.env = deadline, env
        self.process = None
        self.diagnostics = bytearray()
        until = min(deadline,connect_deadline if connect_deadline is not None else deadline)
        if time.monotonic()>=until: raise TimeoutError('SSH master original deadline')
        m.need(len(os.fsencode(self.path)) < 100 and not self.path.exists(), 'SSH private socket path')
        # args was constructed by ssh_args(target, []), including the exact
        # private key, pinned host alias and isolated IAP credential file.
        m.need(args[-1] == '' and 'ControlMaster=no' in args and 'ControlPath=none' in args,
               'SSH master original arguments')
        self.args = [v if v != 'ControlPath=none' else 'ControlPath='+str(self.path) for v in args[:-1]]
        master = [v if v != 'ControlMaster=no' else 'ControlMaster=yes' for v in self.args]
        master = [*master[:-1], '-o', 'ControlPersist=no', '-N', master[-1]]
        try:
            self.process = subprocess.Popen(master, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, start_new_session=True, env=env)
            os.set_blocking(self.process.stderr.fileno(), False)
            while not self.path.exists():
                self.drain()
                if self.process.poll() is not None: raise self.failure()
                if time.monotonic() >= until: raise TimeoutError('SSH master original deadline')
                time.sleep(min(.02, max(0, until-time.monotonic())))
            self.check(until)
        except BaseException:
            self.close(); raise

    def check(self, deadline):
        if not time.monotonic() < deadline <= self.deadline: raise TimeoutError('SSH master original deadline')
        self.drain()
        if self.process is not None and self.process.poll() is not None: raise self.failure()
        if self.process is None or not self.path.exists(): raise transport.ProcessError('SSH_MASTER_CLOSED')
        info = self.path.lstat()
        m.need(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0,
               'SSH master socket ownership')

    def drain(self):
        if self.process is None: return
        while True:
            try: chunk = os.read(self.process.stderr.fileno(),4096)
            except BlockingIOError: break
            if not chunk: break
            self.diagnostics.extend(chunk)
            m.need(len(self.diagnostics)<=65536,'SSH master diagnostic bound')

    def failure(self):
        self.drain()
        code = self.process.poll() if self.process is not None else None
        if code == 0: return transport.ProcessError('SSH_MASTER_CLOSED')
        return transport.exit_error(255,bytes(self.diagnostics),ssh=True)

    def exchange(self, remote, data, deadline, **options):
        import shlex
        try:
            self.check(deadline)
            # OpenSSH normally falls back if a control socket disappears. This
            # explicitly prevents an unnoticed second connection or submission.
            args = [v if not v.startswith('ProxyCommand=') else 'ProxyCommand=false' for v in self.args]
            return transport.process([*args, shlex.join(remote)], data, deadline, env=self.env, **options)
        except transport.ProcessError as error:
            # A multiplexed channel may only report a closed connection. Prefer
            # a terminal authentication/host error from its private master.
            try:
                self.drain()
                detail = transport.exit_error(255,bytes(self.diagnostics),ssh=True)
            finally: self.close()
            if detail.code in ('SSH_HOST_KEY','SSH_AUTHENTICATION','IAP_PERMISSION'): raise detail from None
            raise error from None
        except BaseException:
            self.close(); raise

    def close(self):
        if self.process is not None:
            try: os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            self.process.wait(timeout=5)
            self.process.stderr.close()
            self.process = None
        self.diagnostics.clear()
        self.path.unlink(missing_ok=True)
