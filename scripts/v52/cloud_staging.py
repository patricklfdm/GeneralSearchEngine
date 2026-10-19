"""Stage exactly the five original verified JARs; never rebuild or replace one.

The live handle is local input ownership, not cloud admission. It keeps opened
directory handles while writing, rejects linked paths/files and rechecks paths
and bytes before use. A partial write stays visible and is never repaired here.
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import stat
from . import cloud_inputs as inputs
from .evidence import need, encoded, digest

SCHEMA='gse-v52-original-input-staging-v1'
_TICKET=object()
DIR=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
FILE=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC


def paths():
    version=inputs.VERSION
    return (f'target/general-search-engine-{version}.jar',
        f'general-search-engine-replication/target/general-search-engine-replication-{version}.jar',
        *['target/v52-controls/'+name for name in sorted(inputs.CONTROL_NAMES)])


def same(first,second):
    return (first.st_dev,first.st_ino)==(second.st_dev,second.st_ino)


def directory(fd):
    own=os.fstat(fd)
    need(stat.S_ISDIR(own.st_mode) and own.st_uid==os.getuid() and not own.st_mode&0o022,
         'V5.2 staging directory owner/mode')
    return own


@contextmanager
def parent(root_fd,name,*,create=False):
    need(name in paths(),'V5.2 staging unlisted destination')
    current=os.dup(root_fd)
    try:
        for part in Path(name).parts[:-1]:
            try:next_fd=os.open(part,DIR,dir_fd=current)
            except FileNotFoundError:
                if not create:yield None;return
                os.mkdir(part,0o755,dir_fd=current);os.fsync(current)
                next_fd=os.open(part,DIR,dir_fd=current)
            try:directory(next_fd)
            except BaseException:os.close(next_fd);raise
            os.close(current);current=next_fd
        yield current
    finally:os.close(current)


def observed(fd,name,expected):
    try:opened=os.open(Path(name).name,FILE,dir_fd=fd)
    except FileNotFoundError:return False
    with os.fdopen(opened,'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.getuid() and
             not before.st_mode&0o022 and before.st_size==len(expected),'V5.2 staged file type/size')
        raw=stream.read(len(expected)+1);after=os.fstat(stream.fileno())
        stable=('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        need(raw==expected and all(getattr(before,k)==getattr(after,k) for k in stable) and
             same(after,os.stat(Path(name).name,dir_fd=fd,follow_symlinks=False)),
             'V5.2 staged original bytes changed')
    return True


class Staged:
    def __init__(self,root,proof,files,ticket):
        need(ticket is _TICKET,'V5.2 staging verified factory required')
        self.root=Path(root).absolute();self.proof=deepcopy(proof)
        self.files={name:files['artifacts/'+Path(name).name] for name in paths()}
        need(not any(p.is_symlink() for p in (self.root,*self.root.parents)),'V5.2 staging root symlink')
        self.fd=os.open(self.root,DIR);self.closed=False
        try:self.identity=directory(self.fd)
        except BaseException:os.close(self.fd);self.closed=True;raise
        self.receipt=None

    def root_check(self):
        need(not self.closed and not any(p.is_symlink() for p in (self.root,*self.root.parents)) and
             same(self.identity,self.root.stat()),'V5.2 staging root changed/closed')
        directory(self.fd)

    def check(self):
        self.root_check()
        need(inputs.checkout(self.root,self.proof['source']['source'])==self.proof['source'],'V5.2 staged source changed')
        for name,raw in self.files.items():
            with parent(self.fd,name) as fd:
                need(fd is not None and observed(fd,name,raw),'V5.2 staged original input missing')
        return deepcopy(self.proof)

    def install(self):
        self.root_check();reused={}
        # Check every existing destination before creating even the first file.
        for name,raw in self.files.items():
            with parent(self.fd,name) as fd:reused[name]=fd is not None and observed(fd,name,raw)
        for name,raw in self.files.items():
            with parent(self.fd,name,create=True) as fd:
                if reused[name]:need(observed(fd,name,raw),'V5.2 reused original input disappeared')
                else:
                    opened=os.open(Path(name).name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o644,dir_fd=fd)
                    with os.fdopen(opened,'wb') as stream:
                        stream.write(raw);stream.flush();os.fsync(stream.fileno())
                    os.fsync(fd)
        self.check()
        self.receipt=dict(schema=SCHEMA,status='ORIGINAL_INPUTS_STAGED_NOT_ADMITTED',proof=deepcopy(self.proof),
            files={name:dict(bytes=len(raw),sha256=digest(raw),reused=reused[name]) for name,raw in self.files.items()},
            paidAdmission=False,fullRemoteQualification=False)
        return deepcopy(self.receipt)

    def close(self):
        if not self.closed:self.closed=True;os.close(self.fd)


def stage(root,source,build_directory,package,output,*,expected):
    proof,files=inputs.verified_files(root,source,build_directory,package)
    need(proof==expected,'V5.2 staging original inspection changed')
    output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 staging receipt symlink')
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    staged=None
    try:
        staged=Staged(root,proof,files,_TICKET);receipt=staged.install()
        with (output/'receipt.json').open('xb') as stream:
            stream.write(encoded(receipt)+b'\n');stream.flush();os.fsync(stream.fileno())
        return staged
    except BaseException:
        if staged is not None:staged.close()
        raise
