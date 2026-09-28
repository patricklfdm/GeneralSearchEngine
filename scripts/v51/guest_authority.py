"""Bounded, stopped-voter authority capture. Never collects a neighbour's files."""
import shutil
from pathlib import Path
from . import performance_model as m, remote_command as c, remote_collection as parts

MAX_BYTES = 64 << 20
MAX_PATHS = 4096


def inventory(root):
    root=c.directory(root); count=total=0
    for path in root.rglob('*'):
        count+=1
        m.need(count<=MAX_PATHS and not path.is_symlink() and (path.is_dir() or path.is_file()), 'guest authority path/type bound')
        if path.is_file():
            total+=path.stat().st_size
            m.need(total<=MAX_BYTES, 'guest authority byte bound')
    value=parts.inventory(root)
    m.need(value, 'guest authority empty')
    return value


def capture(cell, node, destination):
    m.need(node in ('node-1','node-2','node-3'), 'guest authority owner')
    source=c.directory(Path(cell)/node); before=inventory(source)
    shutil.copytree(source,destination)
    m.need(inventory(source)==before==inventory(destination), 'guest authority changed during collection')
