"""Original-first replay of complete captures with no BASIS, covered by a later full floor."""
from pathlib import Path
from scripts.v53 import source_release_evidence as e
from scripts.v53 import adoption_install_evidence as a
from scripts.v53.membership_model import need
r,c,g,s,p=e.r,e.c,e.g,e.s,e.p


def cases():
    rows=[dict(size=size,through=through,tail=tail,mode='clean',cut='none')
          for size in (3,4,5) for through in (6,7) for tail in (False,True)]
    rows += [dict(size=3,through=6,tail=False,mode=mode,cut=cut)
             for mode in ('halt','kill') for cut in e.CUTS]
    rows += [dict(size=5,through=7,tail=True,mode=mode,cut='SOURCE_RETIREMENT_FORCED') for mode in ('repeat-halt','repeat-kill')]
    return [dict(v,name=f"{v['size']}-{v['through']}-{str(v['tail']).lower()}-{v['mode']}-{v['cut'].lower()}") for v in rows]


def plan(directory,case):
    directory=Path(directory);initial=directory/'initial';inputs=directory/'inputs'
    original,old,manifest,packet=c.current(inputs/'original',case['size'])
    need([row[0] for row in old]==['PROMISE','PROMISE'] and [row[2]['ballot']['counter'] for row in old]==[10,20]
         and manifest['cut']['index']==0 and (manifest['ownedTail'] is not None)==case['tail'],'captured source original journal/profile')
    root=manifest['root'];id=old[1][2]['basisId'];need(id is not None and g.a.load(directory/'fixture.json')==dict(basisId=id),'captured source original identity')
    source_files={n:g.read(inputs/'original/generations/a'/n,64*1024*1024) for n in ['source.gscp',*[h+'.image' for h in packet['images']]]}
    expected_source={'sources/'+id:dict(directory=True),**{'sources/'+id+'/'+n:r.entry(raw) for n,raw in source_files.items()}}
    need({n:v for n,v in original.items() if n.startswith('sources/')}==expected_source,'captured source exact original bytes')
    # The original capture is independently bound to the selected physical capsule.
    # No BASIS is manufactured or supplied to the implementation.
    fence,_,active,selector,current,data=a.plan(inputs/'adoption',manifest,case)
    need({v.name for v in (inputs/'adoption').iterdir()}=={'inputs','initial'}
         and {v.name for v in (inputs/'adoption/initial').iterdir()}=={'root.gsr'},'captured source adoption input inventory')
    need(g.read(inputs/'adoption/initial/root.gsr',16384)==g.read(inputs/'original/root.gsr',16384),'captured source adoption root')
    peers=[f'node-{i}' for i in range(2,case['size']//2+2)]
    need({v.name for v in inputs.iterdir()}=={'original','adoption',*peers},'captured source peer inventory')
    definition=g.f.decode(g.read(inputs/'original/root.gsr',16384),'records','ROOT')
    references=[dict(voter='node-1',generation=c.sha(active['generation.gsr']),catalog=current['catalog'],snapshot=current['application'])]
    copies={c.sha(active['generation.gsr']):active}
    for ordinal,node in enumerate(peers,1):
        path=inputs/node;rows=g.journal(g.read(path/'grants.gsr',g.LIMIT),root,node)
        peer_promise=g.f.encode('records','PROMISE',dict(old[0][2],view=c.sha(g.f.canonical(dict(root=root,**current['cut']['view'])))))
        need(len(rows)==1 and rows[0][1]==peer_promise,'captured source peer promise')
        files,peer,peer_packet=r.generation(path/'generations/a',root,node,rows,case)
        need(all(peer[k]==current[k] for k in ('root','cut','catalog','application')),'captured source peer floor binding')
        base={n:v for n,v in original.items() if '/' not in n and n not in ('node.gsr','allocator.gsr','grants.gsr','selector.gsr','sources','generations')}
        base.update({'node.gsr':r.entry(g.f.encode('records','NODE',dict(root=root,identity=definition['initial'][ordinal]))),
                     'allocator.gsr':r.entry(g.f.encode('records','ALLOCATOR',dict(root=root,node=node,counter=0))),
                     'grants.gsr':r.entry(peer_promise),'sources':dict(directory=True),'generations':dict(directory=True),'generations/a':dict(directory=True),
                     'selector.gsr':r.entry(g.f.encode('records','SELECTOR',dict(root=root,node=node,generation='a',digest=c.sha(files['generation.gsr']))))})
        base.update({'generations/a/'+n:r.entry(raw) for n,raw in files.items()})
        need(s.inventory(path)==base and peer_packet['objects'][c.sha(g.read(path/'root.gsr',16384))]==g.read(inputs/'original/root.gsr',16384),'captured source exact peer')
        copies[c.sha(files['generation.gsr'])]=files
        references.append(dict(voter=node,generation=c.sha(files['generation.gsr']),catalog=peer['catalog'],snapshot=peer['application']))
    voters={row['voter'] for row in references};view=current['cut']['view']
    need(current['cut']['index']>manifest['cut']['index'] and all(len(voters&set(view[k]))>len(view[k])//2 for k in ('old','new')),'captured source strictly later quorum floor')
    for raw in packet['objects'].values():
        if len(raw)>=48 and raw[:4]==b'GSER' and int.from_bytes(raw[8:10],'big')==g.f.catalog()['records']['ACCEPT']['id']:
            try:accept=g.f.decode(raw,'records','ACCEPT')
            except ValueError:continue
            if accept['root']==root:need(accept['index']<=current['cut']['index'],'captured source uncovered accepted bytes')
    floor=g.f.encode('records','FLOOR',dict(root=root,node='node-1',cut=current['cut'],sources=references))
    expected={n:v for n,v in original.items() if not n.startswith('generations/')}
    expected.update({'generations/b':dict(directory=True),'selector.gsr':r.entry(selector),'grants.gsr':r.entry(b''.join(row[1] for row in old)+fence),
                     'floor-copies':dict(directory=True),'floor-copies/floor.gsr':r.entry(floor),'floor-copies/proposal.gsr':r.entry(floor)})
    expected.update({'generations/b/'+n:r.entry(raw) for n,raw in active.items()})
    for digest,files in copies.items():
        expected['floor-copies/'+digest]=dict(directory=True)
        expected.update({'floor-copies/'+digest+'/'+n:r.entry(raw) for n,raw in files.items()})
    r.snapshot(initial,expected)
    record=g.f.encode('records','RETIREMENT',dict(root=root,node='node-1',floor=c.sha(floor),selector=c.sha(selector),
            files=[dict(path='sources/'+id+'/'+n,size=len(raw),sha256=c.sha(raw)) for n,raw in sorted(source_files.items())]))
    return expected,record+old[1][1]+packet['capsuleBytes'],fence,id


def validate_case(directory,case):
    return e.validate_case(directory,case,plan_builder=plan,execution='private-captured-source-retirement')


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={v['name'] for v in cases()},'captured source complete cases')
    return dict(status='PASS',execution='private-captured-source-retirement',runtimeEnabled=False,
                cases=[validate_case(directory/v['name'],v) for v in cases()])
