"""Large closed measurement packages; predecessor bundle ceilings are unchanged.

One whole history per package. No live-voter resume from downloaded authority.
Only regular USTAR files/directories are accepted, before extension payload reads.
"""
import hashlib
from pathlib import Path,PurePosixPath
import re
import tarfile
from scripts.v51.performance_model import strict_json
from scripts.v51 import storage_inspector as storage
from .evidence import need,encoded

LIMITS=dict(files=400000,directories=4096,expanded=4<<30,compressed=4<<30,member=256<<20,inventory=64<<20)
INDEX='bundle-members.json'
HEX=re.compile(r'[0-9a-f]{64}')


def name(value):
    need(type(value) is str and 0<len(value)<=255 and re.fullmatch(r'[A-Za-z0-9_.$/@+=-]+',value) is not None,'measurement bundle path')
    path=PurePosixPath(value)
    need(path.parts and not path.is_absolute() and str(path)==value and all(v not in ('.','..','') for v in path.parts) and len(path.parts)<=32,'measurement bundle path')
    # Ensure the closed portable representation needs no GNU/PAX long-name record.
    try:tarfile.TarInfo(value).tobuf(format=tarfile.USTAR_FORMAT,encoding='ascii')
    except ValueError:raise ValueError('measurement bundle USTAR path') from None
    return value


def sha_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    return digest.hexdigest()


def members(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'measurement bundle root type')
    result={};total=directories=0
    for path in root.rglob('*'):
        need(not path.is_symlink(),'measurement bundle symlink');relative=name(path.relative_to(root).as_posix())
        if path.is_dir():
            directories+=1;need(directories<=LIMITS['directories'],'measurement bundle directory ceiling');continue
        need(path.is_file(),'measurement bundle member type')
        if relative==INDEX:continue
        size=path.stat().st_size;total+=size
        need(size<=LIMITS['member'] and total<=LIMITS['expanded'] and len(result)<LIMITS['files']-1,'measurement bundle evidence ceiling')
        result[relative]=dict(bytes=size,sha256=sha_file(path))
    return dict(sorted(result.items()))


def validate_index(value):
    need(type(value) is dict and 0<len(value)<LIMITS['files'],'measurement bundle inventory count')
    total=0
    for relative,record in value.items():
        name(relative);need(relative!=INDEX and type(record) is dict and set(record)=={'bytes','sha256'},'measurement bundle inventory fields')
        size=record['bytes'];need(type(size) is int and 0<=size<=LIMITS['member'],'measurement bundle inventory member bound')
        need(type(record['sha256']) is str and HEX.fullmatch(record['sha256']) is not None,'measurement bundle inventory digest')
        total+=size;need(total<=LIMITS['expanded'],'measurement bundle inventory total bound')
        for parent in PurePosixPath(relative).parents:
            need(parent.as_posix() not in value,'measurement bundle file/directory conflict')
    return total


def inventory(root):
    root=Path(root);path=root/INDEX
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=LIMITS['inventory'],'measurement bundle inventory bound/type')
    raw=path.read_bytes();value=strict_json(raw);total=validate_index(value)
    need(total+len(raw)<=LIMITS['expanded'] and value==members(root),'measurement bundle inventory/hash differs')
    return value


class ClosedTarInfo(tarfile.TarInfo):
    def _proc_member(self,archive):
        # TarInfo otherwise reads PAX/GNU extension bodies before yielding an
        # item to the caller. Reject those types before any such allocation.
        need(self.type in (tarfile.REGTYPE,tarfile.AREGTYPE,tarfile.DIRTYPE),'measurement bundle extension/link type')
        return super()._proc_member(archive)


def pack(root,archive):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'measurement bundle root type');root=root.resolve()
    archive=Path(archive);need(not archive.is_symlink(),'measurement bundle archive symlink');archive=archive.parent.resolve()/archive.name
    need(not archive.exists() and not archive.is_symlink() and root not in archive.parents,'measurement bundle fresh sibling archive')
    index=members(root);validate_index(index);raw=encoded(index)+b'\n'
    need(len(raw)<=LIMITS['inventory'] and sum(v['bytes'] for v in index.values())+len(raw)<=LIMITS['expanded'],'measurement bundle inventory ceiling')
    index_path=root/INDEX;need(not index_path.is_symlink(),'measurement bundle inventory symlink');index_path.write_bytes(raw)
    directories=sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir());directory_set=set(directories)
    with archive.open('xb') as destination,tarfile.open(fileobj=destination,mode='w|gz',format=tarfile.USTAR_FORMAT,encoding='ascii') as output:
        for relative in [INDEX,*directories,*index]:
            path=root/relative;item=tarfile.TarInfo(relative);item.mtime=0
            if relative in directory_set:item.type=tarfile.DIRTYPE;item.mode=0o755;output.addfile(item);continue
            need(path.is_file() and not path.is_symlink(),'measurement bundle changed member type');item.size=path.stat().st_size;item.mode=0o644
            need(item.size==(len(raw) if relative==INDEX else index[relative]['bytes']),'measurement bundle changed member size')
            with path.open('rb') as source:output.addfile(item,source)
    need(archive.stat().st_size<=LIMITS['compressed'],'measurement compressed evidence ceiling')
    need(inventory(root)==index,'measurement bundle changed during pack');return index


def unpack(archive,target):
    archive=Path(archive);target=Path(target)
    need(archive.is_file() and not archive.is_symlink() and 0<archive.stat().st_size<=LIMITS['compressed'],'measurement compressed input bound/type')
    need(not target.exists() and not target.is_symlink(),'measurement bundle fresh extraction');target.mkdir(parents=True)
    total=directories=0;seen=set();index=None
    with tarfile.open(archive,'r|gz',tarinfo=ClosedTarInfo,encoding='ascii',errors='strict') as source:
        for item in source:
            # TarInfo normalizes directory trailing slashes; no extract/extractall
            # is used. Every output path is validated before creating it.
            relative=name(item.name);need(relative not in seen,'measurement duplicate bundle member');seen.add(relative)
            need(not item.pax_headers and item.sparse is None,'measurement bundle extended metadata')
            if index is None:need(relative==INDEX and item.isfile(),'measurement bundle first inventory')
            if item.isdir():
                directories+=1;need(item.size==0 and directories<=LIMITS['directories'] and relative not in index,'measurement bundle directory ceiling/type')
                (target/relative).mkdir(parents=True,exist_ok=True);continue
            need(len(seen)-directories<=LIMITS['files'],'measurement bundle file ceiling')
            size=item.size;total+=size
            need(0<=size<=(LIMITS['inventory'] if relative==INDEX else LIMITS['member']) and total<=LIMITS['expanded'],'measurement expanded evidence ceiling')
            if relative!=INDEX:need(relative in index and size==index[relative]['bytes'],'measurement unlisted/changed archive member')
            output=target/relative;output.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256()
            with source.extractfile(item) as incoming,output.open('xb') as destination:
                remaining=size
                while remaining:
                    block=incoming.read(min(1<<20,remaining));need(block,'measurement truncated bundle member')
                    remaining-=len(block);digest.update(block);destination.write(block)
            if relative==INDEX:
                index=strict_json(output.read_bytes());declared=validate_index(index)
                need(declared+size<=LIMITS['expanded'],'measurement declared expanded ceiling')
            else:need(digest.hexdigest()==index[relative]['sha256'],'measurement archive member digest')
    need(index is not None and {v for v in seen if (target/v).is_file()}==set(index)|{INDEX},'measurement missing archive member')
    need(inventory(target)==index,'measurement extracted inventory mismatch');return target


class EvidenceLocation:
    """Verify all package bytes, then inspect authority with its original paths."""
    def __init__(self,root,original):
        root=Path(root);need(not root.is_symlink(),'measurement bundle root type')
        self.root=root.resolve();self.original=Path(original)
        need(self.original.is_absolute() and '..' not in self.original.parts,'measurement original evidence root')
        self.index=inventory(self.root)

    def inspect(self,directory,maximum_bytes=8<<30,maximum_frame=8<<20):
        directory=Path(directory);relative=directory.relative_to(self.root);prefix=relative.as_posix()+'/'
        expected={key[len(prefix):]:dict(size=v['bytes'],sha256=v['sha256']) for key,v in self.index.items() if key.startswith(prefix)}
        need(expected and expected==storage.inventory(directory),'measurement authority inventory differs')
        return storage._inspect(directory,maximum_bytes,maximum_frame,self.original/relative)
