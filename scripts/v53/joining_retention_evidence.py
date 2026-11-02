"""Source-bound joining ledger derivation, not complete protocol qualification.

Reconstruct the seed from original old-voter packets, then the three revision-zero
ledgers and both native transaction files. File identities are recorded original
observations, never the inodes of relocated copies. Full capsule ancestry, force,
network provenance, and the later FINAL/BARRIER history are separate gates.
"""
import argparse
import base64
import copy
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import joining_snapshot as snapshot
from . import source_packet as packet
from . import peer_retention_source_evidence as peer_source
from . import learner_retention_evidence as learner
from . import future_retention_evidence as future
from . import carried_publication_evidence as physical
from . import joining_confirmation_evidence as confirmations

f, need, sha = snapshot.f, snapshot.need, snapshot.s.digest
MIB = snapshot.MIB
LEDGERS = ('peer-retention.gspr', 'future-retention.gsft', 'learner-retention.gslr')
DECISION, DONE = 'joining-retention.gsjr', 'joining-retention.done.gsjr'
SCHEMA = 'gse-v53-joining-retention-seed/1.3'


def parts(raw, bounds):
    values=[];pos=0
    for maximum in bounds:
        need(pos+4<=len(raw), 'joining derivation missing member')
        size=int.from_bytes(raw[pos:pos+4], 'big');pos+=4
        need(0<size<=maximum and size<=len(raw)-pos, 'joining derivation member extent')
        values.append(raw[pos:pos+size]);pos+=size
    need(pos==len(raw), 'joining derivation trailing members')
    return values


def part(raw):return struct.pack('>I',len(raw))+raw


def frozen(raw, magic, maximum):
    need(type(raw) is bytes and 56<len(raw)<=48+8+8192+maximum, 'joining derivation wrapper extent')
    need(struct.unpack('>IHHII',raw[:16])==(magic,1,3,0,len(raw)-48), 'joining derivation settled wrapper')
    need(raw[16:48]==bytes.fromhex(sha(raw[:16]+raw[48:])), 'joining derivation wrapper checksum')
    promise,ledger=parts(raw[48:],[8192,maximum]);value=f.decode(promise,'records','PROMISE')
    need(value['basisId'] is not None, 'joining derivation original promise')
    state=(peer_source.r.decode if magic==0x47535250 else learner.decode)(ledger)
    return value,state


def source(packet_value, basis, magic, maximum):
    found=[]
    for raw in packet_value['objects'].values():
        if raw[:4]!=struct.pack('>I',magic):continue
        promise,state=frozen(raw,magic,maximum)
        if promise['basisId']!=basis['basisId']:continue
        need(all(promise[k]==basis[k] for k in ('root','view','ballot','basisId')), 'joining derivation promise binding')
        found.append((raw,state))
    need(len(found)==1, 'joining derivation unique frozen ledger')
    return found[0]


def points(rows, *, empty=False):
    need(type(rows) is list and (0 if empty else 1)<=len(rows)<=2, 'joining derivation endpoint count')
    prior=-1;result={}
    for row in rows:
        need(type(row) is dict and set(row)=={'cut','catalog','application'}, 'joining derivation endpoint fields')
        for key,kind in [('cut','cut'),('catalog','hash'),('application','hash')]:f.check_type(row[key],kind,f.catalog()['types'])
        index=row['cut']['index'];need(prior<index<=2**63-2, 'joining derivation endpoint order');prior=index
        result[index]=copy.deepcopy(row)
    return result


def union(target, rows):
    for index,row in rows.items():
        need(index not in target or target[index]==row, 'joining derivation conflicting endpoint')
        target[index]=row
    need(len(target)<=2, 'joining derivation conservative endpoint capacity')


def derive(current, joining, originals, *, confirmed_peers=False, source_ancestry=None):
    """Conditional on the supplied original capsule history; never a vote/permit."""
    cap=current['capsule'];view=cap['cut']['view'];root=cap['root']
    catalog=f.decode(current['objects'][cap['catalog']],'records','CATALOG')
    identities={v['node']:v for v in catalog['identities']}
    old=view['old'];new=view['new'];voters=sorted(set(old)|set(new))
    need(old==sorted(set(old)) and new==sorted(set(new)) and 3<=len(old)<=5 and 3<=len(new)<=5
         and len(voters)<=6 and len(set(new)-set(old))==1 and len(set(old)-set(new))<=1
         and len(identities)==len(catalog['identities']) and set(voters)<=set(identities), 'joining derivation membership')
    need(view['operation'] is not None and joining['node'] not in old and joining['node'] in new
         and identities.get(joining['node'])==joining, 'joining derivation exact new identity')
    need(type(originals) in (list,tuple) and len(old)//2<len(originals)<=min(5,len(old)), 'joining derivation old majority')
    need(source_ancestry is None or confirmed_peers and len(source_ancestry)==len(originals), 'joining derivation ancestry inputs')
    prior='';ballot=None;rows=[];peers={node:{} for node in voters};learners={};bound=None;peer_plans=[]
    for basis_raw,packet_raw in originals:
        basis=f.decode(basis_raw,'records','BASIS');node=basis['voter']
        need(node>prior and node in old, 'joining derivation ordered old owners');prior=node
        need(basis['accepted'] is None, 'joining derivation unsettled tail')
        need(basis['root']==root and basis['cut']==cap['cut'], 'joining derivation original source cut')
        vote=basis['ballot'];proposer=identities.get(vote['proposer'])
        need(vote['proposer'] in old and proposer['storage']==vote['incarnation'] and 0<vote['counter']<=2**63-2,
             'joining derivation old proposer')
        need(ballot is None or ballot==vote, 'joining derivation mixed ballots');ballot=vote
        original=packet.decode(packet_raw);packet.bind(original,basis_raw)
        need(all(original['capsule'][k]==cap[k] for k in ('catalog','application')), 'joining derivation original endpoint')
        peer_bytes,peer=source(original,basis,0x47535250,65536)
        learner_bytes,nonvoting=source(original,basis,0x47534c46,32768)
        need(all(state['root']==root and state['owner']==identities[node] for state in (peer,nonvoting)), 'joining derivation frozen owner')
        plan=peer['plan']
        need(set(plan)=={'root','view','peers'} and plan['root']==root and plan['view']==view
             and type(plan['peers']) is list and len(plan['peers'])==len(voters), 'joining derivation peer plan')
        if confirmed_peers:
            confirmations.confirmed.plan(plan);peer_plans.append(plan)
        else:
            for expected,row in zip(voters,plan['peers']):
                need(type(row) is dict and set(row)=={'identity','possible'} and row['identity']==identities[expected], 'joining derivation peer identity')
                union(peers[expected],points(row['possible']))
        plan=nonvoting['plan'];learner.plan(plan)
        if plan['request'] is not None:
            operations=[r['request'] for r in catalog['results'] if r['request']['number']==plan['request']['number']]
            need(plan['learner']==joining and operations==[plan['request']], 'joining derivation learner operation')
            identity=(plan['request'],plan['learner'])
            need(bound is None or bound==identity, 'joining derivation learner binding');bound=identity
            # Decoded confirmations never discharge a lower original endpoint.
            union(learners,points(plan.get('renewals',[]),empty=True));union(learners,points(plan['possible']))
        if source_ancestry is not None:
            confirmations.bind_endpoints(original,source_ancestry[len(rows)],peer['plan'],plan)
        row=dict(basis=base64.b64encode(basis_raw).decode(),
                 envelope=base64.b64encode(part(original['capsuleBytes'])+part(original['indexBytes'])).decode(),
                 peers=base64.b64encode(peer_bytes).decode(),learner=base64.b64encode(learner_bytes).decode())
        need(len(f.canonical(row))<=2*MIB, 'joining derivation fragment capacity');rows.append(row)
    peer_plan=dict(root=root,view=view,peers=[dict(identity=identities[n],possible=[peers[n][k] for k in sorted(peers[n])]) for n in voters])
    if confirmed_peers:peer_plan=confirmations.merge(peer_plans,current,identities,list(learners.values()))
    learner_plan=dict(root=root,request=bound[0] if bound else None,learner=bound[1] if bound else None,
                      possible=[learners[k] for k in sorted(learners)])
    anchors={cap['cut']['index']:{k:cap[k] for k in ('cut','catalog','application')}}
    for point in [p for row in peer_plan['peers'] for p in row['possible']]+learner_plan['possible']:
        index=point['cut']['index']
        need(index<=cap['cut']['index'] and (index not in anchors or anchors[index]==point), 'joining derivation inconsistent history endpoint')
        anchors[index]=point
    need(len(f.canonical(peer_plan))<=32768, 'joining derivation peer capacity');learner.plan(learner_plan)
    seed=f.canonical(dict(schema=SCHEMA,root=root,joining=joining,cut=cap['cut'],catalog=cap['catalog'],application=cap['application'],sources=rows))
    need(len(seed)<=8*MIB, 'joining derivation seed capacity')
    metadata=dict(root=root,owner=joining,revision=0,previous=None)
    initial={LEDGERS[0]:peer_source.r.frame(dict(metadata,plan=peer_plan)),
             LEDGERS[1]:future.frame(dict(metadata,parent=None,peers=[]),{}),
             LEDGERS[2]:learner.frame(dict(metadata,plan=learner_plan))}
    return seed,initial


def framed(magic, body):
    return struct.pack('>IHHI',magic,1,3,44+len(body))+bytes.fromhex(sha(body))+body


def transaction_frames(snap, seed, initial):
    """Derive transaction bytes using retained original identities, never copy inodes."""
    read=lambda family,name:snapshot.s.e.parse(snap.member(family,name))
    identity=lambda family,name:next(v['identity'] for v in snap.identities[family]['files'] if v['name']==name)
    joined=read('placement','joined.json');native=read('nativeOwner','native.json')
    need(joined['schema']=='gse-v53-joined-admission/1.3' and native['schema']=='gse-v53-native-joining/1.3'
         and all(native[k]==joined[k] for k in ('root','plan','identity')), 'joining derivation native admission')
    need(native['path']==snap.identities['nativeOwner']['path']
         and native['directoryKey']==identity('nativeOwner','.')['key']
         and native['recordKey']==identity('nativeOwner','native.json')['key']
         and joined['recordKey']==identity('placement','joined.json')['key']
         and joined['replica']==snap.identities['replica']['path'], 'joining derivation original native identities')
    decoded=snapshot.s.e.parse(seed)
    need(decoded['root']==joined['root'] and decoded['joining']==joined['identity'] and decoded['cut']==joined['cut'], 'joining derivation installed cut')
    binding=dict(plan=joined['plan'],native=sha(snap.member('nativeOwner','native.json')),
                 nativeKey=identity('nativeOwner','native.json')['key'],generation=joined['generation'],cut=joined['cut'])
    metadata=dict(schema='gse-v53-joining-retention/1.3',root=joined['root'],owner=joined['identity'],native=binding,
                  fileKey=identity('replica',DECISION)['key'])
    decision=framed(0x47534a52,part(f.canonical(metadata))+part(seed)+b''.join(part(initial[n]) for n in LEDGERS))
    done=dict(metadata,schema='gse-v53-joining-retention-done/1.3',fileKey=identity('replica',DONE)['key'],
              seed=sha(decision),seedKey=metadata['fileKey'],files=[dict(name=n,sha256=sha(initial[n])) for n in LEDGERS])
    return {DECISION:decision,DONE:framed(0x47534a44,f.canonical(done)),**initial}


def transaction(snap, seed, initial):
    """Compare bytes to independently derived expectations, including original keys."""
    expected=transaction_frames(snap,seed,initial)
    need(snap.member('replica',DECISION)==expected[DECISION], 'joining derivation exact original decision')
    need(snap.member('replica',DONE)==expected[DONE], 'joining derivation exact original completion')
    names={v['name'] for v in snap.identities['replica']['files']}
    need(not names & {'joining-retention.next.gsjr','joining-retention.done.next.gsjr','peer-retention.next.gspr',
                      'future-retention.next.gsft','learner-retention.next.gslr'}, 'joining derivation incomplete transaction')
    for name in LEDGERS:need(snap.member('replica',name)==initial[name], 'joining derivation exact initial ledger: '+name)


def original_derivation(root, snap, *, confirmed_peers=False):
    """Read the old majority's original grants, source packets and endpoint ancestry."""
    root=Path(root)
    files={v['name']:snap.member('replica',v['name']) for v in snap.identities['replica']['files'] if 'directory' not in v['identity']}
    prefix,_,current=physical.current(files);joining=f.decode(files['node.gsr'],'records','NODE')['identity']
    joined=snapshot.s.e.parse(snap.member('placement','joined.json'))
    need(sha(files[prefix+'generation.gsr'])==joined['generation'], 'joining derivation original installed generation')
    paths=sorted(root.glob('joining-retention-node-*.gsr'))
    need(2<=len(paths)<=5 and {p.stem for p in paths}=={p.stem for p in root.glob('joining-retention-node-*.gscp')},
         'joining derivation retained source count');originals=[];ancestry=[]
    identities={v['node']:v for v in f.decode(current['objects'][current['capsule']['catalog']],'records','CATALOG')['identities']}
    for path in paths:
        raw=snapshot.s.regular(path,16384);basis=f.decode(raw,'records','BASIS');node=basis['voter']
        need(path.name=='joining-retention-'+node+'.gsr', 'joining derivation original source name')
        data=snapshot.s.regular(path.with_suffix('.gscp'),32*MIB)
        original=physical.inventory(root/'before-joint-continuation'/node)
        need(f.decode(original['node.gsr'],'records','NODE',basis['root'])['identity']==identities.get(node), 'joining derivation original journal owner')
        rows=physical.journal(original['grants.gsr'],basis['root'],node)
        need(sum(kind=='BASIS' and value==raw for kind,value,_ in rows)==1, 'joining derivation original grant absent')
        need(original.get('sources/'+basis['basisId']+'/source.gscp')==data, 'joining derivation original source absent')
        if confirmed_peers:
            _,members,current_source=physical.current(original)
            cap=packet.decode(data)['capsule']
            need(all(current_source['capsule'][k]==cap[k] for k in ('root','cut','catalog','application')),
                 'joining derivation original ancestry cut')
            ancestry.append(members.get('ancestry.gsr',b''))
        originals.append((raw,data))
    seed,initial=derive(current,joining,originals,confirmed_peers=confirmed_peers,
                        source_ancestry=ancestry if confirmed_peers else None)
    return seed,initial,len(originals)


def validate(root, *, confirmed_peers=False):
    root=Path(root);snap=snapshot.read(root/'joining-originals-native')
    seed,initial,count=original_derivation(root,snap,confirmed_peers=confirmed_peers)
    transaction(snap,seed,initial)
    return dict(status='PARTIAL',scope='original-source-bound-joining-ledgers',oldSources=count,
                seedSha256=sha(seed),initialLedgers={n:sha(v) for n,v in initial.items()},
                originalSourceBindingsVerified=True,initialLedgerBytesVerified=True,
                confirmedPeerProjection=confirmed_peers,originalEndpointBindingsVerified=confirmed_peers,
                capsuleAncestryQualified=False,forceAndNetworkQualified=False,nativeHistoryQualified=False,phase3Complete=False)


def mutate(root, name):
    """Rewrite copied inventory too, so semantic negatives reach the next layer."""
    snap=root/'joining-originals-native';replica=snap/'replica'
    def replace(member, raw):
        (replica/member).write_bytes(raw)
        rows=json.loads((snap/'inventory.json').read_bytes())
        row=next(v for v in rows if v['name']=='replica')
        identity=next(v['identity'] for v in row['files'] if v['name']==member)
        identity.update(size=len(raw),sha256=sha(raw));(snap/'inventory.json').write_bytes(f.canonical(rows))
    if name=='decision-checksum':
        raw=(replica/DECISION).read_bytes();replace(DECISION,raw[:12]+b'\0'*32+raw[44:])
    elif name=='decision-key':
        values=parts((replica/DECISION).read_bytes()[44:],[16384,8*MIB,65536,16384,32768])
        value=json.loads(values[0]);value['fileKey']='forged-original-key';values[0]=f.canonical(value)
        replace(DECISION,framed(0x47534a52,b''.join(part(v) for v in values)))
    elif name in ('completion-key','completion-hash'):
        value=json.loads((replica/DONE).read_bytes()[44:]);value['seedKey' if name.endswith('key') else 'seed']='f'*64
        replace(DONE,framed(0x47534a44,f.canonical(value)))
    elif name in ('peer-owner','drop-peer-uncertainty'):
        value=peer_source.r.decode((replica/LEDGERS[0]).read_bytes())
        if name=='peer-owner':value['owner']['storage']='00000000-0000-0000-0000-000000000099'
        else:value['plan']['peers'][-1]['possible']=[]
        replace(LEDGERS[0],peer_source.r.frame(value))
    elif name in ('peer-confirmation-missing','peer-confirmation-changed'):
        value=peer_source.r.decode((replica/LEDGERS[0]).read_bytes())
        rows=[v for v in value['plan']['peers'] if 'confirmation' in v]
        need(bool(rows),'negative requires original peer confirmation');row=rows[0]
        if name.endswith('missing'):row.pop('confirmation')
        else:
            proof=f.decode(base64.b64decode(row['confirmation'],validate=True),'records','GENERATION')
            proof['generation']='a' if proof['generation']=='b' else 'b'
            row['confirmation']=base64.b64encode(f.encode('records','GENERATION',proof)).decode()
        replace(LEDGERS[0],peer_source.r.frame(value))
    elif name=='learner-empty':
        value=learner.decode((replica/LEDGERS[2]).read_bytes());value['plan']=dict(root=value['root'],request=None,learner=None,possible=[])
        replace(LEDGERS[2],learner.frame(value))
    elif name=='future-revision':
        node=f.decode((replica/'node.gsr').read_bytes(),'records','NODE')
        replace(LEDGERS[1],future.frame(dict(root=node['root'],owner=node['identity'],revision=1,previous='f'*64,parent=None,peers=[]),{}))
    elif name=='copied-inode':
        rows=json.loads((snap/'inventory.json').read_bytes());row=next(v for v in rows if v['name']=='replica')
        next(v['identity'] for v in row['files'] if v['name']==DECISION)['key']='copied-inode-is-not-original'
        (snap/'inventory.json').write_bytes(f.canonical(rows))
    elif name in ('source-missing','grant-missing','journal-owner'):
        path=sorted(root.glob('joining-retention-node-*.gsr'))[0];raw=path.read_bytes();basis=f.decode(raw,'records','BASIS')
        original=root/'before-joint-continuation'/basis['voter']
        if name=='source-missing':(original/'sources'/basis['basisId']/'source.gscp').unlink()
        elif name=='grant-missing':
            path=original/'grants.gsr';value=path.read_bytes();need(value.count(raw)==1,'negative original grant count');path.write_bytes(value.replace(raw,b''))
        else:
            path=original/'node.gsr';node=f.decode(path.read_bytes(),'records','NODE');node['identity']['storage']='00000000-0000-0000-0000-000000000099';path.write_bytes(f.encode('records','NODE',node))
    elif name=='source-orphan':sorted(root.glob('joining-retention-node-*.gscp'))[-1].unlink()
    else:raise ValueError('unknown joining derivation negative')


NEGATIVES = {
    'decision-checksum':'joining derivation exact original decision',
    'decision-key':'joining derivation exact original decision',
    'completion-key':'joining derivation exact original completion',
    'completion-hash':'joining derivation exact original completion',
    'peer-owner':'joining derivation exact initial ledger: '+LEDGERS[0],
    'drop-peer-uncertainty':'joining derivation exact initial ledger: '+LEDGERS[0],
    'learner-empty':'joining derivation exact initial ledger: '+LEDGERS[2],
    'future-revision':'joining derivation exact initial ledger: '+LEDGERS[1],
    'copied-inode':'joining derivation exact original decision',
    'source-missing':'joining derivation original source absent',
    'grant-missing':'joining derivation original grant absent',
    'journal-owner':'joining derivation original journal owner',
    'source-orphan':'joining derivation retained source count',
}
CONFIRMATION_NEGATIVES = {
    'peer-confirmation-missing':'joining derivation exact initial ledger: '+LEDGERS[0],
    'peer-confirmation-changed':'joining derivation exact initial ledger: '+LEDGERS[0],
}


def qualify(root, *, confirmed_peers=False):
    validate_mode=lambda path:validate(path,confirmed_peers=True) if confirmed_peers else validate(path)
    original=validate_mode(root);results=[]
    cases=NEGATIVES | (CONFIRMATION_NEGATIVES if confirmed_peers else {})
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-ledger-negative-') as directory:
            copied=Path(directory)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate_mode(copied)
            except ValueError as error:need(str(error)==reason,'joining derivation negative wrong rejection: '+str(error))
            else:raise ValueError('joining derivation negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results,status='PARTIAL',phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--confirmed-peers',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root,confirmed_peers=args.confirmed_peers),sort_keys=True))
