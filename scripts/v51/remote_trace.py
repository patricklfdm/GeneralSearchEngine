"""Bounded, lossless large-string dictionary for guest observation streams."""
import base64
import re
import zlib
from . import performance_model as m


class Decoder:
    def __init__(self,budget=None):
        self.strings={};self.expanded=0
        self.budget=budget if budget is not None else [6<<30]

    def row(self,value,encoded_bytes):
        # JSON objects have no field ordering. Definitions within this same row
        # are available to its references; references to later rows still fail.
        m.need(encoded_bytes<=4<<20,'encoded trace row bound')
        self.definition_bytes=encoded_bytes
        self.definitions(value)
        self.row_bytes=encoded_bytes
        result=self.decode(value)
        m.need(self.row_bytes<=4<<20,'logical trace row bound')
        self.expanded+=self.row_bytes
        self.budget[0]-=self.row_bytes
        m.need(self.budget[0]>=0,'trace expansion budget')
        return result

    def definitions(self,value):
        if isinstance(value,list):
            for item in value:self.definitions(item)
        elif isinstance(value,dict):
            if '$gseString' not in value:
                for item in value.values():self.definitions(item)
                return
            m.need(set(value)=={'$gseString'} and isinstance(value['$gseString'],dict),'trace encoding fields')
            record=value['$gseString']
            if set(record)=={'ref'}:return
            m.need(set(record)=={'sha256','bytes','zlib'} and re.fullmatch('[0-9a-f]{64}',record['sha256']) and
                   type(record['bytes']) is int and 0<record['bytes']<=4<<20,'trace string identity/size')
            m.need(len(self.strings)<20000 and record['sha256'] not in self.strings,'trace dictionary duplicate/limit')
            wrapper_bytes=len(m.canonical({'$gseString':record}))
            m.need(self.definition_bytes+record['bytes']-wrapper_bytes<=min(4<<20,self.budget[0]),'logical trace row bound')
            encoded=base64.b64decode(record['zlib'],validate=True)
            inflater=zlib.decompressobj()
            raw=inflater.decompress(encoded,record['bytes']+1)
            m.need(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail and
                   len(raw)==record['bytes'] and m.sha(raw)==record['sha256'],'trace string bytes/hash')
            text=raw.decode('utf-8','strict')
            expanded_bytes=len(m.canonical(text))
            self.definition_bytes+=expanded_bytes-wrapper_bytes
            m.need(self.definition_bytes<=min(4<<20,self.budget[0]),'logical trace row bound')
            self.strings[record['sha256']]=(text,expanded_bytes)

    def decode(self,value):
        if isinstance(value,list):return [self.decode(v) for v in value]
        if not isinstance(value,dict):return value
        if '$gseString' not in value:return {k:self.decode(v) for k,v in value.items()}
        record=value['$gseString'];digest=record.get('ref',record.get('sha256'))
        m.need(digest in self.strings,'trace reference precedes definition')
        text,expanded_bytes=self.strings[digest]
        self.row_bytes+=expanded_bytes-len(m.canonical(value))
        m.need(self.row_bytes<=4<<20,'logical trace row bound')
        return text
