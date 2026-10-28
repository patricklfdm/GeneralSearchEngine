"""Replay two native certified preparations and immutable learner selection.

No voter admission or successor installation is inferred from receiving a copy.
Both complete client sessions must account for the entire original server trace.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_typed_evidence as t
s,source,e,f,need=t.s,t.source,t.e,t.f,t.need
b,c,d,a,VOTERS=t.b,t.c,t.d,t.a,t.VOTERS


def physical(root):
    group=d.s.initialize(b.original(root,3,False))
    group={n:dict(v,**{d.future.FILE:d.future.frame(d.future.initial(v),{})}) for n,v in group.items()}
    b.match(root,'before-network',group)
    _,_,installed=d.s.campaign(root,{n:group[n] for n in VOTERS},2,'installed',selected_prefix=d.slot.prefix)
    group=dict(group,**installed);b.match(root,'installed',group)
    need((root/'selected.gsr').read_bytes()==c.current(group['node-1'])[1]['selected.gsr'],'learner typed original selection')
    model=a.NativeSlot.__new__(a.NativeSlot)
    model.root=root;model.group=group;model.active=list(VOTERS);model.voters=VOTERS
    model.required=set();model.slot=0;model.counter=2;model.first=None;model.observed=set();model.phases={};model.documents=[]
    model.history=f.decode(group['node-1']['root.gsr'],'records','ROOT')['historyId']
    supplied=e.parse((root/'learner-reserve-payload.bin').read_bytes());request=supplied['request']
    need(set(supplied)=={'request'} and request['kind']=='ADD' and request['number']==1 and len(request['target'])==4,
         'learner typed native request')
    learner=next(v for v in request['target'] if v['node']=='node-4')
    for kind,command in [('BARRIER',None),('RESERVE',supplied),('PREPARE',dict(number=1,revision=1))]:
        model.group=a.maintenance(model.group,VOTERS);model.publish(kind,command)
    b.match(root,'before-learner-source',model.group);b.match(root,'after-learner-source',model.group)
    prepared=copy.deepcopy(model.group);packet=c.current(prepared['node-1'])[2]
    catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG');operation=catalog['results'][0]
    need(catalog['active']==1 and operation['phase']=='PREPARING' and operation['revision']==1 and operation['request']==request,
         'learner typed native preparation')
    receipt=dict(root=request['root'],number=1,request=e.digest(f.canonical(request)),identity=learner,
                 image=operation['prepared']['application'],prepared=operation['prepared'])
    raw=f.encode('records','LEARNER',dict(root=request['root'],receipt=receipt))
    need((root/'learner-receipt.gsr').read_bytes()==raw,'learner typed exact receipt')
    model.group=a.maintenance(model.group,VOTERS);model.publish('PREPARE',dict(number=1,revision=2))
    b.match(root,'before-learner-refresh',model.group);b.match(root,'after-learner-refresh',model.group)
    refreshed=copy.deepcopy(model.group)
    model.group=a.maintenance(model.group,VOTERS);model.publish('CANCEL',dict(number=1))
    b.match(root,'after-close',model.group)
    return prepared,refreshed,request,learner,raw


def check_trace(rows):
    t.check_trace(rows,False)
    actual=[v for v in rows if v.startswith(('LEARNER_TYPED_','LEARNER_PREPARED_'))]
    expected=t.trace(False)+['LEARNER_PREPARED'+v for v in ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED',
                            '_PARENT_FORCED','_BEFORE_SELECT','_BEFORE_RETURN')]
    need(actual==expected,'learner prepared exact selection force order')


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
           'learner-plan.gslp','admitted','typed','learner-typed-events.json','learner-prepared-result.json'}
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
    check_trace(d.read(root/'learner-typed-events.json'))
    need(d.read(root/'learner-prepared-result.json')==dict(status='PASS',scope='native-prepared-learner-refresh',voter=False,
         liveCore=False,publicReady=False,phase3Complete=False,testBudgetSeconds=600),'learner prepared result scope')
    return dict(status='PASS',scope='native-prepared-learner-refresh',acquisition=acquisition,refresh=refresh,
                physicalQualification=True,successorInstalled=False,jointEligible=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={'selection':'learner prepared original selection','receipt':'learner typed exact receipt',
           'old-source':'admitted exact before-learner-source: node-1',
           'new-source':'admitted exact before-learner-refresh: node-1',
           'refreshed-copy':'learner source exact original generation','missing-exchange':'learner source exact received trace',
           'missing-force':'learner prepared exact selection force order','early-select':'learner prepared exact selection force order',
           'backup':'learner typed original backup and receipt','false-ready':'learner prepared result scope'}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-prepared-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='selection':(path/'typed/prepared.json').write_bytes(b'bad')
            elif name=='receipt':(path/'learner-receipt.gsr').write_bytes(b'bad')
            elif name in ('old-source','new-source'):
                stage='before-learner-source' if name=='old-source' else 'before-learner-refresh'
                (path/stage/'node-1/selector.gsr').write_bytes(b'bad')
            elif name=='refreshed-copy':(path/'learner-refresh-copy/generation.gsr').write_bytes(b'bad')
            elif name=='missing-exchange':
                p=path/'learner-refresh-wire.json';rows=d.read(p);rows.pop();p.write_bytes(f.canonical(rows))
            elif name in ('missing-force','early-select'):
                p=path/'learner-typed-events.json';rows=d.read(p)
                if name=='missing-force':rows.remove('LEARNER_PREPARED_FORCED')
                else:
                    rows.remove('LEARNER_PREPARED_BEFORE_SELECT');rows.insert(rows.index('LEARNER_PREPARED_FORCED'),'LEARNER_PREPARED_BEFORE_SELECT')
                p.write_bytes(f.canonical(rows))
            elif name=='backup':(path/'typed/backup/gse-backup-checkpoint').write_bytes(b'bad')
            else:
                p=path/'learner-prepared-result.json';v=d.read(p);v['publicReady']=True;p.write_bytes(f.canonical(v))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'learner prepared unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner prepared accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))
