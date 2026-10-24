"""Derive source-backed retirement from actual admitted covered-minority originals."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_minority_evidence as covered
from . import retirement_evidence as retirement

e=covered.e;c=covered.c;t=covered.t;selection=covered.selection
BINDING='retirement/images.json'
CUTS=tuple(v for v in retirement.CUTS[:25] if v not in ('RETIREMENT_IMAGE_WRITTEN','RETIREMENT_IMAGE_FORCED'))+(
    'RETIREMENT_BORROW_PREFIX_WRITTEN','RETIREMENT_BORROW_WRITTEN','RETIREMENT_BORROW_FORCED','RETIREMENT_BORROWED_IMAGES_FORCED','RETIREMENT_BORROW_CLEARED',
    'CONTEXT_SOURCE_MEMBER_FORCED','CONTEXT_SOURCE_DIRECTORY_FORCED','CONTEXT_SOURCE_PARENT_FORCED','RETIREMENT_BORROWED_SOURCE_FORCED')


def plan(root):
    required={'original-plan.gsbp','original-application.image','initial','observations.json','minority-entry.gsr','minority-payload.bin','selected-entry.gsr','selected-payload.bin','minority-accepted','before-install'}
    required|={f'round-{r}-{s}' for r in (1,3) for s in ('prepared','selected','installed','settled')}
    required|={'round-4-prepared','round-4-selected'}|{f'slot-1-{s}' for s in ('accepted','proved','certified','applied','published','settled')}
    required|={f'typed-1-node-{n}' for n in (2,3,4)};selection.layout(root/'reference',required,'source retirement reference')
    before,after,observed=covered.prefix(root/'reference',4,False);covered.observations(root/'reference',observed)
    initial=dict(after['node-1']);refs=[];copies={}
    for node in ('node-1','node-2','node-3'):
        prefix,members,packet=c.current(after[node]);manifest=after[node][prefix+'generation.gsr'];value=e.f.decode(manifest,'records','GENERATION')
        h=e.digest(manifest);copies[h]=dict(members,**{'generation.gsr':manifest});refs.append(dict(voter=node,generation=h,catalog=value['catalog'],snapshot=value['application']))
    prefix,members,packet=c.current(initial);cap=packet['capsule'];floor=e.f.encode('records','FLOOR',dict(root=cap['root'],node='node-1',cut=cap['cut'],sources=refs))
    initial.update({'floor-copies':None,'floor-copies/proposal.gsr':floor,'floor-copies/floor.gsr':floor})
    for h,files in copies.items():initial['floor-copies/'+h]=None;initial.update({'floor-copies/'+h+'/'+n:v for n,v in files.items()})
    e.need(c.inventory(root/'initial')==initial,'source retirement exact admitted floor')
    old_prefix,old,_=c.current(before['node-1']);old=dict(old,**{'generation.gsr':before['node-1'][old_prefix+'generation.gsr']})
    inventory=[dict(path=old_prefix+n,size=len(v),sha256=e.digest(v)) for n,v in sorted(old.items())]
    record=e.f.encode('records','RETIREMENT',dict(root=cap['root'],node='node-1',floor=e.digest(floor),selector=e.digest(initial['selector.gsr']),files=inventory))
    local=e.f.decode(initial['node.gsr'],'records','NODE')['identity'];basis=e.f.decode(members['basis.gsr'],'records','BASIS');source='sources/'+basis['basisId']+'/'
    packet=e.p.decode(initial[source+'source.gscp']);e.p.bind(packet,members['basis.gsr'])
    images=[row for row in inventory if row['path'].endswith('.image')]
    e.need(all(initial[source+row['sha256']+'.image']==old[row['sha256']+'.image'] for row in images),'source retirement exact pinned image')
    binding=e.f.canonical(dict(schema='gse-v53-retirement-source-images-v1',retirement=e.digest(record),floor=e.digest(floor),root=cap['root'],node='node-1',storage=local['storage'],
        selector=e.digest(initial['selector.gsr']),generation=e.digest(initial[prefix+'generation.gsr']),basis=e.digest(members['basis.gsr']),images=images))
    source_events=['CONTEXT_SOURCE_MEMBER_FORCED']*len([n for n in initial if n.startswith(source)])+['CONTEXT_SOURCE_DIRECTORY_FORCED','CONTEXT_SOURCE_PARENT_FORCED','RETIREMENT_BORROWED_SOURCE_FORCED','RETIREMENT_BORROWED_IMAGES_FORCED']
    return initial,old,old_prefix,record,binding,source_events


def transaction(initial,old,prefix,record,binding,source_events,cut=None):
    state=dict(initial);events=[]
    class Stop(Exception):pass
    def event(name):
        events.append(name)
        if name==cut:raise Stop()
    def write(path,raw,label):state[path]=raw;event(label+'_WRITTEN');event(label+'_FORCED')
    def directory(path,label):state[path]=None;event(label)
    def remove(path,label):state.pop(path);event(label)
    def reseal():
        for name in source_events:event(name)
    try:
        for name in covered.OPEN+covered.SEAL:event(name)
        if prefix[:-1] not in state and 'retirement/retirement.gsr' not in state:
            if 'retirement' in state:remove('retirement','RETIREMENT_CLEARED')
            e.need(cut is None,'source retirement interruption not reached');return state,events
        if 'retirement/retirement.gsr' not in state:
            event('RETIREMENT_OLD_FILES_FORCED');event('RETIREMENT_RESERVED');directory('retirement','RETIREMENT_CREATED')
            offset=len(state.get(BINDING,b''));state[BINDING]=binding[:offset+(len(binding)-offset)//2];event('RETIREMENT_BORROW_PREFIX_WRITTEN');write(BINDING,binding,'RETIREMENT_BORROW')
            write('retirement/proposal.gsr',record,'RETIREMENT_PROPOSAL');directory('retirement/source','RETIREMENT_SOURCE_CREATED')
            write('retirement/source/generation.gsr',old['generation.gsr'],'RETIREMENT_MANIFEST')
            for name,raw in sorted(old.items()):
                if name!='generation.gsr' and not name.endswith('.image'):write('retirement/source/'+name,raw,'RETIREMENT_MEMBER')
            event('RETIREMENT_SOURCE_FORCED');reseal();write('retirement/retirement.gsr',record,'RETIREMENT_AUTHORITY');event('RETIREMENT_PARENT_FORCED')
        else:
            if BINDING in state:reseal()
            event('RETIREMENT_AUTHORITY_RESEALED')
        if prefix[:-1] in state:
            event('RETIREMENT_DELETE_VALIDATED')
            for name in sorted(old):
                if prefix+name in state:remove(prefix+name,'RETIREMENT_FILE_DELETED')
            remove(prefix[:-1],'RETIREMENT_DIRECTORY_DELETED')
        for name in sorted(old):
            if 'retirement/source/'+name in state:remove('retirement/source/'+name,'RETIREMENT_SAVED_FILE_DELETED')
        if 'retirement/source' in state:remove('retirement/source','RETIREMENT_SAVED_DIRECTORY_DELETED')
        if 'retirement/proposal.gsr' in state:remove('retirement/proposal.gsr','RETIREMENT_PROPOSAL_CLEARED')
        if BINDING in state:remove(BINDING,'RETIREMENT_BORROW_CLEARED')
        remove('retirement/retirement.gsr','RETIREMENT_AUTHORITY_CLEARED');remove('retirement','RETIREMENT_CLEARED');event('RETIREMENT_BEFORE_RETURN')
    except Stop:return state,events
    e.need(cut is None,'source retirement interruption not reached');return state,events


def validate(root):
    root=Path(root);selection.layout(root,{'reference','initial','receipt.json',*CUTS},'source retirement interruptions')
    initial,old,prefix,record,binding,sealing=plan(root);rows=[]
    for cut in CUTS:
        path=root/cut;selection.layout(path,{'first','second','final','events.json'},'source retirement case');traces=e.parse(t.plans.read(path/'events.json',e.MIB));e.exact(traces,'first second final')
        state,events=transaction(initial,old,prefix,record,binding,sealing,cut)
        e.need(c.inventory(path/'first')==state,'source retirement first exact prefix');e.need(traces['first']==events,'source retirement first force order')
        repeat='retirement/retirement.gsr' in state
        if repeat:state,events=transaction(state,old,prefix,record,binding,sealing,'RETIREMENT_AUTHORITY_RESEALED')
        else:events=[]
        e.need(c.inventory(path/'second')==state,'source retirement second exact prefix');e.need(traces['second']==events,'source retirement second force order')
        state,events=transaction(state,old,prefix,record,binding,sealing)
        e.need(c.inventory(path/'final')==state,'source retirement final exact authority');e.need(traces['final']==events,'source retirement completion force order')
        e.need(all(v==state[k] for k,v in initial.items() if k in state) and not any(n.startswith(prefix) for n in state),'source retirement protected originals')
        for phase in ('first','second','final'):
            files=c.inventory(path/phase);images=sum(n.endswith('.image') for n in files);sources=sum(n.startswith(('sources/','floor-copies/')) and n.count('/')==1 and v is None for n,v in files.items())+int(BINDING in files or 'retirement/source' in files)
            e.need(images<=7 and sources<=6,'source retirement physical capacity')
        rows.append(dict(cut=cut,secondInterrupted=repeat,status='PASS'))
    e.need(e.f.canonical(e.parse(t.plans.read(root/'receipt.json',65536)))==e.f.canonical(dict(status='PASS',cases=rows,maximumImages=7,freshProcesses=False)),'source retirement exact receipt')
    return dict(status='PASS',cases=len(CUTS),publicBootstrap=True,freshProcesses=False,maximumImages=7,maximumSources=6,maximalBytes=False)


VARIANTS={
    'original-vote':'admitted exact minority-accepted: node-1',
    'floor':'source retirement exact admitted floor',
    'missing-case':'context selection source retirement interruptions inventory',
    'binding':'source retirement first exact prefix',
    'backing-source':'source retirement first exact prefix',
    'early-deletion':'source retirement first exact prefix',
    'lost-second-authority':'source retirement second exact prefix',
    'final-old-image':'source retirement final exact authority',
    'source-force':'source retirement first force order',
    'second-force':'source retirement second force order',
    'false-return':'source retirement completion force order',
    'receipt-flag':'source retirement exact receipt',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-retirement-source-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'RETIREMENT_PARENT_FORCED'
            if name=='original-vote':(moved/'reference/minority-accepted/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name=='floor':(moved/'initial/floor-copies/floor.gsr').write_bytes(b'changed')
            elif name=='missing-case':shutil.rmtree(case)
            elif name=='binding':(case/'first'/BINDING).write_bytes(b'{}')
            elif name=='backing-source':next((case/'first/sources').glob('*/source.gscp')).unlink()
            elif name=='early-deletion':
                active=c.current(c.inventory(case/'first'))[0];old='b' if active=='generations/a/' else 'a';next((case/'first/generations'/old).glob('*.image')).unlink()
            elif name=='lost-second-authority':(case/'second/retirement/retirement.gsr').unlink()
            elif name=='final-old-image':
                active=c.current(c.inventory(case/'final'))[0];old='b' if active=='generations/a/' else 'a';(case/'final/generations'/old).mkdir()
            elif name=='receipt-flag':
                path=moved/'receipt.json';value=e.parse(path.read_bytes());value['freshProcesses']=0;path.write_bytes(e.f.canonical(value))
            else:
                path=case/'events.json';rows=e.parse(path.read_bytes())
                if name=='source-force':rows['first'].remove('RETIREMENT_BORROWED_SOURCE_FORCED')
                elif name=='second-force':rows['second'].remove('RETIREMENT_AUTHORITY_RESEALED')
                else:rows['final'].append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong source retirement rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted source retirement mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-retirement-source-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'source retirement portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
