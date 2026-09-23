"""Resolve portable evidence bytes while preserving recorded runtime path identities."""
from pathlib import Path, PurePosixPath
from .performance_model import need, sha


def recorded_path(value):
    path=PurePosixPath(value)
    need(path.is_absolute() and str(path)==value and '..' not in path.parts and
         '\\' not in value and path.parent.name=='artifacts' and path.suffix=='.jar', 'recorded artifact path')
    return path


def retained(root, value, digest):
    recorded=recorded_path(value)
    path=Path(root)/'artifacts'/recorded.name
    need(not path.parent.is_symlink() and path.is_file() and not path.is_symlink() and
         path.stat().st_size<=64<<20 and sha(path.read_bytes())==digest, 'retained artifact identity')
    return path


class EvidenceLocation:
    """Explicit immutable-bundle inspection; never authorizes starting copied voters."""
    def __init__(self, root, original):
        from . import performance_bundle as bundle
        from .performance_model import strict_json
        self.root=Path(root).resolve();self.original=Path(original)
        need(self.original.is_absolute() and '..' not in self.original.parts, 'original evidence root')
        self.index=None
        if self.original!=self.root:
            index=self.root/'bundle-members.json'
            need(index.is_file() and not index.is_symlink() and index.stat().st_size<=4<<20, 'relocated evidence inventory')
            self.index=strict_json(index.read_bytes())
            need(self.index==bundle.members(self.root), 'relocated evidence inventory differs')

    def inspect(self, directory, maximum_bytes=8<<30, maximum_frame=8<<20):
        from . import storage_inspector as storage
        directory=Path(directory)
        if self.index is None:return storage.inspect(directory,maximum_bytes,maximum_frame)
        relative=directory.relative_to(self.root);prefix=relative.as_posix()+'/'
        expected={name[len(prefix):]:dict(size=v['bytes'],sha256=v['sha256'])
                  for name,v in self.index.items() if name.startswith(prefix)}
        need(expected and expected==storage.inventory(directory), 'relocated authority inventory differs')
        return storage._inspect(directory,maximum_bytes,maximum_frame,self.original/relative)
