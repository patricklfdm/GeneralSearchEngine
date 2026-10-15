"""Private bounded spool of already losslessly decoded observation bytes.

Decode every original row and enforce all trace bounds before exposing an iterator.
Semantic validators still parse fresh rows and decode actual authority on each
pass. Nothing here establishes publication, query correctness or member success.
"""
from contextlib import contextmanager,ExitStack
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from . import measurement_trace as trace,measurement_bundle as bundle
from .evidence import need

HEADER=36  # uint32 length, SHA-256, then original UTF-8 row bytes


class VerifiedTrace:
    def __init__(self,source,directory):
        self.limits=source.limits;self.file=tempfile.TemporaryFile(dir=directory);self.size=0;self.count=0
        digest=hashlib.sha256()
        try:
            for raw in source.raw_rows():
                header=struct.pack('>I',len(raw))+hashlib.sha256(raw).digest()
                self.file.write(header);self.file.write(raw);digest.update(header);digest.update(raw)
                self.count+=1;self.size+=HEADER+len(raw)
                need(self.count<=self.limits.rows and self.size<=self.limits.decoded_bytes+HEADER*self.limits.rows,
                     'measurement verified spool bound')
            self.file.flush();self.sha256=digest.digest();self.stats=dict(source.stats)
        except BaseException:self.close();raise

    def close(self):self.file.close()

    def read(self,offset,size):
        need(not self.file.closed,'measurement verified spool closed')
        result=os.pread(self.file.fileno(),size,offset)
        need(len(result)==size,'measurement verified spool truncated')
        return result

    def __iter__(self):
        offset=0;digest=hashlib.sha256()
        for _ in range(self.count):
            header=self.read(offset,HEADER);size=struct.unpack('>I',header[:4])[0]
            need(0<size<=self.limits.raw_line and offset+HEADER+size<=self.size,'measurement verified spool row bound')
            raw=self.read(offset+HEADER,size)
            need(hashlib.sha256(raw).digest()==header[4:],'measurement verified spool row changed')
            digest.update(header);digest.update(raw);offset+=HEADER+size
            # The strict parser, original digest, metadata and ordering checks
            # already ran on these exact bytes. Return a new mutable row each
            # time, so negative views cannot contaminate another iteration.
            yield json.loads(raw)
        need(offset==self.size and os.fstat(self.file.fileno()).st_size==self.size and digest.digest()==self.sha256,
             'measurement verified spool changed')

    def verify(self):
        need(not self.file.closed and os.fstat(self.file.fileno()).st_size==self.size,'measurement verified spool changed')
        digest=hashlib.sha256();offset=0
        while offset<self.size:
            raw=self.read(offset,min(1<<20,self.size-offset));digest.update(raw);offset+=len(raw)
        need(digest.digest()==self.sha256,'measurement verified spool changed')


@contextmanager
def traces(root,output):
    """Bind original inventory around all positive/negative semantic passes."""
    root=Path(root).resolve();output=Path(output).resolve()
    need(output!=root and root not in output.parents and output not in root.parents,'measurement verified spool overlaps input')
    original=bundle.inventory(root)
    with tempfile.TemporaryDirectory(prefix='verified-',dir=output) as directory,ExitStack() as stack:
        values={}
        for node in ('node-1','node-2','node-3'):
            value=VerifiedTrace(trace.Trace(root/(node+'-trace.jsonl'),node=node),directory)
            stack.callback(value.close);values[node]=value
        try:yield values
        finally:
            for value in values.values():value.verify()
            need(bundle.inventory(root)==original,'measurement source changed during verified replay')
