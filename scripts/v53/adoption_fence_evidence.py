"""Independent physical promise-fence replay; incoming remote ownership stays conditional."""
from pathlib import Path
from .context_evidence import parse
from . import current_generation_evidence as c
from . import durable_selection_evidence as d
from . import grant_evidence as g
from . import source_packet as p
from .membership_model import need

CUTS=('ADOPTION_VALIDATED','PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED','ADOPTION_BEFORE_RETURN')


def cases():
    return [dict(name=f'{size}-{through}-{mode}-{cut.lower()}',size=size,through=through,mode=mode,cut=cut)
            for size in (3,4,5) for through in (6,7) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in CUTS]]


def quorum(view,voters):
    need(voters==sorted(set(voters)) and set(voters)<=set(view['old']+view['new']) and
         all(len(set(voters)&set(view[k]))>len(view[k])//2 for k in ('old','new')),'adoption certificate quorum')


def original_fence(directory,initial,case):
    path=Path(directory)/'inputs';packet=p.decode(g.read(path/'source.gscp',g.LIMIT));cap=packet['capsule'];objects=packet['objects'];root=initial['root']
    need(path.is_dir() and not path.is_symlink() and {v.name for v in path.iterdir()}=={'source.gscp',*[h+'.image' for h in packet['images']]},'adoption input inventory')
    for h,count in packet['images'].items():
        raw=g.read(path/(h+'.image'),count);need(len(raw)==count and c.sha(raw)==h,'adoption image')
    root_bytes=g.read(Path(directory)/'initial/root.gsr',16384)
    need(cap['root']==root and objects.get(c.sha(root_bytes))==root_bytes,'adoption original root')
    catalog=g.f.decode(objects[cap['catalog']],'records','CATALOG',root);identities={r['node']:r for r in catalog['identities']}
    at=initial['cut'];application=initial['application'];catalog_hash=initial['catalog'];highest=None
    for item in cap['items']:
        statement=g.f.decode(objects[item['statement']],'records','CHECKPOINT',root);end=statement['end']
        need(statement['start']==at and statement['catalogBefore']==catalog_hash and statement['applicationBefore']==application
             and statement['scope']==item['kind'],'adoption checkpoint chain')
        view=at['view'];authority=c.sha(g.f.canonical(dict(root=root,**view)))
        if item['kind']=='MEMBERSHIP':
            cert=g.f.decode(objects[item['certificate']],'records','CERTIFICATE',root)
            entry=g.f.decode(objects[cert['entry']],'records','ENTRY',root)
            need(cert['authority']==entry['authority']==authority and cert['index']==entry['index']==at['index']+1
                 and entry['previous']==at['entry'] and end['entry']==cert['entry'] and end['index']==entry['index'],'adoption certificate parent')
            ballot=cert['ballot'];need(ballot['proposer'] in view['old']+view['new'] and
                identities[ballot['proposer']]['storage']==ballot['incarnation'] and g.order(entry['origin'])<=g.order(ballot),'adoption certificate ballot')
            for phase,field in (('ACCEPT','accepts'),('PROOF','proofs')):
                value={k:v for k,v in cert.items() if k not in (('accepts','proofs') if phase=='ACCEPT' else ('proofs',))}
                raw=g.f.encode('records',phase,value);digest=c.sha(raw);need(objects.get(digest)==raw,'adoption exact phased bytes')
                witnesses=cert[field];quorum(view,[w['voter'] for w in witnesses])
                for witness in witnesses:
                    node=witness['voter'];storage=identities[node]['storage']
                    expected=c.sha(g.f.canonical(dict(root=root,voter=node,incarnation=storage,phase=phase,record=digest)))
                    need(witness['incarnation']==storage and witness['receipt']==expected,'adoption phased receipt')
            descriptor=parse(objects[item['descriptor']])
            payload=parse(objects[entry['payload']])
            if entry['kind']=='INTENT':
                need(payload['sealed']==descriptor and view['operation'] is None,'adoption intent payload')
                expected=dict(view,new=[v['node'] for v in descriptor['request']['target']],operation=item['descriptor'])
            else:
                need(entry['kind']=='FINAL' and payload['binding']==item['descriptor']==view['operation'],'adoption final payload')
                expected=dict(generation=view['generation']+1,old=view['new'],new=view['new'],operation=None)
            need(end['view']==expected and statement['applicationAfter']==application,'adoption membership successor')
            if highest is None or g.order(ballot)>=g.order(highest['ballot']):highest=cert
        else:
            need(item['kind']=='RANGE' and item['certificate'] is None and item['descriptor'] is None and
                 view['operation'] is None and end['view']==view and end['index']>at['index'],'adoption range boundary')
        voters=[]
        for h in item['endorsements']:
            ack=g.f.decode(objects[h],'records','CHECKPOINT_ACK',root);node=ack['voter'];voters.append(node)
            need(ack['statement']==item['statement'] and ack['cut']==end and ack['incarnation']==identities[node]['storage'],'adoption checkpoint endorsement')
        quorum(end['view'],voters);at=end;application=statement['applicationAfter'];catalog_hash=statement['catalogAfter']
    need(at==cap['cut'] and application==cap['application'] and catalog_hash==cap['catalog'] and at['index']==case['through'],'adoption terminal binding')
    need(highest is not None and highest['ballot']['counter']==24+case['through'],'adoption original certificate floor')
    value=dict(root=root,view=highest['authority'],ballot=highest['ballot'],basisId=None)
    return g.f.encode('records','PROMISE',value),value


def state(path,size,initial,rows,fence,written):
    actual,journal,_,_=c.current(path,size)
    expected=dict(initial);raw=b''.join(r[1] for r in rows)+(fence if written else b'')
    expected['grants.gsr']=dict(bytes=len(raw),sha256=c.sha(raw))
    need(actual==expected and journal[:len(rows)]==rows and len(journal)==len(rows)+int(written),'adoption changed prefix/source/history')
    if written:need(journal[-1][0]=='PROMISE' and journal[-1][1]==fence and journal[-1][2]['basisId'] is None,'adoption became grant')


def result(stdout,fence,value):
    row=stdout[-1];need(row['promise']==c.sha(fence) and all(row[k]==value[k] for k in ('view','ballot')) and
        row['hasBasis'] is False and row['prefixInstalled'] is False and row['networkAck'] is False,'adoption returned binding')


def validate_case(directory,case):
    directory=Path(directory);record=g.a.load(directory/'case.json');need(record['case']==case,'adoption case identity')
    need(record['execution']=='private-adoption-fence' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False
         and record['prefixInstalled'] is False,'adoption scope')
    initial,rows,generation,_=c.current(directory/'initial',case['size'])
    need([r[0] for r in rows]==['PROMISE','PROMISE','BASIS'] and generation['cut']['index']==0,'adoption initial grant')
    fence,value=original_fence(directory,generation,case);d.process(directory,record,'init','init',0);order=list(c.OPEN+CUTS)
    clean=case['mode']=='clean';name='original' if clean else 'resumed';state(directory/name,case['size'],initial,rows,fence,True)
    if clean:
        stdout=d.process(directory,record,'first','adopt',0);need(g.events(stdout)==order,'adoption force order');result(stdout,fence,value)
        stdout=d.process(directory,record,'duplicate','adopt',0);need(g.events(stdout)==list(c.OPEN+('ADOPTION_VALIDATED',)),'adoption duplicate wrote');result(stdout,fence,value)
        state(directory/'duplicate',case['size'],initial,rows,fence,True)
    else:
        cut=case['cut'];stdout=d.process(directory,record,'fault','adopt',73 if case['mode']=='halt' else -9)
        need(g.events(stdout)==order[:order.index(cut)+1]+(['AWAITING_KILL'] if case['mode']=='kill' else []),'adoption crash cut')
        if case['mode']=='kill':need(stdout[-1]==dict(event='AWAITING_KILL',cut=cut),'adoption kill handshake')
        written=CUTS.index(cut)>=2;state(directory/'crash',case['size'],initial,rows,fence,written)
        stdout=d.process(directory,record,'resume','adopt',0)
        need(g.events(stdout)==(list(c.OPEN+('ADOPTION_VALIDATED',)) if written else order),'adoption recovery force order');result(stdout,fence,value)
    for name in ('same','old'):
        stdout=d.process(directory,record,name,name,2);need(g.events(stdout)==list(c.OPEN+(c.CAPTURE,)),'adoption refusal wrote')
        reason='uninstalled adoption fence; prefix recovery required'
        need(stdout[-1]['reason']==reason,'adoption refusal reason');state(directory/('same' if name=='same' else 'final'),case['size'],initial,rows,fence,True)
    state(directory/'authority',case['size'],initial,rows,fence,True)
    processes={'init','first','duplicate','same','old'} if clean else {'init','fault','resume','same','old'}
    snapshots={'initial','original','duplicate','same','final','authority'} if clean else {'initial','crash','resumed','same','final','authority'}
    need(set(record['processes'])==processes and {p.name for p in directory.iterdir()}=={'case.json','inputs',*snapshots}|{n+s for n in processes for s in ('.stdout','.stderr')},'adoption case inventory')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,prefixInstalled=False)


def validate(directory):
    directory=Path(directory);need({p.name for p in directory.iterdir()}=={c['name'] for c in cases()},'adoption complete cases')
    return dict(status='PASS',execution='private-adoption-fence',runtimeEnabled=False,prefixInstalled=False,
                cases=[validate_case(directory/c['name'],c) for c in cases()])
