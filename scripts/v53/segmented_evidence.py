"""Bounded, immutable segmented observations; no protocol or cohort admission.

The caller explicitly chooses this format. Ordinary JSON readers never discover
it or raise their limits. A cut is a prefix of a complete captured lifetime.
"""
from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from . import format_fixture as f
from . import json_budget
from .membership_model import need

SCHEMA='gse-v53-segmented-evidence-v1'
ROW_BYTES=16*1024*1024
SEGMENT_BYTES=64*1024*1024
MAXIMUM=128*1024*1024*1024
ROWS=65536
SEGMENTS=4096
CUTS=16


def rows(value):
    """Only the original list or this fully checked concrete reader is admitted."""
    return type(value) is list or type(value) is Reader


def parse_budget(raw):
    json_budget.scan(raw, budget_error='segmented evidence parser budget',
                     balance_error='segmented evidence JSON balance', string_error='segmented evidence JSON string')


def canonical(raw):
    need(0<len(raw)<=ROW_BYTES,'segmented evidence row capacity')
    parse_budget(raw)
    def unique(pairs):
        need(len(pairs)==len(dict(pairs)) and all(re.fullmatch('[A-Za-z][A-Za-z0-9_]*',k) for k,_ in pairs),
             'segmented evidence JSON keys')
        return dict(pairs)
    def integer(value):
        result=int(value);need(-2**63<=result<2**63,'segmented evidence integer');return result
    def invalid(value):raise ValueError('segmented evidence JSON number')
    try:value=json.loads(raw.decode('ascii'),object_pairs_hook=unique,parse_int=integer,parse_float=invalid,parse_constant=invalid)
    except (UnicodeError,json.JSONDecodeError) as error:raise ValueError('segmented evidence JSON') from error
    need(type(value) is dict and f.canonical(value)==raw,'segmented evidence canonical object')
    return value


def identity(path,*,directory=False):
    info=path.lstat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink==1,
         'segmented evidence '+('directory' if directory else 'regular file'))
    return (info.st_dev,info.st_ino) if directory else (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


class Reader(Sequence):
    def __init__(self,root,*,cut=None,maximum=MAXIMUM):
        need(type(maximum) is int and 0<=maximum<=MAXIMUM,'segmented evidence byte limit')
        need(cut is None or type(cut) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',cut),'segmented evidence cut')
        self.root=Path(root);self.maximum=maximum;self.directories={};self.files={};self.rows=[];self.index_hashes={}
        for path in (self.root,self.root/'segments',self.root/'cuts'):self.directories[path]=identity(path,directory=True)
        need(self.names(self.root,3)=={'segments','cuts','complete.json'},'segmented evidence complete layout')
        complete=self.index(self.root/'complete.json')
        cut_names=self.names(self.root/'cuts',CUTS)
        need(all(re.fullmatch('[a-z][a-z0-9-]{0,63}\.json',name) for name in cut_names),'segmented evidence cut')
        snapshots={}
        for name in sorted(cut_names):
            value=self.index(self.root/'cuts'/name);parts=value['segments']
            need(parts==complete['segments'][:len(parts)],'segmented evidence cut prefix')
            snapshots[name[:-5]]=value
        need(cut is None or cut in snapshots,'segmented evidence absent cut')
        selected=complete if cut is None else snapshots[cut]
        need(self.names(self.root/'segments',SEGMENTS)=={v['path'] for v in complete['segments']},
             'segmented evidence segment inventory')
        # Validate the entire lifetime before exposing even its first row. The
        # caller cannot turn a damaged tail into a valid earlier observation.
        for segment in complete['segments']:self.scan(segment)
        need(len(self.rows)==complete['rows'],'segmented evidence complete rows')
        self.count=selected['rows'];self.complete=complete;self.cut=cut
        self.check_unchanged()

    @staticmethod
    def names(path,limit):
        names=set()
        for member in path.iterdir():
            need(len(names)<limit,'segmented evidence inventory capacity');names.add(member.name)
        return names

    def open(self,path):
        key=identity(path)
        need(path not in self.files or self.files[path]==key,'segmented evidence file changed')
        self.files.setdefault(path,key)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            need((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)==key and info.st_nlink==1,
                 'segmented evidence file changed')
            return os.fdopen(fd,'rb')
        except BaseException:os.close(fd);raise

    def index(self,path):
        with self.open(path) as stream:raw=stream.read(ROW_BYTES+1)
        value=canonical(raw)
        self.index_hashes[path]=hashlib.sha256(raw).digest()
        need(set(value)=={'schema','rows','bytes','segments'} and value['schema']==SCHEMA and
             type(value['rows']) is int and 0<=value['rows']<=ROWS and
             type(value['bytes']) is int and 0<=value['bytes']<=self.maximum and
             type(value['segments']) is list and len(value['segments'])<=SEGMENTS,'segmented evidence index')
        rows=total=0
        for i,part in enumerate(value['segments']):
            need(type(part) is dict and set(part)=={'path','rows','bytes','sha256'} and
                 part['path']==f'segment-{i:04d}.jsonl' and type(part['rows']) is int and 0<part['rows']<=ROWS and
                 type(part['bytes']) is int and 0<part['bytes']<=SEGMENT_BYTES and
                 type(part['sha256']) is str and re.fullmatch('[0-9a-f]{64}',part['sha256']),
                 'segmented evidence segment descriptor')
            rows+=part['rows'];total+=part['bytes']
        need(rows==value['rows'] and total==value['bytes'],'segmented evidence index totals')
        return value

    def scan(self,part):
        path=self.root/'segments'/part['path'];digest=hashlib.sha256();count=offset=0
        with self.open(path) as stream:
            need(os.fstat(stream.fileno()).st_size==part['bytes'],'segmented evidence segment extent')
            while True:
                raw=stream.readline(ROW_BYTES+2)
                if not raw:break
                need(len(self.rows)<ROWS and raw.endswith(b'\n') and 1<len(raw)<=ROW_BYTES+1,'segmented evidence row extent')
                canonical(raw[:-1]);digest.update(raw)
                self.rows.append((path,offset,len(raw),hashlib.sha256(raw).digest()))
                offset+=len(raw);count+=1
        need(count==part['rows'] and offset==part['bytes'] and digest.hexdigest()==part['sha256'],
             'segmented evidence segment content')

    def check_unchanged(self):
        for path,key in self.directories.items():need(identity(path,directory=True)==key,'segmented evidence directory changed')
        for path,key in self.files.items():need(identity(path)==key,'segmented evidence file changed')
        for path,digest in self.index_hashes.items():
            with self.open(path) as stream:raw=stream.read(ROW_BYTES+1)
            need(hashlib.sha256(raw).digest()==digest,'segmented evidence index changed')
        need(self.names(self.root,3)=={'segments','cuts','complete.json'} and
             self.names(self.root/'segments',SEGMENTS)=={p.name for p in self.files if p.parent==self.root/'segments'} and
             self.names(self.root/'cuts',CUTS)=={p.name for p in self.files if p.parent==self.root/'cuts'},
             'segmented evidence inventory changed')

    def __len__(self):return self.count

    def __getitem__(self,index):
        need(type(index) is int,'segmented evidence integer index only')
        if index<0:index+=self.count
        if not 0<=index<self.count:raise IndexError(index)
        for path,key in self.directories.items():need(identity(path,directory=True)==key,'segmented evidence directory changed')
        for path,key in self.files.items():
            if path.parent!=self.root/'segments':need(identity(path)==key,'segmented evidence file changed')
        path,offset,size,digest=self.rows[index]
        with self.open(path) as stream:stream.seek(offset);raw=stream.read(size)
        need(len(raw)==size and hashlib.sha256(raw).digest()==digest,'segmented evidence row content')
        need(identity(path)==self.files[path],'segmented evidence file changed')
        return canonical(raw[:-1])

    def __iter__(self):
        self.check_unchanged()
        for i in range(self.count):yield self[i]
        self.check_unchanged()
