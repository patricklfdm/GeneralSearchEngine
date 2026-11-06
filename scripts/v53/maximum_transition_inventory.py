"""Bounded streaming inventories for large retained copies, never runtime authority."""
import hashlib
import os
from pathlib import Path
import stat
from .membership_model import need

CHUNK = 1024*1024
FILE_LIMIT = 256*1024*1024
MEMBERS = 65536


def identity(value):
    return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink


def inventory(root, *, maximum):
    need(type(maximum) is int and maximum > 0, 'maximum-transition inventory explicit bound')
    root = Path(root); first = root.lstat()
    need(stat.S_ISDIR(first.st_mode), 'maximum-transition inventory root')
    files, directories, observed, total = {}, [], [], 0
    pending = [(root, 0)]
    while pending:
        directory, depth = pending.pop(); before = directory.lstat()
        need(stat.S_ISDIR(before.st_mode) and depth <= 64, 'maximum-transition inventory directory')
        observed.append((directory, identity(before)))
        for path in sorted(directory.iterdir()):
            entry = path.lstat(); name = path.relative_to(root).as_posix()
            need(len(files)+len(directories) < MEMBERS, 'maximum-transition inventory member bound')
            if stat.S_ISDIR(entry.st_mode):
                directories.append(name); pending.append((path, depth+1)); continue
            need(stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1, 'maximum-transition inventory regular member')
            need(entry.st_size <= FILE_LIMIT and total+entry.st_size <= maximum, 'maximum-transition inventory byte bound')
            # No oversized read(maximum+1): even a one-byte file must not request
            # a 128 GiB allocation. Recheck the original file before and after.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(fd, 'rb') as stream:
                need(identity(os.fstat(stream.fileno())) == identity(entry), 'maximum-transition inventory file replaced')
                digest = hashlib.sha256(); size = 0
                while True:
                    chunk = stream.read(CHUNK)
                    if not chunk: break
                    size += len(chunk); need(size <= entry.st_size, 'maximum-transition inventory file grew')
                    digest.update(chunk)
                need(size == entry.st_size and identity(os.fstat(stream.fileno())) == identity(entry) and
                     identity(path.lstat()) == identity(entry), 'maximum-transition inventory file changed')
            files[name] = digest.hexdigest(); total += size
        need(identity(directory.lstat()) == identity(before), 'maximum-transition inventory directory changed')
    need(all(identity(path.lstat()) == saved for path, saved in observed) and identity(root.lstat()) == identity(first),
         'maximum-transition inventory tree changed')
    return dict(files=files, directories=sorted(directories), bytes=total)
