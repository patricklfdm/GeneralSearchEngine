"""Explicit backup wire layout and shared bounded inventory; never auto-discovered."""
import hashlib
import os
from pathlib import Path
import re
from . import segmented_evidence as segmented
from . import bootstrap_replay_contract as source
from . import joining_history_run as legacy

need=source.need
DIRECTORY='segmented-wire'
SCHEMA='gse-v53-segmented-wire-v1'
JSON='JSON'
SEGMENTED='SEGMENTED_BACKUP'
LIMITS={'wire.json':64*1024*1024,'joining-intent-wire.json':8*1024*1024,
        'joining-ack-wire.json':1024*1024,'joining-head-wire.json':1024*1024,
        'joining-retention-wire.json':8*1024*1024,'joining-continuation-wire.json':64*1024*1024}


def checked_file(path,maximum):
    before=segmented.identity(path);need(before[2]<=maximum,'segmented wire index capacity')
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        need((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)==before,'segmented wire file changed')
        raw=stream.read(maximum+1)
    need(len(raw)==before[2] and segmented.identity(path)==before,'segmented wire file changed')
    return raw


def inventory(root,maximum):
    """Bound the entire registry before parsing any history, including metadata."""
    pending=[root];files={};directories={};total=0
    while pending:
        directory=pending.pop();directories[str(directory.relative_to(root))]=segmented.identity(directory,directory=True)
        for member in directory.iterdir():
            relative=member.relative_to(root)
            need(len(relative.parts)<=3 and len(files)+len(directories)+len(pending)<65536,'segmented wire inventory capacity')
            if member.is_dir() and not member.is_symlink():pending.append(member)
            else:
                key=segmented.identity(member);need(key[2]<=segmented.SEGMENT_BYTES,'segmented wire member capacity')
                total+=key[2];need(total<=maximum,'segmented wire shared byte capacity');files[str(relative)]=key
    return dict(files=files,directories=directories,bytes=total)


class Archive:
    def __init__(self,native_root,*,bootstrap_source,maximum=segmented.MAXIMUM):
        need(source.check(bootstrap_source)==source.BACKUP,'segmented wire backup source required')
        need(type(maximum) is int and 0<=maximum<=segmented.MAXIMUM,'segmented wire byte limit')
        self.native=Path(native_root);self.native_identity=segmented.identity(self.native,directory=True)
        need(not any((self.native/name).exists() or (self.native/name).is_symlink() for name in (*LIMITS,'auxiliary-wire-spools')),
             'segmented wire legacy conflict')
        self.root=self.native/DIRECTORY;self.maximum=maximum;self.before=inventory(self.root,maximum)
        self.index_bytes=checked_file(self.root/'index.json',65536);index=segmented.canonical(self.index_bytes)
        need(set(index)=={'schema','histories'} and index['schema']==SCHEMA and
             type(index['histories']) is list and 1<=len(index['histories'])<=len(LIMITS),'segmented wire registry')
        self.entries={};self.readers={}
        for row in index['histories']:
            need(type(row) is dict and set(row)=={'file','completeSha256','observedSha256'} and
                 type(row['file']) is str and row['file'] in LIMITS and row['file'] not in self.entries and
                 type(row['completeSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['completeSha256']) and
                 (row['observedSha256'] is None or type(row['observedSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['observedSha256'])),
                 'segmented wire history descriptor')
            self.entries[row['file']]=row
        need(list(self.entries)==sorted(self.entries) and 'wire.json' in self.entries and
             self.entries['wire.json']['observedSha256'] is None,'segmented wire exact histories')
        need(segmented.Reader.names(self.root,len(LIMITS)+1)=={'index.json',*(name[:-5] for name in self.entries)},
             'segmented wire registry inventory')
        for name,row in self.entries.items():
            base=self.root/name[:-5];complete=checked_file(base/'complete.json',segmented.ROW_BYTES)
            need(hashlib.sha256(complete).hexdigest()==row['completeSha256'],'segmented wire complete binding')
            cut='observed' if row['observedSha256'] is not None else None
            if cut:
                raw=checked_file(base/'cuts/observed.json',segmented.ROW_BYTES)
                need(hashlib.sha256(raw).hexdigest()==row['observedSha256'],'segmented wire cut binding')
            need(segmented.Reader.names(base/'cuts',segmented.CUTS)==({'observed.json'} if cut else set()),'segmented wire exact cuts')
            self.readers[name]=segmented.Reader(base,cut=cut,maximum=maximum)
        self.check_unchanged()

    def read(self,name):
        need(type(name) is str and name in self.entries,'segmented wire missing history')
        need(name=='wire.json' or self.entries[name]['observedSha256'] is not None,'segmented wire missing observed cut')
        self.check_unchanged();return self.readers[name]

    def check_unchanged(self):
        need(segmented.identity(self.native,directory=True)==self.native_identity,'segmented wire native root changed')
        need(inventory(self.root,self.maximum)==self.before,'segmented wire inventory changed')
        need(checked_file(self.root/'index.json',65536)==self.index_bytes,'segmented wire registry changed')
        for reader in self.readers.values():reader.check_unchanged()


def read(native_root,name,*,bootstrap_source=source.EMPTY,layout=JSON):
    source.check(bootstrap_source)
    need(type(name) is str and name in LIMITS,'segmented wire logical name')
    need(type(layout) is str and layout in (JSON,SEGMENTED),'segmented wire explicit layout')
    if layout==JSON:
        root=Path(native_root)
        need(not (root/DIRECTORY).exists() and not (root/DIRECTORY).is_symlink(),'segmented wire unexpected layout')
        return legacy.read_json(root,name,LIMITS[name])
    return Archive(native_root,bootstrap_source=bootstrap_source).read(name)
