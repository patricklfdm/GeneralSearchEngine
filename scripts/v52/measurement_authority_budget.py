"""Pre-admit aggregate state before general physical replay allocates its maps.

Only fingerprints and bounded descriptors are retained here. Passing this scan
does not prove quorum, a chosen entry, a durable publication or query truth.
"""
from scripts.v51 import runtime_evidence as physical
from .evidence import need,digest

LIMITS={'entries':(8192,16<<20),'votes':(65536,64<<20),'proofs':(65536,64<<20),
        'replies':(131072,512<<20),'bases':(128,8<<20),'basisChunks':(131072,64<<20),
        'selections':(64,4<<20)}
MAX_SELECTION_EXPANSION=128<<20
MAX_SELECTORS=8192


class Retained:
    def __init__(self,name,count,byte_limit):
        self.name=name;self.count=count;self.byte_limit=byte_limit;self.values={};self.bytes=0
    def add(self,key,data):
        fingerprint=(digest(data),len(data))
        if key in self.values:
            need(self.values[key]==fingerprint,'measurement changed retained '+self.name);return False
        need(len(self.values)<self.count and self.bytes+len(data)<=self.byte_limit,'measurement retained budget '+self.name)
        self.values[key]=fingerprint;self.bytes+=len(data);return True
    def report(self):return dict(count=len(self.values),bytes=self.bytes)


def validate(traces,manifest):
    buckets={name:Retained(name,*bounds) for name,bounds in LIMITS.items()};descriptors={};selected={};selectors=0
    for node,rows in traces.items():
        for row in rows:
            need(row['node']==node and row['groupId']==manifest['groupId'] and row['manifestDigest']==manifest['digest'],
                 'measurement preflight trace authority')
            event=row['event']
            if event=='FORCE' and row['kind'] in ('ACCEPT','PROOF'):
                data=physical.raw(row['record']);record=physical.frame(row['record'],row['kind'],manifest)
                if row['kind']=='ACCEPT':
                    entry_bytes=physical.raw(record['entry']);entry=physical.frame(record['entry'],'ENTRY',manifest)
                    need(1<=entry['index']<=LIMITS['entries'][0],'measurement retained entry index bound')
                    buckets['entries'].add(record['entryDigest'],entry_bytes)
                    buckets['votes'].add((node,record['epoch'],record['incarnation'],entry['index'],record['entryDigest']),data)
                else:buckets['proofs'].add(digest(data),data)
            elif event in ('REPLY','RECEIVED'):
                data=physical.raw(row['frame']);buckets['replies'].add(digest(data),data)
                wire=physical.f.wire(data,manifest);payload=wire['payload'];kind=wire['type']
                for raw in ([payload['basis']] if kind=='PROMISE' else payload['bases'] if kind=='SELECTED_OFFER' else []):
                    data=physical.raw(raw);basis=physical.frame(raw,'BASIS',manifest);key=(basis['node'],basis['basisId'])
                    buckets['bases'].add(key,data);descriptors[key]=dict(bytes=basis['imageBytes'],sha256=data[16:48].hex())
                if kind=='BASIS_CHUNK' and payload['action']=='DATA':
                    data=physical.raw(payload['chunk'])
                    need(len(data)>0,'measurement empty retained basis chunk')
                    buckets['basisChunks'].add((wire['sender'],payload['basisId'],payload['offset']),data)
                if kind=='SELECTED_OFFER' and payload['response']:
                    data=physical.raw(payload['selected']);selection=physical.frame(payload['selected'],'SELECTED',manifest)
                    if buckets['selections'].add(digest(data),data):selected[digest(data)]=selection['bases']
            elif event=='STORAGE_CUT' and row['cut']=='SELECTOR_BEFORE_ACK':
                selectors+=1;need(selectors<=MAX_SELECTORS,'measurement retained selector count')
    # Repeated choices can share a basis but allocate separate selected snapshots
    # in the general validator. Charge each selected pair before reconstructing it.
    expansion=0
    for pair in selected.values():
        for value in pair:
            key=(value['node'],value['basisId']);need(key in descriptors,'measurement budget selection lacks descriptor')
            descriptor=descriptors[key];need(descriptor['sha256']==value['basisDigest'],'measurement budget selected descriptor differs')
            expansion+=descriptor['bytes']
            need(expansion<=MAX_SELECTION_EXPANSION,'measurement retained selected expansion budget')
    return dict(status='PASS',execution='bounded-authority-admission-only',qualifiedMeasurement=False,
                retained={k:v.report() for k,v in buckets.items()},selectedExpansionBytes=expansion,selectors=selectors)
