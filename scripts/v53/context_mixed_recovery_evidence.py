"""Original-first mixed-ballot cleanup interrupted twice under fresh local owners."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import context_mixed_acceptance_evidence as mixed
from . import context_acceptance_evidence as acceptance

e, owner, source = mixed.e, mixed.owner, mixed.source
ACCEPT_CUTS=('CONTEXT_ACCEPT_SUCCESSOR_FORCED','CONTEXT_REDUNDANT_DELETED','CONTEXT_ACCEPT_CLEARED',
             'FLOOR_RELEASE_AUTHORITY_WRITTEN','FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_FILE_DELETED','FLOOR_RELEASE_AUTHORITY_CLEARED','CONTEXT_ACCEPT_BEFORE_RETURN')
SOURCE_CUTS=('SOURCE_RETIREMENT_FORCED','SOURCE_RETIREMENT_JOURNAL_PRUNED','SOURCE_RETIREMENT_FILE_DELETED','SOURCE_RETIREMENT_BEFORE_RETURN')


def state(files):
    return {p:dict(directory=True) if v is None else source.release.r.entry(v) for p,v in files.items()}


def plan(root, accept):
    node='node-1' if accept else 'node-2';stage='round-24/source-retired' if accept else 'retired'
    files=mixed.carried.inventory(root/'reference'/stage/node)
    current=mixed.carried.current(files)[2];prefix='floor-copies/'
    if not accept:
        segments,metadata,binding=e.decode(files['pending.context']);basis=e.f.decode(metadata['basis.gsr'],'records','BASIS')
        prefix='sources/'+basis['basisId']+'/'
    record=e.f.encode('records','RETIREMENT',dict(root=current['capsule']['root'],node=node,floor=e.digest(files['floor-copies/floor.gsr']),selector=e.digest(files['selector.gsr']),
        files=[dict(path=p,size=len(v),sha256=e.digest(v)) for p,v in sorted(files.items()) if p.startswith(prefix) and v is not None]))
    if accept:
        successor=mixed.accept(files)['pending.accept']
        return state(files),lambda value,ack:acceptance.transition(value,successor,record,acknowledge=ack)
    rows=owner.journal(files['grants.gsr'],basis['root'],node);promise=next(r[1] for r in rows if r[0]=='PROMISE' and r[2]['basisId']==basis['basisId'])
    packet=e.p.decode(files[prefix+'source.gscp']);authority=record+promise+e.f.encode('records','BASIS',basis)+packet['capsuleBytes']
    compact=mixed.retire_source(files,basis)['grants.gsr']
    return state(files),lambda value,ack:source.release.transaction(value,authority,compact,basis['basisId'])


def validate(root):
    root=Path(root);mixed.selection.layout(root,{'reference','receipt.json',*ACCEPT_CUTS,*SOURCE_CUTS},'mixed recovery')
    mixed.validate(root/'reference');rows=[]
    for accept,cuts in ((True,ACCEPT_CUTS),(False,SOURCE_CUTS)):
        initial,transition=plan(root,accept);steps=transition(initial,True);final=steps[-1][1]
        for cut in cuts:
            row=root/cut;mixed.selection.layout(row,{'first','second','final','events.json'},'mixed recovery case')
            at=next(i for i,(name,_) in enumerate(steps) if name==cut);first=steps[at][1]
            e.need(source.state(row/'first')==first,'mixed recovery first prefix')
            if accept:
                second_steps=transition(first,False) if owner.ACTIVE in first else [('ACCEPT_ACTIVE_FORCED',first)]
                stop=next(i for i,(name,_) in enumerate(second_steps) if name=='ACCEPT_ACTIVE_FORCED');second=second_steps[stop][1]
            else:second=first
            e.need(source.state(row/'second')==second,'mixed recovery second prefix')
            e.need(source.state(row/'final')==final,'mixed recovery final authority')
            events=source.load(row/'events.json',262144);e.exact(events,'first second resumed')
            select=acceptance.selected if accept else source.selected_events
            e.need(select(events['first'])==[name for name,_ in steps[:at+1]],'mixed recovery first force order')
            if accept:
                e.need(select(events['second'])==[name for name,_ in second_steps[:stop+1]],'mixed recovery second force order')
                cleanup=[name for name,_ in transition(second,False)];sealing=list(acceptance.accept.SEAL)
                expected=(cleanup+sealing if owner.ACTIVE in second else sealing+cleanup)+['ACCEPT_BEFORE_RETURN']*2
                explicit='EXPLICIT_ACCEPT_RETURNED';count=2
            else:
                e.need(select(events['second'])==[] and events['second'][-1]=='CONTEXT_SOURCE_PARENT_FORCED','mixed recovery second force order')
                expected=[name for name,_ in transition(second,False)];explicit='EXPLICIT_RETIRE_RETURNED';count=1
            e.need(select(events['resumed'])==expected,'mixed recovery resumed force order')
            e.need(events['resumed'].count('OPEN_RETURNED')==1 and events['resumed'].count(explicit)==count
                   and events['resumed'].index('OPEN_RETURNED')<events['resumed'].index(explicit),'mixed recovery explicit return boundary')
            rows.append(dict(cut=cut,node=1 if accept else 2,status='PASS',operation='accept' if accept else 'source-retirement'))
    e.need(source.load(root/'receipt.json')==dict(schema='gse-v53-context-mixed-recovery-v1',status='PASS',cases=rows,guardVariants=14,freshProcesses=False,runtimeEnabled=False),'mixed recovery receipt scope')
    return dict(status='PASS',cases=len(rows),interruptions=2*len(rows),originalFirst=True,physicalBytes=True,freshProcesses=False,powerLoss=False,runtimeEnabled=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'original':'mixed exact accepted: node-1', 'missing':'context selection mixed recovery inventory',
              'accept-first':'mixed recovery first prefix','accept-second':'mixed recovery second prefix','accept-final':'mixed recovery final authority',
              'source-first':'mixed recovery first prefix','source-second':'mixed recovery second prefix','source-final':'mixed recovery final authority',
              'first-force':'mixed recovery first force order','second-force':'mixed recovery second force order','resume-force':'mixed recovery resumed force order',
              'implicit-return':'mixed recovery explicit return boundary','scope':'mixed recovery receipt scope'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-mixed-recovery-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);row=moved/(SOURCE_CUTS[0] if name.startswith('source-') else ACCEPT_CUTS[0])
            if name=='original':(moved/'reference/accepted/node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(moved/SOURCE_CUTS[-1])
            elif name.startswith(('accept-','source-')):(row/name.split('-')[1]/'allocator.gsr').write_bytes(b'changed')
            elif name=='scope':
                path=moved/'receipt.json';value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            else:
                path=row/'events.json';value=source.load(path,262144)
                if name=='implicit-return':value['resumed'].remove('OPEN_RETURNED')
                else:
                    key={'first-force':'first','second-force':'second','resume-force':'resumed'}[name]
                    value[key].remove(acceptance.selected(value[key])[0])
                path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong mixed recovery negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted mixed recovery mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-mixed-recovery-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'mixed recovery portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
