"""Exact physical replay of one ENTRY retained under different local ACCEPT ballots.

Original-first; no online runtime, maximal-capacity or power-loss claim. Only
fresh local source UUIDs and typed application image bytes come from the producer;
all intervening metadata, objects, inventories and cleanup are independently derived.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import context_installation_lifetime_evidence as lifetime

selection = lifetime.selection
e, owner, source = lifetime.e, lifetime.owner, lifetime.source
carried = selection.publication.carried
NODES = selection.NODES


def vote(files):
    # The retained original can be ACCEPT-only or fully certified. This fixture
    # records which form it owns in its already derived context; never accept a
    # malformed/truncated certified vote as a shorter successful parse.
    phases = ()
    if 'pending.context' in files:
        binding = e.decode(files['pending.context'])[2]
        phases = ('PROOF', 'CERTIFICATE') if binding['certificate'] is not None else ('PROOF',) if binding['proof'] is not None else ()
    return carried.pending(files['pending.accept'], phases)


def accept(files):
    frames, values = vote(files); _, members, _ = carried.current(files)
    ballot = e.f.decode(members['promise.gsr'], 'records', 'PROMISE')['ballot']
    raw = e.f.encode('records', 'ACCEPT', dict(values['ACCEPT'], ballot=ballot))
    result = {p:v for p,v in files.items() if p not in ('pending.context', 'floor-copies') and not p.startswith('floor-copies/')}
    result['pending.accept'] = e.container([files['selector.gsr'], members['promise.gsr'], members['selected.gsr'], frames['ENTRY'], raw], frames['PAYLOAD'])
    return result


def capture(files, observed, counter, node):
    _, members, current = carried.current(files); frames, values = vote(files)
    previous = owner.journal(files['grants.gsr'], current['capsule']['root'], node)
    rows = owner.journal(observed['grants.gsr'], current['capsule']['root'], node)
    e.need(rows[:len(previous)] == previous and len(rows) in (len(previous)+2, len(previous)+3), 'mixed capture journal')
    promise = rows[len(previous)]; e.need(promise[0] == 'PROMISE', 'mixed fresh promise kind')
    old = [r for r in previous if r[0] == 'PROMISE'][-1][2]
    wanted = dict(old, ballot=dict(old['ballot'], counter=counter), basisId=promise[2]['basisId'])
    e.need(promise[2] == wanted and all(r[2].get('basisId') != wanted['basisId'] for r in previous), 'mixed fresh promise identity')
    objects = dict(current['objects']); images = dict(current['images'])
    if 'pending.context' in files:
        segments, metadata, binding = e.decode(files['pending.context'])
        old_basis = e.f.decode(segments[3], 'records', 'BASIS'); backing = e.p.decode(files['sources/'+old_basis['basisId']+'/source.gscp'])
        _, original = e.reconstruct(segments[4], backing)
        objects.update(original['objects']); images.update(original['images'])
    for kind in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE'):
        if kind in frames: objects[e.digest(frames[kind])] = frames[kind]
    selected = frames['ACCEPT']
    if 'owned-tail.gsr' in members:
        tail = e.f.decode(members['owned-tail.gsr'], 'records', 'ACCEPT')
        e.need({k:v for k,v in tail.items() if k != 'ballot'} == {k:v for k,v in values['ACCEPT'].items() if k != 'ballot'}, 'mixed original slot')
        if tail['ballot']['counter'] > values['ACCEPT']['ballot']['counter']: selected = members['owned-tail.gsr']
    packet_raw = e.packet_bytes(current['capsule'], objects, images); packet = e.p.decode(packet_raw)
    basis = dict(wanted, voter=node, cut=packet['capsule']['cut'], capsule=e.digest(packet['capsuleBytes']), inventory=e.digest(packet['indexBytes']), accepted=e.digest(selected))
    basis_raw = e.f.encode('records', 'BASIS', basis); prefix = 'sources/'+wanted['basisId']
    result = dict(files, **{'grants.gsr': files['grants.gsr']+promise[1]+basis_raw, prefix:None, prefix+'/source.gscp':packet_raw})
    for h in images:
        candidates = [v for p,v in files.items() if p.endswith('/'+h+'.image')]
        e.need(candidates and all(v == candidates[0] for v in candidates) and e.digest(candidates[0]) == h and len(candidates[0]) == images[h], 'mixed capture images')
        result[prefix+'/'+h+'.image'] = candidates[0]
    if 'pending.context' in files:
        segments[0] = e.f.canonical(dict(binding, backingPacket=e.info(packet_raw))); segments[2:4] = [promise[1], basis_raw]
        result['pending.context'] = e.encode(segments, metadata)
    return result


def bases(group):
    result = {}
    for node, files in group.items():
        cap = carried.current(files)[2]['capsule']
        result[node] = [r for r in owner.journal(files['grants.gsr'], cap['root'], node) if r[0] == 'BASIS'][-1]
    return result


def select(group):
    local = bases(group); basis = local['node-1'][2]
    packets = {n:e.p.decode(group[n]['sources/'+row[2]['basisId']+'/source.gscp']) for n,row in local.items()}
    entries = {e.f.decode(packets[n]['objects'][row[2]['accepted']], 'records', 'ACCEPT')['entry'] for n,row in local.items()}
    e.need(len(entries) == 1 and len({r[2]['basisId'] for r in local.values()}) == 3, 'mixed same entry separate owners')
    raw = e.f.encode('records', 'SELECTED', dict(root=basis['root'], view=basis['view'], ballot=basis['ballot'], cut=basis['cut'], nextEntry=next(iter(entries)),
        sources=[dict(voter=n, basisId=local[n][2]['basisId'], basisDigest=e.digest(local[n][1])) for n in NODES]))
    return {n:dict(files, **{'grants.gsr':files['grants.gsr']+raw}) for n,files in group.items()}, raw


def install(group, selected):
    local = bases(group); packets = {n:e.p.decode(group[n]['sources/'+row[2]['basisId']+'/source.gscp']) for n,row in local.items()}
    candidates = [packets[n]['objects'][row[2]['accepted']] for n,row in local.items()]
    tail = max(candidates, key=lambda raw:e.f.decode(raw,'records','ACCEPT')['ballot']['counter'])
    base = packets['node-1']; objects = dict(base['objects']); objects[e.digest(tail)] = tail
    packet_raw = e.packet_bytes(base['capsule'], objects, base['images']); packet = e.p.decode(packet_raw); result = {}
    for node,files in group.items():
        _, old, old_packet = carried.current(files); selector = e.f.decode(files['selector.gsr'], 'records', 'SELECTOR')
        basis = local[node]; rows = owner.journal(files['grants.gsr'], basis[2]['root'], node)
        promise = next(r[1] for r in rows if r[0] == 'PROMISE' and r[2]['basisId'] == basis[2]['basisId'])
        members = {'promise.gsr':promise, 'basis.gsr':basis[1], 'selected.gsr':selected, 'selected-sources.gsr':b''.join(local[n][1] for n in NODES), 'owned-tail.gsr':tail, 'source.gscp':packet_raw}
        members.update({h+'.image':group['node-1']['sources/'+local['node-1'][2]['basisId']+'/'+h+'.image'] for h in packet['images']})
        new_selector,generation = carried.generation(members, packet['capsule'], node, 'b' if selector['generation']=='a' else 'a', e.digest(tail))
        result[node] = dict(files, **generation, **{'selector.gsr':new_selector})
        if 'pending.context' not in files:
            frames,values = vote(files); identity = e.f.decode(files['node.gsr'],'records','NODE')['identity']
            backing = files['sources/'+basis[2]['basisId']+'/source.gscp']
            binding = dict(schema='gse-v53-pending-context/1.3',root=basis[2]['root'],node=node,storage=identity['storage'],backingPacket=e.info(backing),vote=e.info(files['pending.accept']),
                entry=e.digest(frames['ENTRY']),payload=e.digest(frames['PAYLOAD']),accept=e.digest(frames['ACCEPT']),proof=None,certificate=None)
            envelope = struct.pack('>I',len(old_packet['capsuleBytes']))+old_packet['capsuleBytes']+struct.pack('>I',len(old_packet['indexBytes']))+old_packet['indexBytes']
            metadata = {p:v for p,v in old.items() if p!='source.gscp' and not p.endswith('.image')}
            metadata['generation.gsr'] = files['generations/'+selector['generation']+'/generation.gsr']
            result[node]['pending.context'] = e.encode([e.f.canonical(binding),files['selector.gsr'],promise,basis[1],envelope],metadata)
    return result


def floors(group):
    result = dict(group)
    for node in ('node-2','node-3'):
        refs=[]; copies={}
        for peer in ('node-2','node-3'):
            path,members,packet=carried.current(group[peer]); members=dict(members, **{'generation.gsr':group[peer][path+'generation.gsr']})
            manifest=e.f.decode(members['generation.gsr'],'records','GENERATION')
            digest=e.digest(members['generation.gsr']); prefix='floor-copies/'+digest
            refs.append(dict(voter=peer,generation=digest,catalog=manifest['catalog'],snapshot=manifest['application']))
            copies.update({prefix:None, **{prefix+'/'+p:v for p,v in members.items()}})
        floor=e.f.encode('records','FLOOR',dict(root=manifest['root'],node=node,cut=packet['capsule']['cut'],sources=refs))
        result[node]=dict(group[node],**{'floor-copies':None,'floor-copies/floor.gsr':floor,'floor-copies/proposal.gsr':floor},**copies)
    return result


def retire_generation(files):
    selected=e.f.decode(files['selector.gsr'],'records','SELECTOR'); prefix='generations/'+('b' if selected['generation']=='a' else 'a')
    e.need(prefix in files,'mixed missing retired generation')
    return {p:v for p,v in files.items() if p!=prefix and not p.startswith(prefix+'/')}


def retire_source(files, basis):
    prefix='sources/'+basis['basisId']; packet=e.p.decode(files[prefix+'/source.gscp'])
    e.p.bind(packet,e.f.encode('records','BASIS',basis))
    current=carried.current(files)[2]
    e.need(packet['capsule']['cut']==current['capsule']['cut'] and all(current['objects'].get(h)==v for h,v in packet['objects'].items()),'mixed source exact coverage')
    result={p:v for p,v in files.items() if p!=prefix and not p.startswith(prefix+'/')}
    result['grants.gsr']=b''.join(r[1] for r in owner.journal(files['grants.gsr'],basis['root'],basis['voter']) if r[2]['ballot']!=basis['ballot'])
    return result


def snapshot(root, stage, group):
    selection.layout(root/stage,NODES,'mixed owners')
    for node,files in group.items():e.need(carried.inventory(root/stage/node)==files,'mixed exact '+stage+': '+node)


def validate(root):
    root=Path(root)
    selection.layout(root,{'reference','mixed','selected','installed','floors','retired','predecessors-retired','round-23','round-24','accepted','originals','carried-snapshots','receipt.json'},'mixed acceptance')
    selection.layout(root/'originals',{'slot-2'},'mixed originals');selection.layout(root/'originals/slot-2',NODES,'mixed original owners')
    selection.layout(root/'carried-snapshots',{'published'},'mixed publication')
    selection.publication.validate(root/'reference')
    initial={n:carried.inventory(root/'reference/carried-snapshots/source-retired'/n) for n in NODES}
    group={n:accept(files) if n!='node-1' else files for n,files in initial.items()};snapshot(root,'mixed',group)
    captured={n:capture(files,carried.inventory(root/'selected'/n),22,n) for n,files in group.items()}
    group,selected=select(captured);snapshot(root,'selected',group)
    group=install(group,selected);snapshot(root,'installed',group)
    group=floors(group);snapshot(root,'floors',group)
    group={n:retire_generation(files) for n,files in group.items()};snapshot(root,'retired',group)
    for n in ('node-2','node-3'):
        frames,_=vote(group[n]); basis=e.f.decode(e.decode(group[n]['pending.context'])[1]['basis.gsr'],'records','BASIS')
        group[n]=retire_source(group[n],basis)
    snapshot(root,'predecessors-retired',group)
    for counter in (23,24):
        stage=f'round-{counter}';selection.layout(root/stage,{'captured','selected','installed','generation-retired','source-retired'},'mixed round')
        old=bases(group)
        group={n:capture(files,carried.inventory(root/stage/'captured'/n),counter,n) for n,files in group.items()};snapshot(root,stage+'/captured',group)
        group,selected=select(group);snapshot(root,stage+'/selected',group)
        group=install(group,selected);snapshot(root,stage+'/installed',group)
        group={n:retire_generation(files) for n,files in group.items()};snapshot(root,stage+'/generation-retired',group)
        group={n:retire_source(files,old[n][2]) if counter>23 or n=='node-1' else files for n,files in group.items()};snapshot(root,stage+'/source-retired',group)
    group={n:accept(files) for n,files in group.items()};snapshot(root,'accepted',group)
    carried.publication(root,2,group,None)
    e.need(source.load(root/'receipt.json')==dict(schema='gse-v53-context-mixed-acceptance-v1',status='PASS',nodes=3,originalAccepts=[20,21,21],installedBallot=24,entryOrigin=20,publishedCut=2,applicationSequence=43,runtimeEnabled=False),'mixed receipt scope')
    return dict(status='PASS',nodes=3,originalAccepts=[20,21,21],installedBallots=[22,23,24],entryOrigin=20,publishedCut=2,applicationSequence=43,originalFirst=True,physicalBytes=True,freshProcesses=False,powerLoss=False,runtimeEnabled=False,maximalCapacity=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'original': 'context publication exact source-retired: node-1',
              'missing':'context selection mixed acceptance inventory',
              'published':'carried exact publication/retirement bytes',
              'ack':'carried original applied ends', 'scope':'mixed receipt scope',
              'linked':'application evidence inventory bound'}
    stages=('mixed','selected','installed','floors','retired','predecessors-retired',
            'round-23/captured','round-23/selected','round-23/installed','round-23/generation-retired','round-23/source-retired',
            'round-24/captured','round-24/installed','round-24/source-retired','accepted')
    variants.update({stage:'mixed exact '+stage+': node-1' for stage in stages})
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-mixed-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved)
            if name=='original':(moved/'reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(moved/'round-24')
            elif name in stages:(moved/name/'node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='published':(moved/'carried-snapshots/published/node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='ack':(moved/'originals/slot-2/node-1/applied-end/ack.gsr').write_bytes(b'changed')
            elif name=='linked':
                path=moved/'accepted/node-1/allocator.gsr';path.unlink();path.symlink_to((root/'accepted/node-1/allocator.gsr').resolve())
            else:
                path=moved/'receipt.json';value=source.load(path);value['runtimeEnabled']=True;path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong mixed negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted mixed mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-mixed-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'mixed portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
