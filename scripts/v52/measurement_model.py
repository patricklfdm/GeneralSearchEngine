"""Frozen offered program and independent document bytes; this never runs a workload."""
import argparse
from pathlib import Path
import struct
from .evidence import need,digest,encoded
from .public_reads_evidence import read

PLAN=Path(__file__).resolve().parents[2]/'docs/v5x/v5.2/phase6-program.json'
PLAN_SHA='da2c68dc014595e176e1842a85181ea2d6fbd8ef9d8fef5c712993a0aa9126be'
KINDS=('get','filter','ranked','highlight','explain')
MODES=('published-v51-legacy-strong','candidate-legacy-strong','candidate-explicit-strong','candidate-stale','candidate-minimum')


def document(key,revision,seed=52):
    need(type(key) is int and 1<=key<=64 and type(revision) is int and 0<=revision<=3 and seed==52,'measurement document domain')
    return dict(id=key,value=f'java search memory group {(key+seed)%8} item {key} revision {revision}')


def encode_document(value):
    need(set(value)=={'id','value'} and type(value['id']) is int and type(value['value']) is str,'measurement document fields')
    raw=struct.pack('>i',value['id'])+value['value'].encode('utf-8');need(len(raw)<=128,'measurement document byte bound');return raw


def decode_document(raw):
    need(isinstance(raw,bytes) and 4<len(raw)<=128,'measurement document byte bound')
    key=struct.unpack('>i',raw[:4])[0];value=raw[4:].decode('utf-8','strict')
    matches=[document(key,r) for r in range(4) if document(key,r)['value']==value]
    need(len(matches)==1,'document outside frozen measurement program');return matches[0]


def query(ordinal):
    need(type(ordinal) is int and 0<=ordinal<1800,'measurement read ordinal')
    kind=KINDS[ordinal%5];cycle=ordinal//5
    if kind=='get':return dict(kind=kind,id=1+cycle%64)
    if kind=='explain':return dict(kind=kind,id=1+cycle%64,text='java search',limit=5)
    if kind=='filter':return dict(kind=kind,prefix=f'java search memory group {cycle%8} ')
    if kind=='ranked':return dict(kind=kind,text='java search',limit=5)
    return dict(kind=kind,text='java search',limit=5,contextCharacters=3,maxFragmentsPerField=3)


def program():
    calls=[]
    for ordinal in range(1800):
        offset=ordinal*100_000_000
        calls.append(dict(kind='read',ordinal=ordinal,offsetNanos=offset,window='warmup' if offset<60_000_000_000 else 'measured',query=query(ordinal)))
    for ordinal in range(180):
        offset=ordinal*1_000_000_000+50_000_000
        calls.append(dict(kind='update',ordinal=ordinal,offsetNanos=offset,window='warmup' if offset<60_000_000_000 else 'measured',
                          document=document(1+ordinal%64,1+ordinal//64)))
    return sorted(calls,key=lambda v:v['offsetNanos'])


def corpus():return [document(i,0) for i in range(1,65)]


def queries():
    """Every distinct descriptor in the offered program, in first-use order."""
    return list({encoded(query(i)):query(i) for i in range(1800)}.values())


def corpus_bytes():
    docs=[encode_document(v) for v in corpus()]
    return b''.join(struct.pack('>i',len(raw))+raw for raw in docs)


def projection(calls):
    state={v['id']:v for v in corpus()};sequence=1
    for call in calls:
        if call['kind']=='update':
            value=decode_document(encode_document(call['document']));need(value['id'] in state,'measurement update missing key')
            state[value['id']]=value;sequence+=1
        else:need(call['kind']=='read','measurement unknown command')
    return dict(sequence=sequence,documents=list(state.values()))


def validate(value):
    need(digest(encoded(value))==PLAN_SHA,'unreviewed measurement program')
    need(digest((PLAN.parent/'published-controls.json').read_bytes())==value['controlsManifestSha256'],'measurement published controls changed')
    calls=program();reads=[v for v in calls if v['kind']=='read'];writes=[v for v in calls if v['kind']=='update']
    need(len(calls)==1980 and len(reads)==1800 and len(writes)==180,'measurement offered counts')
    need(all(a['offsetNanos']<b['offsetNanos'] for a,b in zip(calls,calls[1:])),'measurement offered order')
    need(digest(corpus_bytes())==value['corpus']['sha256'] and digest(encoded(calls))==value['m01']['programSha256'],'measurement corpus/program digest')
    need([v['name'] for v in value['m01']['modes']]==list(MODES),'measurement mode identities')
    for window,count in (('warmup',600),('measured',1200)):
        selected=[v for v in reads if v['window']==window]
        need(len(selected)==count and all(sum(v['query']['kind']==kind for v in selected)==count//5 for kind in KINDS),'measurement exact query mix')
    return dict(status='PASS',execution='program-admission-only',measured=False,paidCloud=False,programSha256=PLAN_SHA,
                corpusBytes=len(corpus_bytes()),documents=64,baseSequence=1,finalSequence=projection(calls)['sequence'],
                callsPerHistory=len(calls),readsPerHistory=len(reads),writesPerHistory=len(writes),healthyHistories=15,
                warmupCalls=660,measuredCalls=1320,minimumHealthyWindowSeconds=2700)


def load():return validate(read(PLAN))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args();result=load()
    if args.output:
        args.output.mkdir(parents=True,exist_ok=False)
        for name,value in (('corpus.json',corpus()),('calls.json',program()),('final-state.json',projection(program())),('receipt.json',result)):
            (args.output/name).write_bytes(encoded(value)+b'\n')
    print(encoded(result).decode())
