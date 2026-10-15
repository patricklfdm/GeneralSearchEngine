"""Bounded lossless observation decoding. This does not establish replica correctness.

Small rows are inline; large rows reference exact 4 KiB content-addressed chunks.
Readers stream one reconstructed row at a time and may be iterated again. No row
is dropped, synthesized or parsed as authority merely because its hash matches.
"""
import base64
from dataclasses import dataclass
from pathlib import Path
import re
from scripts.v51.performance_model import strict_json
from .evidence import need,digest

SCHEMA='gse-v52-chunk-trace-v1'
META=('node','pid','generation','order','localNanos','event','groupId','manifestDigest')
CHUNK=4096
INLINE=8192
HEX=re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class Limits:
    raw_line:int=4<<20
    encoded_line:int=128<<10
    decoded_bytes:int=8<<30
    encoded_bytes:int=128<<20
    chunk_bytes:int=512<<20
    chunks:int=131072
    rows:int=262144


class Trace:
    def __init__(self,path,*,node,limits=Limits()):
        self.path=Path(path);self.directory=self.path.with_name(self.path.name+'.chunks')
        self.node=node;self.limits=limits;self.stats=None
        need(node in ('node-1','node-2','node-3'),'measurement trace voter')
        need(all(type(v) is int and v>0 for v in vars(limits).values()),'measurement decoder limits')
        need(self.path.is_file() and not self.path.is_symlink() and
             0<self.path.stat().st_size<=limits.encoded_bytes,'measurement encoded trace bound/type')
        need(not self.path.with_name(self.path.name+'.pending').exists() and
             not self.path.with_name(self.path.name+'.staging').exists(),'measurement unfinished append')
        self.members=self.inventory()

    def inventory(self):
        need(self.directory.is_dir() and not self.directory.is_symlink(),'measurement chunk directory')
        members={};total=0
        for path in self.directory.iterdir():
            need(len(members)<self.limits.chunks,'measurement chunk count bound')
            need(path.is_file() and not path.is_symlink() and path.name.endswith('.bin') and
                 HEX.fullmatch(path.name[:-4]) is not None,'measurement chunk member type/name')
            need(0<path.stat().st_size<=CHUNK,'measurement chunk length')
            with path.open('rb') as stream:raw=stream.read(CHUNK+1)
            need(0<len(raw)<=CHUNK and digest(raw)==path.stem,'measurement chunk digest')
            total+=len(raw);need(total<=self.limits.chunk_bytes,'measurement stored chunk byte bound')
            members[path.stem]=len(raw)
        return members

    def raw_rows(self):
        self.stats=None;decoded=encoded=count=0;orders={};clocks={};used=set();pids={};last_generation=0;authority=None
        with self.path.open('rb') as source:
            while True:
                line=source.readline(self.limits.encoded_line+1)
                if not line:break
                need(len(line)<=self.limits.encoded_line and line.endswith(b'\n'),'measurement reference line bound/completeness')
                encoded+=len(line);count+=1
                need(encoded<=self.limits.encoded_bytes and count<=self.limits.rows,'measurement reference total bound')
                ref=strict_json(line)
                need(type(ref) is dict and set(ref) in (set(META)|{'encoding','bytes','sha256','inline'},
                     set(META)|{'encoding','bytes','sha256','pieces'}) and ref['encoding']==SCHEMA,'measurement reference fields')
                size=ref['bytes'];need(type(size) is int and 0<size<=self.limits.raw_line,'measurement decoded row bound')
                decoded+=size;need(decoded<=self.limits.decoded_bytes,'measurement decoded total bound')
                need(type(ref['sha256']) is str and HEX.fullmatch(ref['sha256']) is not None,'measurement row digest shape')
                if 'inline' in ref:
                    need(size<=INLINE and type(ref['inline']) is str and len(ref['inline'])==4*((size+2)//3),'measurement inline bound')
                    raw=base64.b64decode(ref['inline'],validate=True)
                else:
                    pieces=ref['pieces'];need(size>INLINE and type(pieces) is list and len(pieces)==(size+CHUNK-1)//CHUNK,'measurement chunk references')
                    parts=[]
                    for i,key in enumerate(pieces):
                        need(type(key) is str and HEX.fullmatch(key) is not None and key in self.members,'measurement missing/invalid chunk')
                        path=self.directory/(key+'.bin')
                        need(path.is_file() and not path.is_symlink() and path.stat().st_size==self.members[key],'measurement changed chunk')
                        with path.open('rb') as stream:part=stream.read(CHUNK+1)
                        need(len(part)<=CHUNK and digest(part)==key,'measurement chunk digest')
                        need(len(part)==(CHUNK if i<len(pieces)-1 else size-CHUNK*i),'measurement chunk position length')
                        parts.append(part);used.add(key)
                    raw=b''.join(parts)
                need(len(raw)==size and digest(raw)==ref['sha256'],'measurement reconstructed row digest/length')
                need(raw.endswith(b'\n') and len(raw.splitlines())==1,'measurement reconstructed row completeness')
                row=strict_json(raw)
                need(type(row) is dict and all(k in row and type(row[k]) is type(ref[k]) and row[k]==ref[k] for k in META),'measurement reconstructed metadata')
                need(row['node']==self.node and all(type(row[k]) is int and row[k]>0 for k in ('pid','generation','order','localNanos')),
                     'measurement process/counter types')
                need(type(row['event']) is str and 0<len(row['event'])<=128 and type(row['groupId']) is str and
                     type(row['manifestDigest']) is str and HEX.fullmatch(row['manifestDigest']) is not None,'measurement observation identity')
                pid,generation=row['pid'],row['generation'];identity=pid,generation
                identity_authority=row['groupId'],row['manifestDigest']
                need(authority is None or authority==identity_authority,'measurement observation authority changed')
                authority=identity_authority
                need(generation in (last_generation,last_generation+1) and (generation not in pids or pids[generation]==pid) and
                     (pid not in pids.values() or pids.get(generation)==pid),'measurement process generation reuse/order')
                pids[generation]=pid;last_generation=generation
                need(row['order']==orders.get(identity,0)+1 and row['localNanos']>=clocks.get(identity,0),'measurement observation order')
                orders[identity]=row['order'];clocks[identity]=row['localNanos']
                yield raw
        need(count>0 and encoded==self.path.stat().st_size and self.inventory()==self.members,'measurement trace changed during decoding')
        self.stats=dict(rows=count,decodedBytes=decoded,encodedBytes=encoded,chunkBytes=sum(self.members.values()),
                        chunks=len(self.members),unreferencedChunks=len(set(self.members)-used),processGenerations=len(pids))

    def __iter__(self):
        for raw in self.raw_rows():yield strict_json(raw)

    def verify(self):
        for _ in self.raw_rows():pass
        return dict(status='PASS',execution='lossless-observation-decoding-only',**self.stats)
