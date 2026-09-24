"""Independent byte/force/transport/prefix oracle for the 512-slot component gate.

No product/fixture encoder is imported. This is deliberately not an election,
public-history linearizability, transfer-lifetime or cloud-performance oracle.
"""
import argparse
import copy
from pathlib import Path
from . import performance_model as m, performance_plan as plan, performance_projection as projection
from . import cloud_workload_contract as cloud
from . import format_inspector as fmt, recovery_inspector as recovery, storage_inspector as storage
from . import performance_semantics as semantics, performance_evidence as provenance
from . import remote_collection as collection
from .remote_rich_evidence import EvidenceLocation

NODES=('node-1','node-2','node-3')
SCHEMA='gse-v51-full-size-v1'
need=m.need
raw=projection.raw


def read(path):
    path=Path(path);need(path.is_file() and not path.is_symlink() and path.stat().st_size<=32<<20,'full-size member bound')
    return path.read_bytes()


def json(path):return m.strict_json(read(path))


def journal(data,kind,manifest):
    result=[];offset=0
    while offset<len(data):
        need(offset+48<=len(data),'full-size torn journal')
        size=48+int.from_bytes(data[offset+12:offset+16],'big',signed=True)
        need(48<size<=1<<20 and offset+size<=len(data),'full-size journal extent')
        encoded=data[offset:offset+size];row=fmt.contextual_frame(encoded,'JOURNAL' if offset==0 else kind,manifest)
        if offset:result.append(encoded)
        offset+=size
    need(offset>0,'full-size empty journal');return result


def documents(state):return [list(state.documents[key]) for key in sorted(state.documents)]


def facts(root,events=None,overrides=None):
    root=Path(root);overrides=overrides or {}
    def member(name):return overrides[name] if name in overrides else read(root/name)
    manifest_bytes=member('group/node-1/manifest.gsr');genesis_bytes=member('group/node-1/genesis.gsr')
    manifest=dict(fmt.inspect(manifest_bytes,'MANIFEST'),digest=manifest_bytes[16:48].hex())
    events=events if events is not None else [m.strict_json(line) for line in member('events.jsonl').splitlines()]
    need(len(events)<=20000 and [r['serial'] for r in events]==list(range(1,len(events)+1)), 'full-size event order')
    need(all(a['nanos']<=b['nanos'] for a,b in zip(events,events[1:])), 'full-size event clock')
    forced={r['serial']:r for r in events if r['event']=='force'}
    votes={node:[] for node in NODES};proofs={node:[] for node in NODES};used=set();seen_votes=set()
    # Records claimed as forced must also occur in a retained actual journal.
    retained={}
    for node in NODES[:2]:
        for kind,filename in [('accept','accepted.gsr'),('proof','proofs.gsr')]:
            rows=[]
            for name in ('before-reproposal','two-generations'):
                for prefix in ('','generation-a/','generation-b/'):
                    path=f'{name}/{node}/{prefix}{filename}'
                    if (root/path).is_file():rows+=journal(member(path),'ACCEPT' if kind=='accept' else 'PROOF',manifest)
            retained[node,kind]=set(rows)
    for event in events:
        kind=event['event']
        if kind not in ('accept','proof'):continue
        node=event['node'];need(node in NODES[:2],'full-size vote owner')
        f=forced.get(event['force']);need(f is not None and event['force'] not in used and f['serial']<event['serial'] and
            f['node']==node and f['cut']==kind.upper()+'_AFTER_FORCE','full-size actual force boundary');used.add(event['force'])
        encoded=raw(event['record']);need(encoded in retained[node,kind],'full-size forced record absent from journal')
        value=fmt.contextual_frame(encoded,kind.upper(),manifest)
        index=fmt.inspect(raw(value['entry']),'ENTRY')['index'] if kind=='accept' else value['index']
        digest=value['entryDigest'] if kind=='accept' else m.sha(encoded)
        need(event['receipt']==fmt.receipt('ACCEPT_ACK' if kind=='accept' else 'PROOF_ACK',manifest['digest'],node,
              value['epoch'],value['proposer'],value['incarnation'],index,digest),'full-size force receipt')
        if kind=='accept':votes[node].append(encoded);seen_votes.add((node,event['receipt']))
        else:
            need(all((r['voter'],r['digest']) in seen_votes for r in value['receipts']),'full-size proof before acceptance quorum')
            proofs[node].append(encoded)
    need([len(votes[n]) for n in NODES]==[513,513,0] and [len(proofs[n]) for n in NODES]==[512,512,0],
         'full-size exact force counts')
    projected=projection.project_cloud(manifest_bytes,genesis_bytes,votes)
    need(len(projected['chosen'])==512,'full-size actual slot coverage')
    for index,digest in projected['chosen'].items():
        entry=projected['entries'][digest]
        need(entry['originEpoch']==2 and entry['operation']==(9 if index==1 else 2),'full-size entry schedule')
        if index>1:
            command=m.decode_command(2,raw(entry['payload']));key=1+(index-2)%64;doc=m.document(key,1+(index-2)//64)
            need(command==[(key,doc)],'full-size rich update schedule')
    for node in NODES[:2]:
        accepted=[fmt.inspect(v,'ACCEPT') for v in votes[node]]
        need([v['epoch'] for v in accepted]==[2]*512+[5] and accepted[-1]['entry']==accepted[-2]['entry'],
             'full-size same-slot reproposal')
        need([fmt.inspect(p,'PROOF')['index'] for p in proofs[node]]==list(range(1,513)),'full-size proof coverage')
    complete=member('snapshot-512.gsr');projection.snapshot(projected,complete)
    need(len(fmt.inspect(complete,'SNAPSHOT')['anchors'])==512,'full-size snapshot cut')
    bases={}
    for phase,cut,accepted in [('pending-basis',511,True),('full-basis',512,False)]:
        pair=[]
        for node in NODES[:2]:
            descriptor=member(f'{phase}/{node}-basis.gsr');image=member(f'{phase}/{node}-image.gsr')
            b=recovery.basis(descriptor,image,manifest);pair.append(b)
            need(b[0]['node']==node and len(b[1]['anchors'])==cut and (b[2] is not None)==accepted,'full-size frozen basis cut')
            projection.snapshot(projected,raw(fmt.inspect(image,'IMAGE')['snapshot']))
        bases[phase]=pair
    for node in NODES[:2]:
        selected=fmt.contextual_frame(member(f'selected/{node}.gsr'),'SELECTED',manifest)
        recovery.select(selected,bases['pending-basis'],manifest)
        need(selected['prefixIndex']==511 and selected['nextEntry']==fmt.inspect(votes[node][-1],'ACCEPT')['entry'],
             'full-size selected reproposal')
    # Only actual sender/receiver callbacks can substantiate a successful exchange.
    observations={}
    for e in events:
        if e['event']=='transport':observations.setdefault((e['request'],e['response']),[]).append(e)
    basis_chunks={};transferred=bytearray();offer=None;installed=False;wire_peak=0
    for e in events:
        if e['event']!='wire':continue
        request,response=raw(e['request']),raw(e['response']);wire_peak=max(wire_peak,len(request),len(response))
        need(max(len(request),len(response))<=1<<20,'full-size wire bound')
        q,a=fmt.wire(request,manifest),fmt.wire(response,manifest)
        need(all(q[k]==a[k] for k in ('traceId','eventSequence','epoch','proposer','incarnationId','manifestDigest')) and
             (q['sender'],q['recipient'])==(a['recipient'],a['sender']),'full-size wire correlation')
        observed=observations.get((e['request'],e['response']),[])
        need(len(observed)==2 and [(r['node'],r['cut']) for r in observed]==[(q['recipient'],'BEFORE_RESPONSE_WRITE'),(q['sender'],'AFTER_RESPONSE_READ')] and
             e['startNanos']<=observed[0]['nanos']<=observed[1]['nanos']<=e['nanos'],'full-size actual TCP exchange')
        p,r=q['payload'],a['payload'];kind=q['type']
        if kind=='BASIS_CHUNK':
            need(a['type']==kind and r['action']=='DATA' and r['basisId']==p['basisId'] and r['offset']==p['offset'] and
                 p['maxChunkBytes']==r['maxChunkBytes']==4096,'full-size basis chunk identity')
            b=basis_chunks.setdefault(p['basisId'],bytearray());need(p['offset']==len(b),'full-size basis chunk continuity');b.extend(raw(r['chunk']))
        elif kind=='SNAPSHOT_OFFER':
            need(offer is None and r==dict(p,response=True),'full-size transfer offer');offer=p
        elif kind=='SNAPSHOT_CHUNK':
            need(offer is not None and not installed and p['transferId']==offer['transferId'] and p['offset']==len(transferred) and
                 p['maxChunkBytes']==4096 and r==dict(p,action='ACK',chunk=''),'full-size transfer chunk continuity')
            transferred.extend(raw(p['chunk']))
        elif kind=='REJOIN_INSTALL':
            need(not installed and offer is not None and p['transferId']==offer['transferId'] and p['imageDigest']==offer['imageDigest'] and
                 r==dict(p,response=True),'full-size transfer installation');installed=True
        else:need(kind=='PREPARE' and a['type']=='PROMISE' and r['nonce']==p['nonce'],'full-size wire type')
    need(len(basis_chunks)==2,'full-size basis transfer count')
    for phase in bases:
        descriptor=bases[phase][1][0];image=member(f'{phase}/node-2-image.gsr')
        need(bytes(basis_chunks.get(descriptor['basisId'],b''))==image,'full-size complete basis transfer')
    image=member('transfer-image.gsr');value=fmt.contextual_frame(image,'IMAGE',manifest)
    need(installed and bytes(transferred)==image and offer['imageBytes']==len(image) and offer['imageDigest']==image[16:48].hex() and
         raw(value['snapshot'])==complete and not value['acceptances'],'full-size complete snapshot transfer')
    pins=[r for r in events if r['event'] in ('pin-captured','pin-released')]
    need(len(pins)==2 and [r['event'] for r in pins]==['pin-captured','pin-released'] and
         all(r['index']==511 and r['documents']==documents(projected['states'][511]) for r in pins),'full-size pinned read')
    archives={r['name']:r['serial'] for r in events if r['event']=='archive'}
    need(pins[0]['serial']<archives['two-generations']<archives['after-cleanup']<pins[1]['serial'],'full-size cleanup while pinned')
    for node in NODES:
        floors=[r['serial'] for r in events if r['event']=='force' and r['node']==node and r['cut']=='FLOOR_AFTER_FORCE']
        deletes=[r['serial'] for r in events if r['event']=='force' and r['node']==node and r['cut'].startswith('DELETE_AFTER')]
        need(len(floors)==1 and deletes and pins[0]['serial']<floors[0]<min(deletes)<=max(deletes)<archives['after-cleanup'],
             'full-size floor before deletion')
    for kind in ('final-read','reopened'):
        rows=[r for r in events if r['event']==kind]
        need([r['node'] for r in rows]==list(NODES) and all(r['index']==512 and r['sequence']==515 and
             r['documents']==documents(projected['states'][512]) and r['serial']>pins[1]['serial'] for r in rows),'full-size '+kind)
    return dict(status='PASS',slots=512,acceptanceForces=1026,proofForces=1024,reproposalSlot=512,
                applicationSequence=515,basisBytes=[len(member(f'{p}/node-2-image.gsr')) for p in bases],
                transferBytes=len(image),wirePeakBytes=wire_peak)


def validate(root):
    root=Path(root).resolve();execution=json(root/'execution.json');admitted=plan.load(root/'plan.json')
    need(execution['schema']==SCHEMA and execution['status']=='EXECUTED' and execution['execution']=='local-component-boundaries' and
         execution['paidCloud'] is False and execution['fullRemoteQualification'] is False,'full-size qualification scope')
    EvidenceLocation(root,execution['root'])  # Validate the complete inventory before relocated inspection.
    members=storage.inventory(root);need(len(members)<=16000 and sum(v['size'] for v in members.values())<=8<<30 and
         max(v['size'] for v in members.values())<=32<<20,'full-size evidence limits')
    adapters=execution['adapters'];original=Path(execution['root'])
    need(set(adapters)=={'published-v4.4-local','published-v5.0-configured','candidate-v5.1-automatic'},'full-size adapter set')
    commands={
        'prepare-source':('published-v4.4-local','admission.V51MeasuredLocal',[original,'prepare',original/'plan.json',original/'source']),
        'bootstrap':('candidate-v5.1-automatic','admission.V51MeasuredAutomatic',[original/'group','setup',original/'plan.json',original/'source']),
        'boundaries':('candidate-v5.1-automatic','replication.V51FullSizeBoundary',[original])}
    for label,(mode,main,args) in commands.items():
        process=json(root/(label+'.json'))
        need(process['exitCode']==0 and 0<process['endNanos']-process['startNanos']<=90_000_000_000 and
             process['args']==['java',*admitted['jvmArguments'],'-cp',adapters[mode]['cp'],
                              'io.github.patricklfdm.generalsearch.'+main,*map(str,args)],
             'full-size process provenance')
    source=json(root/'source-inventory.json');need(m.sha(read(root/'source-inventory.json'))==execution['sourceInventorySha256'],'full-size source inventory')
    pinned={a['artifact']+'-'+a['version']+'.jar':a['sha256'] for a in admitted['publishedControls']['artifacts']}
    for mode,adapter in execution['adapters'].items():provenance.artifacts(root,mode,adapter,pinned,source)
    backup=semantics.source_backup(root/'source',m.initial(admitted));need(backup==execution['sourceBackup'],'full-size source backup')
    genesis=fmt.inspect(read(root/'group/node-1/genesis.gsr'),'GENESIS')
    source_inventory=[dict(path=p,kind=1,**v) for p,v in storage.inventory(root/'source').items()]
    need(genesis['sourceDigest']==m.sha(m.canonical(source_inventory)),'full-size bootstrap source')
    binding=fmt.inspect(read(root/'group/operation/bootstrap-binding.gsr'),'BOOTSTRAP_BINDING')
    descriptor=m.strict_json(raw(binding['descriptor']));frozen=cloud.load()
    need(descriptor['sourceInventory']==source_inventory and [v['node'] for v in descriptor['replicas']]==list(NODES),
         'full-size bootstrap members')
    for replica in descriptor['replicas']:
        need(replica['replicationBounds']==frozen['replicationBounds'] and
             replica['materialization']['bounds']=={k:frozen['application'][k] for k in ('checkpointWalBytes','maxBulkElements','maxDerivedStateBytes','maxDocuments',
                 'maxEncodedDocumentBytes','maxEncodedKeyBytes','maxRetainedBytes')},
             'full-size frozen resource limits')
    result=facts(root);peaks=[]
    complete=read(root/'snapshot-512.gsr');anchors=fmt.inspect(complete,'SNAPSHOT')['anchors']
    snapshots={512:complete,511:raw(fmt.inspect(read(root/'pending-basis/node-1-image.gsr'),'IMAGE')['snapshot'])}
    for stage in ('before-reproposal','two-generations','after-cleanup','group'):
        for node in NODES:
            directory=root/stage/node
            # Archived authority retains its original sealed path. Never open it as a voter.
            original=Path(execution['root'])/'group'/node
            report=storage._inspect(directory,64<<20,1<<20,original)
            peaks.append(report['retainedBytes'])
            expected=511 if stage=='before-reproposal' else 512
            if node=='node-3' and stage in ('before-reproposal','two-generations'):expected=0
            need(report['provenThrough']==expected and report['acceptedDigests']==
                 [v['entryDigest'] for v in anchors[:report['acceptedThrough']]],'full-size retained prefix')
            for path in directory.glob('generation-*/snapshot.gsr'):
                encoded=read(path);cut=len(fmt.inspect(encoded,'SNAPSHOT')['anchors'])
                need(encoded==snapshots.get(cut),'full-size retained application image')
            if stage=='two-generations' and node in NODES[:2]:
                cuts=sorted(len(fmt.inspect(read(directory/g/'snapshot.gsr'),'SNAPSHOT')['anchors']) for g in ('generation-a','generation-b'))
                need(cuts==[511,512],'full-size two retained generations')
            if stage in ('after-cleanup','group'):
                need(sum((directory/g).exists() for g in ('generation-a','generation-b'))==1 and
                     (directory/'recovery-floor.gsr').is_file() and not (directory/'transfer/retiring').exists(),'full-size floor cleanup')
    result['retainedPeakBytes']=max(peaks);return result


def negatives(root):
    # Baseline must pass; unrelated invalid input cannot count as successful rejection.
    validate(root);events=[m.strict_json(line) for line in read(Path(root)/'events.jsonl').splitlines()];results=[]
    def reject(name,reason,changed=None,overrides=None):
        try:facts(root,changed,overrides)
        except ValueError as e:
            need(str(e)==reason,'unrelated full-size negative: '+name+': '+str(e));results.append(dict(case=name,status='REJECTED',reason=reason));return
        raise ValueError('full-size mutation accepted: '+name)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='accept')['force']=0
    reject('missing-force','full-size actual force boundary',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='proof')['receipt']='0'*64
    reject('wrong-receipt','full-size force receipt',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='transport')['cut']='UNOBSERVED'
    reject('missing-peer','full-size actual TCP exchange',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='pin-released')['index']=512
    reject('changed-pinned-cut','full-size pinned read',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='pin-released')['documents'][0][1]='changed'
    reject('changed-pinned-answer','full-size pinned read',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='reopened')['index']=511
    reject('short-reopen','full-size reopened',changed)
    changed=copy.deepcopy(events);next(r for r in changed if r['event']=='force' and r['cut']=='FLOOR_AFTER_FORCE')['cut']='UNOBSERVED'
    reject('missing-floor-force','full-size floor before deletion',changed)
    changed=copy.deepcopy(events);[r for r in changed if r['event']=='accept'][-1]['event']='OMITTED'
    reject('missing-reproposal-vote','full-size proof before acceptance quorum',changed)
    image=fmt.inspect(read(Path(root)/'pending-basis/node-1-image.gsr'),'IMAGE')
    reject('short-snapshot','full-size snapshot cut',overrides={'snapshot-512.gsr':raw(image['snapshot'])})
    reject('copied-basis-owner','full-size frozen basis cut',overrides={
        'pending-basis/node-2-basis.gsr':read(Path(root)/'pending-basis/node-1-basis.gsr'),
        'pending-basis/node-2-image.gsr':read(Path(root)/'pending-basis/node-1-image.gsr')})
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(m.canonical(validate(a.root)).decode())
