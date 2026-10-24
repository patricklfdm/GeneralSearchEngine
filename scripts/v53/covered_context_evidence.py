"""Original-byte replay of a protected context covered by a published majority.

Derive every saved authority from admitted originals and actual phase ownership.
Typed image semantics remain the producer's responsibility. No transport,
power-loss or maximal-capacity claim is made by these small-image cases.
"""
import argparse
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import covered_minority_evidence as covered
from . import pending_context_evidence as context

d, b, e, c, t = covered.d, covered.b, covered.e, covered.c, covered.t
match = b.match


def read(path, limit=1024*1024):
    return e.parse(t.plans.read(path, limit))


def phase_names(phase):
    e.need(phase in ('ACCEPT', 'PROOF', 'CERTIFICATE'), 'covered context phase')
    return () if phase == 'ACCEPT' else ('PROOF',) if phase == 'PROOF' else ('PROOF', 'CERTIFICATE')


def capture(files, phases):
    _, members, packet = c.current(files)
    objects, images = dict(packet['objects']), dict(packet['images'])
    tail = e.f.decode(files[c.current(files)[0]+'generation.gsr'], 'records', 'GENERATION')['ownedTail']
    if 'pending.context' in files:
        segments, _, _ = context.decode(files['pending.context'])
        basis = e.f.decode(segments[3], 'records', 'BASIS')
        backing = e.p.decode(files['sources/'+basis['basisId']+'/source.gscp'])
        _, original = context.reconstruct(segments[4], backing)
        objects.update(original['objects']); images.update(original['images'])
    if files['pending.accept'] != c.EMPTY:
        frames, values = c.pending(files['pending.accept'], phases)
        objects.update({e.digest(frames[k]): frames[k] for k in ('ENTRY', 'ACCEPT', 'PAYLOAD', *phases)})
        if tail is None or values['ACCEPT']['ballot']['counter'] >= e.f.decode(objects[tail], 'records', 'ACCEPT')['ballot']['counter']:
            tail = e.digest(frames['ACCEPT'])
    return e.packet_bytes(packet['capsule'], objects, images), tail


def campaign(root, group, counter, phases, carried=False):
    names = sorted(group); proposer = names[-1]
    identity = e.f.decode(group[proposer]['node.gsr'], 'records', 'NODE')['identity']
    ballot = dict(counter=counter, proposer=proposer, incarnation=identity['storage'])
    prepared, rows, packets, identifiers = {}, {}, {}, set()
    for node, files in group.items():
        raw, tail = capture(files, phases); packet = e.p.decode(raw); cap = packet['capsule']
        actual = c.inventory(root/f'round-{counter}-prepared'/node)
        history = c.journal(actual['grants.gsr'], cap['root'], node); prior = c.journal(files['grants.gsr'], cap['root'], node)
        e.need(history[:len(prior)] == prior and [r[0] for r in history[len(prior):]] == ['PROMISE', 'BASIS'], 'covered context grant extension')
        promise, basis = history[-2:]; identifier = promise[2]['basisId']
        e.need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers and all(r[2].get('basisId') != identifier for r in prior), 'covered context fresh source UUID')
        identifiers.add(identifier)
        expected = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
        e.need(promise[2] == expected and basis[2] == dict(expected, voter=node, cut=cap['cut'], capsule=e.digest(packet['capsuleBytes']), inventory=e.digest(packet['indexBytes']), accepted=tail), 'covered context captured source')
        prefix = 'sources/'+identifier
        changed = dict(files, **{'grants.gsr': files['grants.gsr']+promise[1]+basis[1], prefix: None, prefix+'/source.gscp': raw})
        for h, size in packet['images'].items():
            candidates = [v for k,v in files.items() if k.endswith('/'+h+'.image')]
            e.need(candidates and all(v == candidates[0] for v in candidates) and len(candidates[0]) == size and e.digest(candidates[0]) == h, 'covered context source image')
            changed[prefix+'/'+h+'.image'] = candidates[0]
        if node == proposer: changed['allocator.gsr'] = e.f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=counter))
        if 'pending.context' in files:
            segments, metadata, binding = context.decode(files['pending.context'])
            segments[0] = e.f.canonical(dict(binding, backingPacket=context.info(raw))); segments[2:4] = [promise[1], basis[1]]
            changed['pending.context'] = context.encode(segments, metadata)
        prepared[node] = changed; rows[node] = (promise, basis); packets[node] = packet
    match(root, f'round-{counter}-prepared', prepared)
    longest = max(reversed(names), key=lambda n: packets[n]['capsule']['cut']['index']); packet = packets[longest]; cap = packet['capsule']
    choices = []
    for node in names:
        local = packets[node]['capsule']
        e.need(local['root'] == cap['root'] and local['cut']['view'] == cap['cut']['view'] and cap['cut']['view']['operation'] is None, 'covered context stable authority')
        if local['cut']['index'] == cap['cut']['index']: e.need(c.anchor(local) == c.anchor(cap), 'covered context conflicting parent')
        else:
            e.need(len(cap['items']) == 1 and cap['items'][0]['kind'] == 'RANGE', 'covered context range')
            statement = e.f.decode(packet['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT')
            e.need(dict(cut=statement['start'], catalog=statement['catalogBefore'], application=statement['applicationBefore']) == c.anchor(local), 'covered context authenticated parent')
        tail = rows[node][1][2]['accepted']
        if tail:
            accepted = e.f.decode(packets[node]['objects'][tail], 'records', 'ACCEPT')
            if accepted['index'] > cap['cut']['index']: choices.append((accepted['ballot']['counter'], node, tail, accepted))
    chosen_tail = max(choices, key=lambda x:x[0]) if choices else None
    e.need(bool(chosen_tail) == carried, 'covered context selected slot')
    selected = e.f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, cut=cap['cut'], nextEntry=chosen_tail[3]['entry'] if chosen_tail else None,
        sources=[dict(voter=n, basisId=rows[n][1][2]['basisId'], basisDigest=e.digest(rows[n][1][1])) for n in names]))
    chosen = {n:dict(files, **{'grants.gsr': files['grants.gsr']+selected}) for n,files in prepared.items()}
    match(root, f'round-{counter}-selected', chosen)
    objects = dict(packet['objects']); tail = chosen_tail[2] if chosen_tail else None
    if tail:
        source = packets[chosen_tail[1]]; entry = e.f.decode(source['objects'][chosen_tail[3]['entry']], 'records', 'ENTRY')
        for h in (tail, chosen_tail[3]['entry'], entry['payload']): objects[h] = source['objects'][h]
    result = {}
    for node, files in chosen.items():
        prefix, old_members, _ = c.current(files); local_objects = dict(objects)
        if not carried and 'pending.context' in files:
            frames, _ = c.pending(files['pending.accept'], phases)
            for kind in ('ACCEPT', 'ENTRY', 'PAYLOAD'): local_objects[e.digest(frames[kind])] = frames[kind]
            if 'owned-tail.gsr' in old_members:
                accept = e.f.decode(old_members['owned-tail.gsr'], 'records', 'ACCEPT')
                local_objects[e.digest(old_members['owned-tail.gsr'])] = old_members['owned-tail.gsr']
                original_entry = e.f.decode(packets[node]['objects'][accept['entry']], 'records', 'ENTRY')
                for h in (accept['entry'], original_entry['payload']): local_objects[h] = packets[node]['objects'][h]
        raw = e.packet_bytes(cap, local_objects, packet['images'])
        members = {'promise.gsr': rows[node][0][1], 'basis.gsr': rows[node][1][1], 'selected.gsr': selected, 'selected-sources.gsr': b''.join(rows[n][1][1] for n in names), 'source.gscp': raw}
        if tail: members['owned-tail.gsr'] = objects[tail]
        source_prefix = 'sources/'+rows[longest][1][2]['basisId']
        members.update({h+'.image': prepared[longest][source_prefix+'/'+h+'.image'] for h in packet['images']})
        selector, generation = c.generation(members, e.p.decode(raw)['capsule'], node, 'b' if prefix == 'generations/a/' else 'a', tail)
        changed = dict(files, **generation, **{'selector.gsr': selector})
        if not carried:
            changed['pending.accept'] = c.EMPTY; changed.pop('pending.context', None)
        result[node] = changed
    return chosen, result, ballot


def retain(group, old, phases):
    result = {}
    for node, files in group.items():
        _, members, _ = c.current(files); prefix, original, packet = c.current(old[node])
        frames, _ = c.pending(old[node]['pending.accept'], phases)
        basis = e.f.decode(members['basis.gsr'], 'records', 'BASIS')
        identity = e.f.decode(files['node.gsr'], 'records', 'NODE')['identity']
        binding = dict(schema='gse-v53-pending-context/1.3', root=basis['root'], node=node, storage=identity['storage'], backingPacket=context.info(files['sources/'+basis['basisId']+'/source.gscp']), vote=context.info(old[node]['pending.accept']),
            entry=e.digest(frames['ENTRY']), accept=e.digest(frames['ACCEPT']), payload=e.digest(frames['PAYLOAD']), proof=e.digest(frames['PROOF']) if 'PROOF' in frames else None, certificate=e.digest(frames['CERTIFICATE']) if 'CERTIFICATE' in frames else None)
        envelope = struct.pack('>I', len(packet['capsuleBytes']))+packet['capsuleBytes']+struct.pack('>I', len(packet['indexBytes']))+packet['indexBytes']
        metadata = {k:v for k,v in original.items() if k != 'source.gscp' and not k.endswith('.image')}
        metadata['generation.gsr'] = old[node][prefix+'generation.gsr']
        result[node] = dict(files, **{'pending.context': context.encode([e.f.canonical(binding), old[node]['selector.gsr'], members['promise.gsr'], members['basis.gsr'], envelope], metadata)})
    return result


def retire_original(group):
    result = {}; names = sorted(group)
    for node, files in group.items():
        peers = sorted([node]+[n for n in names if n != node][:len(names)//2]); copies = {}; refs = []
        for peer in peers:
            prefix, members, packet = c.current(group[peer]); members = dict(members, **{'generation.gsr': group[peer][prefix+'generation.gsr']})
            raw = members['generation.gsr']; manifest = e.f.decode(raw, 'records', 'GENERATION'); dest = 'floor-copies/'+e.digest(raw)
            copies[dest] = None; copies.update({dest+'/'+k:v for k,v in members.items()})
            refs.append(dict(voter=peer, generation=e.digest(raw), catalog=manifest['catalog'], snapshot=manifest['application']))
        floor = e.f.encode('records', 'FLOOR', dict(root=packet['capsule']['root'], node=node, cut=packet['capsule']['cut'], sources=refs))
        prefix, _, _ = c.current(files); _, metadata, _ = context.decode(files['pending.context'])
        old = e.f.decode(metadata['basis.gsr'], 'records', 'BASIS'); source = 'sources/'+old['basisId']
        changed = {k:v for k,v in files.items() if (not k.startswith('generations/') or k == prefix[:-1] or k.startswith(prefix)) and k != source and not k.startswith(source+'/')}
        changed['grants.gsr'] = b''.join(r[1] for r in c.journal(files['grants.gsr'], old['root'], node) if r[2]['ballot'] != old['ballot'])
        changed.update({'floor-copies': None, 'floor-copies/floor.gsr': floor, 'floor-copies/proposal.gsr': floor}); changed.update(copies); result[node] = changed
    return result


def release(files):
    return {k:v for k,v in files.items() if k != 'floor-copies' and not k.startswith('floor-copies/')}


def prefix(root):
    profile = read(root/'profile.json'); e.exact(profile, 'size backup phase')
    size, backup, phase = profile['size'], profile['backup'], profile['phase']; phases = phase_names(phase)
    e.need(type(size) is int and size in (3,4,5) and type(backup) is bool, 'covered context profile')
    group = b.campaign(root, b.original(root,size,backup), 1); names = sorted(group); majority = names[size-(size//2+1):]; observed = []
    ballot = e.f.decode(c.current(group[names[0]])[1]['promise.gsr'], 'records', 'PROMISE')['ballot']
    payload = d.payload(404, 'majority-selected'); entry = d.entry(group,payload,ballot)
    e.need(t.plans.read(root/'entry.gsr',16384) == entry and t.plans.read(root/'payload.bin',e.MIB) == payload, 'covered context original ENTRY')
    group = d.vote(root,'initial-votes',group,names,entry,payload,observed)
    if phases:
        _, members, packet = c.current(group[names[0]]); frames, values = c.pending(group[names[0]]['pending.accept'],())
        ids = {n:e.f.decode(group[n]['node.gsr'],'records','NODE')['identity']['storage'] for n in names}
        def witnesses(raw,kind):return [dict(voter=n,incarnation=ids[n],receipt=e.digest(e.f.canonical(dict(root=packet['capsule']['root'],voter=n,incarnation=ids[n],phase=kind,record=e.digest(raw))))) for n in names]
        proof = e.f.encode('records','PROOF',dict(values['ACCEPT'],accepts=witnesses(frames['ACCEPT'],'ACCEPT')))
        for node in names:
            raw = group[node]['pending.accept']+proof; group[node] = dict(group[node], **{'pending.accept': raw[:8]+struct.pack('>I',len(raw))+raw[12:]})
            observed.append(dict(voter=node,storage=ids[node],record=e.digest(proof),parent=e.digest(e.f.canonical(packet['capsule']['cut']))))
        match(root,'original-proved',group)
        if phase == 'CERTIFICATE':
            certificate = e.f.encode('records','CERTIFICATE',dict(e.f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
            for node in names:
                raw = group[node]['pending.accept']+certificate; group[node] = dict(group[node], **{'pending.accept':raw[:8]+struct.pack('>I',len(raw))+raw[12:]})
            match(root,'original-certified',group)
    original = group; _, group, _ = campaign(root,group,3,phases,True); match(root,'round-3-installed',group)
    group = retain(group,original,phases); match(root,'contexts',group)
    group = retire_original(group); match(root,'original-retired',group)
    for node in majority:
        files = group[node]; _, members, _ = c.current(files); frames, values = c.pending(files['pending.accept'],phases)
        accept = e.f.encode('records','ACCEPT',dict(values['ACCEPT'],ballot=e.f.decode(members['promise.gsr'],'records','PROMISE')['ballot']))
        changed = release(files); changed.pop('pending.context')
        changed['pending.accept'] = e.container([files['selector.gsr'],members['promise.gsr'],members['selected.gsr'],entry,accept],payload); group[node] = changed
        observed.append(dict(voter=node,storage=e.f.decode(files['node.gsr'],'records','NODE')['identity']['storage'],record=e.digest(accept),parent=e.digest(e.f.canonical(c.current(files)[2]['capsule']['cut']))))
    match(root,'majority-reaccepted',group); group,_ = covered.publication(root,group,1,entry,payload,observed,majority)
    before, after, _ = campaign(root,group,4,phases); match(root,'advanced-selected',before)
    return profile,names,majority,before,after,observed


def clean(root):
    root = Path(root); p,names,majority,before,group,observed = prefix(root); layout(root,p,names,majority,True)
    match(root,'covered-installed',group)
    for node in names:
        if node not in majority:
            files = release(group[node]); generation_prefix = c.current(files)[0]
            group[node] = {k:v for k,v in files.items() if not k.startswith('generations/') or k == generation_prefix[:-1] or k.startswith(generation_prefix)}
    match(root,'floor-released',group)
    group = d.settle(root,'round-4-settled',group,names)
    _,group,ballot = campaign(root,group,5,()); match(root,'round-5-installed',group); group = d.settle(root,'round-5-settled',group,names)
    barrier = d.entry(group,b'',ballot,'BARRIER'); e.need(t.plans.read(root/'barrier.gsr',16384) == barrier,'covered context continuation ENTRY')
    group,_ = covered.publication(root,group,2,barrier,b'',observed,names); covered.observations(root,observed); calls(root,p,names,majority,True)
    for slot,owners in ((1,majority),(2,names)):
        for node in owners:
            _,members,packet = c.current(c.inventory(root/f'slot-{slot}-settled'/node)); b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    peak=0
    for stage in root.iterdir():
        if stage.is_dir() and (stage/names[0]).is_dir():
            for node in names:
                files=c.inventory(stage/node);images=[raw for path,raw in files.items() if path.endswith('.image')]
                e.need(len(images)<=7 and all(len(raw)<=64*e.MIB for raw in images),'covered context physical image bound');peak=max(peak,len(images))
    return dict(status='PASS',**p,nodePublications=len(names)+len(majority),peakPhysicalImages=peak,publicBootstrap=True,freshProcesses=False,powerLoss=False,publicRuntime=False)


def layout(root,p,names,majority,complete):
    paths={'original-plan.gsbp','original-application.image','initial','profile.json','entry.gsr','payload.bin','calls.json','observations.json',
           'initial-votes','contexts','original-retired','majority-reaccepted','advanced-selected'}
    paths|={f'round-1-{s}' for s in ('prepared','selected','installed','settled')}
    paths|={f'round-3-{s}' for s in ('prepared','selected','installed')}
    paths|={f'round-4-{s}' for s in ('prepared','selected')}
    if p['phase']!='ACCEPT':paths.add('original-proved')
    if p['phase']=='CERTIFICATE':paths.add('original-certified')
    for slot,owners in [(1,majority)]+([(2,names)] if complete else []):
        paths|={f'slot-{slot}-{s}' for s in ('accepted','proved','certified','applied','published','settled')}
        paths|={f'typed-{slot}-{n}' for n in owners}
    if complete:
        paths|={'covered-installed','floor-released','round-4-settled','barrier.gsr'}
        paths|={f'round-5-{s}' for s in ('prepared','selected','installed','settled')}
    else:paths|={'interruptions.json'}|{'interrupted-'+cut for cut in CUTS}
    b.selection.layout(root,paths,'covered context evidence')


def calls(root,p,names,majority,complete):
    expected=[]
    def many(nodes,label):expected.extend((n,label) for n in nodes)
    def maintain(nodes,label):many(nodes,label+'-copy');many(nodes,label+'-maintain')
    def campaign_order(counter,install=True):
        expected.append((names[-1],f'allocate-{counter}'))
        for label in ('prepare','select')+(('install',) if install else ()):many(names,f'{label}-{counter}')
    def publish(slot,nodes):
        for label in ('accept','proof','certificate','apply','publish'):many(nodes,f'{label}-{slot}')
        maintain(nodes,f'slot-{slot}-settled');many(nodes,f'inspect-{slot}')
    expected.append((names[0],'allocate-1'))
    for label in ('prepare','select','install'):many(names,label+'-1')
    maintain(names,'round-1-settled');expected.append((names[-1],'entry'));many(names,'initial-vote')
    if p['phase']!='ACCEPT':many(names,'original-proof')
    if p['phase']=='CERTIFICATE':many(names,'original-certificate')
    campaign_order(3);many(names,'retain-context');many(names,'context-retirement');many(majority,'majority-reaccept');publish(1,majority);campaign_order(4,False)
    if complete:
        many(names,'install-4');many([n for n in names if n not in majority],'release-covered-floor');maintain(names,'round-4-settled')
        campaign_order(5);maintain(names,'round-5-settled');expected.append((names[-1],'entry'));publish(2,names)
    rows=read(root/'calls.json',8*e.MIB)
    e.need(type(rows) is list and [(v.get('node'),v.get('operation')) for v in rows]==expected,'covered context call inventory')
    for row in rows:
        e.exact(row,'node operation events');events=row['events']
        e.need(type(events) is list and all(type(v) is str for v in events),'covered context force trace type')
        if row['operation']=='install-4' and row['node'] not in majority:
            required=['INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED','CONTEXT_SETTLEMENT_VALIDATED','SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED',
                      'CONTEXT_SETTLEMENT_EMPTY_FORCED','CONTEXT_REDUNDANT_DELETED','CONTEXT_REDUNDANT_PARENT_FORCED','CONTEXT_SETTLEMENT_CLEARED','INSTALL_BEFORE_RETURN']
            e.need([v for v in events if v in required]==required,'covered context installation cleanup force order')


CUTS=('INSTALL_MANIFEST_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED',
      'CONTEXT_SETTLEMENT_VALIDATED','SETTLED_VOTE_PREFIX_WRITTEN','SETTLED_VOTE_RENAMED','CONTEXT_SETTLEMENT_EMPTY_FORCED',
      'CONTEXT_REDUNDANT_DELETED','CONTEXT_REDUNDANT_PARENT_FORCED','CONTEXT_SETTLEMENT_CLEARED')


def transaction(before,after,cut=None):
    state=dict(before);trace=[]
    class Stop(Exception):pass
    def event(name):
        trace.append(name)
        if name==cut:raise Stop()
    def events(names):
        for name in names:event(name)
    def cleanup():
        event('CONTEXT_SETTLEMENT_VALIDATED')
        if state['pending.accept']!=c.EMPTY:
            next_file='pending.accept.next'
            if next_file not in state:state[next_file]=b'';event('SETTLED_VOTE_CANDIDATE_CREATED')
            value=state[next_file];e.need(len(value)<=len(c.EMPTY) and c.EMPTY.startswith(value),'covered context exact empty candidate')
            offset=len(value);state[next_file]=c.EMPTY[:offset+(len(c.EMPTY)-offset)//2];event('SETTLED_VOTE_PREFIX_WRITTEN')
            state[next_file]=c.EMPTY;events(['SETTLED_VOTE_CANDIDATE_WRITTEN','SETTLED_VOTE_CANDIDATE_FORCED','SETTLED_VOTE_CANDIDATE_PARENT_FORCED'])
            state['pending.accept']=state.pop(next_file);events(['SETTLED_VOTE_RENAMED','SETTLED_VOTE_PARENT_FORCED'])
        else:e.need('pending.accept.next' not in state,'covered context unexpected empty candidate')
        events(covered.SEAL);event('CONTEXT_SETTLEMENT_EMPTY_FORCED');del state['pending.context']
        events(['CONTEXT_REDUNDANT_DELETED','CONTEXT_REDUNDANT_PARENT_FORCED','CONTEXT_SETTLEMENT_CLEARED'])
    try:
        events(covered.OPEN);advanced=state['selector.gsr']==after['selector.gsr']
        if 'pending.context' in state:
            if advanced:cleanup()
            else:events(b.selection.reseal(state)[1])
        events(covered.SEAL if advanced else ['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED'])
        if not advanced:
            generation_prefix,members,_=c.current(after);members=dict(members,**{'generation.gsr':after[generation_prefix+'generation.gsr']})
            order,writes=covered.installation.transaction(members)
            for i,name in enumerate(order):
                if name=='INSTALL_DIRECTORY_CREATED':state[generation_prefix[:-1]]=None
                for member,index in writes.items():
                    if index==i:state[generation_prefix+member]=members[member]
                if name=='INSTALL_SELECTOR_WRITTEN':state['selector.pending.gsr']=after['selector.gsr']
                if name=='INSTALL_SELECTOR_RENAMED':state['selector.gsr']=state.pop('selector.pending.gsr')
                event(name)
            events(covered.OPEN);cleanup();event('INSTALL_BEFORE_RETURN')
        event('FLOOR_COPY_BEFORE_RETURN')
    except Stop:return state,trace
    e.need(cut is None,'covered context interruption not reached');return state,trace


def interrupted(root):
    root=Path(root);p,names,majority,before,after,observed=prefix(root);layout(root,p,names,majority,False)
    e.need(p==dict(size=3,backup=False,phase='CERTIFICATE'),'covered context interruption profile');calls(root,p,names,majority,False);covered.observations(root,observed)
    rows=[]
    for cut in CUTS:
        base=root/('interrupted-'+cut);b.selection.layout(base,{'first','second','final','events.json'},'covered context interruption')
        first,trace1=transaction(before['node-1'],after['node-1'],cut)
        retry='CONTEXT_SOURCE_PARENT_FORCED' if cut in CUTS[:2] else 'CONTEXT_SETTLEMENT_EMPTY_FORCED' if 'pending.context' in first else 'ACCEPT_ACTIVE_FORCED'
        second,trace2=transaction(first,after['node-1'],retry);final,trace3=transaction(second,after['node-1'])
        for name,files in (('first',first),('second',second),('final',final)):
            e.need(c.inventory(base/name)==files,'covered context exact interrupted '+name)
        e.need(final==after['node-1'],'covered context completed installation')
        e.need(read(base/'events.json')==dict(first=trace1,second=trace2,final=trace3),'covered context exact interrupted trace')
        rows.append(dict(cut=cut,secondCut=retry,status='PASS'))
    e.need(read(root/'interruptions.json')==rows,'covered context interruption receipt')
    return dict(status='PASS',cases=len(CUTS),interruptions=2*len(CUTS),freshProcesses=False,powerLoss=False)


def validate(profiles,interruptions,accept,proof):
    profiles=Path(profiles);names=[str(size)+'-'+kind for size in (3,4,5) for kind in ('empty','backup')]
    b.selection.layout(profiles,set(names)|{'receipt.json'},'covered context profiles');rows=[];results=[]
    for name in names:
        result=clean(profiles/name);size=int(name[0]);backup=name.endswith('backup')
        e.need((result['size'],result['backup'],result['phase'])==(size,backup,'CERTIFICATE'),'covered context profile location')
        results.append(result);rows.append(dict(case=name,status='PASS',size=size,backup=backup))
    e.need(e.f.canonical(read(profiles/'receipt.json'))==e.f.canonical(dict(schema='gse-v53-covered-context-profiles-v1',status='PASS',cases=rows)),'covered context profile receipt')
    for path,phase in ((accept,'ACCEPT'),(proof,'PROOF')):
        result=clean(Path(path));e.need((result['size'],result['backup'],result['phase'])==(3,False,phase),'covered context extra phase profile');results.append(result)
    return dict(status='PASS',profiles=results,recovery=interrupted(Path(interruptions)),originalFirst=True,physicalBytes=True,independentImageSemantics=False,maximalCapacity=False)


def qualify(profiles,interruptions,accept,proof):
    roots=list(map(Path,(profiles,interruptions,accept,proof)));result=validate(*roots);negatives=[]
    changes={
        'context':('contexts/node-1/pending.context','admitted exact contexts: node-1'),
        'floor':('original-retired/node-1/floor-copies/floor.gsr','admitted exact original-retired: node-1'),
        'selected-original':('advanced-selected/node-1/pending.accept','admitted exact advanced-selected: node-1'),
        'installed-original':('covered-installed/node-1/pending.accept','admitted exact covered-installed: node-1'),
        'floor-release':('floor-released/node-1/pending.accept','admitted exact floor-released: node-1'),
        'continuation':('slot-2-settled/node-1/pending.accept','admitted exact slot-2-settled: node-1')}
    for name in (*changes,'bootstrap','source','selection','ownership','force-order','extra-file','linked','first','second','trace'):
        crash=name in ('first','second','trace');source=roots[1] if crash else roots[0]/'3-empty'
        with tempfile.TemporaryDirectory(prefix='v53-covered-context-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(source,moved)
            if name in changes:
                path,reason=changes[name];(moved/path).write_bytes(b'changed')
            elif name=='bootstrap':
                (moved/'initial/target-0/node.gsr').write_bytes(b'changed');reason='admitted original public bootstrap'
            elif name=='source':
                node=moved/'round-4-prepared/node-1';segments,_,_=context.decode((node/'pending.context').read_bytes())
                basis=e.f.decode(segments[3],'records','BASIS');(node/'sources'/basis['basisId']/'source.gscp').write_bytes(b'changed')
                reason='admitted exact round-4-prepared: node-1'
            elif name=='selection':
                path=moved/'round-4-selected/node-1/grants.gsr';path.write_bytes(path.read_bytes()+b'changed');reason='admitted exact round-4-selected: node-1'
            elif name=='ownership':
                path=moved/'observations.json';rows=read(path);rows.pop();path.write_bytes(e.f.canonical(rows));reason='covered actual owner observations'
            elif name=='force-order':
                path=moved/'calls.json';rows=read(path,8*e.MIB)
                row=next(v for v in rows if v['node']=='node-1' and v['operation']=='install-4');row['events'].remove('SETTLED_VOTE_PARENT_FORCED')
                path.write_bytes(e.f.canonical(rows));reason='covered context installation cleanup force order'
            elif name=='extra-file':
                (moved/'unexpected').write_text('extra');reason='context selection covered context evidence inventory'
            elif name=='linked':
                path=moved/'initial-votes/node-1/pending.accept';path.unlink();path.symlink_to((source/'initial-votes/node-1/pending.accept').resolve());reason='application evidence inventory bound'
            elif name in ('first','second'):
                (moved/('interrupted-'+CUTS[0])/name/'pending.accept').write_bytes(b'changed');reason='covered context exact interrupted '+name
            else:
                path=moved/('interrupted-'+CUTS[0])/'events.json';rows=read(path);rows['final'].append('INSTALL_BEFORE_RETURN');path.write_bytes(e.f.canonical(rows));reason='covered context exact interrupted trace'
            try:(interrupted if crash else clean)(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong covered context negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted covered context mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-covered-context-receipt-') as tmp:
        moved=Path(tmp)/'profiles';shutil.copytree(roots[0],moved);path=moved/'receipt.json';receipt=read(path);receipt['cases'][0]['backup']=0
        path.write_bytes(e.f.canonical(receipt))
        try:validate(moved,*roots[1:])
        except ValueError as error:
            e.need(str(error)=='covered context profile receipt','wrong covered context receipt negative');negatives.append(dict(case='receipt-type',reason=str(error)))
        else:raise ValueError('accepted covered context receipt type mutation')
    with tempfile.TemporaryDirectory(prefix='v53-covered-context-portable-') as tmp:
        moved=[]
        for i,root in enumerate(roots):
            target=Path(tmp)/str(i);shutil.copytree(root,target);moved.append(target)
        e.need(validate(*moved)==result,'covered context relocated replay changed')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('profiles');parser.add_argument('interruptions');parser.add_argument('accept');parser.add_argument('proof')
    args=parser.parse_args();print(json.dumps(qualify(args.profiles,args.interruptions,args.accept,args.proof),sort_keys=True))
