"""Fixed unprivileged, once-only Java image installation. No guest downloads.

This module is also delivered as trusted source with remote_python_receiver.
An external descriptor pin is mandatory; installed JSON grants no authority.
"""
import hashlib
import gzip
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
from . import remote_python_receiver as p

SCHEMA='gse-v52-java-image-v1'
RECEIPT='gse-v52-java-install-v1'
MODULES=('java.base','java.management','jdk.management','jdk.unsupported')
MAX_BYTES=128<<20
MAX_FILE=96<<20
MAX_FILES=512
MAX_MANIFEST=256<<10
PIECE=64<<10
ENV={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'}


def name(value):
    p.need(type(value) is str and len(value)<=256 and re.fullmatch(r'[A-Za-z0-9._+/-]+',value) and
           not value.startswith('/') and all(v not in ('','.','..') for v in value.split('/')),'Java image path')
    return value


def descriptor(value):
    p.need(type(value) is dict and set(value)=={'schema','source','modules','files','bytes','sha256'} and
           value['schema']==SCHEMA and value['modules']==list(MODULES),'Java image descriptor')
    source=value['source']
    p.need(type(source) is dict and set(source)=={'source','checkoutSha256','java'},'Java image source')
    p.hex_value(source['source'],40);p.hex_value(source['checkoutSha256'],64)
    p.need(type(source['java']) is dict and set(source['java'])=={'java.runtime.version','java.vendor'} and
           all(type(s) is str and 0<len(s)<=256 for s in source['java'].values()),'Java image version')
    files=value['files'];p.need(type(files) is dict and 3<=len(files)<=MAX_FILES and
        {'bin/java','lib/modules','release'}<=files.keys(),'Java image inventory')
    total=0
    for path,row in files.items():
        name(path);p.need(type(row) is dict and set(row)=={'bytes','sha256','executable'} and
            type(row['bytes']) is int and 0<=row['bytes']<=MAX_FILE and type(row['executable']) is bool,'Java image member')
        p.hex_value(row['sha256'],64);total+=row['bytes']
        p.need(not any(parent.as_posix() in files for parent in Path(path).parents),'Java image path collision')
    p.need(files['bin/java']['executable'] and 0<total<=MAX_BYTES and len(p.encoded(value))<=MAX_MANIFEST,'Java image expansion')
    p.need(type(value['bytes']) is int and 0<value['bytes']<=MAX_BYTES,'Java image archive bound')
    p.hex_value(value['sha256'],64);return value


def selection(value):
    p.need(type(value) is dict and set(value)=={'root','descriptorSha256'},'Java image selection')
    p.hex_value(value['descriptorSha256'],64);path=value['root']
    p.need(type(path) is str and 0<len(path)<=4096 and Path(path).is_absolute() and str(Path(path))==path and
           '..' not in Path(path).parts and '\x00' not in path,'Java image selected path');return value


def location(parent,value):
    # Reuse only the fixed owned-ancestor policy, never Python descriptor authority.
    parent=Path(parent);p.location(parent,{'sha256':descriptor(value)['sha256']})
    return parent/('java-'+value['sha256'])


def read_file(path,row):
    p.owned(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno());p.need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and
            info.st_size==row['bytes'] and stat.S_IMODE(info.st_mode)==(0o500 if row['executable'] else 0o400),'Java installed file mode/size')
        sha=hashlib.sha256();remaining=row['bytes']
        while remaining:
            raw=stream.read(min(PIECE,remaining));p.need(raw,'Java installed truncated file');remaining-=len(raw);sha.update(raw)
        p.need(not stream.read(1) and sha.hexdigest()==row['sha256'],'Java installed file hash')


def files(root,value):
    own=Path(root)/'files';p.owned(own,True);found=set();dirs=set()
    expected={str(v) for n in value['files'] for v in Path(n).parents if str(v)!='.'}
    for path in own.rglob('*'):
        relative=path.relative_to(own).as_posix();info=path.lstat()
        if stat.S_ISDIR(info.st_mode):
            p.need(relative in expected,'Java extra directory');p.owned(path,True);dirs.add(relative)
        else:
            p.need(relative in value['files'],'Java extra file');read_file(path,value['files'][relative]);found.add(relative)
    p.need(found==set(value['files']) and dirs==expected,'Java incomplete inventory')


def properties(executable,*,env=ENV):
    # Closed environment avoids JAVA_TOOL_OPTIONS/LD_PRELOAD changing an approved image.
    result=subprocess.run([str(executable),'-XshowSettings:properties','-version'],check=True,capture_output=True,
                          text=True,timeout=30,env=env)
    p.need(len(result.stdout)+len(result.stderr)<=65536,'Java version output bound')
    return dict(re.findall(r'^\s*(java\.(?:runtime.version|vendor)) = (.+)$',result.stderr,re.MULTILINE))


def checked(root,value,*,observe=True):
    descriptor(value);root=Path(root);p.need(root==location(root.parent,value),'Java installation path')
    p.owned(root,True);p.need(p.decode(p.read(root/'descriptor.json',MAX_MANIFEST))==value,'Java installed descriptor')
    files(root,value)
    if observe:
        p.need(properties(root/'files/bin/java')==value['source']['java'],'Java installed runtime differs')
        result=subprocess.run([str(root/'files/bin/java'),'--list-modules'],check=True,capture_output=True,text=True,timeout=30,env=ENV)
        p.need(len(result.stdout)<=65536 and sorted(v.split('@')[0] for v in result.stdout.splitlines())==sorted(MODULES),
               'Java installed module set')
        files(root,value)
    return dict(schema=RECEIPT,descriptorSha256=p.digest(p.encoded(value)),root=str(root),host=p.host(root.parent),
                filesSha256=p.digest(p.encoded(value['files'])),java=value['source']['java'])


def installed(root,value):
    wanted=checked(root,value)
    read_file(Path(root)/'archive.tar.gz',dict(bytes=value['bytes'],sha256=value['sha256'],executable=False))
    p.need({v.name for v in Path(root).iterdir()}=={'descriptor.json','archive.tar.gz','files','receipt.json'},'Java incomplete/extra installation')
    p.need(p.decode(p.read(Path(root)/'receipt.json',MAX_MANIFEST))==wanted,'Java original installation receipt')
    return wanted


class ClosedTarInfo(tarfile.TarInfo):
    def _proc_pax(self,*args,**kwargs):raise ValueError('Java extended archive header')
    def _proc_gnulong(self,*args,**kwargs):raise ValueError('Java extended archive header')
    def _proc_sparse(self,*args,**kwargs):raise ValueError('Java sparse archive')


def verify_archive(path,value,accept=None):
    """Replay original bytes without executing anything from retained evidence."""
    descriptor(value);path=Path(path)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        info=os.fstat(stream.fileno())
        p.need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size==value['bytes'],'Java retained archive size/type')
        sha=hashlib.sha256()
        while raw:=stream.read(PIECE):sha.update(raw)
        p.need(sha.hexdigest()==value['sha256'],'Java retained archive hash');stream.seek(0)
        class Bounded:
            def __init__(self,source):self.source=source;self.remaining=MAX_BYTES+MAX_FILES*1024+10240
            def read(self,n):
                raw=self.source.read(min(n,self.remaining+1));self.remaining-=len(raw)
                p.need(self.remaining>=0,'Java archive expanded bound');return raw
        with gzip.GzipFile(fileobj=stream,mode='rb') as compressed:
            bounded=Bounded(compressed);seen=set()
            with tarfile.open(fileobj=bounded,mode='r|',bufsize=512,tarinfo=ClosedTarInfo) as tar:
                for entry in tar:
                    p.need(entry.isfile() and not entry.pax_headers and entry.sparse is None and
                           entry.name in value['files'] and entry.name not in seen,'Java archive entry')
                    row=value['files'][entry.name]
                    p.need(entry.size==row['bytes'] and entry.mode==(0o755 if row['executable'] else 0o644),'Java archive file size/mode')
                    with tar.extractfile(entry) as source:
                        sha=hashlib.sha256();left=entry.size
                        def chunks():
                            nonlocal left
                            while left:
                                raw=source.read(min(left,PIECE));p.need(raw,'Java archive truncated member')
                                left-=len(raw);sha.update(raw);yield raw
                        if accept is None:
                            for _ in chunks():pass
                        else:accept(entry.name,row,chunks())
                        p.need(left==0 and sha.hexdigest()==row['sha256'],'Java archive member hash')
                    seen.add(entry.name)
            # Reject hidden members/trailing payload; padding is bounded too.
            while raw:=bounded.read(PIECE):p.need(not any(raw),'Java archive trailing payload')
            p.need(seen==set(value['files']),'Java archive missing member')


def install(parent,value,incoming):
    value=descriptor(value);root=location(parent,value);root.mkdir(mode=0o700);p.sync(root.parent)
    p.write(root/'descriptor.json',p.encoded(value))  # Partial transfer consumes this destination.
    archive=root/'archive.tar.gz';sha=hashlib.sha256();left=value['bytes']
    with os.fdopen(os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400),'wb') as stream:
        while left:
            raw=incoming.read(min(left,PIECE));p.need(raw,'Java truncated upload');left-=len(raw);sha.update(raw);stream.write(raw)
        p.need(not incoming.read(1) and sha.hexdigest()==value['sha256'],'Java upload hash/trailing bytes')
        stream.flush();os.fsync(stream.fileno())
    p.sync(root);own=root/'files';own.mkdir(mode=0o700);p.sync(root)
    def accept(name,row,chunks):
        path=own/name;path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
        for parent_ in path.parents:
            if parent_==own:break
            parent_.chmod(0o700)
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,
                0o500 if row['executable'] else 0o400),'wb') as out:
            for raw in chunks:out.write(raw)
            out.flush();os.fsync(out.fileno())
        read_file(path,row)
    verify_archive(archive,value,accept)
    for path in sorted((v for v in own.rglob('*') if v.is_dir()),key=lambda v:len(v.parts),reverse=True):p.sync(path)
    p.sync(own);receipt=checked(root,value);p.write(root/'receipt.json',p.encoded(receipt));return installed(root,value)


def main():
    p.need(len(sys.argv)==4 and sys.argv[1] in ('install','verify'),'Java receiver action')
    p.hex_value(sys.argv[3],64);raw=sys.stdin.buffer.readline(MAX_MANIFEST+2)
    p.need(raw.endswith(b'\n') and len(raw)<=MAX_MANIFEST+1,'Java receiver header bound')
    value=descriptor(p.decode(raw));p.need(p.digest(p.encoded(value))==sys.argv[3],'Java external descriptor pin')
    if sys.argv[1]=='install':result=install(sys.argv[2],value,sys.stdin.buffer)
    else:
        p.need(not sys.stdin.buffer.read(1),'Java verify body');result=installed(location(sys.argv[2],value),value)
    sys.stdout.buffer.write(p.encoded(result)+b'\n')


if __name__=='__main__':main()
