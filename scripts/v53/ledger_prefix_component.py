"""Real ledger-writer component with conditional original transaction snapshots."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import native_carried_ledger_prefixes as p


def metadata(raw,kind):
    if kind=='peer':return p.model.retention.peer.peers.decode(raw)
    need=p.need;future=p.model.retention.future.future
    need(type(raw) is bytes and 48<len(raw)<=3*1024*1024,'ledger component future extent')
    need(struct.unpack('>IHHI',raw[:12])==(0x47534654,1,3,len(raw)) and bytes.fromhex(p.shared.sha(raw[44:]))==raw[12:44],
         'ledger component future frame')
    at=44
    def part():
        nonlocal at
        need(at+4<=len(raw),'ledger component future part');size=int.from_bytes(raw[at:at+4],'big');at+=4
        need(0<size<=len(raw)-at,'ledger component future part');value=raw[at:at+size];at+=size;return value
    encoded=part();meta=json.loads(encoded,object_pairs_hook=p.model.retention.peer.peers.unique)
    need(type(meta) is dict and set(meta)=={'root','owner','revision','previous','parent','peers'} and
         type(meta['revision']) is int and 0<=meta['revision']<=2**63-2,'ledger component future metadata')
    need(at+4<=len(raw),'ledger component future inventory');count=int.from_bytes(raw[at:at+4],'big');at+=4
    need(count in (0,9,10),'ledger component future inventory')
    records={name:part() for name in future.RECORDS[:count]}
    need(at==len(raw) and future.frame(meta,records)==raw,'ledger component future exact bytes');return meta


def validate(root,sidecar=None):
    root=Path(root);sidecar=root/'captures' if sidecar is None else Path(sidecar)
    original=p.collection.inventory(root);result=p.shared.g.json_file(root/'result.json')[1]
    p.need(set(result)=={'schema','cases','pid','root','expectedBytes','nativeCarriedProcess'} and
           result['schema']=='gse-v53-ledger-prefix-component-v1' and result['expectedBytes']=='conditional-transaction-snapshots' and
           result['nativeCarriedProcess'] is False and type(result['cases']) is list,'ledger component scope')
    cases=result['cases'];names=[f'case-{i:02}' for i in range(10)]
    p.need(len(cases)==10 and [v['name'] for v in cases]==names and
           {v.name for v in root.iterdir()}=={'captures','prerequisite','events.json','result.json',*names},'ledger component exact cases')
    raw=(root/'events.json').read_bytes();events=json.loads(raw);header=p.shared.g.json_file(sidecar/'collection.json')[1]
    p.need(set(header)=={'schema','root','life','pid','terminal','eventsSha256','captures','storedBytes'} and header['schema']==p.SCHEMA and
           header['root']==result['root'] and type(header['pid']) is int and type(result['pid']) is int and header['pid']==result['pid'] and
           type(header['life']) is int and header['life']==2 and header['terminal']=='CLOSED' and header['eventsSha256']==p.shared.sha(raw),
           'ledger component original header')
    inventory=p.model.forces.c.inventory;initial=inventory(root/names[0]/'before')
    p.f.decode(initial['root.gsr'],'records','ROOT');p.need(initial['root.gsr'][16:48].hex()==result['root'],'ledger component original root')
    p.need(all(type(row) is dict and set(row)=={'node','event'} and row['node']=='node-1' and type(row['event']) is str for row in events),
           'ledger component event owner')
    copies,_=p.shared.collect_contents(sidecar,events,header,1,lambda node:{key:initial[key] for key in ('root.gsr','node.gsr')},
        p.collection.inventory(sidecar),schema=p.CAPTURE_SCHEMA,kinds=p.KINDS)
    state={kind:initial[files[0]] for kind,files in p.model.FILES.items()};used=set();prior=-1;writes=reseals=0
    for case in cases:
        p.need(set(case)=={'name','kind','mode','start','end'} and case['kind'] in p.KINDS and case['mode'] in ('write','reseal') and
               type(case['start']) is int and type(case['end']) is int and prior<case['start']<case['end']<len(events),'ledger component original intervals')
        prior=case['end'];kind=case['kind'];active,candidate=p.model.FILES[kind]
        before=inventory(root/case['name']/'before');after=inventory(root/case['name']/'after')
        p.need(all(before[files[0]]==state[k] for k,files in p.model.FILES.items()),'ledger component continuous original revisions')
        first=metadata(before[active],kind);last=metadata(after[active],kind)
        p.need(first['root']==last['root']==result['root'] and first['owner']==last['owner'] and first['owner']['node']=='node-1',
               'ledger component original revision owner')
        if case['mode']=='write':
            p.need(last['revision']==first['revision']+1 and last['previous']==p.shared.sha(before[active]) and
                   after==dict(before,**{active:after[active]}),'ledger component exact replacement')
            plan=p.model.transaction(p.model.physical(before),before[active],after[active],kind);writes+=1
        else:
            p.need(before==after and candidate not in before,'ledger component unchanged reseal')
            plan=[(kind,point,p.model.physical(before)) for point in p.model.RESEALS[kind]];reseals+=1
        indices=[i for i in range(case['start'],case['end']+1) if events[i]['event'] in p.model.POINTS]
        p.need(len(indices)==len(plan),'ledger component original callback count')
        for at,(wanted,point,files) in zip(indices,plan):
            p.need(at not in used and events[at]['event']==point,'ledger component original callback order');used.add(at)
            p.need(at in copies and copies[at]['node']=='node-1' and (copies[at]['kind'],copies[at]['point'])==(wanted,point),
                   'ledger component original capture binding')
            p.need(p.model.physical(copies[at]['files'])==files,'carried prefix exact original state: '+point)
        state[kind]=after[active]
    p.need(writes==4 and reseals==6 and used==copies.keys()=={i for i,v in enumerate(events) if v['event'] in p.model.POINTS},
           'ledger component complete original coverage')
    p.need(p.collection.inventory(root)==original,'ledger component original changed')
    return dict(status='PASS',transactions=writes,reseals=reseals,capturedPrefixes=len(used),
                expectedBytes='conditional-transaction-snapshots',nativeCarriedProcess=False)


def qualify(root):
    root=Path(root);original=validate(root);before=p.collection.inventory(root);negatives=[]
    for name in p.PHYSICAL:
        with tempfile.TemporaryDirectory(prefix='v53-ledger-component-negative-') as temp:
            changed=Path(temp);shutil.copytree(root/'captures',changed/'life-2');p.mutate(changed,name)
            try:validate(root,changed/'life-2')
            except ValueError as error:p.need(str(error)==p.NEGATIVES[name],'ledger component unrelated negative: '+name+': '+str(error))
            else:raise ValueError('ledger component accepted mutation: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=p.NEGATIVES[name]))
    p.need(before==p.collection.inventory(root),'ledger component negative changed original')
    return dict(original=original,negatives=negatives,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
