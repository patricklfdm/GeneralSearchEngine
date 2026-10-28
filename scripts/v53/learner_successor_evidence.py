"""Replay original certified preparations, installed successor and exact reopen.

No voter eligibility or old-generation retirement is inferred from this history.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import base64
from . import learner_typed_evidence as t
from . import learner_prepared_evidence as prepared
from . import source_packet
s,source,e,f,need=t.s,t.source,t.e,t.f,t.need
b,c,d,a,VOTERS=t.b,t.c,t.d,t.a,t.VOTERS


physical=prepared.physical


def check_trace(rows,resume=False):
    t.check_trace(rows,resume)
    def writes(prefix):
        return [prefix+x for x in (('_FORCED','_PARENT_FORCED') if resume else
                ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED','_PARENT_FORCED'))]
    expected=t.trace(resume)+writes('LEARNER_PREPARED')+['LEARNER_PREPARED_BEFORE_SELECT','LEARNER_PREPARED_BEFORE_RETURN']
    if not resume:
        expected+=['LEARNER_SUCCESSOR_DIRECTORY_FORCED']+writes('LEARNER_SUCCESSOR_PLAN')+[
                   'LEARNER_SUCCESSOR_CANDIDATE_FORCED','LEARNER_SUCCESSOR_CANDIDATE_PARENT_FORCED','LEARNER_SUCCESSOR_PLAN_RENAMED']
    expected+=['LEARNER_SUCCESSOR_ACTIVE_FORCED','LEARNER_SUCCESSOR_ACTIVE_PARENT_FORCED']
    if not resume:expected+=['LEARNER_SUCCESSOR_SOURCE_MOVED']
    expected+=['LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED']+writes('LEARNER_SUCCESSOR_SELECT')+['LEARNER_SUCCESSOR_BEFORE_RETURN']
    actual=[v for v in rows if v.startswith(('LEARNER_TYPED_','LEARNER_PREPARED_','LEARNER_SUCCESSOR_'))]
    need(actual==expected,'learner successor exact force order')


def installed(root,plan,original,new,request,learner,receipt):
    path=root/'successor';other=root/'successor-resumed'
    need(c.inventory(path)==c.inventory(other),'learner successor exact reopened bytes')
    need({p.name for p in path.iterdir()}=={'successor.lock','install.json','selected.json','source','identity.json'},'learner successor installed inventory')
    need((path/'successor.lock').read_bytes()==b'' and s.files(path/'source')==new,'learner successor exact installed originals')
    raw=(path/'install.json').read_bytes();v=e.parse(raw)
    need(len(raw)<=256*1024 and raw==f.canonical(v) and set(v)=={'schema','plan','previous','receipt','path','directoryKey','staging','sourceKey','source','generation','files'},
         'learner successor plan shape')
    old_packet=source_packet.decode(original['source.gscp'])
    old=old_packet['capsule']
    peer=next(x for x in request['target'] if x['node']=='node-1')
    need(v['schema']=='gse-v53-learner-successor/1.3' and v['plan']==e.digest((root/'learner-plan.gslp').read_bytes())
         and v['previous']==dict(source=e.digest(original['source.gscp']),cut=old['cut'],catalog=old['catalog'],application=old['application'])
         and v['receipt']==e.digest(receipt) and v['source']==peer
         and v['generation']==base64.b64encode(new['generation.gsr']).decode(),'learner successor original plan fields')
    directory=t.binding(v['path']);staging=t.binding(v['staging']);bound=[t.binding(x) for x in plan['paths']]
    operation=next(x for x in bound if x.name=='learner-operation')
    need(directory==operation.parent/('.gse-v53-learner-successor-'+v['plan']),'learner successor deterministic path')
    bound+=[directory,staging]
    need(all(x!=y and x not in y.parents and y not in x.parents for i,x in enumerate(bound) for y in bound[i+1:]),'learner successor disjoint paths')
    need(all(type(v[k]) is str and v[k].strip() and len(v[k].encode())<=4096 for k in ('directoryKey','sourceKey')),'learner successor directory keys')
    expected=[dict(path=n,size=len(data),sha256=e.digest(data)) for n,data in sorted(new.items())]
    need(type(v['files']) is list and len(v['files'])==len(expected),'learner successor original file count')
    for row,entry in zip(v['files'],expected):
        need(type(row) is dict and set(row)=={'path','size','sha256','key'} and {k:row[k] for k in entry}==entry
             and type(row['key']) is str and row['key'].strip() and len(row['key'].encode())<=4096,'learner successor original file inventory')
    need(d.read(path/'identity.json')==dict(directoryKey=v['directoryKey'],sourceKey=v['sourceKey'],
         files=[dict(path=row['path'],key=row['key']) for row in v['files']]),'learner successor retained inode binding')
    selector=dict(schema='gse-v53-learner-successor-selected/1.3',plan=e.digest(raw),root=request['root'],identity=learner,
                  generation=e.digest(new['generation.gsr']),location=str(directory/'source'))
    need((path/'selected.json').read_bytes()==f.canonical(selector),'learner successor exact selected original')


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'learner prepared evidence directory');total=0
    for count,p in enumerate(root.rglob('*'),1):
        need(not p.is_symlink() and (p.is_file() or p.is_dir()),'learner prepared regular evidence')
        if p.is_file():
            size=p.stat().st_size;need(size<=64*e.MIB,'learner prepared file capacity');total+=size
        need(count<=65536 and total<=512*e.MIB,'learner prepared evidence capacity')
    names={'initial','original-plan.gsbp','original-application.image','before-network','installed','selected.gsr','after-close',
           'calls.json','events.json','wire.json','failures.json','before-learner-source','after-learner-source',
           'before-learner-refresh','after-learner-refresh','learner-refresh-wire.json','learner-refresh-copy',
           'learner-reserve-payload.bin','learner-source-copy','learner-source-wire.json','learner-receipt.gsr',
           'learner-plan.gslp','admitted','typed','learner-typed-events.json','learner-successor-result.json',
           'successor','successor-resumed','learner-successor-resume-events.json'}
    names|={f'{stage}-{i}' for stage in ('applied','published') for i in range(1,6)}
    b.selection.layout(root,names,'learner prepared')
    prepared,refreshed,request,learner,receipt=physical(root)
    first=d.read(root/'learner-source-wire.json');second=d.read(root/'learner-refresh-wire.json')
    acquisition=source.network(root,prepared,request,learner,following=second)
    refresh=source.network(root,refreshed,request,learner,preceding=first,trace_name='learner-refresh-wire.json',copy_name='learner-refresh-copy')
    original=c.inventory(root/'learner-source-copy');root_bytes=prepared['node-1']['root.gsr']
    raw=(root/'learner-plan.gslp').read_bytes();peer=next(v for v in request['target'] if v['node']=='node-1')
    plan=s.p.plan(raw,root_bytes,original,request,learner,peer)
    retained=(root/'admitted/operation'/s.RETAIN).read_bytes();decision=s.retention(retained,raw,plan)
    operation={'operation.lock':b'','learner.gslp':raw,s.RETAIN:retained}
    replica={'replica.lock':b'','root.gsr':root_bytes,'node.gsr':f.encode('records','NODE',dict(root=request['root'],identity=learner)),s.ADMISSION:retained}
    s.state(root/'admitted',operation,replica,original,decision,'retained')
    t.sidecar(root,c.inventory(root/'typed'),plan,original,request,receipt,raw,selected=True)
    installed(root,plan,original,c.inventory(root/'learner-refresh-copy'),request,learner,receipt)
    check_trace(d.read(root/'learner-typed-events.json'))
    check_trace(d.read(root/'learner-successor-resume-events.json'),True)
    need(d.read(root/'learner-successor-result.json')==dict(status='PASS',scope='native-installed-learner-successor',voter=False,
         liveCore=False,publicReady=False,phase3Complete=False,testBudgetSeconds=600),'learner successor result scope')
    return dict(status='PASS',scope='native-installed-learner-successor',acquisition=acquisition,refresh=refresh,
                physicalQualification=True,successorInstalled=True,oldGenerationRetired=False,jointEligible=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={'reopened':'learner successor exact reopened bytes','selected':'learner successor exact selected original',
           'source':'learner successor exact installed originals','receipt':'learner successor original plan fields',
           'peer':'learner successor original plan fields','inode':'learner successor retained inode binding',
           'missing-force':'learner successor exact force order','early-select':'learner successor exact force order',
           'resume-force':'learner successor exact force order','extra-file':'learner successor installed inventory',
           'missing-exchange':'learner source exact received trace','false-ready':'learner successor result scope'}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-successor-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='reopened':(path/'successor-resumed/selected.json').write_bytes(b'bad')
            elif name in ('selected','source','receipt','peer','inode','extra-file'):
                for stage in ('successor','successor-resumed'):
                    target=path/stage
                    if name=='selected':(target/'selected.json').write_bytes(b'bad')
                    elif name=='source':(target/'source/generation.gsr').write_bytes(b'bad')
                    elif name=='extra-file':(target/'extra').write_bytes(b'bad')
                    elif name=='inode':
                        p=target/'identity.json';v=d.read(p);v['sourceKey']='foreign';p.write_bytes(f.canonical(v))
                    else:
                        p=target/'install.json';v=d.read(p)
                        if name=='receipt':v['receipt']='0'*64
                        else:v['source']['storage']='00000000-0000-0000-0000-000000000053'
                        p.write_bytes(f.canonical(v))
            elif name=='missing-exchange':
                p=path/'learner-refresh-wire.json';rows=d.read(p);rows.pop();p.write_bytes(f.canonical(rows))
            elif name in ('missing-force','early-select','resume-force'):
                p=path/('learner-successor-resume-events.json' if name=='resume-force' else 'learner-typed-events.json');rows=d.read(p)
                if name=='early-select':
                    rows.remove('LEARNER_SUCCESSOR_SELECT_CREATED');rows.insert(rows.index('LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED'),'LEARNER_SUCCESSOR_SELECT_CREATED')
                else:rows.remove('LEARNER_SUCCESSOR_SELECT_FORCED')
                p.write_bytes(f.canonical(rows))
            else:
                p=path/'learner-successor-result.json';v=d.read(p);v['publicReady']=True;p.write_bytes(f.canonical(v))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'learner successor unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner successor accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))
