"""Conditional four-copy writer cuts and bounded original recovery.

Real native historical authority, process death and full maintenance remain
separate obligations. Fixture generations never become Phase 3 admission.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import current_generation_evidence as current
from . import joint_floor_recovery_evidence as joint

c, f, h, need = joint.c, joint.f, joint.h, joint.need
sha, read = joint.catalog.sha, joint.read
NODES = ('node-1', 'node-2', 'node-5', 'node-6')
CUTS = ('FLOOR_COPY_CREATED', 'FLOOR_MANIFEST_FORCED', 'FLOOR_IMAGE_FORCED', 'FLOOR_MEMBER_FORCED')
FILES = {'case.json','receipt.json','initial','originals','interrupted','after-close','after-reopen',
         'completed','after-complete-close','initial-events.json','resumed-events.json','wire.json'}


def identity(number):
    return dict(node='node-'+str(number),storage='00000000-0000-0005-0000-'+format(number,'012x'),host='127.0.0.1',port=19000+number)


def position(events, ordinal, cut):
    count = 0
    for index, row in enumerate(events):
        if row['event'] == 'FLOOR_COPY_CREATED': count += 1
        if count == ordinal and row['event'] == cut: return index
    raise ValueError('partial joint declared writer cut absent')


def transfers(root, copies, cap, ballot):
    rows = read(root/'wire.json'); peers = {node:[] for node in NODES[1:]}
    order = []
    for row in rows:
        need(type(row) is dict and set(row) == {'request','response'}, 'partial joint exact exchange row')
        _, query = joint.generation.t.t.wire(row['request']); node = query['recipient']['node']
        need(node in peers, 'partial joint exact remote cohort')
        if not order or order[-1] != node: order.append(node)
        peers[node].append(row)
    need(order == ['node-6','node-2','node-5'], 'partial joint original transfer order')
    view = sha(f.canonical(dict(root=cap['root'],**cap['cut']['view'])))
    for node, rows in peers.items():
        sessions = joint.generation.sessions(rows); members = copies[node]
        packet = sha(f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-packet')))
        generation = sha(f.canonical(dict(root=cap['root'],cut=cap['cut'],scope='retained-current-generation-metadata')))
        wanted = [[(packet,members['source.gscp'],'CAPSULE')],[(generation,members['generation.gsr'],'RECORD')]]
        if 'ancestry.gsr' in members: wanted[1].append((sha(members['ancestry.gsr']),members['ancestry.gsr'],'RECORD'))
        wanted[1] += [(sha(data),data,'RECORD') for name,data in sorted(members.items())
                      if name not in ('generation.gsr','source.gscp','ancestry.gsr') and not name.endswith('.image')]
        for (_, exchange), expected in zip(sessions,wanted):
            joint.generation.t.transcript(joint.generation.attempts(exchange),expected,cap['root'],view,ballot,identity(1),identity(int(node[5:])),
                                         'partial joint original',chunk_bytes=4*1024**2)
    return sum(len(rows) for rows in peers.values())


def validate(directory):
    root = Path(directory); before = h.inventory(root)
    need({p.name for p in root.iterdir()} == FILES, 'partial joint exact inventory')
    case = read(root/'case.json')
    need(type(case) is dict and set(case) == {'profile','ordinal','cut','handoff','historicalOwnershipVerified','processDeath','nativeRuntime','phase3Complete'} and
         type(case['ordinal']) is int and 1 <= case['ordinal'] <= 4 and case['cut'] in CUTS, 'partial joint declared case')
    joint.same(case,dict(profile='5-REPLACE',ordinal=case['ordinal'],cut=case['cut'],handoff=True,historicalOwnershipVerified=False,
                        processDeath=False,nativeRuntime=False,phase3Complete=False),'partial joint bounded scope')
    joint.same(read(root/'receipt.json'),dict(schema='gse-v53-partial-joint-floor-v1',status='PASS',
        execution='conditional-original-writer-and-transfer-service',phase3Complete=False),'partial joint producer completion')
    _, journal, manifest, packet = current.current(root/'initial',5)
    need([(kind,v['ballot']['counter']) for kind,raw,v in journal] == [('PROMISE',10),('PROMISE',20),('BASIS',20),('PROMISE',21),('BASIS',21)],
         'partial joint two original promises')
    cap = packet['capsule']; initial = c.inventory(root/'initial')
    need(f.decode(initial['allocator.gsr'],'records','ALLOCATOR')['counter'] == 0, 'partial joint original allocator')
    need(cap['cut']['index'] == 6 and cap['cut']['view']['old'] == ['node-'+str(i) for i in range(1,6)] and
         cap['cut']['view']['new'] == ['node-1','node-2','node-3','node-4','node-6'], 'partial joint conditional view')
    need({p.name for p in (root/'originals').iterdir()} == set(NODES), 'partial joint original owners')
    copies = {}; references = []
    for node in NODES:
        generation = f.encode('records','GENERATION',dict(manifest,node=node))
        expected = dict(initial)
        if node != 'node-1':
            expected = {n:v for n,v in expected.items() if not n.startswith('sources/')}
            expected.update({'grants.gsr':journal[0][1],
                'node.gsr':f.encode('records','NODE',dict(root=cap['root'],identity=identity(int(node[5:])))),
                'allocator.gsr':f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=0)),
                'generations/a/generation.gsr':generation,
                'selector.gsr':f.encode('records','SELECTOR',dict(root=cap['root'],node=node,generation='a',digest=sha(generation)))})
        need(c.inventory(root/'originals'/node) == expected, 'partial joint exact conditional original: '+node)
        copies[node] = {name[len('generations/a/'):]:data for name,data in expected.items() if name.startswith('generations/a/')}
        references.append(dict(voter=node,generation=sha(generation),catalog=cap['catalog'],snapshot=cap['application']))
    joint.catalog.catalog.majority(cap['cut']['view'],list(NODES))
    proposal = f.encode('records','FLOOR',dict(root=cap['root'],node='node-1',cut=cap['cut'],sources=references))
    offered = {sha(m['generation.gsr']):m for m in copies.values()}
    events, files, writes, directories = joint.generation.floor.transaction(offered,proposal,handoff=True)
    at = position(events,case['ordinal'],case['cut'])
    interrupted = dict(initial,**{n:None for n,i in directories.items() if i <= at},**{n:v for n,v in files.items() if writes[n] <= at})
    for name in ('interrupted','after-close','after-reopen'):
        need(c.inventory(root/name) == interrupted, 'partial joint exact original cut: '+name)
    ordered = sorted(copies, key=lambda n:(n == 'node-1',sha(copies[n]['generation.gsr'])))
    need(ordered[-1] == 'node-1', 'partial joint local original last')
    completed = dict(initial,**{n:None for n in directories},**files)
    for name in ('completed','after-complete-close'):
        need(c.inventory(root/name) == completed, 'partial joint exact complete originals: '+name)
    first = read(root/'initial-events.json'); resumed = read(root/'resumed-events.json')
    joint.bounded(first,3+case['ordinal'],2+case['ordinal']); joint.bounded(resumed,7,6)
    need([r['event'] for r in first] == ['FLOOR_COPY_BEFORE_RETURN',*[r['event'] for r in events[:at+1]]], 'partial joint original force cut')
    wanted = sum((joint.resume.resume_events(copies[n]) for n in ('node-6','node-2','node-5','node-1')),[])+[r['event'] for r in events]
    need([r['event'] for r in resumed if r['event'].startswith('FLOOR_') and r['event'] != 'FLOOR_COPY_BEFORE_RETURN'] == wanted,
         'partial joint exact recovery force order')
    need(not any(r['event'].startswith(('PROMISE_','BASIS_','INSTALL_','SELECTED_')) for r in resumed), 'partial joint no grant before authority')
    exchanges = transfers(root,copies,cap,journal[-1][2]['ballot'])
    need(sum(n.endswith('.image') for n in completed) == 7 and h.inventory(root) == before, 'partial joint unchanged originals')
    return dict(status='PASS',ordinal=case['ordinal'],cut=case['cut'],incompleteOwner=ordered[case['ordinal']-1],
        reopenedSources=2+case['ordinal'],peakImages=7,peakSources=6,exchanges=exchanges,
        scope='conditional-joint-writer-cuts',nativeHistoryQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES = {
    'scope':'partial joint bounded scope', 'proposal':'partial joint exact original cut: interrupted',
    'cold-original':'partial joint exact original cut: after-reopen',
    'authority':'partial joint exact complete originals: completed',
    'premature-authority':'partial joint exact original cut: interrupted',
    'lost-promise-source':'partial joint exact complete originals: completed',
    'remote-original':'partial joint exact conditional original: node-2',
    'image-overflow':'joint floor bounded resource observations',
    'missing-force':'partial joint exact recovery force order',
    'original-cut':'partial joint original force cut',
    'lost-exchange':'generation request sequence',
}


def mutate(root,name):
    need(name in NEGATIVES,'partial joint declared mutation')
    if name == 'scope':
        case=read(root/'case.json');case['nativeRuntime']=True;h.save(root/'case.json',case)
    elif name == 'proposal': (root/'interrupted/floor-copies/proposal.gsr').write_bytes(b'changed')
    elif name == 'cold-original': (root/'after-reopen/unrelated').write_bytes(b'changed')
    elif name == 'authority': (root/'completed/floor-copies/floor.gsr').unlink()
    elif name == 'premature-authority': (root/'interrupted/floor-copies/floor.gsr').write_bytes((root/'completed/floor-copies/floor.gsr').read_bytes())
    elif name == 'lost-promise-source': shutil.rmtree(next((root/'completed/sources').iterdir()))
    elif name == 'remote-original': (root/'originals/node-2/generations/a/promise.gsr').write_bytes(b'changed')
    elif name == 'image-overflow':
        rows=read(root/'resumed-events.json');rows[-1]['usage']['counts']['APPLICATION']=8
        rows[-1]['usage']['leases']=sum(rows[-1]['usage']['counts'].values());h.save(root/'resumed-events.json',rows)
    elif name == 'missing-force':
        rows=read(root/'resumed-events.json');rows.pop(next(i for i,r in enumerate(rows) if r['event']=='FLOOR_RESUME_COPY_FORCED'));h.save(root/'resumed-events.json',rows)
    elif name == 'original-cut':
        rows=read(root/'initial-events.json');rows[0]['event']='FLOOR_RESERVED';h.save(root/'initial-events.json',rows)
    elif name == 'lost-exchange':
        rows=read(root/'wire.json');rows.pop(1);h.save(root/'wire.json',rows)


def qualify(root):
    root=Path(root);before=h.inventory(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-partial-joint-') as tmp:
            changed=Path(tmp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try: validate(changed)
            except ValueError as error:need(str(error)==reason,'partial joint unrelated rejection: '+name+': '+str(error))
            else:raise ValueError('partial joint accepted mutation: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(root)==before,'partial joint original changed')
    return dict(original=original,negatives=negatives)


def matrix(root, negatives=False):
    root=Path(root);before=h.inventory(root);results=[];seen=set()
    need(len(list(root.iterdir()))==16,'partial joint complete matrix')
    for path in sorted(root.iterdir()):
        result=qualify(path) if negatives else dict(original=validate(path));case=result['original'];key=(case['ordinal'],case['cut'])
        need(key not in seen,'partial joint duplicate case');seen.add(key);results.append(result)
        print(json.dumps(dict(ordinal=key[0],cut=key[1],status='PASS',negatives=len(result.get('negatives',[])))),file=sys.stderr,flush=True)
    need(seen=={(n,cut) for n in range(1,5) for cut in CUTS} and h.inventory(root)==before,'partial joint exact matrix and originals')
    return dict(status='PASS',cases=results,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(matrix(a.root,a.qualify),sort_keys=True))
