"""Original-first physical replay of applied-but-unpublished covered certificates.

The typed Java producer validates application semantics. This reader checks bytes,
original authority, derived retirement inventory and force/delete ordering; it
neither claims power-loss durability nor invents remote observations.
"""
import argparse
import json
import struct
import tempfile
import shutil
from pathlib import Path
from . import covered_phased_vote_evidence as phased
m=phased.model;e=m.e;c=m.c;b=m.b;d=m.d;selection=m.selection

CUTS=('STAGED_RETIREMENT_AUTHORITY_VALIDATED','REPLAY_CLAIM_PREFIX_WRITTEN','REPLAY_APPLICATION_FINISHED',
      'SUPERSEDED_END_VALIDATED','SUPERSEDED_END_RETIREMENT_CREATED','SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN',
      'SUPERSEDED_END_RETIREMENT_WRITTEN','SUPERSEDED_END_RETIREMENT_FORCED','SUPERSEDED_END_RETIREMENT_PARENT_FORCED',
      'SUPERSEDED_END_RETIREMENT_RENAMED','SUPERSEDED_END_AUTHORITY_FORCED','SUPERSEDED_END_BEFORE_DELETE','SUPERSEDED_END_FILE_DELETED',
      'SUPERSEDED_END_BEFORE_RETIREMENT_DELETE','SUPERSEDED_END_RETIREMENT_DELETED','SUPERSEDED_END_BEFORE_DIRECTORY_DELETE',
      'SUPERSEDED_END_DIRECTORY_DELETED','STAGED_RETIREMENT_BEFORE_RETURN')


def without_staging(files):
    return {k:v for k,v in files.items() if k!='applied-end' and not k.startswith('applied-end/') and k!='application-replay' and not k.startswith('application-replay/')}


def staged(root,group,lagging,majority,observed):
    result=dict(group);donor=c.inventory(root/'slot-1-applied'/majority[0])
    for node in lagging:
        files=group[node];frames,_=c.pending(files['pending.accept'],('PROOF','CERTIFICATE'))
        identity=e.f.decode(files['node.gsr'],'records','NODE')['identity']
        end={k.removeprefix('applied-end/'):v for k,v in donor.items() if k.startswith('applied-end/') and k not in ('applied-end/plan.json','applied-end/ack.gsr')}
        end['selector.gsr']=files['selector.gsr'];e.need(end['certificate.gsr']==frames['CERTIFICATE'],'covered staging exact original certificate')
        statement=e.f.decode(end['statement.gsr'],'records','CHECKPOINT')
        ack=e.f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter=node,incarnation=identity['storage'],cut=statement['end'],statement=e.digest(end['statement.gsr'])))
        end['ack.gsr']=ack;end['plan.json']=e.f.canonical(dict(schema='gse-v53-applied-end/1.3',root=statement['root'],node=node,
            files=[dict(path=k,**e.info(v)) for k,v in sorted(end.items())]))
        result[node]=dict(files,**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})
        observed.append(dict(voter=node,storage=identity['storage'],record=e.digest(ack),parent=e.digest(e.f.canonical(statement['end']))))
    b.match(root,'lagging-applied',result);return result


def authority(before,after):
    node=e.f.decode(before['node.gsr'],'records','NODE')['identity'];_,old,packet=c.current(before);_,new,_=c.current(after)
    frames,_=c.pending(before['pending.accept'],('PROOF','CERTIFICATE'));rows=c.journal(before['grants.gsr'],packet['capsule']['root'],node['node'])
    promise,basis,selected=rows[-3:];source=before['sources/'+basis[2]['basisId']+'/source.gscp']
    value=dict(mode='covered-prefix',coveringGeneration=e.f.decode(after['selector.gsr'],'records','SELECTOR')['digest'],coveringSelector=e.digest(after['selector.gsr']),
        pending=e.digest(before['pending.accept']),oldGeneration=e.f.decode(before['selector.gsr'],'records','SELECTOR')['digest'],selector=e.digest(before['selector.gsr']),generation=e.f.decode(before['selector.gsr'],'records','SELECTOR')['digest'],
        promise=e.digest(promise[1]),selection=e.digest(selected[1]),basis=e.digest(basis[1]),source=e.digest(source),ancestry=e.digest(old.get('ancestry.gsr',b'')),
        coverage=e.digest(old.get(c.COVERAGE,b'')),parentSources=sorted([dict(basis=e.digest(raw),packet=e.digest(before['sources/'+obj['basisId']+'/source.gscp']))
            for kind,raw,obj in rows if kind=='BASIS'],key=lambda r:r['basis']),floor='')
    original={k.removeprefix('applied-end/'):v for k,v in before.items() if k.startswith('applied-end/')}
    body=e.f.canonical(dict(schema='gse-v53-applied-end-retirement/1.3',root=packet['capsule']['root'],node=node['node'],storage=node['storage'],
        selector=e.digest(before['selector.gsr']),plan=e.digest(original['plan.json']),authority=value,
        files=[dict(path=k,type='file',**e.info(v)) for k,v in sorted(original.items())]))
    header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));marker=header+bytes.fromhex(e.digest(header+body))+body
    return marker


def cleanup(initial,marker,stop=None):
    """Simulate only derived-end retirement. Replay scratch is checked separately."""
    files=dict(initial);events=[]
    class Stop(Exception):pass
    def event(name):
        events.append(name)
        if name==stop:raise Stop()
    try:
        if 'applied-end' not in files:return files,events
        event('STAGED_RETIREMENT_AUTHORITY_VALIDATED')
        if stop in ('REPLAY_CLAIM_PREFIX_WRITTEN','REPLAY_APPLICATION_FINISHED'):raise Stop()
        event('SUPERSEDED_END_VALIDATED')
        active='applied-end/retirement.gsat';next_file=active+'.next'
        if active not in files:
            body=e.parse(marker[48:]);body['files']=[dict(path=k.removeprefix('applied-end/'),type='file',**e.info(v)) for k,v in sorted(files.items()) if k.startswith('applied-end/') and k!=next_file]
            body=e.f.canonical(body);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));marker=header+bytes.fromhex(e.digest(header+body))+body
            if next_file not in files:files[next_file]=b'';event('SUPERSEDED_END_RETIREMENT_CREATED')
            offset=len(files[next_file]);e.need(marker.startswith(files[next_file]),'covered staging exact retirement prefix')
            files[next_file]=marker[:offset+(len(marker)-offset)//2];event('SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN')
            files[next_file]=marker;event('SUPERSEDED_END_RETIREMENT_WRITTEN');event('SUPERSEDED_END_RETIREMENT_FORCED')
            event('SUPERSEDED_END_RETIREMENT_PARENT_FORCED');files[active]=files.pop(next_file);event('SUPERSEDED_END_RETIREMENT_RENAMED')
        else:
            body=e.parse(marker[48:]);body['files']=[];body=e.f.canonical(body);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));empty=header+bytes.fromhex(e.digest(header+body))+body
            e.need(files[active] in (marker,empty),'covered staging exact retained authority');event('SUPERSEDED_END_RETIREMENT_RESEALED')
        event('SUPERSEDED_END_AUTHORITY_FORCED')
        names=sorted(k for k in files if k.startswith('applied-end/') and k not in (active,'applied-end/plan.json'))
        if 'applied-end/plan.json' in files:names.append('applied-end/plan.json')
        for name in names:event('SUPERSEDED_END_BEFORE_DELETE');del files[name];event('SUPERSEDED_END_FILE_DELETED')
        event('SUPERSEDED_END_BEFORE_RETIREMENT_DELETE');del files[active];event('SUPERSEDED_END_RETIREMENT_DELETED')
        event('SUPERSEDED_END_BEFORE_DIRECTORY_DELETE');del files['applied-end'];event('SUPERSEDED_END_DIRECTORY_DELETED');event('STAGED_RETIREMENT_BEFORE_RETURN')
    except Stop:pass
    return files,events


def selected_events(events):return [v for v in events if v.startswith(('STAGED_','SUPERSEDED_'))]
def no_ack(events):e.need(not any(v.startswith('APPLY_ACK_') or v=='APPLY_BEFORE_RETURN' for v in events),'covered staging emitted old ACK')


def prefix(root,mode):
    extras={'lagging-applied'}|({'staging-retired'} if mode=='clean' else {'interruptions.json'}|{'interrupted-'+v for v in CUTS})
    p,names,lagging,majority=phased.layout(root,'clean' if mode=='clean' else 'prepared',extras)
    e.need(p['phase']=='CERTIFICATE','covered staging requires certificate profile')
    before,after,observed=phased.prefix(root,p,names,lagging,majority,staging=staged)
    after={n:without_staging(v) for n,v in after.items()};return p,names,lagging,majority,before,after,observed


def clean(root):
    root=Path(root);p,names,lagging,majority,before,after,observed=prefix(root,'clean')
    retired={n:without_staging(v) for n,v in before.items()};b.match(root,'staging-retired',retired);b.match(root,'round-3-installed',after)
    group=d.settle(root,'round-3-settled',after,names);_,group,ballot=m.advanced_campaign(root,group,4,names);group=d.settle(root,'round-4-settled',group,names)
    barrier=d.entry(group,b'',ballot,'BARRIER');e.need(phased.t.plans.read(root/'barrier.gsr',16384)==barrier,'covered staging continuation BARRIER')
    m.publication(root,group,2,barrier,b'',observed,names);m.observations(root,observed)
    phased.calls(root,p,names,lagging,majority,retired,after,True,staging=True)
    for call in phased.read(root/'calls.json',8*e.MIB):
        if call['operation']=='retire-covered-application':
            node=call['node'];expected,events=cleanup(before[node],authority(before[node],after[node]))
            e.need(expected==retired[node] and selected_events(call['events'])==events,'covered staging exact force/delete order');no_ack(call['events'])
    for node in names:
        _,members,packet=c.current(c.inventory(root/'slot-2-settled'/node));b.typed_image(root/('typed-2-'+node),members[packet['capsule']['application']+'.image'])
    return dict(status='PASS',size=p['size'],backup=p['backup'],laggingVoters=len(lagging),nodePublications=len(names)+len(majority))


def interruptions(root):
    root=Path(root);p,names,lagging,majority,before,after,observed=prefix(root,'interrupted')
    e.need(p['size']==3 and p['backup'] is False,'covered staging interruption profile');m.observations(root,observed)
    phased.calls(root,p,names,lagging,majority,before,after,False,staging=True);original=before['node-1'];marker=authority(original,after['node-1']);rows=[]
    for cut in CUTS:
        case=root/('interrupted-'+cut);selection.layout(case,{'first','second','final','installed','events.json'},'covered staging interruption')
        traces=phased.read(case/'events.json');e.exact(traces,'first second final');second='CERTIFICATE_ACTIVE_FORCED' if cut in ('STAGED_RETIREMENT_BEFORE_RETURN','SUPERSEDED_END_DIRECTORY_DELETED') else 'SUPERSEDED_END_AUTHORITY_FORCED'
        state=dict(original)
        for stage,point in [('first',cut),('second',second),('final',None)]:
            if point=='CERTIFICATE_ACTIVE_FORCED':expected,events=state,[]
            else:expected,events=cleanup(state,marker,point)
            actual=c.inventory(case/stage);scratch={k:v for k,v in actual.items() if k=='application-replay' or k.startswith('application-replay/')}
            if point in ('REPLAY_CLAIM_PREFIX_WRITTEN','REPLAY_APPLICATION_FINISHED'):
                frames,_=c.pending(original['pending.accept'],('PROOF','CERTIFICATE'));identity=e.f.decode(original['node.gsr'],'records','NODE')['identity'];selector=e.f.decode(original['selector.gsr'],'records','SELECTOR')
                claim=e.f.canonical(dict(schema='gse-v53-application-replay/1.3',root=selector['root'],node='node-1',storage=identity['storage'],selector=e.digest(original['selector.gsr']),certificate=e.digest(frames['CERTIFICATE'])))
                e.need(scratch.get('application-replay/claim.json')==(claim[:len(claim)//2] if point=='REPLAY_CLAIM_PREFIX_WRITTEN' else claim),'covered staging exact replay claim')
                e.need(len(scratch)<=32 and sum(len(v) for v in scratch.values() if v is not None)<=64*e.MIB,'covered staging replay bound')
                if point=='REPLAY_CLAIM_PREFIX_WRITTEN':e.need(set(scratch)=={'application-replay','application-replay/claim.json'},'covered staging replay prefix inventory')
                else:e.need(all(k in ('application-replay','application-replay/claim.json') or k.startswith('application-replay/work') for k in scratch),'covered staging replay work inventory')
            else:e.need(not scratch,'covered staging unexpected replay scratch')
            actual={k:v for k,v in actual.items() if k not in scratch}
            e.need(actual==expected,'covered staging exact '+stage+' snapshot');e.need(selected_events(traces[stage])==events,'covered staging exact '+stage+' force order');no_ack(traces[stage]);state=expected
        e.need(state==without_staging(original) and c.inventory(case/'installed')==after['node-1'],'covered staging exact post-cleanup installation')
        rows.append(dict(cut=cut,second=second,status='PASS'))
    e.need(phased.read(root/'interruptions.json')==rows,'covered staging interruption receipt')
    return dict(status='PASS',cases=len(rows),interruptions=2*len(rows),scratchSemantics='producer-only')


def validate(profiles,interrupted):
    root=Path(profiles);rows=[dict(case=str(n)+'-'+('backup' if backup else 'empty'),size=n,backup=backup,status='PASS') for n in (3,4,5) for backup in (False,True)]
    selection.layout(root,{'receipt.json'}|{r['case'] for r in rows},'covered staging profiles')
    results=[clean(root/r['case']) for r in rows]
    for row,result in zip(rows,results):e.need(all(e.f.canonical(row[k])==e.f.canonical(result[k]) for k in ('size','backup','status')),'covered staging profile binding')
    expected=dict(schema='gse-v53-covered-staging-profiles-v1',status='PASS',cases=rows,runtimeEnabled=False)
    e.need(e.f.canonical(phased.read(root/'receipt.json'))==e.f.canonical(expected),'covered staging profile receipt')
    return dict(status='PASS',profiles=results,interruptions=interruptions(interrupted),publicBootstrap=True,oldAcknowledgement=False,publicRuntime=False,freshProcesses=False,powerLoss=False)

VARIANTS={
    'applied-certificate':'admitted exact lagging-applied: node-1',
    'applied-image':'admitted exact lagging-applied: node-1',
    'applied-ack':'admitted exact lagging-applied: node-1',
    'applied-plan':'admitted exact lagging-applied: node-1',
    'retired-vote':'admitted exact staging-retired: node-1',
    'retired-source':'admitted exact staging-retired: node-1',
    'retired-selector':'admitted exact staging-retired: node-1',
    'remaining-image':'admitted exact staging-retired: node-1',
    'cleanup-force':'covered staging exact force/delete order',
    'cleanup-old-ack':'covered staging emitted old ACK',
    'first-authority':'covered staging exact first snapshot',
    'first-inventory':'covered staging exact first snapshot',
    'partial-delete':'covered staging exact first snapshot',
    'replay-claim':'covered staging exact replay claim',
    'recovery-force':'covered staging exact second force order',
    'final-old-vote':'covered staging exact final snapshot',
    'installed-tail':'covered staging exact post-cleanup installation',
}


def qualify(profiles,interrupted):
    baseline=validate(profiles,interrupted);rows=[]
    for name,reason in VARIANTS.items():
        is_interrupted=name in ('first-authority','first-inventory','partial-delete','replay-claim','recovery-force','final-old-vote','installed-tail')
        with tempfile.TemporaryDirectory(prefix='v53-covered-staging-negative-') as temp:
            root=Path(temp)/'raw';shutil.copytree(Path(interrupted) if is_interrupted else Path(profiles)/'3-empty',root)
            if name.startswith('applied-'):
                member={'applied-certificate':'certificate.gsr','applied-image':'application.image','applied-ack':'ack.gsr','applied-plan':'plan.json'}[name]
                path=root/'lagging-applied/node-1/applied-end'/member;raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
            elif name.startswith('retired-'):
                member={'retired-vote':'pending.accept','retired-selector':'selector.gsr'}.get(name)
                path=root/'staging-retired/node-1'/member if member else sorted((root/'staging-retired/node-1/sources').glob('*/source.gscp'))[-1]
                path.unlink()
            elif name=='remaining-image':
                path=root/'staging-retired/node-1/applied-end';path.mkdir();shutil.copyfile(root/'lagging-applied/node-1/applied-end/application.image',path/'application.image')
            elif name in ('cleanup-force','cleanup-old-ack'):
                path=root/'calls.json';calls=phased.read(path,8*e.MIB);events=next(v['events'] for v in calls if v['operation']=='retire-covered-application')
                if name=='cleanup-force':events.remove('SUPERSEDED_END_AUTHORITY_FORCED')
                else:events.append('APPLY_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(calls))
            elif name in ('first-authority','first-inventory'):
                path=root/'interrupted-SUPERSEDED_END_AUTHORITY_FORCED/first/applied-end/retirement.gsat';raw=path.read_bytes();body=e.parse(raw[48:])
                if name=='first-authority':body['authority']['coveringGeneration']='0'*64
                else:body['files']=body['files'][:-1]
                body=e.f.canonical(body);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));path.write_bytes(header+bytes.fromhex(e.digest(header+body))+body)
            elif name=='partial-delete':
                path=root/'interrupted-SUPERSEDED_END_FILE_DELETED/first/pending.accept';path.unlink()
            elif name=='replay-claim':
                path=root/'interrupted-REPLAY_CLAIM_PREFIX_WRITTEN/first/application-replay/claim.json';path.write_bytes(b'{}')
            elif name=='recovery-force':
                path=root/'interrupted-SUPERSEDED_END_AUTHORITY_FORCED/events.json';events=phased.read(path);events['second'].remove('SUPERSEDED_END_RETIREMENT_RESEALED');path.write_bytes(e.f.canonical(events))
            elif name=='final-old-vote':(root/'interrupted-SUPERSEDED_END_FILE_DELETED/final/pending.accept').write_bytes(c.EMPTY)
            elif name=='installed-tail':shutil.copyfile(root/'before-install/node-1/pending.accept',root/'interrupted-SUPERSEDED_END_FILE_DELETED/installed/pending.accept')
            try:(interruptions if is_interrupted else clean)(root)
            except ValueError as error:e.need(str(error)==reason,'covered staging negative wrong reason: '+name+': '+str(error))
            else:raise ValueError('covered staging mutation accepted: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(**baseline,negatives=rows)


def portable(profiles,interrupted):
    result=qualify(profiles,interrupted)
    with tempfile.TemporaryDirectory(prefix='v53-covered-staging-portable-') as temp:
        root=Path(temp);shutil.copytree(profiles,root/'profiles');shutil.copytree(interrupted,root/'interruptions')
        e.need(qualify(root/'profiles',root/'interruptions')==result,'covered staging portable replay changed')
    return dict(**result,portableReplay='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('profiles');p.add_argument('interruptions');p.add_argument('--qualify',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args()
    print(json.dumps((portable if a.portable else qualify if a.qualify else validate)(a.profiles,a.interruptions),sort_keys=True))
