"""Original physical multi-voter ACCEPTs and exact local PROOF transaction replay.

The initial application/certified prefix is an explicit fixture. This does not
claim network delivery, application publication or remote production readiness.
"""
import struct
from pathlib import Path
from . import pending_accept_evidence as a
from . import current_generation_evidence as c
from . import generation_install_evidence as install
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as packet
from . import capture_journal_evidence as capture
from .membership_model import need

ACTIVE=a.ACTIVE;NEXT=a.NEXT;EMPTY=a.EMPTY
CUTS=tuple(v.replace('ACCEPT','PROOF') for v in a.CUTS)
SEAL=tuple(v.replace('ACCEPT','PROOF') for v in a.SEAL)
RECOVERY=('PROOF_RECOVERY_VALIDATED',)+CUTS[2:-1]


def cases():
    rows=[dict(size=size,through=through,mode='clean',cut='none') for size in (3,4,5) for through in (0,6,7)]
    rows += [dict(size=3,through=0,mode=mode,cut=cut) for mode in ('halt','kill') for cut in CUTS]
    rows += [dict(size=5,through=6,mode=mode,cut=cut) for mode in ('repeat-halt','repeat-kill') for cut in RECOVERY+SEAL]
    for row in rows:row['name']=f"{row['size']}-{row['through']}-{row['mode']}-{row['cut'].lower()}"
    return rows


def inventory(root):
    # Keep the existing per-voter file bound. This matrix owns up to six separate
    # voter directories; it must not reuse the single-voter 80-file total.
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'proof voter inventory root')
    nodes=sorted(root.iterdir());need(3<=len(nodes)<=6 and all(p.is_dir() and not p.is_symlink() and p.name in {f'node-{i}' for i in range(1,7)} for p in nodes),'proof voter inventory')
    result={}
    for node in nodes:
        result[node.name]=dict(directory=True)
        result.update({node.name+'/'+name:value for name,value in s.inventory(node).items()})
    return result


def container(frames,payload,proof):
    raw=a.container(frames,payload)+proof
    return raw[:8]+struct.pack('>I',len(raw))+raw[12:]


def generation(path,root,node):
    selector=g.read(path/'selector.gsr',4096);sel=g.f.decode(selector,'records','SELECTOR',root)
    need(sel['node']==node,'proof selector owner');folder=path/'generations'/sel['generation']
    raw=g.read(folder/'generation.gsr',65536);manifest=g.f.decode(raw,'records','GENERATION',root)
    need(manifest['node']==node and manifest['generation']==sel['generation'] and c.sha(raw)==sel['digest'],'proof generation selector')
    allowed={'source.gscp','promise.gsr','basis.gsr','selected.gsr','owned-tail.gsr'}
    need(all(v['path'] in allowed or len(v['path'])==70 and v['path'].endswith('.image') and all(x in '0123456789abcdef' for x in v['path'][:64]) for v in manifest['files']),'proof generation member path')
    files={v['path']:g.read(folder/v['path'],v['size']) for v in manifest['files']}
    need(manifest['files']==[dict(path=n,size=len(v),sha256=c.sha(v)) for n,v in sorted(files.items())]
         and {v.name for v in folder.iterdir()}==set(files)|{'generation.gsr'},'proof original generation files')
    data=packet.decode(files['source.gscp']);cap=data['capsule']
    need(all(manifest[k]==cap[k] for k in ('root','cut','catalog','application')) and manifest['capsule']==c.sha(data['capsuleBytes']),'proof original capsule')
    need(all(c.sha(files[h+'.image'])==h and len(files[h+'.image'])==count for h,count in data['images'].items()),'proof original application images')
    return selector,manifest,files,data


def model(root,case):
    initial=root/'installed';nodes=sorted(p.name for p in initial.iterdir());need(len(nodes)==case['size']+(case['through']==6),'proof governing voter count')
    whole=inventory(initial);provision=inventory(root/'provisioned');expected=dict(provision);models={};refs=[]
    for node in nodes:
        path=initial/node;original=root/'provisioned'/node
        raw=g.read(path/'root.gsr',16384);digest=raw[16:48].hex();identity=g.f.decode(g.read(path/'node.gsr',4096),'records','NODE',digest)['identity']
        need(identity['node']==node,'proof owner identity');selector,manifest,files,data=generation(original,digest,node)
        need({p.name for p in original.iterdir()}==g.a.NAMES|{'grants.gsr','selector.gsr','sources','generations',ACTIVE}
             and not list((original/'sources').iterdir()) and {p.name for p in (original/'generations').iterdir()}=={'a'},'proof provisioned inventory')
        need(manifest['selection'] is None and manifest['basis'] is None and manifest['ownedTail'] is None and set(files)=={'source.gscp','promise.gsr',*[h+'.image' for h in data['images']]},'proof initial fixture scope')
        need(g.read(original/'replica.lock',0)==b'' and g.f.decode(g.read(original/'allocator.gsr',4096),'records','ALLOCATOR',digest)==dict(root=digest,node=node,counter=0),'proof initial owner allocator')
        root_record=g.f.decode(raw,'records','ROOT');genesis=g.read(original/'genesis.gsr',65536)
        need(root_record['genesis']==c.sha(genesis) and root_record['limits']==c.sha(g.f.canonical(g.f.catalog()['resources'])) and len(root_record['initial'])==case['size'],'proof root genesis/resources')
        cap=data['capsule'];catalog=g.f.decode(data['objects'][cap['catalog']],'records','CATALOG',digest)
        need(identity in catalog['identities'],'proof permanent voter identity')
        view=cap['cut']['view'];need(nodes==sorted(set(view['old'])|set(view['new'])),'proof governing voter set')
        need(cap['cut']['index']==case['through'] and data['objects'].get(c.sha(raw))==raw,'proof historical input cut/root')
        rows=g.journal(g.read(path/'grants.gsr',g.LIMIT),digest,node);need([r[0] for r in rows]==['PROMISE','PROMISE','BASIS','SELECTED'],'proof installed grant history')
        need(g.read(original/'grants.gsr',g.LIMIT)==rows[0][1] and rows[0][2]['ballot']['counter']==10,'proof provisioned promise')
        p,b,selected=rows[1:];need(p[2]['ballot']['counter']==20 and b[2]['accepted'] is None and b[2]['cut']==cap['cut'],'proof original frozen basis')
        basisdir=path/'sources'/b[2]['basisId'];need(g.read(basisdir/'source.gscp',g.LIMIT)==files['source.gscp'],'proof original source bytes')
        packet.bind(data,b[1]);refs.append(dict(voter=node,basisId=b[2]['basisId'],basisDigest=c.sha(b[1])))
        names={'source.gscp',*[h+'.image' for h in data['images']]}
        need({v.name for v in basisdir.iterdir()}==names and all(g.read(basisdir/n,len(files[n]))==files[n] for n in names),'proof complete frozen source')
        generated={n:files[n] for n in names};generated.update({'promise.gsr':p[1],'basis.gsr':b[1],'selected.gsr':selected[1]})
        value=dict(root=digest,node=node,generation='b',cut=cap['cut'],application=cap['application'],catalog=cap['catalog'],capsule=c.sha(data['capsuleBytes']),
                   promise=c.sha(p[1]),basis=c.sha(b[1]),selection=c.sha(selected[1]),ownedTail=None,
                   files=[dict(path=n,size=len(v),sha256=c.sha(v)) for n,v in sorted(generated.items())])
        generated['generation.gsr']=g.f.encode('records','GENERATION',value)
        selected_raw=g.f.encode('records','SELECTOR',dict(root=digest,node=node,generation='b',digest=c.sha(generated['generation.gsr'])))
        expected[node+'/selector.gsr']=a.info(selected_raw);expected[node+'/grants.gsr']=a.info(b''.join(r[1] for r in rows));expected[node+'/generations/b']=dict(directory=True)
        expected.update({node+'/generations/b/'+n:a.info(v) for n,v in generated.items()});expected[node+'/sources/'+b[2]['basisId']]=dict(directory=True)
        expected.update({node+'/sources/'+b[2]['basisId']+'/'+n:a.info(files[n]) for n in names})
        need(g.read(original/ACTIVE,12)==EMPTY,'proof provisioned empty vote')
        models[node]=dict(root=digest,identity=identity,selector=selected_raw,rows=rows,files=generated,data=data,cut=cap['cut'])
    need(whole==expected,'proof exact installed generations')
    accepted=dict(whole);returns={}
    for node,m in models.items():
        selected=m['rows'][-1];need(selected[2]==dict(root=m['root'],view=m['rows'][1][2]['view'],ballot=m['rows'][1][2]['ballot'],cut=m['cut'],sources=refs,nextEntry=None),'proof actual selected quorum')
        payload=b'original-real-quorum-payload' if case['through']!=6 else g.f.canonical(dict(binding=m['cut']['view']['operation']))
        entry=g.f.encode('records','ENTRY',dict(root=m['root'],authority=selected[2]['view'],index=m['cut']['index']+1,previous=m['cut']['entry'],origin=selected[2]['ballot'],kind='FINAL' if case['through']==6 else 'DATA',payload=c.sha(payload)))
        accept=g.f.encode('records','ACCEPT',dict(root=m['root'],authority=selected[2]['view'],index=m['cut']['index']+1,ballot=selected[2]['ballot'],entry=c.sha(entry)))
        frames=[m['selector'],m['rows'][1][1],selected[1],entry,accept];m.update(frames=frames,payload=payload,entry=entry,accept=accept)
        accepted[node+'/'+ACTIVE]=a.info(a.container(frames,payload));returns[node]=dict(node=node,accepted=c.sha(accept),parent=c.sha(g.f.canonical(m['cut'])),storage=m['identity']['storage'])
    need(inventory(root/'accepted')==accepted,'proof actual ACCEPT files')
    own=models['node-1'];witnesses=[]
    for node,m in models.items():
        if node=='node-1':continue
        need(m['accept']==own['accept'] and m['cut']==own['cut'],'proof peer exact ACCEPT parent')
        receipt=dict(root=m['root'],voter=node,incarnation=m['identity']['storage'],phase='ACCEPT',record=c.sha(m['accept']))
        witnesses.append(dict(voter=node,incarnation=m['identity']['storage'],receipt=c.sha(g.f.canonical(receipt))))
    need(all(len({w['voter'] for w in witnesses}&set(own['cut']['view'][side]))>len(own['cut']['view'][side])//2 for side in ('old','new')),'proof actual both majorities')
    proof=g.f.encode('records','PROOF',dict(g.f.decode(own['accept'],'records','ACCEPT'),accepts=witnesses));vote=container(own['frames'],own['payload'],proof)
    def state(point=None):
        value=dict(accepted);pos=len(CUTS) if point is None else CUTS.index(point)
        if pos>=CUTS.index('PROOF_RENAMED'):value['node-1/'+ACTIVE]=a.info(vote)
        elif pos>=1:value['node-1/'+NEXT]=a.info(vote[:0 if pos==1 else len(vote)//2 if pos==2 else len(vote)])
        return value
    data=own['data'];objects=dict(data['objects']);objects.update({c.sha(v):v for v in (own['entry'],own['accept'],own['payload'],proof)})
    source=install.packet_bytes(data['capsule'],objects,data['images']);decoded=packet.decode(source)
    final=inventory(root/'final');rows=g.journal(g.read(root/'final/node-1/grants.gsr',g.LIMIT),own['root'],'node-1')
    need(rows[:4]==own['rows'] and [r[0] for r in rows[4:]]==['PROMISE','BASIS'],'proof fresh capture history')
    p,b=rows[4:];need(p[2]['ballot']==dict(own['rows'][1][2]['ballot'],counter=21),'proof fresh capture ballot')
    need(b[2]==dict(p[2],voter='node-1',cut=own['cut'],capsule=c.sha(decoded['capsuleBytes']),inventory=c.sha(decoded['indexBytes']),accepted=c.sha(own['accept'])),'proof captured ACCEPT binding')
    packet.bind(decoded,b[1]);expected=state();prefix='node-1/sources/'+b[2]['basisId'];expected[prefix]=dict(directory=True)
    expected[prefix+'/source.gscp']=a.info(source);expected.update({prefix+'/'+h+'.image':a.info(own['files'][h+'.image']) for h in data['images']})
    expected['node-1/grants.gsr']=a.info(b''.join(r[1] for r in rows))
    need(final==expected,'proof exact final source');need(inventory(root/'authority')==final,'proof final authority')
    for node in models:
        need(sum(v.get('bytes',0) for n,v in final.items() if n in (node+'/grants.gsr',node+'/'+ACTIVE,node+'/'+NEXT))<=g.LIMIT,'proof shared journal limit')
        need(sum(n.startswith(node+'/') and n.endswith('.image') for n in final)<=7,'proof shared image limit')
    return state,rows,returns,dict(proof=c.sha(proof),accepted=c.sha(own['accept']),parent=c.sha(g.f.canonical(own['cut'])))


def validate_case(directory,case):
    root=Path(directory);record=g.a.load(root/'case.json');need(record['case']==case,'proof case identity')
    need(record['execution']=='private-pending-proof' and record['runtimeEnabled'] is False and record['localVotersVerified'] is True and record['networkAck'] is False,'proof evidence scope')
    state,history,accepts,returned=model(root,case);clean=case['mode']=='clean';repeat=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
    names={'init','install','accept-all','capture','inspect'}|({'first','duplicate','accept-duplicate'} if clean else {'fault','resume'})|({'recovery-fault'} if repeat else set())
    snapshots={'provisioned','installed','accepted','final','authority'}|({'original','duplicate'} if clean else {'crash','resumed'})|({'recovery-crash'} if repeat else set())
    need(set(record['processes'])==names and {v.name for v in root.iterdir()}=={'case.json',*snapshots}|{n+x for n in names for x in ('.stdout','.stderr')},'proof case inventory')
    def output(name,command,code=0):
        # Existing driver is strict about complete stdout, exits and no early terminal result.
        return a.output(root,record,name,command,code)
    for name in ('init','install'):need(output(name,name)==[dict(status='PASS',command=name)],'proof fixture initialization')
    import json
    rows=[json.loads(line) for line in g.read(root/'accept-all.stdout',65536).splitlines()]
    expected=[]
    for node,value in accepts.items():expected.extend([dict(event=event,node=node) for event in a.OPEN+a.CUTS]+[value])
    need(record['processes']['accept-all']==dict(exitCode=0) and g.read(root/'accept-all.stderr',65536)==b'' and rows==expected+[dict(status='PASS',command='accept-all')],'proof actual ACCEPT force/return order')
    def success(rows,advanced=False):
        basis=history[-1] if advanced else history[2]
        need(rows[-1]==dict(status='PASS',command=rows[-1]['command'],**returned,basis=c.sha(basis[1]),captured=basis[2]['accepted']),'proof returned original binding')
    if clean:
        rows=output('first','prove');need(g.events(rows)==list(a.OPEN+CUTS),'proof force order');success(rows)
        rows=output('duplicate','prove');need(g.events(rows)==list(c.OPEN+SEAL+('PROOF_BEFORE_RETURN',)),'proof duplicate order');success(rows)
        rows=output('accept-duplicate','accept-duplicate');need(g.events(rows)==list(c.OPEN+SEAL+('ACCEPT_BEFORE_RETURN',)),'proof ACCEPT duplicate order');success(rows)
        need(inventory(root/'original')==inventory(root/'duplicate')==state(),'proof preserved duplicate bytes')
    else:
        point='PROOF_CANDIDATE_WRITTEN' if repeat else case['cut'];rows=output('fault','prove',73 if repeat or mode=='halt' else -9);order=a.OPEN+CUTS
        need(g.events(rows)==list(order[:order.index(point)+1])+(['AWAITING_KILL'] if not repeat and mode=='kill' else []),'proof crash order')
        if not repeat and mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=point),'proof kill handshake')
        need(inventory(root/'crash')==state(point),'proof exact crash snapshot');position=CUTS.index(point)
        if repeat:
            rows=output('recovery-fault','prove',73 if mode=='halt' else -9);order=c.OPEN+RECOVERY+SEAL+('PROOF_BEFORE_RETURN',)
            need(g.events(rows)==list(order[:order.index(case['cut'])+1])+(['AWAITING_KILL'] if mode=='kill' else []),'proof recovery order')
            if mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=case['cut']),'proof recovery kill handshake')
            position=3 if case['cut'] in RECOVERY[:4] else CUTS.index(case['cut']) if case['cut'] in CUTS else len(CUTS)
            need(inventory(root/'recovery-crash')==state(None if position>=len(CUTS) else CUTS[position]),'proof exact recovery snapshot')
        rows=output('resume','prove')
        if position>=CUTS.index('PROOF_RENAMED'):order=c.OPEN+SEAL+('PROOF_BEFORE_RETURN',)
        elif position>=3:order=c.OPEN+RECOVERY+SEAL+('PROOF_BEFORE_RETURN',)
        elif position>=1:order=a.OPEN+('PROOF_VALIDATED',)+CUTS[2:]
        else:order=a.OPEN+CUTS
        need(g.events(rows)==list(order),'proof resume order');success(rows);need(inventory(root/'resumed')==state(),'proof resumed bytes')
    rows=output('capture','capture');need(g.events(rows)==list(c.OPEN+SEAL+capture.ORDER[len(c.OPEN):]),'proof capture order');success(rows,True)
    rows=output('inspect','inspect');need(g.events(rows)==list(c.OPEN+SEAL),'proof inspect order');success(rows,True)
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(root):
    root=Path(root);need({v.name for v in root.iterdir()}=={v['name'] for v in cases()},'proof complete case set')
    return dict(status='PASS',execution='private-pending-proof',cases=[validate_case(root/v['name'],v) for v in cases()])
