"""Derive covered unapplied PROOF/certificate recovery from admitted originals."""
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import covered_minority_evidence as model

e=model.e;c=model.c;t=model.t;b=model.b;d=model.d;selection=model.selection


def read(path,limit=1024*1024):return e.parse(t.plans.read(path,limit))
def phases(phase):return ('PROOF',) if phase=='PROOF' else ('PROOF','CERTIFICATE')
def append(raw,frame):
    result=raw+frame;return result[:8]+struct.pack('>I',len(result))+result[12:]


def profile(root):
    value=read(root/'profile.json');e.exact(value,'size backup phase')
    e.need(type(value['size']) is int and value['size'] in (3,4,5) and type(value['backup']) is bool and value['phase'] in ('PROOF','CERTIFICATE'),'covered phased exact profile')
    return value


def layout(root,mode,extras=()):
    p=profile(root);names=['node-'+str(i+1) for i in range(p['size'])];lagging=names[:p['size']-(p['size']//2+1)];majority=names[len(lagging):]
    required={'profile.json','original-plan.gsbp','original-application.image','initial','calls.json','observations.json','entry.gsr','payload.bin','initial-votes','lagging-proved','before-install'}
    required|={f'round-1-{s}' for s in ('prepared','selected','installed','settled')}|{'round-3-prepared','round-3-selected'}
    required|={f'slot-1-{s}' for s in ('accepted','proved','certified','applied','published','settled')}|{'typed-1-'+n for n in majority}
    if p['phase']=='CERTIFICATE':required.add('lagging-certified')
    if mode=='clean':
        required|={'round-3-installed','round-3-settled','barrier.gsr'}|{f'round-4-{s}' for s in ('prepared','selected','installed','settled')}
        required|={f'slot-2-{s}' for s in ('accepted','proved','certified','applied','published','settled')}|{'typed-2-'+n for n in names}
    elif mode=='interrupted':required|={'interruptions.json'}|{'interrupted-'+cut for cut in model.CUTS}
    elif mode=='prepared':pass
    else:raise ValueError('covered phased mode')
    selection.layout(root,required|set(extras),'covered phased '+mode);return p,names,lagging,majority


def prefix(root,p,names,lagging,majority,staging=None):
    observed=[];group=b.campaign(root,b.original(root,p['size'],p['backup']),1)
    ballot=e.f.decode(c.current(group['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot'];body=d.payload(404,'majority-selected');entry=d.entry(group,body,ballot)
    e.need(t.plans.read(root/'entry.gsr',16384)==entry and t.plans.read(root/'payload.bin',e.MIB)==body,'covered phased original ENTRY')
    group=d.vote(root,'initial-votes',group,names,entry,body,observed)
    group,_=model.publication(root,group,1,entry,body,observed,majority)
    frames,_=c.pending(c.inventory(root/'slot-1-certified'/majority[0])['pending.accept'],('PROOF','CERTIFICATE'))
    for node in lagging:
        files=group[node];group[node]=dict(files,**{'pending.accept':append(files['pending.accept'],frames['PROOF'])})
        identity=e.f.decode(files['node.gsr'],'records','NODE')['identity'];cap=c.current(files)[2]['capsule']
        observed.append(dict(voter=node,storage=identity['storage'],record=e.digest(frames['PROOF']),parent=e.digest(e.f.canonical(cap['cut']))))
    b.match(root,'lagging-proved',group)
    if p['phase']=='CERTIFICATE':
        for node in lagging:group[node]=dict(group[node],**{'pending.accept':append(group[node]['pending.accept'],frames['CERTIFICATE'])})
        b.match(root,'lagging-certified',group)
    if staging is not None:group=staging(root,group,lagging,majority,observed)
    before,after,_=model.advanced_campaign(root,group,3,names,False,phases(p['phase']));b.match(root,'before-install',before)
    for node in majority:
        _,members,packet=c.current(c.inventory(root/'slot-1-settled'/node));b.typed_image(root/('typed-1-'+node),members[packet['capsule']['application']+'.image'])
    return before,after,observed


def calls(root,p,names,lagging,majority,before,after,clean,staging=False):
    expected=[]
    def many(nodes,label):expected.extend((n,label) for n in nodes)
    def maintain(nodes,label):many(nodes,label+'-copy');many(nodes,label+'-maintain')
    def campaign(counter,installed=True):
        expected.append((names[0] if counter==1 else names[-1],'allocate-'+str(counter)))
        for part in ('prepare','select','install') if installed else ('prepare','select'):many(names,part+'-'+str(counter))
    def publish(slot,nodes):
        for part in ('accept','proof','certificate','apply','publish'):many(nodes,part+'-'+str(slot))
        maintain(nodes,'slot-'+str(slot)+'-settled');many(nodes,'inspect-'+str(slot))
    campaign(1);maintain(names,'round-1-settled');expected.append((names[-1],'entry'));many(names,'initial-vote');publish(1,majority)
    many(lagging,'lagging-proof')
    if p['phase']=='CERTIFICATE':many(lagging,'lagging-certificate')
    if staging:many(lagging,'lagging-apply')
    campaign(3,False)
    if clean:
        if staging:many(lagging,'retire-covered-application')
        many(names,'install-3');maintain(names,'round-3-settled');campaign(4);maintain(names,'round-4-settled');expected.append((names[-1],'entry'));publish(2,names)
    rows=read(root/'calls.json',8*e.MIB);e.need(type(rows) is list and len(rows)==len(expected),'covered phased owner call inventory')
    for row,(node,operation) in zip(rows,expected):
        e.exact(row,'node operation events');events=row['events']
        e.need(row['node']==node and row['operation']==operation and type(events) is list and 0<len(events)<=4096 and all(type(v) is str for v in events),'covered phased exact owner calls')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
                  'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
                  'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
                  'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
                  'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
                  'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
                  'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if operation=='lagging-apply':required=['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']
        if operation in ('lagging-proof','lagging-certificate'):
            label=operation.split('-')[1].upper();required=[label+'_CANDIDATE_FORCED',label+'_PARENT_FORCED',label+'_BEFORE_RETURN',label+'_BEFORE_RETURN']
        if required:e.need([v for v in events if v in set(required)]==required,'covered phased force before response: '+operation)
        if operation=='initial-vote' or phase=='accept':
            required=['ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']
            if operation!='accept-1':required=['ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED',*required]
            e.need([v for v in events if v in {'ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN'}]==required,'covered phased accept force/duplicate order')
        if operation=='install-3' and node in lagging:
            _,order=model.transaction(before[node],after[node],floor=False,phase=p['phase']);e.need(events==order,'covered phased exact settlement order')
        elif any(v.startswith('SETTLED_VOTE_') for v in events):raise ValueError('covered phased unexpected settlement')


def clean(root):
    root=Path(root);p,names,lagging,majority=layout(root,'clean');before,after,observed=prefix(root,p,names,lagging,majority)
    b.match(root,'round-3-installed',after);group=d.settle(root,'round-3-settled',after,names)
    _,group,ballot=model.advanced_campaign(root,group,4,names);group=d.settle(root,'round-4-settled',group,names)
    barrier=d.entry(group,b'',ballot,'BARRIER');e.need(t.plans.read(root/'barrier.gsr',16384)==barrier,'covered phased continuation BARRIER')
    model.publication(root,group,2,barrier,b'',observed,names);model.observations(root,observed);calls(root,p,names,lagging,majority,before,after,True)
    for node in names:
        _,members,packet=c.current(c.inventory(root/'slot-2-settled'/node));b.typed_image(root/('typed-2-'+node),members[packet['capsule']['application']+'.image'])
    return dict(status='PASS',**p,laggingVoters=len(lagging),nodePublications=len(names)+len(majority))


def interrupted(root):
    root=Path(root);p,names,lagging,majority=layout(root,'interrupted');e.need(p['size']==3 and not p['backup'],'covered phased interruption profile')
    before,after,observed=prefix(root,p,names,lagging,majority);model.observations(root,observed);calls(root,p,names,lagging,majority,before,after,False);rows=[]
    for cut in model.CUTS:
        case=root/('interrupted-'+cut);selection.layout(case,{'first','second','final','events.json'},'covered phased interruption')
        second=p['phase']+'_ACTIVE_FORCED' if cut=='INSTALL_MANIFEST_FORCED' else 'ACCEPT_ACTIVE_FORCED' if cut in ('SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED','SETTLED_VOTE_BEFORE_RETURN') else 'SETTLED_VOTE_CANDIDATE_PARENT_FORCED'
        traces=read(case/'events.json');e.exact(traces,'first second final');state=before['node-1']
        for stage,point in [('first',cut),('second',second),('final',None)]:
            state,events=model.transaction(state,after['node-1'],point,phase=p['phase'])
            e.need(c.inventory(case/stage)==state,'covered phased exact '+stage+' snapshot');e.need(traces[stage]==events,'covered phased exact '+stage+' force order')
        rows.append(dict(cut=cut,second=second,status='PASS'))
    e.need(e.f.canonical(read(root/'interruptions.json'))==e.f.canonical(rows),'covered phased exact interruption receipt')
    return dict(status='PASS',cases=12,interruptions=24,**p)


def validate(profiles,proof,certificate):
    profiles=Path(profiles);rows=[];results=[]
    for phase in ('PROOF','CERTIFICATE'):
        for size in (3,4,5):
            for backup in (False,True):
                name=phase+'-'+str(size)+'-'+('backup' if backup else 'empty');rows.append(dict(case=name,phase=phase,size=size,backup=backup,status='PASS'))
    selection.layout(profiles,{'receipt.json'}|{v['case'] for v in rows},'covered phased profiles')
    for row in rows:
        result=clean(profiles/row['case']);e.need(all(e.f.canonical(result[k])==e.f.canonical(row[k]) for k in ('phase','size','backup','status')),'covered phased profile mapping');results.append(result)
    expected=dict(schema='gse-v53-covered-phased-profiles-v1',status='PASS',cases=rows,publicBootstrap=True,runtimeEnabled=False)
    e.need(e.f.canonical(read(profiles/'receipt.json'))==e.f.canonical(expected),'covered phased exact profile receipt')
    interruptions=[interrupted(proof),interrupted(certificate)]
    e.need([v['phase'] for v in interruptions]==['PROOF','CERTIFICATE'],'covered phased interruption phases')
    return dict(status='PASS',profiles=results,interruptions=interruptions,publicBootstrap=True,publicRuntime=False,freshProcesses=False,maximalCapacity=False,independentImageSemantics=False)


VARIANTS={
    'original-vote':'admitted exact initial-votes: node-1',
    'proof':'admitted exact lagging-proved: node-1',
    'certificate':'admitted exact lagging-certified: node-1',
    'pinned-source':'admitted exact round-3-prepared: node-1',
    'selected-prefix':'admitted exact round-3-installed: node-1',
    'remaining-proof':'admitted exact round-3-installed: node-1',
    'old-source-deletion':'admitted exact round-3-installed: node-1',
    'accept-original':'covered phased accept force/duplicate order',
    'proof-force':'covered phased force before response: lagging-proof',
    'certificate-force':'covered phased force before response: lagging-certificate',
    'premature-settlement':'covered phased exact settlement order',
    'first-prefix':'covered phased exact first snapshot',
    'second-prefix':'covered phased exact second snapshot',
    'final-original':'covered phased exact final snapshot',
    'second-force':'covered phased exact second force order',
    'receipt-flag':'covered phased exact profile receipt',
    'profile-type':'covered phased exact profile',
    'observations':'covered actual owner observations',
}


def qualify(profiles,proof,certificate):
    roots=[Path(profiles),Path(proof),Path(certificate)];result=validate(*roots);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-covered-phased-negative-') as tmp:
            copies=[Path(tmp)/n for n in ('profiles','proof','certificate')]
            for original,copy in zip(roots,copies):shutil.copytree(original,copy)
            case=copies[0]/('CERTIFICATE-3-empty' if name in ('certificate','certificate-force') else 'PROOF-3-empty')
            if name in ('original-vote','proof','certificate','remaining-proof'):
                stage={'original-vote':'initial-votes','proof':'lagging-proved','certificate':'lagging-certified','remaining-proof':'round-3-installed'}[name];(case/stage/'node-1/pending.accept').write_bytes(b'changed')
            elif name=='pinned-source':next((case/'round-3-prepared/node-1/sources').glob('*/source.gscp')).unlink()
            elif name=='selected-prefix':(case/'round-3-installed/node-1/selector.gsr').write_bytes(b'changed')
            elif name=='old-source-deletion':next((case/'round-3-installed/node-1/sources').glob('*/source.gscp')).unlink()
            elif name in ('accept-original','proof-force','certificate-force','premature-settlement'):
                path=case/'calls.json';value=read(path,8*e.MIB)
                label={'accept-original':'initial-vote','proof-force':'lagging-proof','certificate-force':'lagging-certificate','premature-settlement':'install-3'}[name]
                row=next(v for v in value if v['node']=='node-1' and v['operation']==label)
                event={'accept-original':'ACCEPT_PARENT_FORCED','proof-force':'PROOF_PARENT_FORCED','certificate-force':'CERTIFICATE_PARENT_FORCED','premature-settlement':'SETTLED_VOTE_VALIDATED'}[name]
                row['events'].remove(event)
                if name=='premature-settlement':row['events'].insert(0,event)
                path.write_bytes(e.f.canonical(value))
            elif name in ('first-prefix','second-prefix','final-original','second-force'):
                case=copies[1]/'interrupted-INSTALL_SELECTOR_RENAMED'
                if name=='second-force':
                    path=case/'events.json';value=read(path);value['second'].remove('SETTLED_VOTE_CANDIDATE_FORCED');path.write_bytes(e.f.canonical(value))
                else:
                    stage={'first-prefix':'first','second-prefix':'second','final-original':'final'}[name];(case/stage/'pending.accept').write_bytes(b'changed')
            elif name=='observations':
                path=case/'observations.json';value=read(path);value.pop();path.write_bytes(e.f.canonical(value))
            else:
                path=copies[0]/'receipt.json' if name=='receipt-flag' else case/'profile.json';value=read(path);value['publicBootstrap' if name=='receipt-flag' else 'backup']=1;path.write_bytes(e.f.canonical(value))
            try:validate(*copies)
            except ValueError as error:
                e.need(str(error)==reason,'wrong covered phased rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted covered phased mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-covered-phased-portable-') as tmp:
        copies=[Path(tmp)/n for n in ('profiles','proof','certificate')]
        for original,copy in zip(roots,copies):shutil.copytree(original,copy)
        e.need(validate(*copies)==result,'covered phased portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profiles');p.add_argument('proof');p.add_argument('certificate');a=p.parse_args();print(json.dumps(qualify(a.profiles,a.proof,a.certificate),sort_keys=True))
