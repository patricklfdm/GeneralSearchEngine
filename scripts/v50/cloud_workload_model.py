"""Independent payload replay and deterministic cloud request oracle, without Java decoders."""
import json
import struct
from . import admission_format as f
from .performance_model import OPERATIONS, OP_IDS, INDEXES, document, encoded, blob, digest, canonical, display


def operation(cycle, call, sustained=False):
    lane, lane_call = call % 4, call // 4
    op = ('QUERY' if lane_call % 4 == 3 else 'UPDATE') if sustained else OPERATIONS[call % 10]
    size = 16 if op.endswith('_ALL') else 1
    keys = [lane+1 if sustained else 1+(cycle+i)%4096 if op.startswith('UPDATE') else 100000+cycle*100+i for i in range(size)]
    if op in ('INDEX_DROP','INDEX_CREATE','QUERY'): keys=[]
    if op=='GET': keys=[1+cycle%4096]
    return dict(operation=op, keys=keys, revision=lane_call+1 if sustained else cycle+1,
                lane=lane if sustained else 0, documents=0 if op.startswith('INDEX') or op=='QUERY' else size)


def payload(op, keys, revision):
    result=struct.pack('>H',1)
    if op in ('INDEX_DROP','INDEX_CREATE'):
        return result+blob(('category' if op=='INDEX_DROP' else INDEXES[1]).encode())
    result+=struct.pack('>i',len(keys))
    for key in keys:
        result+=blob(struct.pack('>i',key))
        if not op.startswith('REMOVE'):result+=blob(encoded(document(key,revision)))
    return result


def entry(raw):
    f.check(len(raw)<=2560,'encoded entry bound')
    r=f.record(raw,5,2560)
    identity,epoch,incarnation,index,op=r.take(32),r.number('q'),r.take(16),r.number('q'),r.number('B')
    previous_epoch,previous_index,previous=r.number('q'),r.number('q'),r.take(32)
    size,claimed=r.number('i'),r.take(32);body=r.take(size);r.end()
    f.check(size<=2048 and f.sha(body)==claimed and (op<=8 or not body),'entry payload bound/digest')
    return dict(identity=identity,epoch=epoch,incarnation=incarnation,index=index,op=op,previousEpoch=previous_epoch,
                previousIndex=previous_index,previous=previous,digest=raw[16:48].hex(),payload=body,payloadSha256=claimed.hex())


class Model:
    def __init__(self):
        self.docs={i:document(i,0) for i in range(1,4097)};self.indexes=list(INDEXES);self.sequence=256
    def apply(self,op,body):
        if op>=9:return
        r=f.Reader(body);f.check(r.number('H')==1,'application operation version')
        name=next(k for k,v in OP_IDS.items() if v==op)
        if name=='INDEX_DROP':
            f.check(r.text()=='category' and INDEXES[1] in self.indexes,'drop semantics');self.indexes.remove(INDEXES[1])
        elif name=='INDEX_CREATE':
            f.check(r.text()==INDEXES[1] and INDEXES[1] not in self.indexes,'create semantics');self.indexes.append(INDEXES[1]);self.indexes.sort(key=lambda value:json.loads(value)["field"])
        else:
            count=r.count(16,8);f.check(count>0,'empty mutation');keys=[]
            for _ in range(count):
                key=struct.unpack('>i',r.blob(4))[0];keys.append(key)
                if name.startswith('REMOVE'):
                    f.check(key in self.docs,'remove absent key');del self.docs[key]
                else:
                    raw=r.blob(256);parts=raw.decode().split('\n');f.check(len(parts)==5,'document codec')
                    doc=(int(parts[0]),parts[1],parts[2],int(parts[3]),parts[4])
                    f.check(doc[0]==key and encoded(doc)==raw,'noncanonical document')
                    if name.startswith('ADD'): f.check(key not in self.docs,'duplicate add')
                    else:f.check(key in self.docs,'update absent key')
                    self.docs[key]=doc
            f.check(len(keys)==len(set(keys)),'duplicate mutation key')
        r.end();self.sequence+=1
        f.check(len(self.docs)<=8192,'application document cap')
    def view(self, keys=(), documents=False):
        docs=[encoded(d).decode() for d in self.docs.values()]
        return dict(sequence=self.sequence,count=len(docs),documentsSha256=digest(canonical(docs)),indexCount=len(self.indexes),
                    queryDigest=digest(canonical([d[0] for d in self.docs.values() if d[2]=='guide'])),documents=docs if documents else None,
                    gets={i:display(self.docs[i]) for i in keys})
