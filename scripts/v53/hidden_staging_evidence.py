"""Original-first replay of an applied endpoint hidden inside a later RANGE."""
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import covered_staging_evidence as q

p=q.phased;m=q.m;e=q.e;c=q.c;b=q.b;d=q.d;s=q.selection
CUTS=('SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN','SUPERSEDED_END_AUTHORITY_FORCED',
      'SUPERSEDED_END_FILE_DELETED','SUPERSEDED_END_RETIREMENT_DELETED')


def extend(root,group,lagging,majority,observed):
    group=q.staged(root,group,lagging,majority,observed)
    _,members,packet=c.current(group[majority[0]]);cap=packet['capsule'];coverage=e.parse(members[c.COVERAGE])
    frames,_=c.pending(c.inventory(root/'slot-1-certified'/majority[0])['pending.accept'],('PROOF','CERTIFICATE'))
    originals=[frames[k] for k in ('ENTRY','ACCEPT','PROOF','CERTIFICATE','PAYLOAD')]
    first=dict(parent=coverage['parent'],end=c.anchor(cap),certificate=coverage['certificate'],proof={e.digest(v):v for v in originals})
    ballot=e.f.decode(members['promise.gsr'],'records','PROMISE')['ballot'];barrier=d.entry({'node-1':group[majority[0]]},b'',ballot,'BARRIER')
    e.need(p.t.plans.read(root/'barrier.gsr',16384)==barrier,'hidden staging exact majority continuation')
    group,_=m.publication(root,group,2,barrier,b'',observed,majority,first=first)
    return group


def prefix(root,clean):
    root=Path(root);profile=p.profile(root);names=['node-'+str(i+1) for i in range(profile['size'])];majority=names[profile['size']-(profile['size']//2+1):]
    extras={'lagging-applied','barrier.gsr','applied-ancestry.gsr'}|{f'slot-2-{v}' for v in ('accepted','proved','certified','applied','published','settled')}|{'typed-2-'+n for n in majority}
    if clean:
        extras|={'staging-retired','round-3-installed','round-3-settled','continued.gsr'}|{f'round-4-{v}' for v in ('prepared','selected','installed','settled')}
        extras|={f'slot-3-{v}' for v in ('accepted','proved','certified','applied','published','settled')}|{'typed-3-'+n for n in names}
    else:extras|={'interruptions.json'}|{'interrupted-'+v for v in CUTS}
    profile,names,lagging,majority=p.layout(root,'prepared',extras);e.need(profile['phase']=='CERTIFICATE','hidden staging certificate profile')
    before,after,observed=p.prefix(root,profile,names,lagging,majority,staging=extend)
    after={n:q.without_staging(v) for n,v in after.items()}
    donors=[c.inventory(root/'slot-2-applied'/n) for n in majority]
    proof=donors[0]['applied-end/parent-statement.gsr']+b''.join(v['applied-end/parent-ack.gsr'] for v in donors)
    e.need(p.t.plans.read(root/'applied-ancestry.gsr',96*1024)==proof,'hidden staging exact applied ancestry')
    for node in majority:
        _,members,packet=c.current(c.inventory(root/'slot-2-settled'/node));b.typed_image(root/('typed-2-'+node),members[packet['capsule']['application']+'.image'])
    return profile,names,lagging,majority,before,after,observed,proof


def authority(before,after,proof):
    original=q.authority(before,after);value=e.parse(original[48:]);value['authority']['appliedAncestry']=e.digest(proof)
    body=e.f.canonical(value);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));return header+bytes.fromhex(e.digest(header+body))+body


def calls(root,names,lagging,majority,before,after,clean):
    expected=[]
    def many(nodes,operation):expected.extend((n,operation) for n in nodes)
    def maintain(nodes,label):many(nodes,label+'-copy');many(nodes,label+'-maintain')
    def campaign(counter,installed=True):
        expected.append((names[0] if counter==1 else names[-1],'allocate-'+str(counter)))
        for part in ('prepare','select','install') if installed else ('prepare','select'):many(names,part+'-'+str(counter))
    def publish(slot,nodes):
        for part in ('accept','proof','certificate','apply','publish'):many(nodes,part+'-'+str(slot))
        maintain(nodes,'slot-'+str(slot)+'-settled');many(nodes,'inspect-'+str(slot))
    campaign(1);maintain(names,'round-1-settled');expected.append((names[-1],'entry'));many(names,'initial-vote');publish(1,majority)
    many(lagging,'lagging-proof');many(lagging,'lagging-certificate');many(lagging,'lagging-apply');expected.append((names[-1],'entry'));publish(2,majority);campaign(3,False)
    if clean:
        many(lagging,'retire-hidden-application');many(names,'install-3');maintain(names,'round-3-settled');campaign(4);maintain(names,'round-4-settled');expected.append((names[-1],'entry'));publish(3,names)
    rows=p.read(root/'calls.json',8*e.MIB);e.need(type(rows) is list and len(rows)==len(expected),'hidden staging owner call inventory')
    for row,(node,operation) in zip(rows,expected):
        e.exact(row,'node operation events');events=row['events'];e.need(row['node']==node and row['operation']==operation and type(events) is list and 0<len(events)<=4096 and all(type(v) is str for v in events),'hidden staging exact owner calls')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
                  'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
                  'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
                  'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
                  'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
                  'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']*2,
                  'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if operation=='lagging-apply':required=['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']
        if operation in ('lagging-proof','lagging-certificate'):
            label=operation.split('-')[1].upper();required=[label+'_CANDIDATE_FORCED',label+'_PARENT_FORCED',label+'_BEFORE_RETURN',label+'_BEFORE_RETURN']
        if operation=='initial-vote' or phase=='accept':
            required=([] if operation=='accept-1' else ['ACCEPT_CANDIDATE_FORCED','ACCEPT_PARENT_FORCED'])+['ACCEPT_BEFORE_RETURN']*2
        if required:e.need([v for v in events if v in set(required)]==required,'hidden staging force before response: '+operation)
        if operation=='install-3' and node in lagging:
            _,order=m.transaction(q.without_staging(before[node]),after[node],floor=False,phase='CERTIFICATE');e.need(events==order,'hidden staging exact settlement order')
        elif any(v.startswith('SETTLED_VOTE_') for v in events):raise ValueError('hidden staging unexpected settlement')


def clean(root):
    root=Path(root);profile,names,lagging,majority,before,after,observed,proof=prefix(root,True)
    retired={n:q.without_staging(v) for n,v in before.items()};b.match(root,'staging-retired',retired);b.match(root,'round-3-installed',after)
    group=d.settle(root,'round-3-settled',after,names);_,group,ballot=m.advanced_campaign(root,group,4,names);group=d.settle(root,'round-4-settled',group,names)
    barrier=d.entry(group,b'',ballot,'BARRIER');e.need(p.t.plans.read(root/'continued.gsr',16384)==barrier,'hidden staging exact recovered continuation')
    m.publication(root,group,3,barrier,b'',observed,names);m.observations(root,observed);calls(root,names,lagging,majority,before,after,True)
    for row in p.read(root/'calls.json',8*e.MIB):
        if row['operation']=='retire-hidden-application':
            n=row['node'];expected,events=q.cleanup(before[n],authority(before[n],after[n],proof));e.need(expected==retired[n] and q.selected_events(row['events'])==events,'hidden staging cleanup order');q.no_ack(row['events'])
    for node in names:
        _,members,packet=c.current(c.inventory(root/'slot-3-settled'/node));b.typed_image(root/('typed-3-'+node),members[packet['capsule']['application']+'.image'])
    return dict(status='PASS',size=profile['size'],backup=profile['backup'],nodePublications=2*len(majority)+len(names))


def interruptions(root):
    root=Path(root);profile,names,lagging,majority,before,after,observed,proof=prefix(root,False)
    e.need(profile==dict(size=3,backup=False,phase='CERTIFICATE'),'hidden staging interruption profile');m.observations(root,observed);calls(root,names,lagging,majority,before,after,False)
    initial=before['node-1'];marker=authority(initial,after['node-1'],proof);rows=[]
    for cut in CUTS:
        case=root/('interrupted-'+cut);s.layout(case,{'first','second','final','installed','events.json'},'hidden staging interruption');events=p.read(case/'events.json');e.exact(events,'first second final');state=initial
        for stage,point in [('first',cut),('second','SUPERSEDED_END_AUTHORITY_FORCED'),('final',None)]:
            state,trace=q.cleanup(state,marker,point)
            e.need(c.inventory(case/stage)==state,'hidden staging exact '+stage+' snapshot');e.need(q.selected_events(events[stage])==trace,'hidden staging exact '+stage+' force order');q.no_ack(events[stage])
        e.need(state==q.without_staging(initial) and c.inventory(case/'installed')==after['node-1'],'hidden staging exact installed result');rows.append(dict(cut=cut,status='PASS'))
    e.need(p.read(root/'interruptions.json')==rows,'hidden staging interruption receipt');return dict(status='PASS',cases=4,interruptions=8)


def validate(profiles,interrupted):
    root=Path(profiles);rows=[dict(case=str(n)+'-'+('backup' if backup else 'empty'),size=n,backup=backup,status='PASS') for n in (3,4,5) for backup in (False,True)]
    s.layout(root,{'receipt.json'}|{r['case'] for r in rows},'hidden staging profiles');results=[clean(root/r['case']) for r in rows]
    e.need(e.f.canonical(p.read(root/'receipt.json'))==e.f.canonical(dict(schema='gse-v53-hidden-staging-v1',status='PASS',cases=rows)),'hidden staging exact profile receipt')
    return dict(status='PASS',profiles=results,interruptions=interruptions(interrupted),publicRuntime=False,powerLoss=False,freshProcesses=False)


VARIANTS={
    'original-applied':'admitted exact lagging-applied: node-1',
    'hidden-proof':'hidden staging exact applied ancestry',
    'cleanup-original':'admitted exact staging-retired: node-1',
    'cleanup-source':'admitted exact staging-retired: node-1',
    'cleanup-force':'hidden staging cleanup order',
    'cleanup-old-ack':'covered staging emitted old ACK',
    'installed-ancestry':'admitted exact round-3-installed: node-1',
    'retirement-proof':'hidden staging exact first snapshot',
    'retirement-inventory':'hidden staging exact first snapshot',
    'recovery-vote':'hidden staging exact second snapshot',
    'recovery-force':'hidden staging exact second force order',
    'installed-vote':'hidden staging exact installed result',
}


def qualify(profiles,interrupted):
    result=validate(profiles,interrupted);negatives=[]
    for name,reason in VARIANTS.items():
        interrupted_case=name.startswith(('retirement-','recovery-')) or name=='installed-vote'
        with tempfile.TemporaryDirectory(prefix='v53-hidden-staging-negative-') as temp:
            root=Path(temp)/'raw';shutil.copytree(interrupted if interrupted_case else Path(profiles)/'3-empty',root)
            case=root/'interrupted-SUPERSEDED_END_AUTHORITY_FORCED'
            if name=='original-applied':(root/'lagging-applied/node-1/applied-end/application.image').write_bytes(b'changed')
            elif name=='hidden-proof':(root/'applied-ancestry.gsr').write_bytes(b'')
            elif name=='cleanup-original':(root/'staging-retired/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='cleanup-source':next((root/'staging-retired/node-1/sources').glob('*/source.gscp')).unlink()
            elif name in ('cleanup-force','cleanup-old-ack'):
                path=root/'calls.json';rows=p.read(path,8*e.MIB);events=next(v['events'] for v in rows if v['operation']=='retire-hidden-application')
                if name=='cleanup-force':events.remove('SUPERSEDED_END_AUTHORITY_FORCED')
                else:events.append('APPLY_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(rows))
            elif name=='installed-ancestry':
                files=c.inventory(root/'round-3-installed/node-1');pref,_,_=c.current(files);(root/'round-3-installed/node-1'/pref/'ancestry.gsr').write_bytes((root/'applied-ancestry.gsr').read_bytes())
            elif name.startswith('retirement-'):
                path=case/'first/applied-end/retirement.gsat';raw=path.read_bytes();value=e.parse(raw[48:])
                if name=='retirement-proof':value['authority']['appliedAncestry']='0'*64
                else:value['files']=value['files'][:-1]
                body=e.f.canonical(value);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));path.write_bytes(header+bytes.fromhex(e.digest(header+body))+body)
            elif name=='recovery-vote':(case/'second/pending.accept').write_bytes(c.EMPTY)
            elif name=='recovery-force':
                path=case/'events.json';events=p.read(path);events['second'].remove('SUPERSEDED_END_AUTHORITY_FORCED');path.write_bytes(e.f.canonical(events))
            elif name=='installed-vote':shutil.copyfile(root/'before-install/node-1/pending.accept',case/'installed/pending.accept')
            try:(interruptions if interrupted_case else clean)(root)
            except ValueError as error:e.need(str(error)==reason,'hidden staging wrong rejection: '+name+': '+str(error))
            else:raise ValueError('hidden staging mutation accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**result,negatives=negatives)


def portable(profiles,interrupted):
    original=qualify(profiles,interrupted)
    with tempfile.TemporaryDirectory(prefix='v53-hidden-staging-portable-') as temp:
        root=Path(temp);shutil.copytree(profiles,root/'profiles');shutil.copytree(interrupted,root/'interrupted')
        e.need(qualify(root/'profiles',root/'interrupted')==original,'hidden staging relocated replay changed')
    return dict(**original,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('profiles');parser.add_argument('interruptions');parser.add_argument('--portable',action='store_true');parser.add_argument('--qualify',action='store_true');a=parser.parse_args()
    print(json.dumps((portable if a.portable else qualify if a.qualify else validate)(a.profiles,a.interruptions),sort_keys=True))
