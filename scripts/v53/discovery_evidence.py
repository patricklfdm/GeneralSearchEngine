"""Derive published cuts before replaying read-only original TCP status exchanges.

The retained Java execution binds the actual socket/owner calls. This reader checks
all physical originals and the complete peer pairs, not just a claimed result.
No STATUS establishes a proof, vote, public read or cross-view adoption.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b
from .transport_evidence import load

e=b.e


def transcript(rows,group):
    pairs=[(a,z) for a in sorted(group) for z in sorted(group) if a!=z]
    e.need(len(rows)==len(pairs),'discovery complete ordered pairs')
    ids={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in group.items()}
    traces=set();nonces=set()
    for row,(sender,recipient) in zip(rows,pairs):
        e.need(set(row)=={'request','response'},'discovery wire row')
        request=e.f.decode(base64.b64decode(row['request'],validate=True),'wire','STATUS_PROBE')
        reply=e.f.decode(base64.b64decode(row['response'],validate=True),'wire','STATUS')
        _,source,p=b.c.current(group[sender]);_,_,target=b.c.current(group[recipient]);cap=p['capsule']
        trace=request['trace'];nonce=request['payload']['nonce']
        e.need(str(uuid.UUID(trace))==trace and int(uuid.UUID(trace))!=0 and trace not in traces and
               str(uuid.UUID(nonce))==nonce and int(uuid.UUID(nonce))!=0 and nonce not in nonces,'discovery fresh correlation')
        traces.add(trace);nonces.add(nonce)
        fields=dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),
                    ballot=e.f.decode(source['selected.gsr'],'records','SELECTED')['ballot'],trace=trace,sequence=1)
        e.need(request==dict(fields,sender=ids[sender],recipient=ids[recipient],payload=dict(nonce=nonce)) and
               reply==dict(fields,sender=ids[recipient],recipient=ids[sender],payload=dict(nonce=nonce,cut=target['capsule']['cut'],ready=False)),
               'discovery exact original cut/identity/correlation')
    return len(pairs)


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink(),'discovery case directory')
    names={f'node-{n}' for n in range(1,size+1)}
    expected={'original-plan.gsbp','original-application.image','initial','after','wire.json','events.json','entry-1.gsr','payload-1.bin'}
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-1-{stage}' for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-1-{node}' for node in names}
    e.need({p.name for p in root.iterdir()}==expected,'discovery case inventory')
    group=b.campaign(root,b.original(root,size,False),1)
    group,_=b.publication(root,group,1,None,[])
    for node,files in group.items():
        _,members,packet=b.c.current(files);b.typed_image(root/f'typed-1-{node}',members[packet['capsule']['application']+'.image'])
    b.match(root,'after',group)
    e.need(load(root/'events.json')==[],'discovery performed authority writes')
    return dict(size=size,exchanges=transcript(load(root/'wire.json'),group))


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'discovery evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'discovery complete inventory')
    cases=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-discovery-v1',status='PASS',cases=cases,network=True,publicRuntime=False,adoption=False,scope='read-only-published-cut-discovery')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'discovery scope/receipt')
    return expected


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','discovery scope/receipt'),('missing-profile','discovery complete inventory'),('storage','admitted exact after'),
              ('force','discovery performed authority writes'),('missing-pair','discovery complete ordered pairs'),
              ('duplicate-pair','discovery fresh correlation'),('foreign-root','discovery exact original cut/identity/correlation'),
              ('foreign-storage','discovery exact original cut/identity/correlation'),('nonce','discovery exact original cut/identity/correlation'),
              ('cut','discovery exact original cut/identity/correlation'),('ready','discovery exact original cut/identity/correlation')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-discovery-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);root=target/'stable-3'
            if name=='scope':
                p=target/'receipt.json';v=load(p);v['adoption']=True;p.write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='storage':(root/'after/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='force':(root/'events.json').write_text('["PROMISE_FORCED"]')
            else:
                path=root/'wire.json';rows=load(path)
                if name=='missing-pair':rows.pop()
                elif name=='duplicate-pair':rows[1]=rows[0]
                else:
                    reply=e.f.decode(base64.b64decode(rows[0]['response']),'wire','STATUS')
                    if name=='foreign-root':reply['root']='0'*64
                    elif name=='foreign-storage':reply['sender']['storage']=str(uuid.UUID(int=53))
                    elif name=='nonce':reply['payload']['nonce']=str(uuid.UUID(int=54))
                    elif name=='cut':reply['payload']['cut']['index']+=1
                    else:reply['payload']['ready']=True
                    rows[0]['response']=base64.b64encode(e.f.encode('wire','STATUS',reply)).decode()
                path.write_text(json.dumps(rows))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'discovery unrelated negative: '+name+': '+str(error))
            else:raise ValueError('discovery accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
