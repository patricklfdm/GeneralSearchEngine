"""Bounded content-addressed observations; no captured bytes confer authority.

One checked pool is shared by immutable prefix mappings. Only semantic reads
materialize a single bounded file. Comparisons hash selected originals through
the streaming reader, including identities and directory membership checks.
"""
from collections.abc import Mapping
import hashlib
from pathlib import Path
import re
from types import MappingProxyType
from . import bootstrap_replay_contract as policy
from . import physical_snapshot as physical
from .membership_model import need
from . import replica_capture_limits as replica_limits

MAXIMUM_OBJECTS=8192
SNAPSHOT_BYTES=replica_limits.SNAPSHOT_BYTES


class Pool:
    def __init__(self, root, *, bootstrap_source, wire_layout, label='capture objects'):
        policy.check_layout(bootstrap_source,wire_layout)
        need(wire_layout==policy.SEGMENTED,'capture object pool requires explicit segmented backup')
        root=Path(root);need(root.is_dir() and not root.is_symlink(),'capture object pool directory')
        names=set()
        for path in root.iterdir():
            need(re.fullmatch('[0-9a-f]{64}',path.name) is not None and len(names)<MAXIMUM_OBJECTS,'capture object pool name/count')
            names.add(path.name)
        self.snapshot=physical.Snapshot(root,limits=physical.Limits(policy.ORIGINAL_BYTES,MAXIMUM_OBJECTS,0))
        metadata=self.snapshot.identities()
        need(set(metadata)==names and all(set(v)=={'size','sha256'} and v['sha256']==k for k,v in metadata.items()),
             label+' object identity/capacity')
        self._sizes=MappingProxyType({k:v['size'] for k,v in metadata.items()})

    def __contains__(self, digest):return digest in self._sizes
    def keys(self):return self._sizes.keys()
    def size(self, digest):return self._sizes[digest]
    def read(self, digest):return self.snapshot[digest]
    def check_unchanged(self):self.snapshot.check_unchanged()
    def view(self, names):return Files(self,names)


class Files(Mapping):
    def __init__(self,pool,names):
        need(type(pool) is Pool and type(names) is dict,'capture object prefix shape')
        need(all(value is None or type(value) is str and value in pool for value in names.values()),'capture object prefix reference')
        need(sum(pool.size(value) for value in names.values() if value is not None)<=SNAPSHOT_BYTES,
             'capture object prefix byte capacity')
        self.pool=pool;self._names=MappingProxyType(dict(names))
        self._objects=frozenset(value for value in names.values() if value is not None)

    def __getitem__(self,name):
        digest=self._names[name];return None if digest is None else self.pool.read(digest)
    def __iter__(self):return iter(self._names)
    def __len__(self):return len(self._names)
    def __contains__(self,name):return name in self._names
    def check_unchanged(self):self.pool.snapshot.check_members(self._objects)
    def identities(self):
        self.check_unchanged()
        return {name:dict(directory=True) if digest is None else dict(size=self.pool.size(digest),sha256=digest)
                for name,digest in self._names.items()}
    def __eq__(self,other):
        if not isinstance(other,Mapping):return NotImplemented
        if set(self)!=set(other):return False
        if type(other) is Files:return self.identities()==other.identities()
        expected={}
        for name in self:
            raw=other[name]
            if raw is None:expected[name]=dict(directory=True)
            elif type(raw) is bytes:expected[name]=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            else:return False
        return self.identities()==expected
    def __deepcopy__(self,memo):
        self.check_unchanged();memo[id(self)]=self;return self
