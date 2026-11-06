"""Bind optional actual handle-to-handle observations to original resource journals.

The ordinary delta cannot distinguish swaps of equal-byte reservations. These
rows come from the committed transfer map, not a pairing inferred from totals.
They are diagnostic observations, never file or deletion authority.
"""
import json
from pathlib import Path
from . import resource_transitions as t

need=t.need
DIRECTORY='storage-transfer-captures'
SCHEMA='gse-v53-storage-transfers-v1'


def read(path):
    raw=t.collection.snapshot.s.regular(Path(path),128*t.MIB)
    def unique(pairs):
        need(len(pairs)==len(dict(pairs)),'storage transfer duplicate JSON key');return dict(pairs)
    value=json.loads(raw,object_pairs_hook=unique)
    need(type(value) is dict and type(value.get('rows')) is list and len(value['rows'])<=262144,
         'storage transfer encoded collection')
    need(t.collection.snapshot.f.canonical(value)==raw,'storage transfer canonical JSON')
    for row in [dict(value,rows=[]),*value['rows']]:
        encoded=t.collection.snapshot.f.canonical(row)
        need(len(encoded)<=65536,'storage transfer individual row capacity')
        t.collection.snapshot.f.parse_budget(encoded)
    return raw,value


def load(root,index):
    directory=Path(root)/DIRECTORY
    need(directory.is_dir() and not directory.is_symlink(),'storage transfer missing original capture')
    captured=t.collection.read_json(directory,'index.json',16384)
    need(type(captured) is dict and set(captured)=={'schema','root','eventsSha256','owners'} and
         captured['schema']=='gse-v53-storage-transfer-capture-v1' and captured['root']==index['root'] and
         captured['eventsSha256']==index['eventsSha256'] and type(captured['owners']) is list and
         len(captured['owners'])==len(index['owners']),'storage transfer original index')
    traces={};names={'index.json'};total=0
    for ref,original in zip(captured['owners'],index['owners']):
        need(type(ref) is dict and set(ref)=={'identity','path','sha256','resourceSha256'} and
             ref['identity']==original['identity'] and ref['path']==original['path'] and
             ref['resourceSha256']==original['sha256'],'storage transfer original resource binding')
        raw,value=read(directory/ref['path']);total+=len(raw)
        need(total<=256*t.MIB and t.collection.digest(raw)==ref['sha256'],'storage transfer capture digest/capacity')
        traces[ref['identity']['node']]=value;names.add(ref['path'])
    need({p.name for p in directory.iterdir()}==names,'storage transfer capture inventory')
    return traces


def replay(trace,value):
    t.replay(trace)
    need(type(value) is dict and set(value)=={'schema','transitions','truncated','failed','rows'} and
         value['schema']==SCHEMA and value['truncated'] is False and value['failed'] is False and
         type(value['transitions']) is int and value['transitions']==trace['transitions'] and
         type(value['rows']) is list and len(value['rows'])<=262144,'storage transfer complete recorder')
    expected=[v['sequence'] for v in trace['changes'] if v['event']=='TRANSFER']
    need(len(value['rows'])==len(expected),'storage transfer complete switch coverage')
    for row,seq in zip(value['rows'],expected):
        need(type(row) is dict and set(row)=={'resourceSequence','moves'} and
             type(row['resourceSequence']) is int and row['resourceSequence']==seq and
             type(row['moves']) is list and 0<len(row['moves'])<=32,'storage transfer exact ordered switch')
        moves=row['moves']
        need(all(type(m) is dict and set(m)=={'before','after'} for m in moves),'storage transfer pair shape')
        t.charges([m['before'] for m in moves]);t.charges(sorted([m['after'] for m in moves],key=t.order_key))
        need(all(m['before']['unit']==m['after']['unit'] and m['before']['bytes']==m['after']['bytes'] and
                 not m['before']['claimSource'] and not m['after']['claimSource'] and
                 m['before']['unit'] not in ('CONTROL','WAITER') for m in moves),'storage transfer exact preserved extent')
    # Reconstruct both states, including unchanged names and cyclic same-size
    # renames whose ordinary delta is empty. Never zip sorted removed/added sets.
    recorded={v['resourceSequence']:v for v in value['rows']};state={}
    for row in trace['changes']:
        seq=row['sequence'];before=dict(state)
        for v in row['removed']:del state[t.key(v)]
        for v in row['added']:state[t.key(v)]=v
        if seq not in recorded:continue
        moves=recorded[seq]['moves']
        for move in moves:
            need(before.pop(t.key(move['before']),None)==move['before'],'storage transfer live predecessor')
        for move in moves:
            need(t.key(move['after']) not in before,'storage transfer occupied successor')
            before[t.key(move['after'])]=move['after']
        need(before==state,'storage transfer exact resulting state')
    return value['rows']


def all_owners(traces,transfers):
    need(type(transfers) is dict and set(traces)==set(transfers) and traces,'storage transfer complete original owners')
    return {node:replay(trace,transfers[node]) for node,trace in traces.items()}
