"""Replay exact root-bound TCP component transcripts against original bootstrap.

The Java test supplies the socket execution observation. This independent reader
checks its complete pair inventory, identities, bytes and unchanged storage; it
does not turn a transcript into distributed consensus or network authentication.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b

e=b.e


def load(path):
    return json.loads(b.t.plans.read(Path(path),e.MIB))


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink(),'transport case directory')
    e.need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','after','wire.json'},'transport case inventory')
    before=b.original(root,size,False);b.match(root,'after',before)
    _,_,packet=b.c.current(before['node-1']);cap=packet['capsule'];r=cap['root']
    identities={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in before.items()}
    rows=load(root/'wire.json');pairs=[(a,z) for a in sorted(before) for z in sorted(before) if a!=z]
    e.need(len(rows)==len(pairs),'transport complete ordered pairs')
    for row,(sender,recipient) in zip(rows,pairs):
        e.need(set(row)=={'request','response'},'transport exchange row')
        request=e.f.decode(base64.b64decode(row['request'],validate=True),'wire','STATUS_PROBE')
        response=e.f.decode(base64.b64decode(row['response'],validate=True),'wire','STATUS')
        fields=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=dict(counter=2,proposer=sender,incarnation=identities[sender]['storage']),
                    trace=str(uuid.UUID(int=(53<<64)+1)),sequence=1)
        nonce=str(uuid.UUID(int=(51<<64)+53))
        e.need(request==dict(fields,sender=identities[sender],recipient=identities[recipient],payload=dict(nonce=nonce)) and
               response==dict(fields,sender=identities[recipient],recipient=identities[sender],payload=dict(nonce=nonce,cut=cap['cut'],ready=False)),
               'transport exact root/identity/correlation/status')
    return dict(size=size,exchanges=len(pairs))


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'transport evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'transport complete inventory')
    profiles=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    wanted=dict(schema='gse-v53-transport-component-v1',status='PASS',profiles=profiles,execution='loopback-tcp-component',publicRuntime=False,distributedProtocolQualification=False)
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(wanted),'transport scope/receipt')
    return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','transport scope/receipt'),('missing-profile','transport complete inventory'),
              ('changed-storage','admitted exact after'),('missing-pair','transport complete ordered pairs'),
              ('duplicate-pair','transport exact root/identity/correlation/status'),('foreign-root','transport exact root/identity/correlation/status'),
              ('foreign-storage','transport exact root/identity/correlation/status'),('late-sequence','transport exact root/identity/correlation/status'),
              ('wrong-nonce','transport exact root/identity/correlation/status'),('false-ready','transport exact root/identity/correlation/status')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-transport-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);p=target/'stable-3'
            if name=='scope':
                v=load(target/'receipt.json');v['distributedProtocolQualification']=True;(target/'receipt.json').write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='changed-storage':(p/'after/node-1/grants.gsr').write_bytes(b'changed')
            else:
                path=p/'wire.json';v=load(path)
                if name=='missing-pair':v.pop()
                elif name=='duplicate-pair':v[1]=v[0]
                else:
                    reply=e.f.decode(base64.b64decode(v[0]['response']),'wire','STATUS')
                    if name=='foreign-root':reply['root']='0'*64
                    elif name=='foreign-storage':reply['sender']['storage']=str(uuid.UUID(int=53))
                    elif name=='late-sequence':reply['sequence']+=1
                    elif name=='wrong-nonce':reply['payload']['nonce']=str(uuid.UUID(int=54))
                    else:reply['payload']['ready']=True
                    v[0]['response']=base64.b64encode(e.f.encode('wire','STATUS',reply)).decode()
                path.write_text(json.dumps(v))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'transport unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transport accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
