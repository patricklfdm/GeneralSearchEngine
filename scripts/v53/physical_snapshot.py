"""Checked original-file views for explicit segmented-backup physical replay.

No snapshot payload is cached. Each view checks the complete bounded tree up
front, then pins identities and hashes for subsequent exact-byte reads. This
uses the existing per-owner physical limits, not the whole-original allowance.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from .membership_model import need
from . import replica_capture_limits as replica_limits

FILE_BYTES = 64 * 1024**2
TOTAL_BYTES = 512 * 1024**2
MEMBERS = 256
DEPTH = 4
BLOCK = 1024**2


@dataclass(frozen=True)
class Limits:
    total_bytes: int
    members: int
    depth: int

    def __post_init__(self):
        for value, minimum, maximum in ((self.total_bytes, 1, 128*1024**3), (self.members, 1, 65536), (self.depth, 0, 64)):
            need(type(value) is int and minimum <= value <= maximum, 'physical snapshot explicit limits')


def identity(path, *, directory=False):
    value = path.lstat()
    need(stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode) and value.st_nlink == 1,
         'physical snapshot ' + ('directory' if directory else 'regular file'))
    return key(value)


def key(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)


class Snapshot(Mapping):
    def __init__(self, root, *, limits=None):
        self.limits = Limits(TOTAL_BYTES, MEMBERS, DEPTH) if limits is None else limits
        need(type(self.limits) is Limits, 'physical snapshot explicit limits')
        self.root = Path(root)
        self._directories = {self.root:identity(self.root, directory=True)}
        self._entries = {}; self._hashes = {}; self._children = {}; self.total_bytes = 0
        pending = [(self.root, 0)]
        while pending:
            directory, depth = pending.pop()
            need(depth <= self.limits.depth, 'physical snapshot directory depth')
            children = set()
            for path in directory.iterdir():
                need(len(self._entries) < self.limits.members, 'physical snapshot member capacity')
                children.add(path.name)
                value = path.lstat(); name = path.relative_to(self.root).as_posix()
                if stat.S_ISDIR(value.st_mode):
                    self._directories[path] = key(value); self._entries[name] = None
                    pending.append((path, depth+1)); continue
                need(stat.S_ISREG(value.st_mode) and value.st_nlink == 1, 'physical snapshot regular file')
                self.total_bytes += value.st_size
                need(value.st_size <= FILE_BYTES and self.total_bytes <= self.limits.total_bytes, 'physical snapshot byte capacity')
                self._entries[name] = key(value)
            self._children[directory] = frozenset(children)
        self._entries = dict(sorted(self._entries.items()))
        # Reject an invalid late member before opening any payload; then hash
        # every file, including files a subsequent semantic projection omits.
        self._check_tree()
        for name, saved in self._entries.items():
            if saved is not None:
                self._hashes[name] = self._hash(name)
        self._check_tree()

    def _directory(self, path):
        need(identity(path, directory=True) == self._directories[path], 'physical snapshot directory changed')
        names = set()
        for entry in path.iterdir():
            need(len(names) < self.limits.members, 'physical snapshot member capacity'); names.add(entry.name)
        need(names == self._children[path], 'physical snapshot directory members changed')

    def _parents(self, path):
        while True:
            self._directory(path)
            if path == self.root:break
            path = path.parent

    def _open(self, name):
        path = self.root/name; self._parents(path.parent)
        need(identity(path) == self._entries[name], 'physical snapshot file changed')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            need(key(os.fstat(fd)) == self._entries[name], 'physical snapshot file replaced')
            return os.fdopen(fd, 'rb')
        except BaseException:
            os.close(fd); raise

    def _finish(self, name, stream, size):
        saved = self._entries[name]; path = self.root/name
        need(size == saved[3] and key(os.fstat(stream.fileno())) == saved and identity(path) == saved,
             'physical snapshot file changed')
        self._parents(path.parent)

    def _check_tree(self):
        for path in self._directories:self._directory(path)
        for name, saved in self._entries.items():
            if saved is not None:
                need(identity(self.root/name) == saved, 'physical snapshot file changed')

    def _hash(self, name):
        with self._open(name) as stream:
            digest = hashlib.sha256(); size = 0
            while True:
                block = stream.read(BLOCK)
                if not block:break
                size += len(block); need(size <= self._entries[name][3], 'physical snapshot file grew')
                digest.update(block)
            self._finish(name, stream, size)
        return digest.hexdigest()

    def check_unchanged(self):
        # Filesystem timestamp precision alone cannot prove content stability.
        self.check_members(self._hashes)

    def check_members(self, names):
        """Recheck selected payloads without materializing them; still pin the tree."""
        self._check_tree()
        for name in names:
            need(name in self._hashes, 'physical snapshot selected file')
            need(self._hash(name) == self._hashes[name], 'physical snapshot content changed')
        self._check_tree()

    def identities(self):
        """Fresh metadata only; callers cannot replace the pinned identities."""
        self._check_tree()
        return {name:dict(directory=True) if saved is None else dict(size=saved[3], sha256=self._hashes[name])
                for name, saved in self._entries.items()}

    def __getitem__(self, name):
        saved = self._entries[name]
        if saved is None:
            self._parents(self.root/name); return None
        with self._open(name) as stream:
            # Bound by this file's previously checked size, never by the total
            # tree allowance. Return a fresh immutable value to the consumer.
            raw = stream.read(saved[3]+1)
            self._finish(name, stream, len(raw))
        need(hashlib.sha256(raw).hexdigest() == self._hashes[name], 'physical snapshot content changed')
        return raw

    def __iter__(self):
        self._check_tree(); return iter(self._entries)

    def __len__(self):
        self._check_tree(); return len(self._entries)

    def __contains__(self, name):
        self._check_tree(); return name in self._entries

    def __eq__(self, other):
        return equal(self, other)

    def __deepcopy__(self, memo):
        self.check_unchanged(); memo[id(self)] = self; return self


def equal(left, right):
    if not isinstance(right, Mapping):return NotImplemented
    # Mapping's default equality materializes both entire dictionaries.
    if set(left) != set(right):return False
    for name in left:
        if left[name] != right[name]:return False
    left.check_unchanged()
    if type(right) in (Snapshot, Projection):right.check_unchanged()
    return True


class Projection(Mapping):
    """A generation/source window holds original paths, not all image bytes."""
    def __init__(self, source, prefix, exclude):
        need(type(source) is Snapshot, 'physical snapshot projection source')
        source._check_tree(); self.source = source
        self._names = {name.removeprefix(prefix):name for name in source
                       if name.startswith(prefix) and name.removeprefix(prefix) not in exclude}

    def __getitem__(self, name):return self.source[self._names[name]]
    def __iter__(self):
        self.source._check_tree(); return iter(self._names)
    def __len__(self):
        self.source._check_tree(); return len(self._names)
    def __contains__(self, name):
        self.source._check_tree(); return name in self._names
    def check_unchanged(self):self.source.check_unchanged()
    def __eq__(self, other):return equal(self, other)
    def __deepcopy__(self, memo):
        self.check_unchanged(); memo[id(self)] = self; return self


def members(files, prefix, *, exclude=()):
    if type(files) is Snapshot:return Projection(files, prefix, exclude)
    return {name.removeprefix(prefix):raw for name,raw in files.items()
            if name.startswith(prefix) and name.removeprefix(prefix) not in exclude}


def from_model(root, model):
    from . import bootstrap_replay_contract as policy
    source = getattr(model, 'bootstrap_source', policy.EMPTY)
    layout = getattr(model, 'wire_layout', policy.JSON)
    policy.check_layout(source, layout)
    if layout == policy.SEGMENTED:
        from .joining_snapshot import relative
        files = Snapshot(root, limits=Limits(replica_limits.SNAPSHOT_BYTES, replica_limits.MEMBERS, replica_limits.DEPTH))
        for name in files:relative(name)
        return files
    from .carried_publication_evidence import inventory
    return inventory(root)
