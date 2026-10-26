"""Replay original source selection, receiver pulls and actual installed files.

This covers fixed stable bootstrap histories, not automatic discovery or READY.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import promised_source_evidence as p

a=p.a
e=p.e
c=p.c
b=p.b
load=p.load


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}=={'selection','activation','install-pulls'},'selected pull profile inventory')
    first=p.case(root/'selection',size);last=a.case(root/'activation',size)
    e.need(first['selected']==last['selected']==last['installed'],'selected pull source/install count')
    names=[f'node-{i}' for i in range(1,size//2+2)]
    selection=root/'selection';activation=root/'activation'
    for file in ('original-plan.gsbp','original-application.image','selected.gsr'):
        e.need((selection/file).read_bytes()==(activation/file).read_bytes(),'selected pull changed original '+file)
    e.need(c.inventory(selection/'initial')==c.inventory(activation/'initial'),'selected pull changed initial voter')
    before=b.original(selection,size,False);_,initial,packet=c.current(before['node-1'])
    raw=(selection/'selected.gsr').read_bytes();selected=e.f.decode(raw,'records','SELECTED');r=selected['root'];view=selected['view'];ballot=selected['ballot']
    identities={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in before.items()}
    full_wire=load(activation/'wire.json')
    e.need(full_wire[:len(names)-1]==[load(selection/n/'prepare.json') for n in names[1:]],'selected pull changed campaign wire')
    directory=root/'install-pulls';e.need(directory.is_dir() and not directory.is_symlink() and {v.name for v in directory.iterdir()}==set(names[1:]),'selected pull receiver inventory')
    count=0
    for receiver in names[1:]:
        member=directory/receiver;e.need({v.name for v in member.iterdir()}=={'wire.json','received'},'selected pull member inventory')
        groups=[];trace=None;seen=set()
        for row in load(member/'wire.json'):
            _,request=p.t.wire(row['request'])
            if request['trace']!=trace:
                trace=request['trace'];e.need(trace not in seen,'selected pull reused exchange trace');seen.add(trace);groups.append([])
            groups[-1].append(row)
        e.need(len(groups)==len(names),'selected pull complete exchange groups')
        count+=p.transcript(groups[0],[(e.digest(raw),raw,'RECORD')],r,view,ballot,identities[receiver],identities['node-1'],'selected record')
        remotes=[(i,n) for i,n in enumerate(names) if n!=receiver]
        expected_files={}
        for rows,(index,source) in zip(groups[1:],remotes):
            journal=c.journal((selection/'selected'/source/'grants.gsr').read_bytes(),r,source)
            original={kind:data for kind,data,_ in journal[-3:]};basis=original['BASIS'];promise=original['PROMISE']
            expected=[(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),(e.digest(packet['capsuleBytes']),initial['source.gscp'],'CAPSULE')]
            # Every image in these same-cut profiles is already pinned locally.
            # Missing bytes are still fetched in profiles without that exact local image.
            count+=p.transcript(rows,expected,r,view,ballot,identities[receiver],identities[source],'installation source')
            prefix=f'source-{index}';expected_files[prefix]=None;expected_files[prefix+'/source.gscp']=initial['source.gscp']

        e.need(c.inventory(member/'received')==expected_files,'selected pull exact received files')
        events=next(v['events'] for v in load(activation/'events.json') if v['node']==receiver)
        e.need(events.count('INSTALL_REPLIED')==1 and events.index('INSTALL_BEFORE_RETURN')<events.index('INSTALL_REPLIED'),'selected pull ACK before installation')
    return dict(size=size,selected=len(names),installed=len(names),ready=False),count


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'selected pull evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'selected pull complete inventory')
    results=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-selected-pull-v1',status='PASS',cases=[v[0] for v in results],publicRuntime=False,network=True,scope='original-network-selection-through-all-selected-installations')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'selected pull scope/receipt')
    return dict(original=expected,installationPullExchanges=sum(v[1] for v in results))


def qualify(directory):
    original=validate(directory);results=[]
    mutations=[('scope','selected pull scope/receipt'),('missing-profile','selected pull complete inventory'),
               ('missing-install-ack','activation exchange inventory'),('missing-installed-image','activation exact installed bytes'),
               ('changed-received-packet','selected pull exact received files'),('missing-receiver','selected pull receiver inventory'),
               ('missing-install-force','activation force order'),('early-install-ack','selected pull ACK before installation'),
               ('selection-offer','selected record original offer'),('selection-bytes','selected record exact data'),
               ('source-identity','installation source correlation'),('source-sequence','installation source correlation'),
               ('missing-transfer','installation source incomplete transcript'),('changed-source-data','installation source exact data')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-selected-pull-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);root=target/'stable-3';member=root/'install-pulls/node-2'
            if name=='scope':
                v=load(target/'receipt.json');v['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='missing-install-ack':
                q=root/'activation/wire.json';v=load(q);v.pop();q.write_text(json.dumps(v))
            elif name=='missing-installed-image':next((root/'activation/installed/node-2/generations/b').glob('*.image')).unlink()
            elif name=='changed-received-packet':next((member/'received').rglob('*.gscp')).write_bytes(b'changed')
            elif name=='missing-receiver':shutil.rmtree(member)
            elif name in ('missing-install-force','early-install-ack'):
                q=root/'activation/events.json';v=load(q);events=v[1]['events'];events.remove('INSTALL_BEFORE_RETURN' if name=='missing-install-force' else 'INSTALL_REPLIED')
                if name=='early-install-ack':events.insert(0,'INSTALL_REPLIED')
                q.write_text(json.dumps(v))
            else:
                q=member/'wire.json';rows=load(q)
                if name=='missing-transfer':rows.pop()
                else:
                    index={'selection-offer':0,'selection-bytes':1,'source-identity':3,'source-sequence':3,'changed-source-data':4}[name]
                    kind,frame=p.t.wire(rows[index]['response'])
                    if name=='selection-offer':frame['payload']['digest']='0'*64
                    elif name in ('selection-bytes','changed-source-data'):frame['payload']['bytes']=base64.b64encode(b'changed').decode();frame['payload']['digest']=e.digest(b'changed')
                    elif name=='source-identity':frame['sender']=p.t.wire(rows[index]['request'])[1]['sender']
                    else:frame['sequence']+=1
                    rows[index]['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                q.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'selected pull unrelated negative: '+name+': '+str(error))
            else:raise ValueError('selected pull accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
