"""Bounded, hash-complete local evidence packaging; no unsafe archive extraction."""
import hashlib
import tarfile
from pathlib import Path, PurePosixPath
from .performance_model import need, canonical, strict_json

LIMITS = dict(files=4000, expanded=1<<30, compressed=1<<30, member=64<<20, traces=512<<20)


def is_trace(name):
    # Mutated traces remain trace evidence even when stored as one JSON array.
    return name.endswith(('.jsonl','.log','history.json','calls.json','process.json')) or name.startswith('negative-inputs/')


def members(root):
    root=Path(root);result={};total=traces=0
    need(root.is_dir() and not root.is_symlink(),'bundle root type')
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(),'bundle symlink')
        if path.is_dir():continue
        relative=path.relative_to(root).as_posix()
        if relative=='bundle-members.json':continue
        need(path.is_file(),'bundle member type')
        size=path.stat().st_size;total+=size
        if is_trace(relative):traces+=size
        need(size<=LIMITS['member'] and total<=LIMITS['expanded'] and traces<=LIMITS['traces'] and len(result)<LIMITS['files']-1,'bundle evidence ceiling')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1<<20),b''):digest.update(chunk)
        result[relative]=dict(bytes=size,sha256=digest.hexdigest())
    return result


def pack(root,archive):
    root=Path(root);archive=Path(archive)
    need(not archive.exists() and root not in archive.parents,'archive must be a fresh sibling of raw evidence')
    index=members(root);encoded=canonical(index)+b'\n'
    need(len(encoded)<=min(4<<20,LIMITS['member']) and sum(v['bytes'] for v in index.values())+len(encoded)<=LIMITS['expanded'],'bundle inventory bound')
    (root/'bundle-members.json').write_bytes(encoded)
    with tarfile.open(archive,'w:gz') as tar:
        for name in sorted([*index,'bundle-members.json']):
            tar.add(root/name,arcname=name,recursive=False)
    need(archive.stat().st_size<=LIMITS['compressed'],'compressed evidence ceiling')
    return index


def unpack(archive,target):
    archive=Path(archive);target=Path(target)
    need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size<=LIMITS['compressed'],'compressed input bound/type')
    need(not target.exists(),'fresh extraction target')
    target.mkdir(parents=True)
    total=traces=0;seen=set()
    with tarfile.open(archive,'r|gz') as tar:
        for item in tar:
            path=PurePosixPath(item.name)
            need(item.isfile() and not item.issym() and not item.islnk() and not path.is_absolute() and
                 item.name==path.as_posix() and all(p not in ('','..','.') for p in path.parts) and '\\' not in item.name,'unsafe bundle member')
            need(item.name not in seen and len(seen)<LIMITS['files'],'duplicate/too many bundle members')
            seen.add(item.name);total+=item.size
            if is_trace(item.name):traces+=item.size
            need(0<=item.size<=LIMITS['member'] and total<=LIMITS['expanded'] and traces<=LIMITS['traces'],'expanded evidence ceiling')
            output=target/item.name;output.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(item) as source,output.open('xb') as destination:
                remaining=item.size
                while remaining:
                    data=source.read(min(1<<20,remaining));need(data,'truncated bundle member')
                    destination.write(data);remaining-=len(data)
    index=target/'bundle-members.json'
    need(index.is_file() and index.stat().st_size<=4<<20,'missing/bounded bundle inventory')
    need(strict_json(index.read_bytes())==members(target),'bundle member inventory/hash differs')
    return target
