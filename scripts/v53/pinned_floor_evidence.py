"""Conditional four-original floor: exact local pin, retirement and release replay.

The seed's historical certificates are fixture inputs, not native ownership.
This reader qualifies the observed physical lifecycle, not process death,
power loss, a network quorum or the complete Phase 3 history.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import floor_evidence as floor
from . import retirement_images_evidence as retirement
from . import source_release_evidence as source_release
from . import selected_sources_evidence as selected
from . import deferred_grant_process_evidence as original
from .membership_model import need

c,g,p,s=retirement.c,retirement.g,retirement.p,retirement.s
f=g.f
OWNERS=('node-1','node-2','node-5','node-6')
PHASES=('open','floor','retire','compact','release','cold')
PIN='floor-copies/local.gsr'


def members(path):
    inventory=s.inventory(path)
    need(all('directory' not in row for row in inventory.values()),'pinned generation nested inventory')
    return {n:g.read(Path(path)/n,64*1024*1024) for n in inventory}


def generation(path,root,node,rows):
    files=members(path);raw=files['generation.gsr'];value=f.decode(raw,'records','GENERATION',root)
    need(value['node']==node and value['generation']==Path(path).name and value['cut']['index']==6
         and value['ownedTail'] is None,'pinned original generation profile')
    need(value['files']==[dict(path=n,size=len(v),sha256=c.sha(v)) for n,v in sorted(files.items()) if n!='generation.gsr'],
         'pinned original manifest inventory')
    data=p.decode(files['source.gscp']);cap=data['capsule']
    need(all(value[k]==cap[k] for k in ('root','cut','catalog','application')) and value['capsule']==c.sha(data['capsuleBytes']),
         'pinned original capsule')
    names={'generation.gsr','source.gscp','promise.gsr'}|{h+'.image' for h in data['images']}
    for kind,key,name in (('PROMISE','promise','promise.gsr'),('BASIS','basis','basis.gsr'),('SELECTED','selection','selected.gsr')):
        if value[key] is not None:
            names.add(name);need(any(k==kind and frame==files[name] for k,frame,_ in rows) and c.sha(files[name])==value[key],
                                 'pinned original journal binding')
    if value['selection'] is not None:
        selection=f.decode(files['selected.gsr'],'records','SELECTED',root)
        need(selection['cut']==value['cut'] and selection['nextEntry'] is None,'pinned selected cut')
        names.add(selected.FILE);selected.cuts(files[selected.FILE],selection)
    need(set(files)==names and len(data['images'])==1,'pinned original member inventory')
    need(all(original.info(files[h+'.image'])==dict(bytes=n,sha256=h) for h,n in data['images'].items()),'pinned original image')
    return files,value,data


def seed(root):
    need({v.name for v in (root/'seed').iterdir()}==set(OWNERS),'pinned seed owners')
    local=root/'seed/node-1';initial,rows=s.state(local,5,extra_names={'selector.gsr','generations'})
    need({v.name for v in (local/'generations').iterdir()}=={'a','b'},'pinned exact seed generations')
    need([v[0] for v in rows]==['PROMISE','PROMISE','BASIS','SELECTED','PROMISE','BASIS','SELECTED']
         and [v[2]['ballot']['counter'] for v in rows]==[10,20,20,20,21,21,21],'pinned seed two installations')
    root_raw=g.read(local/'root.gsr',16384);identity=root_raw[16:48].hex()
    selector=g.read(local/'selector.gsr',4096);chosen=f.decode(selector,'records','SELECTOR',identity)
    files,value,data=generation(local/'generations/a',identity,'node-1',rows)
    need(chosen==dict(root=identity,node='node-1',generation='a',digest=c.sha(files['generation.gsr']))
         and value['selection']==c.sha(rows[-1][1]),'pinned original selector')
    old,old_value,_=generation(local/'generations/b',identity,'node-1',rows)
    need(old_value['selection']==c.sha(rows[3][1]) and old_value['cut']==value['cut'],'pinned original predecessor')
    copies={c.sha(files['generation.gsr']):files};refs=[]
    for node in OWNERS:
        owner=root/'seed'/node
        need(g.read(owner/'root.gsr',16384)==root_raw,'pinned peer root')
        node_value=f.decode(g.read(owner/'node.gsr',4096),'records','NODE',identity)
        need(node_value['identity']['node']==node,'pinned peer identity')
        if node=='node-1':peer,manifest=files,value
        else:
            peer_rows=g.journal(g.read(owner/'grants.gsr',g.LIMIT),identity,node)
            need(len(peer_rows)==1 and peer_rows[0]==rows[0],'pinned peer original promise')
            peer,manifest,packet=generation(owner/'generations/a',identity,node,peer_rows)
            need(packet['objects'].get(c.sha(root_raw))==root_raw,'pinned peer original root')
            need(g.read(owner/'selector.gsr',4096)==f.encode('records','SELECTOR',dict(root=identity,node=node,generation='a',digest=c.sha(peer['generation.gsr']))),
                 'pinned peer original selector')
            expected={n:initial[n] for n in ('root.gsr','genesis.gsr','replica.lock','sources','generations')}
            expected.update({'node.gsr':original.info(f.encode('records','NODE',node_value)),
                'allocator.gsr':original.info(f.encode('records','ALLOCATOR',dict(root=identity,node=node,counter=0))),
                'grants.gsr':original.info(rows[0][1]),'generations/a':dict(directory=True),
                'selector.gsr':original.info(f.encode('records','SELECTOR',dict(root=identity,node=node,generation='a',digest=c.sha(peer['generation.gsr']))))})
            expected.update({'generations/a/'+n:original.info(v) for n,v in peer.items()})
            need(s.inventory(owner)==expected,'pinned peer exact inventory')
        need(manifest['cut']==value['cut'] and manifest['application']==value['application'] and manifest['catalog']==value['catalog'],
             'pinned peer original covering cut')
        digest=c.sha(peer['generation.gsr']);copies[digest]=peer
        refs.append(dict(voter=node,generation=digest,catalog=manifest['catalog'],snapshot=manifest['application']))
    view=value['cut']['view'];voters=set(OWNERS)
    need(all(len(voters&set(view[k]))>len(view[k])//2 for k in ('old','new')),'pinned joint original quorum')
    raw=f.encode('records','FLOOR',dict(root=identity,node='node-1',cut=value['cut'],sources=refs))
    need(sum(n.endswith('.image') for n in initial)==4,'pinned initial physical images')
    return initial,rows,files,old,copies,raw,selector


def floor_plan(copies,raw,selector):
    own=f.decode(selector,'records','SELECTOR')['digest']
    need(own in copies,'pinned local original absent')
    events,files,_,dirs=floor.transaction({h:v for h,v in copies.items() if h!=own},raw)
    names=[r['event'] for r in events]
    names[2:2]=['FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED']
    return names,dict(files,**{PIN:selector}),dirs


def release_events(state):
    names=['FLOOR_RELEASE_AUTHORITY_CREATED','FLOOR_RELEASE_AUTHORITY_WRITTEN','FLOOR_RELEASE_AUTHORITY_FORCED','FLOOR_RELEASE_PARENT_FORCED',
           'FLOOR_RELEASE_RELINQUISHED']
    names+=['FLOOR_RELEASE_FILE_DELETED' for n in sorted(state) if n.startswith('floor-copies/') and n.count('/')==2]
    names+=['FLOOR_RELEASE_COPY_DELETED' for n,v in sorted(state.items()) if n.startswith('floor-copies/') and 'directory' in v]
    return names+['FLOOR_RELEASE_PROPOSAL_CLEARED','FLOOR_RELEASE_LOCAL_CLEARED','FLOOR_RELEASE_AUTHORITY_CLEARED','FLOOR_RELEASE_CLEARED','FLOOR_RELEASE_BEFORE_RETURN']


def derive(root):
    """Project from original seed bytes; never use a produced snapshot as the plan."""
    root=Path(root)
    initial,rows,local,old,copies,raw,selector=seed(root)
    names,files,dirs=floor_plan(copies,raw,selector)
    pinned=dict(initial,**{n:dict(directory=True) for n in dirs},**{n:original.info(v) for n,v in files.items()})
    expected={'pinned':pinned}
    record=f.encode('records','RETIREMENT',dict(root=f.decode(raw,'records','FLOOR')['root'],node='node-1',floor=c.sha(raw),selector=c.sha(selector),
        files=[dict(path='generations/b/'+n,size=len(v),sha256=c.sha(v)) for n,v in sorted(old.items())]))
    node=f.decode(g.read(root/'seed/node-1/node.gsr',4096),'records','NODE')['identity']
    binding=f.canonical(dict(schema='gse-v53-retirement-floor-images-v1',retirement=c.sha(record),floor=c.sha(raw),root=node_root(raw),node='node-1',
        storage=node['storage'],selector=c.sha(selector),images=[dict(v,generation=c.sha(local['generation.gsr'])) for v in f.decode(record,'records','RETIREMENT')['files'] if v['path'].endswith('.image')]))
    retire,_=retirement.transaction(pinned,old,record,binding,True,slot='b');expected['retired']=retire[-1][1]
    old_id=rows[2][2]['basisId'];prefix='sources/'+old_id+'/'
    source={n[len(prefix):]:g.read(root/'seed/node-1'/n,64*1024*1024) for n in initial if n.startswith(prefix)}
    source_record=f.encode('records','RETIREMENT',dict(root=node_root(raw),node='node-1',floor=c.sha(raw),selector=c.sha(selector),
        files=[dict(path=prefix+n,size=len(v),sha256=c.sha(v)) for n,v in sorted(source.items())]))
    authority=source_record+rows[1][1]+rows[2][1]+p.decode(source['source.gscp'])['capsuleBytes']
    compact=b''.join(row[1] for row in rows[4:])
    compact_steps=source_release.transaction(expected['retired'],authority,compact,old_id);expected['compacted']=compact_steps[-1][1]
    expected['released']={n:v for n,v in expected['compacted'].items() if n!='floor-copies' and not n.startswith('floor-copies/')}
    expected['cold']=expected['released']
    return dict(initial=initial,expected=expected,copies=copies,floor=raw,selector=selector,floorEvents=names,
        old=old,retirement=record,binding=binding,retireSteps=retire,authority=authority,compact=compact,oldSource=old_id,compactSteps=compact_steps)


def validate(root):
    root=Path(root);original.history_inventory(root)
    need({v.name for v in root.iterdir()}=={'seed','pinned','retired','compacted','released','cold','events.json'},'pinned evidence inventory')
    plan=derive(root);expected=plan['expected'];names=plan['floorEvents'];retire=plan['retireSteps'];compact_steps=plan['compactSteps']
    for name,state in expected.items():
        need(s.inventory(root/name)==state,'pinned exact '+name)
        need(sum(n.endswith('.image') for n in state)<=7,'pinned physical image bound')
    observed=original.read(root/'events.json')
    need(type(observed) is list and all(set(row)=={'phase','event','sources','images'} and row['phase'] in PHASES for row in observed),'pinned observation fields')
    need([PHASES.index(r['phase']) for r in observed]==sorted(PHASES.index(r['phase']) for r in observed),'pinned phase order')
    wanted={'open':list(c.OPEN),'floor':['FLOOR_COPY_BEFORE_RETURN']*2+names+['FLOOR_COPY_BEFORE_RETURN'],
            'retire':[name for name,_ in retire],'compact':[name for name,_ in compact_steps],
            'release':release_events(expected['compacted']),'cold':list(c.OPEN)}
    # The producer stops recording the cold-open phase before its next grant.
    for phase in PHASES:
        actual=[r['event'] for r in observed if r['phase']==phase]
        need(actual==wanted[phase],'pinned exact '+phase+' force order')
    need(all(type(row[k]) is int and 0<=row[k]<=limit for row in observed for k,limit in (('sources',6),('images',7))), 'pinned observed capacity')
    need(max(r['sources'] for r in observed)==6 and max(r['images'] for r in observed)==7,'pinned observed capacity peak')
    return dict(status='PASS',execution='conditional-pinned-floor',logicalOriginals=4,copiedOriginals=3,sourcePeak=6,imagePeak=7,
                historicalOwnershipVerified=False,nativeHistory=False,processDeath=False,powerLoss=False)


def node_root(raw):return f.decode(raw,'records','FLOOR')['root']


NEGATIVES={
    'missing-pin':'pinned exact pinned',
    'changed-pin':'pinned exact pinned',
    'missing-original':'pinned exact pinned',
    'extra-local-copy':'pinned exact pinned',
    'wrong-peer':'pinned exact pinned',
    'missing-force':'pinned exact floor force order',
    'reordered-force':'pinned exact floor force order',
    'capacity':'pinned observed capacity',
    'early-source-delete':'pinned exact pinned',
    'retained-floor':'pinned exact released',
    'invalid-seed':'pinned original selector',
}


def mutate(copy,name):
    if name=='missing-pin':(copy/'pinned'/PIN).unlink()
    elif name=='changed-pin':(copy/'pinned'/PIN).write_bytes(b'changed')
    elif name=='missing-original':shutil.rmtree(copy/'pinned/generations/a')
    elif name=='extra-local-copy':shutil.copytree(copy/'pinned/generations/a',copy/'pinned/floor-copies'/c.sha(g.read(copy/'pinned/generations/a/generation.gsr',65536)))
    elif name=='wrong-peer':next((copy/'pinned/floor-copies').glob('*/generation.gsr')).write_bytes(b'changed')
    elif name in ('missing-force','reordered-force','capacity'):
        values=original.read(copy/'events.json');i=next(i for i,v in enumerate(values) if v['event']=='FLOOR_LOCAL_ORIGINAL_FORCED')
        if name=='missing-force':values.pop(i)
        elif name=='reordered-force':values[i],values[i+1]=values[i+1],values[i]
        else:values[i]['images']=8
        (copy/'events.json').write_bytes(f.canonical(values))
    elif name=='early-source-delete':shutil.rmtree(next((copy/'pinned/sources').iterdir()))
    elif name=='retained-floor':shutil.copytree(copy/'pinned/floor-copies',copy/'released/floor-copies')
    elif name=='invalid-seed':
        path=copy/'seed/node-1/selector.gsr';value=f.decode(g.read(path,4096),'records','SELECTOR')
        path.write_bytes(f.encode('records','SELECTOR',dict(value,digest='0'*64)))
    else:raise ValueError('unknown pinned mutation')


def qualify(root):
    root=Path(root);before=original.history_inventory(root);result=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-pinned-negative-') as temp:
            copy=Path(temp)/'evidence';shutil.copytree(root,copy);mutate(copy,name)
            try:validate(copy)
            except ValueError as error:
                need(str(error)==reason,'pinned unrelated negative: '+name+': '+str(error))
                negatives.append(dict(case=name,status='REJECTED',reason=reason))
            else:raise ValueError('pinned mutation accepted: '+name)
    need(original.history_inventory(root)==before,'pinned original evidence changed')
    return dict(result=result,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('evidence');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.evidence) if args.qualify else validate(args.evidence),sort_keys=True))
