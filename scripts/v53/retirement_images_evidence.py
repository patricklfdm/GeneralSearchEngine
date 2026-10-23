"""Independent physical replay of floor-image borrowing; historical edges stay conditional."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import retirement_evidence as old
from .membership_model import need

c,d,g,p,s = old.c,old.d,old.g,old.p,old.s
BINDING='retirement/images.json'
CUTS=('RETIREMENT_CREATED','RETIREMENT_BORROW_PREFIX_WRITTEN','RETIREMENT_BORROW_WRITTEN','RETIREMENT_BORROW_FORCED',
      'RETIREMENT_SOURCE_FORCED','RETIREMENT_BORROWED_IMAGES_FORCED','RETIREMENT_AUTHORITY_WRITTEN','RETIREMENT_PARENT_FORCED',
      'RETIREMENT_FILE_DELETED@2','RETIREMENT_DIRECTORY_DELETED','RETIREMENT_SAVED_FILE_DELETED@2',
      'RETIREMENT_SAVED_DIRECTORY_DELETED','RETIREMENT_PROPOSAL_CLEARED','RETIREMENT_BORROW_CLEARED','RETIREMENT_AUTHORITY_CLEARED')


def cases():
    rows=[(size,through,'clean','none') for size in (3,4,5) for through in (0,6,7)]
    rows += [(5,0,mode,cut) for mode in ('halt','kill') for cut in CUTS]
    rows += [(5,through,mode,cut) for through in (6,7) for mode in ('halt','kill')
             for cut in ('RETIREMENT_BORROWED_IMAGES_FORCED','RETIREMENT_FILE_DELETED@2')]
    rows += [(5,through,mode,'RETIREMENT_AUTHORITY_RESEALED') for through in (0,6,7) for mode in ('repeat-halt','repeat-kill')]
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut) for size,through,mode,cut in rows]


def plan(directory,case):
    directory=Path(directory)
    baseline,original,record,floor,selector=old.plan(directory,case,'baseline')
    values,rows=g.state(directory/'initial',case['size'],{'sources','generations','selector.gsr','floor-copies'})
    before=g.journal(g.read(directory/'baseline/grants.gsr',g.LIMIT),values['root.gsr'][16:48].hex(),'node-1')
    need(rows[:4]==before and [row[0] for row in rows]==['PROMISE','PROMISE','BASIS','SELECTED','PROMISE','BASIS'], 'image retirement extra original grant')
    promise,basis=rows[-2:];b=basis[2]
    need(b['ballot']==dict(before[2][2]['ballot'],counter=101) and promise[2]['ballot']==b['ballot']
         and promise[2]['basisId']==b['basisId'] and b['basisId']!=before[2][2]['basisId'] and b['accepted'] is None
         and b['cut']==before[2][2]['cut'] and b['voter']=='node-1','image retirement next source binding')
    packet=p.decode(original['source.gscp']);p.bind(packet,basis[1])
    initial=dict(baseline);initial['grants.gsr']=old.entry(b''.join(row[1] for row in rows));name='sources/'+b['basisId']
    initial[name]=dict(directory=True)
    initial.update({name+'/'+n:old.entry(original[n]) for n in ['source.gscp',*[h+'.image' for h in packet['images']]]})
    old.snapshot(directory/'initial',initial)
    definition=g.f.decode(values['root.gsr'],'records','ROOT');authority=g.f.decode(record,'records','RETIREMENT')
    bound=dict(schema='gse-v53-retirement-floor-images-v1',retirement=c.sha(record),floor=c.sha(floor),root=authority['root'],
               node='node-1',storage=definition['initial'][0]['storage'],selector=c.sha(selector),
               images=[dict(row,generation=c.sha(original['generation.gsr'])) for row in authority['files'] if row['path'].endswith('.image')])
    return initial,original,record,floor,selector,g.f.canonical(bound)


def transaction(state,original,record,binding,borrow):
    if not borrow:return old.transaction(state,original,record)
    state=dict(state);steps=[]
    def event(name):steps.append((name,dict(state)))
    def directory(name,point):state[name]=dict(directory=True);event(point)
    def write(name,raw,point):state[name]=old.entry(raw);event(point+'_WRITTEN');event(point+'_FORCED')
    def remove(name,point):state.pop(name);event(point)
    if 'generations/a' not in state and 'retirement/retirement.gsr' not in state:
        if 'retirement' in state:remove('retirement','RETIREMENT_CLEARED')
        return steps,None
    if 'retirement/retirement.gsr' not in state:
        event('RETIREMENT_OLD_FILES_FORCED');event('RETIREMENT_RESERVED');directory('retirement','RETIREMENT_CREATED')
        offset=state.get(BINDING,{}).get('bytes',0);middle=offset+(len(binding)-offset)//2
        state[BINDING]=old.entry(binding[:middle]);event('RETIREMENT_BORROW_PREFIX_WRITTEN');write(BINDING,binding,'RETIREMENT_BORROW')
        write('retirement/proposal.gsr',record,'RETIREMENT_PROPOSAL');directory('retirement/source','RETIREMENT_SOURCE_CREATED')
        write('retirement/source/generation.gsr',original['generation.gsr'],'RETIREMENT_MANIFEST')
        for name,raw in sorted(original.items()):
            if name!='generation.gsr' and not name.endswith('.image'):write('retirement/source/'+name,raw,'RETIREMENT_MEMBER')
        event('RETIREMENT_SOURCE_FORCED');event('RETIREMENT_BORROWED_IMAGES_FORCED')
        write('retirement/retirement.gsr',record,'RETIREMENT_AUTHORITY');event('RETIREMENT_PARENT_FORCED')
    else:
        if BINDING in state:event('RETIREMENT_BORROWED_IMAGES_FORCED')
        event('RETIREMENT_AUTHORITY_RESEALED')
    if 'generations/a' in state:
        event('RETIREMENT_DELETE_VALIDATED')
        for name in sorted(original):
            if 'generations/a/'+name in state:remove('generations/a/'+name,'RETIREMENT_FILE_DELETED')
        remove('generations/a','RETIREMENT_DIRECTORY_DELETED')
    for name in sorted(original):
        if 'retirement/source/'+name in state:remove('retirement/source/'+name,'RETIREMENT_SAVED_FILE_DELETED')
    if 'retirement/source' in state:remove('retirement/source','RETIREMENT_SAVED_DIRECTORY_DELETED')
    if 'retirement/proposal.gsr' in state:remove('retirement/proposal.gsr','RETIREMENT_PROPOSAL_CLEARED')
    if BINDING in state:remove(BINDING,'RETIREMENT_BORROW_CLEARED')
    remove('retirement/retirement.gsr','RETIREMENT_AUTHORITY_CLEARED');remove('retirement','RETIREMENT_CLEARED');event('RETIREMENT_BEFORE_RETURN')
    return steps,c.sha(record)


def snapshot(path,expected):
    old.snapshot(path,expected)
    sources=sum(n.startswith('sources/') and n.count('/')==1 and 'directory' in value for n,value in expected.items())
    copies=sum(n.startswith('floor-copies/') and n.count('/')==1 and 'directory' in value for n,value in expected.items())
    need(sources+copies+int('retirement/source' in expected or BINDING in expected)<=6,'image retirement reference metadata owner count')
    saved=sum(value['bytes'] for n,value in expected.items() if (n.startswith('retirement/source/') and not n.endswith('.image')) or n==BINDING)
    need(saved<=32*1024*1024,'image retirement combined saved metadata bound')


def validate_case(directory,case):
    directory=Path(directory);receipt=g.a.load(directory/'case.json');need(receipt['case']==case,'image retirement case')
    need(receipt['execution']=='private-floor-image-retirement' and all(receipt[k] is False for k in ('runtimeEnabled','historicalOwnershipVerified','networkAck')), 'image retirement scope')
    initial,original,authority,floor,selector,binding=plan(directory,case);d.process(directory,receipt,'init','init',0)
    processes={'init'};snapshots={'initial','final','authority','baseline'};peak=[0,0]
    def call(label,state,mode='none',cut='none'):
        steps,returned=transaction(state,original,authority,binding,case['size']>3);fault=mode!='none'
        position=old.cut_position(steps,cut) if fault else len(steps)-1
        rows=d.process(directory,receipt,label,'retire',73 if mode=='halt' else -9 if mode=='kill' else 0)
        expected=[dict(event=name) for name in c.OPEN]+[dict(event=name) for name,_ in steps[:position+1]]
        if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=cut))
        need((rows if fault else rows[:-1])==expected,'image retirement exact force/crash order')
        if not fault:old.result(rows,floor,selector,returned)
        for _,view in steps[:position+1]:
            peak[0]=max(peak[0],sum(n.endswith('.image') for n in view))
            sources=sum(n.startswith('sources/') and n.count('/')==1 and 'directory' in v for n,v in view.items())
            copies=sum(n.startswith('floor-copies/') and n.count('/')==1 and 'directory' in v for n,v in view.items())
            peak[1]=max(peak[1],sources+copies+int('retirement/source' in view or BINDING in view))
        processes.add(label);return steps[position][1] if steps else state
    def state(name,expected):snapshots.add(name);snapshot(directory/name,expected)
    if case['mode']=='clean':
        final=call('first',initial);state('original',final);state('duplicate',call('duplicate',final))
    else:
        repeated=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
        crash=call('fault',initial,'halt' if repeated else mode,'RETIREMENT_FILE_DELETED@2' if repeated else case['cut']);state('crash',crash)
        if repeated:crash=call('recovery-fault',crash,mode,case['cut']);state('recovery-crash',crash)
        final=call('resume',crash);state('resumed',final)
    rows=d.process(directory,receipt,'inspect','inspect',0);need(rows[:-1]==[dict(event=name) for name in c.OPEN],'image retirement inspect force order')
    old.result(rows,floor,selector,None);processes.add('inspect');snapshot(directory/'final',final);snapshot(directory/'authority',final)
    need(set(receipt['processes'])==processes and {v.name for v in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+suffix for n in processes for suffix in ('.stdout','.stderr')},'image retirement exact case inventory')
    need(peak[0]<=7 and peak[1]<=6,'image retirement physical peak')
    return dict(case=case['name'],status='PASS',borrowed=case['size']>3,physicalImagePeak=peak[0],physicalSourcePeak=peak[1],runtimeEnabled=False,networkAck=False)


def validate(directory):
    directory=Path(directory);wanted=cases();need({v.name for v in directory.iterdir()}=={v['name'] for v in wanted},'image retirement complete matrix')
    return dict(status='PASS',execution='private-floor-image-retirement',cases=[validate_case(directory/case['name'],case) for case in wanted],runtimeEnabled=False,powerLoss=False)


def qualify(directory):
    directory=Path(directory);result=validate(directory);selected=next(case for case in cases() if case['size']==5 and case['through']==0 and case['mode']=='halt' and case['cut']=='RETIREMENT_FILE_DELETED@2')
    mutations=('missing-binding','truncated-binding','foreign-floor','foreign-generation','copied-backup-image','missing-saved-packet',
               'changed-floor-image','changed-live-selector','changed-original-source','missing-borrow-force','false-exit-code',
               'changed-retirement','final-binding-leak','final-old-generation','linked-binding')
    negatives=[]
    for mutation in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-retirement-image-negative-') as temporary:
            root=Path(temporary)/selected['name'];shutil.copytree(directory/selected['name'],root);binding=root/'crash'/BINDING
            if mutation=='missing-binding':binding.unlink()
            elif mutation=='truncated-binding':binding.write_bytes(binding.read_bytes()[:-1])
            elif mutation in ('foreign-floor','foreign-generation'):
                value=json.loads(binding.read_bytes())
                if mutation=='foreign-floor':value['floor']='0'*64
                else:value['images'][0]['generation']='0'*64
                binding.write_bytes(g.f.canonical(value))
            elif mutation=='copied-backup-image':
                image=next((root/'initial/generations/a').glob('*.image'));shutil.copyfile(image,root/'crash/retirement/source'/image.name)
            elif mutation=='missing-saved-packet':(root/'crash/retirement/source/source.gscp').unlink()
            elif mutation in ('changed-floor-image','changed-original-source','changed-retirement','changed-live-selector'):
                if mutation=='changed-floor-image':path=next((root/'crash/floor-copies').glob('*/*.image'))
                elif mutation=='changed-original-source':path=next((root/'crash/sources').glob('*/source.gscp'))
                else:path=root/'crash'/('retirement/retirement.gsr' if mutation=='changed-retirement' else 'selector.gsr')
                raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif mutation=='missing-borrow-force':
                path=root/'resume.stdout';path.write_bytes(b'\n'.join(line for line in path.read_bytes().splitlines() if b'RETIREMENT_BORROWED_IMAGES_FORCED' not in line)+b'\n')
            elif mutation=='false-exit-code':
                path=root/'case.json';value=json.loads(path.read_bytes());value['processes']['fault']['exitCode']=0;path.write_text(json.dumps(value))
            elif mutation=='final-binding-leak':
                (root/'final/retirement').mkdir();shutil.copyfile(binding,root/'final'/BINDING)
            elif mutation=='final-old-generation':shutil.copytree(root/'initial/generations/a',root/'final/generations/a')
            else:binding.unlink();binding.symlink_to((directory/selected['name']/'crash'/BINDING).resolve())
            try:validate_case(root,selected)
            except ValueError as error:
                reason={'missing-borrow-force':'image retirement exact force/crash order','false-exit-code':'selection process outcome',
                        'linked-binding':'source file type'}.get(mutation,'retirement exact physical snapshot')
                need(str(error)==reason,'unrelated image retirement negative: '+mutation+': '+str(error))
                negatives.append(dict(case=mutation,status='REJECT',reason=reason))
            else:raise ValueError('accepted image-retirement mutation: '+mutation)
    with tempfile.TemporaryDirectory(prefix='v53-retirement-image-portable-') as temporary:
        root=Path(temporary)/'physical';shutil.copytree(directory,root);need(validate(root)==result,'image retirement portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args();print(json.dumps(qualify(args.directory),sort_keys=True))
