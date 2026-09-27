"""Qualification-only chroot in a private mount namespace. Never shipped to guests.

System binaries and proc are read-only binds; only this private fixture filesystem
is writable. The fixture account and metadata are modeled, explicitly separate
from the real namespace-root receiver file operations.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def main():
    root, parent_namespace, owner, group, *command = sys.argv[1:]
    root = Path(root); owner, group = int(owner), int(group)
    if os.getuid() != 0 or os.readlink('/proc/self/ns/mnt') == parent_namespace:
        raise ValueError('isolated root namespace missing')
    if not root.is_absolute() or root.name != 'rootfs' or not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('root fixture path')
    if root.stat().st_uid != owner: raise ValueError('root fixture owner')
    # Validate before elevating ownership of this private fixture tree. A test
    # symlink is never followed by chown; all system bind targets are directories.
    paths = [root, *root.rglob('*')]
    if any(p.lstat().st_uid != owner for p in paths): raise ValueError('root fixture contents')
    mounted = []
    try:
        for p in paths: os.chown(p, 0, 0, follow_symlinks=False)
        for source in ('/usr', '/lib', '/lib64', '/proc', '/dev/null'):
            if not Path(source).exists(): continue
            target = root/source.lstrip('/')
            subprocess.run(['mount', '--rbind', source, str(target)], check=True, timeout=10)
            mounted.append(target)
            # Recursive read-only is required even on hosts with locked nested
            # mounts (for example WSL /usr/lib). A top-level remount is insufficient.
            attrs = (ctypes.c_uint64*4)(1, 0, 0, 0)  # MOUNT_ATTR_RDONLY
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.syscall(442, -100, os.fsencode(target), 0x8000, ctypes.byref(attrs), ctypes.sizeof(attrs)) != 0:
                raise OSError(ctypes.get_errno(), 'recursive read-only mount_setattr')
        result = subprocess.run(['/usr/sbin/chroot', str(root), *command], env=dict(PATH='/usr/bin:/bin',
            SUDO_USER=(root/'account').read_text(), SUDO_UID='1001', SUDO_GID='1001'))
    finally:
        for target in reversed(mounted): subprocess.run(['umount', '--lazy', str(target)], check=True, timeout=10)
        # Hosted CI's explicit sudo fallback returns only this fixture tree to
        # its original owner after unmounting every host bind.
        if owner != 0:
            for p in [*root.rglob('*'), root]: os.chown(p, owner, group, follow_symlinks=False)
    raise SystemExit(result.returncode)


if __name__ == '__main__': main()
