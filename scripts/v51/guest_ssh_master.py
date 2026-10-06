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
                stderr=subprocess.DEVNULL, start_new_session=True, env=env)
            while not self.path.exists():
                if self.process.poll() is not None: raise ConnectionError('SSH master unavailable')
                if time.monotonic() >= until: raise TimeoutError('SSH master original deadline')
                time.sleep(min(.02, max(0, until-time.monotonic())))
            self.check(until)
        except BaseException:
            self.close(); raise

    def check(self, deadline):
        if not time.monotonic() < deadline <= self.deadline: raise TimeoutError('SSH master original deadline')
        if self.process is None or self.process.poll() is not None or not self.path.exists():
            raise ConnectionError('SSH master closed')
        info = self.path.lstat()
        m.need(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0,
               'SSH master socket ownership')

    def exchange(self, remote, data, deadline, **options):
        import shlex
        try:
            self.check(deadline)
            # OpenSSH normally falls back if a control socket disappears. This
            # explicitly prevents an unnoticed second connection or submission.
            args = [v if not v.startswith('ProxyCommand=') else 'ProxyCommand=false' for v in self.args]
            return transport.process([*args, shlex.join(remote)], data, deadline, env=self.env, **options)
        except BaseException:
            self.close(); raise

    def close(self):
        if self.process is not None:
            try: os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            self.process.wait(timeout=5)
            self.process = None
        self.path.unlink(missing_ok=True)
