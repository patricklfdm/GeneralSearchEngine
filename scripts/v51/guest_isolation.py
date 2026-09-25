"""Linux qualification-only mount views, not a guest security sandbox or GCP disk.

Each command mounts one retained backing directory at the same sealed cell path.
Network/PIDs remain shared. On hosted CI only, explicit sudo can create the mount
namespace before dropping back to the original user; no host mount is modified.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __name__ != '__main__':
    from . import guest_transport as t, performance_model as m, remote_command as c


class Views:
    def __init__(self, root, cell, allow_sudo=False):
        self.root, self.cell = Path(root), Path(cell); self.root.mkdir(parents=True)
        self.parent_namespace = os.readlink('/proc/self/ns/mnt')
        self.prefix = ['unshare', '--user', '--map-root-user', '--mount', '--propagation', 'private']
        probe = subprocess.run([*self.prefix, 'true'], capture_output=True, timeout=10)
        self.sudo = probe.returncode != 0
        m.need(not self.sudo or allow_sudo, 'user mount namespace unavailable; explicit CI sudo option required: '+probe.stderr.decode()[-500:])
        if self.sudo:
            self.prefix = ['sudo', '-n', 'unshare', '--mount', '--propagation', 'private']
            subprocess.run([*self.prefix, 'true'], check=True, timeout=10)
    def args(self, name, command):
        backing = self.root/name; backing.mkdir(exist_ok=True)
        return [*self.prefix, sys.executable, str(Path(__file__).resolve()), str(backing), str(self.cell),
                self.parent_namespace, str(os.getuid()) if self.sudo else '0', str(os.getgid()) if self.sudo else '0',
                *command]
    def execute(self, name, command, data, deadline):
        return t.process(self.args(name, command), data, deadline)
    def client(self, base, config):
        views = self
        class Client(t.Local):
            def args(self, action, *tail):
                return views.args(config['binding']['node'], super().args(action, *tail))
        return Client(base, config)


def prepare(views, packaged, configs, deadline):
    launcher = [sys.executable, '-I', str(packaged/'guest.py'), 'bootstrap']
    raw = views.execute('producer', [*launcher, 'prepare'], m.canonical(configs[0]), deadline)
    answer = m.strict_json(raw); m.need(answer['state'] == 'SUCCEEDED', 'isolated bootstrap preparation')
    exports = answer['result']['bootstrap']; results = []; seals = []
    for config, exported in zip(configs, exports):
        node = config['binding']['node']; m.need(exported['node'] == node, 'isolated bootstrap node order')
        folder = views.root/'producer/agents/node-1/bootstrap'/node
        raw = views.execute(node, [*launcher, 'install', '--input', str(folder), '--digest', exported['descriptorSha256']], m.canonical(config), deadline)
        result = m.strict_json(raw); m.need(result['status'] == 'PASS', 'isolated bootstrap installation'); results.append(result)
        raw = views.execute(node, [*launcher, 'seal'], m.canonical(config), deadline)
        seals.append(m.strict_json(raw))
        # Different backing inodes at identical sealed paths; no neighbouring node
        # storage is available at the paths used by the actual JVM configuration.
        for other in ('node-1', 'node-2', 'node-3'):
            if other != node: m.need(not (views.root/node/other).exists(), 'foreign voter storage distributed')
    m.need(len(results) == len(configs) == len(exports), 'isolated bootstrap member set')
    from .guest_bootstrap import group_identity
    identity = group_identity(seals, configs)
    c.write_once(views.root/'receipt.json', dict(status='PASS', filesystem='independent-mount-views', sudoNamespace=views.sudo, installs=results, localBootstrap=seals, identity=identity))


if __name__ == '__main__':
    # This helper is qualification tooling, excluded from the deployable package.
    p=argparse.ArgumentParser();p.add_argument('backing');p.add_argument('cell');p.add_argument('parent_namespace');p.add_argument('uid',type=int);p.add_argument('gid',type=int);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if os.readlink('/proc/self/ns/mnt') == a.parent_namespace: raise ValueError('mount isolation missing')
    for value in (a.backing,a.cell):
        path=Path(value)
        if not path.is_absolute() or not path.is_dir() or any(q.is_symlink() for q in (path,*path.parents)) or path.stat().st_uid != a.uid:
            raise ValueError('namespace path/owner')
    subprocess.run(['mount','--make-rprivate','/'],check=True,timeout=10)
    subprocess.run(['mount','--bind',a.backing,a.cell],check=True,timeout=10)
    if a.uid != 0:
        os.setgroups([a.gid]);os.setgid(a.gid);os.setuid(a.uid)
    os.execv(a.command[0],a.command)
