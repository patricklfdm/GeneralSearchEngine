"""Independently reconstruct original grants and exported bytes from public bootstrap.

This is read-only source-lifetime evidence. It makes no network, selector install,
remote ownership or distributed protocol acceptance claim.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import bootstrap_publication_evidence as b

e=b.e
c=b.c


def load(path):
    return json.loads(b.t.plans.read(Path(path),e.MIB))


def case(root,size,*,additional=(),backup=False):
    e.need(root.is_dir() and not root.is_symlink(),'source export case directory')
    e.need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','captured','after','exported','contents.json'}|set(additional),'source export case inventory')
    before=b.original(root,size,backup);local='node-1';files=before[local]
    _,initial,packet=c.current(files);cap=packet['capsule'];r=cap['root']
    actual=c.inventory(root/'captured'/local);identity=e.f.decode(files['node.gsr'],'records','NODE')['identity']
    prior=c.journal(files['grants.gsr'],r,local);rows=c.journal(actual['grants.gsr'],r,local)
    e.need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS'],'source export original grant sequence')
    promise,basis=rows[-2:];identifier=promise[2]['basisId'];e.need(str(uuid.UUID(identifier))==identifier,'source export original UUID')
    ballot=dict(counter=2,proposer=local,incarnation=identity['storage'])
    expected=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,basisId=identifier)
    e.need(promise[2]==expected and basis[2]==dict(expected,voter=local,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'source export original promise/basis')
    prefix='sources/'+identifier
    captured=dict(before);captured[local]=dict(files,**{'allocator.gsr':e.f.encode('records','ALLOCATOR',dict(root=r,node=local,counter=2)),
        'grants.gsr':files['grants.gsr']+promise[1]+basis[1],prefix:None,prefix+'/source.gscp':initial['source.gscp']})
    for digest in packet['images']:captured[local][prefix+'/'+digest+'.image']=initial[digest+'.image']
    b.match(root,'captured',captured);b.match(root,'after',captured)
    content=[(promise[1],'RECORD'),(basis[1],'RECORD'),(initial['source.gscp'],'CAPSULE')]
    content += [(initial[h+'.image'],'APPLICATION') for h in packet['images']]
    exported={e.digest(raw)+'.bin':raw for raw,_ in content}
    e.need(c.inventory(root/'exported')==exported,'source export exact complete bytes')
    wanted=sorted([dict(digest=e.digest(raw),bytes=len(raw),kind=kind) for raw,kind in content],key=lambda v:v['digest'])
    e.need(load(root/'contents.json')==wanted,'source export exact descriptor inventory')
    return dict(size=size,contents=len(content))


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'source export evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'source export complete inventory')
    rows=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    wanted=dict(schema='gse-v53-source-export-v1',status='PASS',cases=rows,publicRuntime=False,network=False,scope='read-only-original-source-lifetime')
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(wanted),'source export scope/receipt')
    return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','source export scope/receipt'),('missing-profile','source export complete inventory'),
              ('changed-after','admitted exact after'),('changed-capture','admitted exact captured'),
              ('missing-grant','source export original grant sequence'),('missing-content','source export exact complete bytes'),
              ('changed-content','source export exact complete bytes'),('extra-content','source export exact complete bytes'),
              ('descriptor-size','source export exact descriptor inventory'),('descriptor-kind','source export exact descriptor inventory')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-source-export-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);p=target/'stable-3'
            if name=='scope':
                v=load(target/'receipt.json');v['network']=True;(target/'receipt.json').write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name in ('changed-after','changed-capture'):
                stage='after' if name=='changed-after' else 'captured';(p/stage/'node-2/allocator.gsr').write_bytes(b'changed')
            elif name=='missing-grant':
                path=p/'captured/node-1/grants.gsr';raw=path.read_bytes();path.write_bytes(raw[:len((p/'initial/target-0/grants.gsr').read_bytes())])
            elif name in ('missing-content','changed-content'):
                path=next((p/'exported').iterdir())
                if name=='missing-content':path.unlink()
                else:path.write_bytes(b'changed')
            elif name=='extra-content':(p/'exported/extra.bin').write_bytes(b'extra')
            else:
                path=p/'contents.json';v=load(path)
                if name=='descriptor-size':v[0]['bytes']+=1
                else:v[0]['kind']='FOREIGN'
                path.write_text(json.dumps(v))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'source export unrelated negative: '+name+': '+str(error))
            else:raise ValueError('source export accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
