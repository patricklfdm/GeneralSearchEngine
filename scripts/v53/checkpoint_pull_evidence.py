"""Replay actual retained checkpoint owners and compacted ancestry over TCP.

Reconstruct both publications before interpreting any received ACK. Copied packet
records never stand in for contacting the permanent owner in the transcript.
This qualifies current-view ancestry delivery, not historical capsule bootstrap.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import bootstrap_publication_evidence as b
from . import promised_source_evidence as p

e=b.e
c=b.c
load=p.load


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink(),'checkpoint case directory')
    names={f'node-{n}' for n in range(1,size+1)}
    expected={'original-plan.gsbp','original-application.image','initial','after','wire.json',
              'received-ancestry.gsr','received-observations.json'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-{slot}-{node}' for slot in (1,2) for node in names}
    expected|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    e.need({v.name for v in root.iterdir()}==expected,'checkpoint case inventory')
    group=b.campaign(root,b.original(root,size,False),1);observations=[];first=None
    for slot in (1,2):
        group,first=b.publication(root,group,slot,first,observations)
        for node,files in group.items():
            _,members,packet=c.current(files);b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    b.match(root,'after',group)
    _,members,packet=c.current(group['node-1']);cap=packet['capsule'];r=cap['root'];view=e.authority(r,cap['cut']['view'])
    ids={node:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in group.items()}
    ballot=e.f.decode(members['selected.gsr'],'records','SELECTED')['ballot']
    # These bytes were independently derived and checked in every applied-end above.
    statement=b.t.plans.read(root/'slot-2-applied/node-1/applied-end/parent-statement.gsr',16384)
    checked=e.f.decode(statement,'records','CHECKPOINT')
    e.need(checked['start']['index']==1 and checked['end']['index']==2 and len(cap['items'])==1,'checkpoint compacted endpoints')
    owners=[f'node-{n}' for n in range(1,size//2+2)]
    acknowledgements={node:b.t.plans.read(root/f'slot-2-applied/{node}/applied-end/parent-ack.gsr',4096) for node in owners}
    original=statement+b''.join(acknowledgements.values())
    e.need(members['ancestry.gsr'].startswith(original),'checkpoint original retained ancestry')
    e.need(b.t.plans.read(root/'received-ancestry.gsr',16384)==original,'checkpoint received original ancestry')
    expected_observations=[]
    for node,raw in acknowledgements.items():
        actual=e.f.decode(raw,'records','CHECKPOINT_ACK')
        e.need(actual==dict(root=r,voter=node,incarnation=ids[node]['storage'],cut=checked['end'],statement=e.digest(statement)),'checkpoint original ACK binding')
        expected_observations.append(dict(voter=node,storage=ids[node]['storage'],record=e.digest(raw),parent=e.digest(e.f.canonical(checked['end']))))
    expected_observations.sort(key=lambda row:(row['voter'],row['record']))
    e.need(load(root/'received-observations.json')==expected_observations,'checkpoint actual owner observations')
    rows=load(root/'wire.json');traces={};exchange_count=0;seen=set()
    for row in rows:
        e.need(set(row)=={'request','response'},'checkpoint wire row')
        kind,frame=p.t.wire(row['request']);traces.setdefault(frame['trace'],[]).append(row)
    required=[('node-1',statement),*acknowledgements.items()]
    e.need(len(traces)==len(required),'checkpoint transfer inventory')
    for transcript,(owner,raw) in zip(traces.values(),required):
        _,frame=p.t.wire(transcript[0]['request']);digest=e.digest(raw)
        e.need(frame['recipient']==ids[owner] and frame['payload']['digest']==digest,'checkpoint original owner contact')
        e.need((owner,digest) not in seen,'checkpoint duplicate owner record');seen.add((owner,digest))
        exchange_count+=p.transcript(transcript,[(digest,raw,'RECORD')],r,view,ballot,ids[f'node-{size}'],ids[owner],'checkpoint transfer',chunk_bytes=1024)
    return dict(size=size,owners=len(owners),exchanges=exchange_count)


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'checkpoint evidence directory')
    e.need({v.name for v in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'checkpoint complete inventory')
    cases=[case(root/f'stable-{size}',size) for size in (3,4,5)]
    receipt=dict(schema='gse-v53-checkpoint-pull-v1',status='PASS',cases=cases,network=True,publicRuntime=False,scope='original-compacted-ancestry')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(receipt),'checkpoint scope/receipt')
    return dict(original=receipt,exchanges=sum(row['exchanges'] for row in cases),owners=sum(row['owners'] for row in cases))


def qualify(directory):
    result=validate(directory);negatives=[]
    mutations=[('scope','checkpoint scope/receipt'),('missing-profile','checkpoint complete inventory'),
               ('received-ancestry','checkpoint received original ancestry'),('copied-owner','checkpoint actual owner observations'),
               ('missing-owner','checkpoint transfer inventory'),('foreign-owner','checkpoint original owner contact'),
               ('missing-commit','checkpoint transfer incomplete transcript'),('changed-data','checkpoint transfer exact data'),
               ('wrong-ballot','checkpoint transfer correlation'),('storage-changed','admitted exact after')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-checkpoint-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);member=target/'stable-3'
            if name=='scope':
                path=target/'receipt.json';data=load(path);data['publicRuntime']=True;path.write_text(json.dumps(data))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='received-ancestry':(member/'received-ancestry.gsr').write_bytes(b'changed')
            elif name=='copied-owner':
                path=member/'received-observations.json';data=load(path);data[1]['voter']=data[0]['voter'];path.write_text(json.dumps(data))
            elif name=='storage-changed':(member/'after/node-1/selector.gsr').write_bytes(b'changed')
            else:
                path=member/'wire.json';rows=load(path)
                if name=='missing-owner':
                    trace=p.t.wire(rows[-1]['request'])[1]['trace'];rows=[row for row in rows if p.t.wire(row['request'])[1]['trace']!=trace]
                elif name=='missing-commit':rows.pop()
                else:
                    index=next(i for i,row in enumerate(rows) if p.t.wire(row['response'])[0]=='CHUNK') if name=='changed-data' else 0
                    side='response' if name=='changed-data' else 'request';kind,frame=p.t.wire(rows[index][side])
                    if name=='foreign-owner':frame['recipient']=frame['sender']
                    elif name=='wrong-ballot':frame['ballot']['counter']+=1
                    else:frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    rows[index][side]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'checkpoint unrelated negative: '+name+': '+str(error))
            else:raise ValueError('checkpoint accepted negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
