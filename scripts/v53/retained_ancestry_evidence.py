"""Derive both real publications before replaying one owner's complete ancestry copy.

Historical copied endorsements are not fresh actual-owner vote observations.
Conditional joint/final fixture checks remain separate from this physical oracle.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import prefix_discovery_evidence as p
from . import promised_source_evidence as t
b=p.b;e=b.e;c=b.c;load=p.load


def case(root,size):
    names={f'node-{n}' for n in range(1,size+1)}
    expected={'original-plan.gsbp','original-application.image','initial','after','events.json','received',
              'prefix-wire.json','ancestry-wire.json','received-manifest.gsr','received-ancestry.gsr'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-{slot}-{node}' for slot in (1,2) for node in names}
    expected|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}==expected,'retained ancestry case inventory')
    group=b.campaign(root,b.original(root,size,False),1);observations=[];first=None
    for slot in (1,2):
        group,first=b.publication(root,group,slot,first,observations)
        for node,files in group.items():
            _,members,packet=c.current(files);b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    b.match(root,'after',group);e.need(load(root/'events.json')==[],'retained ancestry authority writes')
    prefix,members,packet=c.current(group['node-2']);cap=packet['capsule'];manifest=group['node-2'][prefix+'generation.gsr'];ancestry=members['ancestry.gsr']
    e.need(c.inventory(root/'received')=={'source.gscp':members['source.gscp'],**{h+'.image':members[h+'.image'] for h in packet['images']}},'retained ancestry received prefix')
    e.need(b.t.plans.read(root/'received-manifest.gsr',65536)==manifest,'retained ancestry exact manifest')
    e.need(b.t.plans.read(root/'received-ancestry.gsr',96*1024)==ancestry,'retained ancestry exact proof')
    # The complete file above was independently reconstructed from original applied-end
    # statements and actual ACKs during publication. No claimed witness set is an input.
    prefix_rows=load(root/'prefix-wire.json');prefix_count=p.transcript(prefix_rows,group)
    source=e.f.decode(group['node-2']['node.gsr'],'records','NODE')['identity'];reader=e.f.decode(group['node-1']['node.gsr'],'records','NODE')['identity']
    _,local,local_packet=c.current(group['node-1']);ballot=e.f.decode(local['selected.gsr'],'records','SELECTED')['ballot']
    reference=e.digest(e.f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-ancestry')))
    rows=load(root/'ancestry-wire.json');e.need(bool(rows),'retained ancestry transcript missing')
    trace=t.t.wire(rows[0]['request'])[1]['trace']
    e.need(all(trace!=t.t.wire(row['request'])[1]['trace'] for row in prefix_rows),'retained ancestry distinct session')
    count=t.transcript(rows,[(reference,manifest,'RECORD'),(e.digest(ancestry),ancestry,'RECORD')],cap['root'],
                       e.authority(cap['root'],local_packet['capsule']['cut']['view']),ballot,reader,source,'retained ancestry',chunk_bytes=4*e.MIB)
    return dict(size=size,prefixExchanges=prefix_count,ancestryExchanges=count)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'retained ancestry directory')
    e.need({v.name for v in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'retained ancestry complete inventory')
    cases=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-retained-ancestry-v1',status='PASS',cases=cases,network=True,publicRuntime=False,adoption=False,scope='authenticated-complete-supplemental-ancestry')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'retained ancestry scope/receipt');return expected


def qualify(directory):
    original=validate(directory);negatives=[]
    variants=[('scope','retained ancestry scope/receipt'),('missing-profile','retained ancestry complete inventory'),
              ('storage','admitted exact after'),('force','retained ancestry authority writes'),('prefix','retained ancestry received prefix'),
              ('manifest','retained ancestry exact manifest'),('proof','retained ancestry exact proof'),
              ('session','retained ancestry distinct session'),('owner','retained ancestry correlation'),('sequence','retained ancestry correlation'),
              ('reference','retained ancestry original offer'),('kind','retained ancestry original offer'),('data','retained ancestry exact data'),
              ('commit','retained ancestry exact commit'),('truncated','retained ancestry incomplete transcript'),('extra','retained ancestry complete transcript')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-retained-ancestry-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);root=target/'stable-3'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['adoption']=True;path.write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='storage':(root/'after/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='force':(root/'events.json').write_text('["PROMISE_FORCED"]')
            elif name=='prefix':(root/'received/source.gscp').write_bytes(b'changed')
            elif name=='manifest':(root/'received-manifest.gsr').write_bytes(b'changed')
            elif name=='proof':(root/'received-ancestry.gsr').write_bytes(b'changed')
            else:
                path=root/'ancestry-wire.json';rows=load(path)
                if name=='truncated':rows.pop()
                elif name=='extra':rows.append(rows[-1])
                else:
                    side='request' if name in ('session','owner','reference') else 'response';index=0
                    if name=='data':index=next(i for i,row in enumerate(rows) if t.t.wire(row['response'])[0]=='CHUNK')
                    elif name=='commit':index=len(rows)-1
                    kind,frame=t.t.wire(rows[index][side])
                    if name=='session':frame['trace']=t.t.wire(load(root/'prefix-wire.json')[0]['request'])[1]['trace']
                    elif name=='owner':frame['recipient']=frame['sender']
                    elif name=='sequence':frame['sequence']+=1
                    elif name=='reference':frame['payload']['digest']='a'*64
                    elif name=='kind':frame['payload']['kind']='CAPSULE'
                    elif name=='data':frame['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
                    else:frame['payload']['digest']='b'*64
                    rows[index][side]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'retained ancestry unrelated negative: '+name+': '+str(error))
            else:raise ValueError('retained ancestry accepted negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');a=parser.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
