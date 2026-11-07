"""On-demand decoded observations bound to an independently checked wire reader.

Only the explicit segmented input uses these views. They keep row positions,
hashes and causal metadata, never complete decoded frames or transfer images.
The returned frames/bytes are fresh values; original observations are immutable.
"""
import base64
from collections.abc import Mapping, MutableMapping
import copy
import hashlib
from . import segmented_evidence as segmented
from .source_exchange_evidence import wire

need=segmented.need
MIB=1024*1024


class Exchange(MutableMapping):
    def __init__(self, source, index, metadata):
        need(type(source) is segmented.Reader and type(index) is int and 0<=index<len(source),
             'segmented transcript original row')
        need(type(metadata) is dict and not {'request','response'} & metadata.keys() and
             {'kind','answer','requestHash','responseHash'}<=metadata.keys(),'segmented transcript metadata')
        self.source=source;self.index=index;self.metadata=dict(metadata)

    def __getitem__(self,key):
        if key not in ('request','response'):return self.metadata[key]
        original=self.source[self.index];raw=original[key]
        kind,value=wire(raw)
        need(kind==self.metadata['kind' if key=='request' else 'answer'] and
             hashlib.sha256(base64.b64decode(raw,validate=True)).hexdigest()==self.metadata[key+'Hash'],
             'segmented transcript frame binding')
        return value

    def __setitem__(self,key,value):
        need(key not in ('request','response'),'segmented transcript immutable frame')
        self.metadata[key]=value

    def __delitem__(self,key):
        need(key not in ('request','response'),'segmented transcript immutable frame')
        del self.metadata[key]

    def __iter__(self):return iter((*self.metadata,'request','response'))
    def __len__(self):return len(self.metadata)+2
    def __deepcopy__(self,memo):
        result=Exchange(self.source,self.index,copy.deepcopy(self.metadata,memo));memo[id(self)]=result;return result


def exchange(source,index,**value):
    """Drop decoded frames only after the caller validated the original exchange."""
    if type(source) is not segmented.Reader:return value
    return Exchange(source,index,{k:v for k,v in value.items() if k not in ('request','response')})


class WireIndex(Mapping):
    def __init__(self,source):
        need(type(source) is segmented.Reader,'segmented transcript original index')
        self.source=source;self.positions={}
        for index,row in enumerate(source):
            identifier=row['connection']['id']
            need(identifier not in self.positions,'segmented transcript duplicate connection')
            self.positions[identifier]=index

    def __iter__(self):return iter(self.positions)
    def __len__(self):return len(self.positions)
    def __getitem__(self,key):return self.source[self.positions[key]]


def by_connection(source):
    return WireIndex(source) if type(source) is segmented.Reader else {v['connection']['id']:v for v in source}


class Content(Mapping):
    def __init__(self, offer, commit, chunks, kind, size, digest):
        need(type(offer) is Exchange and type(commit) is Exchange and commit.source is offer.source and
             all(type(row) is Exchange and row.source is offer.source for row in chunks),
             'segmented transcript transfer ownership')
        need(type(size) is int and 0<=size<=64*MIB and len(chunks)<=segmented.ROWS,
             'segmented transcript transfer bound')
        self.offer=offer;self.commit=commit;self.chunks=tuple(chunks)
        self.kind=kind;self.size=size;self.digest=digest

    def __iter__(self):return iter(('offer','commit','raw','kind'))
    def __len__(self):return 4
    def __getitem__(self,key):
        if key=='offer':return self.offer
        if key=='commit':return self.commit
        if key=='kind':return self.kind
        if key!='raw':raise KeyError(key)
        raw=bytearray();digest=hashlib.sha256()
        for row in self.chunks:
            payload=row['response']['payload'];chunk=base64.b64decode(payload['bytes'],validate=True)
            need(payload['offset']==len(raw) and 0<len(chunk)<=4*MIB and len(raw)+len(chunk)<=self.size and
                 hashlib.sha256(chunk).hexdigest()==payload['digest'],'segmented transcript changed chunk')
            raw.extend(chunk);digest.update(chunk)
        need(len(raw)==self.size and digest.hexdigest()==self.digest,'segmented transcript changed content')
        return bytes(raw)

    def __deepcopy__(self,memo):
        result=Content(copy.deepcopy(self.offer,memo),copy.deepcopy(self.commit,memo),
                       [copy.deepcopy(row,memo) for row in self.chunks],self.kind,self.size,self.digest)
        memo[id(self)]=result;return result
