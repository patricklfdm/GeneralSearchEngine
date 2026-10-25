"""Independent replay of the three admitted activation component histories.

Derive exact selected disk images and correlate the frozen wire bytes. This does
not turn in-process delivery or force callbacks into network/power-loss evidence.
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
c=b.c


def load(path):
    return json.loads(b.t.plans.read(Path(path),e.MIB))


def case(root,size):
    e.need(root.is_dir() and not root.is_symlink(),'activation case directory')
    e.need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','installed','wire.json','events.json','selected.gsr'},'activation case inventory')
    before=b.original(root,size,False);names=[f'node-{i}' for i in range(1,size//2+2)]
    actual={n:c.inventory(root/'installed'/n) for n in before}
    e.need({p.name for p in (root/'installed').iterdir()}==set(before),'activation voter inventory')
    _,initial,packet=c.current(before['node-1']);cap=packet['capsule'];r=cap['root']
    identities={n:e.f.decode(files['node.gsr'],'records','NODE')['identity'] for n,files in before.items()}
    ballot=dict(counter=2,proposer='node-1',incarnation=identities['node-1']['storage'])
    bases={};promises={};prepared={};seen=set()
    for node in before:
        if node not in names:
            e.need(actual[node]==before[node],'activation unselected voter changed');continue
        rows=c.journal(actual[node]['grants.gsr'],r,node);prior=c.journal(before[node]['grants.gsr'],r,node)
        e.need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS','SELECTED'],'activation durable grant/selection')
        promise,basis=rows[-3:-1];identifier=promise[2]['basisId']
        e.need(str(uuid.UUID(identifier))==identifier and identifier not in seen,'activation original source UUID');seen.add(identifier)
        expected=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,basisId=identifier)
        e.need(promise[2]==expected,'activation exact promise')
        e.need(basis[2]==dict(expected,voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),inventory=e.digest(packet['indexBytes']),accepted=None),'activation exact basis')
        promises[node]=promise[1];bases[node]=basis[1];source='sources/'+identifier
        files=dict(before[node],**{'grants.gsr':before[node]['grants.gsr']+promise[1]+basis[1],source:None,source+'/source.gscp':initial['source.gscp']})
        for h in packet['images']:files[source+'/'+h+'.image']=initial[h+'.image']
        if node=='node-1':files['allocator.gsr']=e.f.encode('records','ALLOCATOR',dict(root=r,node=node,counter=2))
        prepared[node]=files
    selection=dict(root=r,view=e.authority(r,cap['cut']['view']),ballot=ballot,cut=cap['cut'],nextEntry=None,
                   sources=[dict(voter=n,basisId=e.f.decode(bases[n],'records','BASIS')['basisId'],basisDigest=e.digest(bases[n])) for n in names])
    raw=e.f.encode('records','SELECTED',selection)
    e.need(b.t.plans.read(root/'selected.gsr',8192)==raw,'activation fixed selection')
    for node in names:
        files=prepared[node];files['grants.gsr']+=raw
        members={'source.gscp':initial['source.gscp'],'promise.gsr':promises[node],'basis.gsr':bases[node],
                 'selected.gsr':raw,'selected-sources.gsr':b''.join(bases[n] for n in names)}
        members.update({h+'.image':initial[h+'.image'] for h in packet['images']})
        selector,generation=c.generation(members,cap,node,'b',None)
        e.need(actual[node]==dict(files,**generation,**{'selector.gsr':selector}),'activation exact installed bytes: '+node)
    wire=load(root/'wire.json');e.need(len(wire)==2*(len(names)-1),'activation exchange inventory');trace=None
    for index,row in enumerate(wire):
        install=index>=len(names)-1;node=names[1+index%(len(names)-1)]
        kind,answer=('SELECTED','INSTALL_ACK') if install else ('PREPARE','PROMISE')
        e.need(set(row)=={'request','response'},'activation exchange row')
        request=e.f.decode(base64.b64decode(row['request'],validate=True),'wire',kind)
        response=e.f.decode(base64.b64decode(row['response'],validate=True),'wire',answer)
        if trace is None:
            trace=request['trace'];e.need(str(uuid.UUID(trace))==trace,'activation trace UUID')
        fields=dict(root=r,view=selection['view'],ballot=ballot,trace=trace,sequence=index+1)
        payload=dict(selection=e.digest(raw)) if install else dict(promise=e.digest(promises['node-1']))
        reply=dict(selection=e.digest(raw),cut=cap['cut']) if install else dict(basis=e.digest(bases[node]))
        e.need(request==dict(fields,sender=identities['node-1'],recipient=identities[node],payload=payload)
               and response==dict(fields,sender=identities[node],recipient=identities['node-1'],payload=reply),'activation exact wire correlation')
    events=load(root/'events.json')
    e.need([v['node'] for v in events]==sorted(before) and all(set(v)=={'node','events'} for v in events),'activation event inventory')
    for row in events:
        steps=row['events']
        if row['node'] not in names:
            e.need('GRANT_BEFORE_RETURN' not in steps and 'INSTALL_BEFORE_RETURN' not in steps,'activation unselected force');continue
        required=['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','SELECTED_FORCED','SELECTED_BEFORE_RETURN','INSTALL_BEFORE_RETURN']
        e.need(all(v in steps for v in required) and [steps.index(v) for v in required]==sorted(steps.index(v) for v in required),'activation force order')
    return dict(case=f'stable-{size}',status='PASS',selected=len(names),installed=len(names))


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink(),'activation evidence directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'activation complete inventory')
    rows=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-activation-component-v1',cases=rows,status='PASS',publicRuntime=False,network=False,syntheticOwners=False)
    e.need(e.f.canonical(load(root/'receipt.json'))==e.f.canonical(expected),'activation scope/receipt')
    return expected


def qualify(directory):
    original=validate(directory);results=[]
    mutations=[('scope','activation scope/receipt'),('missing-profile','activation complete inventory'),
               ('missing-grant','activation durable grant/selection'),('fixed-selection','activation fixed selection'),
               ('missing-image','activation exact installed bytes'),('missing-selector','activation exact installed bytes'),
               ('correlation','activation exact wire correlation'),('foreign-identity','activation exact wire correlation'),
               ('missing-ack','activation exchange inventory'),('missing-force','activation force order')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-activation-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);p=target/'stable-3'
            if name=='scope':
                v=load(target/'receipt.json');v['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(v))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name=='missing-grant':
                q=p/'installed/node-1/grants.gsr';raw=q.read_bytes();rows=c.journal(raw,e.f.decode((p/'selected.gsr').read_bytes(),'records','SELECTED')['root'],'node-1');q.write_bytes(b''.join(v[1] for v in rows[:-1]))
            elif name=='fixed-selection':
                q=p/'selected.gsr';v=e.f.decode(q.read_bytes(),'records','SELECTED');v['sources']=v['sources'][::-1];q.write_bytes(e.f.encode('records','SELECTED',v))
            elif name in ('missing-image','missing-selector'):
                q=next((p/'installed/node-1/generations/b').glob('*.image')) if name=='missing-image' else p/'installed/node-1/selector.gsr';q.unlink()
            elif name=='missing-force':
                q=p/'events.json';v=load(q);v[0]['events'].remove('SELECTED_FORCED');q.write_text(json.dumps(v))
            else:
                q=p/'wire.json';v=load(q)
                if name=='missing-ack':v.pop()
                else:
                    r=e.f.decode(base64.b64decode(v[0]['response']),'wire','PROMISE')
                    if name=='correlation':r['sequence']+=1
                    else:r['sender']['storage']=str(uuid.uuid4())
                    v[0]['response']=base64.b64encode(e.f.encode('wire','PROMISE',r)).decode()
                q.write_text(json.dumps(v))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'activation unrelated negative: '+name+': '+str(error))
            else:raise ValueError('activation accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
