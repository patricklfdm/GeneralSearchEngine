"""Physical local SELECTED replay. Remote source ownership remains fixture evidence."""
import json
from pathlib import Path
from . import current_generation_evidence as c
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need

CUTS=('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{str(tail).lower()}-{mode}-{cut.lower()}',size=size,tail=tail,mode=mode,cut=cut)
            for size in (3,4,5) for tail in (False,True) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def inputs(directory,size,root):
    directory=Path(directory)/'inputs';result={};names=set();images={};identities=set()
    need(directory.is_dir() and not directory.is_symlink(),'selection input directory')
    for ballot in (20,21):
        for node in range(2,size+1):
            name=f'c{ballot}-node-{node}';names|={name+'.basis',name+'.gscp'}
            raw=g.read(directory/(name+'.basis'),16384);basis=g.f.decode(raw,'records','BASIS',root)
            data=p.decode(g.read(directory/(name+'.gscp'),g.LIMIT));p.bind(data,raw)
            need(basis['voter']==f'node-{node}' and basis['ballot']['counter']==ballot,'selection remote fixture identity')
            need(basis['basisId'] not in identities,'selection reused remote basis identity');identities.add(basis['basisId'])
            result[ballot,node]=(raw,basis,data);images.update(data['images'])
    names|={h+'.image' for h in images};need({v.name for v in directory.iterdir()}==names,'selection input inventory')
    for h,size in images.items():
        raw=g.read(directory/(h+'.image'),size);need(len(raw)==size and c.sha(raw)==h,'selection input image')
    return result


def decision(rows,source_inputs,size,ballot,alternate):
    selection=next(row for row in rows if row[0]=='SELECTED' and row[2]['ballot']['counter']==ballot)
    local=next(row for row in rows if row[0]=='BASIS' and row[2]['ballot']['counter']==ballot)
    start=3 if alternate else 2
    sources=[(local[1],local[2],None)]+[source_inputs[ballot,node] for node in range(start,start+size//2)]
    expected=[dict(voter=b['voter'],basisId=b['basisId'],basisDigest=c.sha(raw)) for raw,b,_ in sources]
    need(selection[2]['sources']==expected,'selection source references')
    need(all(b['cut']==local[2]['cut'] and b['ballot']==local[2]['ballot'] for _,b,_ in sources),'selection source cut/ballot')
    # The fixture freezes equal certified cuts. Only the highest original next-slot ACCEPT wins.
    need(selection[2]['cut']==local[2]['cut'],'selection proven cut')
    return selection,local,sources


def choice(selection,sources,authority):
    chosen=None
    for _,basis,data in sources:
        if data is None:data=p.decode(g.read(authority/'sources'/basis['basisId']/'source.gscp',g.LIMIT))
        if basis['accepted'] is None:continue
        accept=g.f.decode(data['objects'][basis['accepted']],'records','ACCEPT',basis['root'])
        if chosen is None or g.order(accept['ballot'])>g.order(chosen['ballot']):chosen=accept
        elif g.order(accept['ballot'])==g.order(chosen['ballot']):need(accept['entry']==chosen['entry'],'conflicting selection input tails')
    need(selection[2]['nextEntry']==(None if chosen is None else chosen['entry']),'selection recovered choice')


def process(directory,record,label,command,code):
    need(type(record['processes'][label]['exitCode']) is int and record['processes'][label]['exitCode']==code,'selection process outcome')
    rows=[json.loads(line) for line in g.read(directory/(label+'.stdout'),65536).splitlines()]
    need(g.read(directory/(label+'.stderr'),65536)==b'','selection stderr')
    if code in (0,2):
        need(rows and rows[-1].get('status')==('PASS' if code==0 else 'FAIL') and rows[-1].get('command')==command
             and not any('status' in row for row in rows[:-1]),'selection terminal result')
    else:need(not any('status' in row for row in rows),'selection result after crash')
    return rows


def result(stdout,selected):
    value=selected[2];row=stdout[-1]
    need(row['selection']==c.sha(selected[1]) and all(row[k]==value[k] for k in ('cut','sources','nextEntry'))
         and row['counter']==value['ballot']['counter'] and row['installationAck'] is False,'selection returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'selection case identity')
    need(record['execution']=='private-durable-selection' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False
         and record['installationAck'] is False,'selection runtime scope')
    size,mode,cut=case['size'],case['mode'],case['cut'];clean=mode=='clean'
    initial,initial_rows,generation,_=c.current(directory/'initial',size)
    need([k for k,_,_ in initial_rows]==['PROMISE','PROMISE','BASIS'] and initial_rows[-1][2]['ballot']['counter']==20,'selection initial grant')
    need((generation['ownedTail'] is not None)==case['tail'],'selection initial tail')
    source_inputs=inputs(directory,size,generation['root']);process(directory,record,'init','init',0)
    original_name='original' if clean else 'resumed'
    original,rows,_,_=c.current(directory/original_name,size)
    need([k for k,_,_ in rows]==['PROMISE','PROMISE','BASIS','SELECTED'] and rows[:3]==initial_rows,'selection first history')
    selected,local,sources=decision(rows,source_inputs,size,20,False);choice(selected,sources,directory/original_name)
    if clean:
        stdout=process(directory,record,'first','select',0);need(g.events(stdout)==list(c.OPEN+CUTS),'selection force order');result(stdout,selected)
        duplicate,again,_,_=c.current(directory/'duplicate',size);need(duplicate==original and again==rows,'selection duplicate changed')
        stdout=process(directory,record,'duplicate','select',0);need(g.events(stdout)==list(c.OPEN),'selection duplicate writes');result(stdout,selected)
    else:
        stdout=process(directory,record,'fault','select',73 if mode=='halt' else -9)
        need(g.events(stdout)==list(c.OPEN+CUTS[:CUTS.index(cut)+1])+(['AWAITING_KILL'] if mode=='kill' else []),'selection crash cut')
        if mode=='kill':need(stdout[-1]==dict(event='AWAITING_KILL',cut=cut),'selection external kill handshake')
        crash,before,_,_=c.current(directory/'crash',size);written=cut!='SELECTED_BEFORE_WRITE'
        need(before==(rows if written else initial_rows),'selection crash journal')
        need(crash==(original if written else initial),'selection crash bytes')
        stdout=process(directory,record,'resume','select',0);need(g.events(stdout)==list(c.OPEN+(() if written else CUTS)),'selection recovery force order');result(stdout,selected)
    conflict=process(directory,record,'conflict','conflict',2)
    need(conflict[-1]['reason']=='selection already fixed; fresh ballot required' and g.events(conflict)==list(c.OPEN),'selection conflict refusal')
    need(c.current(directory/'conflict',size)==c.current(directory/original_name,size),'selection conflict rewrote authority')
    final,final_rows,_,_=c.current(directory/'final',size)
    need(final_rows[:4]==rows and [k for k,_,_ in final_rows[4:]]==['PROMISE','BASIS','SELECTED'],'selection higher ballot history')
    later,_,sources=decision(final_rows,source_inputs,size,21,True);choice(later,sources,directory/'final')
    stdout=process(directory,record,'next','advance',0);need(g.events(stdout)==list(c.ORDER+CUTS),'selection fresh ballot force order');result(stdout,later)
    need(c.current(directory/'authority',size)==c.current(directory/'final',size),'selection final authority')
    snapshots={'initial','original','duplicate','conflict','final','authority'} if clean else {'initial','crash','resumed','conflict','final','authority'}
    processes={'init','first','duplicate','conflict','next'} if clean else {'init','fault','resume','conflict','next'}
    need(set(record['processes'])==processes and {p.name for p in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'selection case inventory')
    for snapshot in snapshots:
        files,_,_,_=c.current(directory/snapshot,size)
        need(all(files.get(n)==v for n,v in initial.items() if n!='grants.gsr'),'selection changed original generation/source')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,installationAck=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'selection complete cases')
    return dict(status='PASS',execution='private-durable-selection',runtimeEnabled=False,installationAck=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
