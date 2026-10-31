"""Derive one same-view joining recovery from its complete original history.

No capture or success receipt supplies expected storage bytes. Whole transport,
export lifetime and process-death qualification remain separate gates.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_continuation_evidence as profile
from . import joining_same_view_semantics as semantic
from . import joining_retirement_replay as retirement

p,c,init,s,f,disk,need,sha=profile.p,profile.c,profile.init,profile.s,profile.f,profile.disk,profile.need,profile.sha
t,PEERS,peers,learner,future=c.t,c.PEERS,c.peers,c.learner,c.future


def covering_floor(files,copies,node):
    """Derive local FLOOR bytes from already derived original generations."""
    own_prefix,own,packet=disk.current(files);cap=packet['capsule']
    need(node in copies and disk.current(copies[node])[1]==own and
         copies[node][own_prefix+'generation.gsr']==files[own_prefix+'generation.gsr'],
         'joining same-view exact local floor copy')
    need(not any(n=='floor-copies' or n.startswith('floor-copies/') for n in files),'joining same-view preceding floor not released')
    s.catalog.majority(cap['cut']['view'],sorted(copies))
    identities=s.catalog.identities(f.decode(packet['objects'][cap['catalog']],'records','CATALOG')['identities'])
    refs=[];stored={}
    for peer,original in sorted(copies.items()):
        prefix,members,other=disk.current(original);candidate=other['capsule']
        need(original['root.gsr']==files['root.gsr'] and candidate['root']==cap['root'] and
             f.decode(original['node.gsr'],'records','NODE')['identity']==identities.get(peer) and
             candidate['cut']['view']==cap['cut']['view'] and candidate['cut']['index']>=cap['cut']['index'],
             'joining same-view governing copy identity/view')
        available=t.confirmation.endpoints(other,members.get('ancestry.gsr',b''))
        need(available.get(cap['cut']['index'])==disk.anchor(cap),'joining same-view exact covering ancestor')
        raw=original[prefix+'generation.gsr'];digest=sha(raw)
        refs.append(dict(voter=peer,generation=digest,catalog=candidate['catalog'],snapshot=candidate['application']))
        stored['floor-copies/'+digest]=None
        stored.update({'floor-copies/'+digest+'/'+n:v for n,v in dict(members,**{'generation.gsr':raw}).items()})
    raw=f.encode('records','FLOOR',dict(root=cap['root'],node=node,cut=cap['cut'],sources=refs))
    return dict(files,**{'floor-copies':None,'floor-copies/proposal.gsr':raw,'floor-copies/floor.gsr':raw},**stored)


def floor_voters(group,node):
    """Healthy known-voter order; stop at both majorities, not all live owners."""
    view=disk.current(group[node])[2]['capsule']['cut']['view'];selected=[node]
    own=disk.current(group[node])[2]['capsule']
    for peer in sorted(set(view['old']+view['new'])):
        if all(len(set(selected)&set(view[key]))>len(view[key])//2 for key in ('old','new')):break
        if peer==node or peer not in group:continue
        other=disk.current(group[peer])[2]['capsule']
        if other['cut']['view']!=view or other['cut']['index']<own['cut']['index']:continue
        selected.append(peer)
    covering_floor(group[node],{n:group[n] for n in selected},node)
    return tuple(selected)


def maintenance(group, node, retiring=None, *, voters):
    """Conditional projection with exact derived copies, debt and source pins."""
    files = copy.deepcopy(group[node]); prefix, members, packet = disk.current(files)
    cap = packet['capsule']; owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']
    need(files['pending.accept'] == disk.EMPTY and not any(n == 'applied-end' or n.startswith('applied-end/') for n in files),
         'joining continuation maintenance unsettled authority')
    t.publication.phases.empty_future(files[future.FILE], files)
    files = c.reconcile(files)
    copies = [node, *[n for n in voters if n != node]]
    covering_floor(files,{n:group[n] for n in copies},node)
    for peer in copies:
        if disk.anchor(disk.current(group[peer])[2]['capsule'])==disk.anchor(cap):
            files[PEERS] = t.observation.observe_same_cut(files[PEERS], files, group[peer], defer_renewal=True)
    available = t.require_coverage(files)
    files = {n: raw for n, raw in files.items() if not n.startswith('generations/') or n == prefix[:-1] or n.startswith(prefix)}
    rows = disk.journal(files['grants.gsr'], cap['root'], owner['node'])
    promises = {v['basisId']: (raw, v) for kind, raw, v in rows if kind == 'PROMISE' and v['basisId'] is not None}
    latest = next(v['ballot'] for kind, _, v in reversed(rows) if kind == 'PROMISE')
    retired = set()
    for name, raw in files.items():
        if not name.startswith('sources/') or not name.endswith('/source.gscp'): continue
        identifier = name.split('/')[1]; promise, value = promises[identifier]
        if promise == members['promise.gsr'] or value['ballot'] == latest: continue
        source = disk.p.decode(raw); point = disk.anchor(source['capsule'])
        need(value['ballot']['counter'] < latest['counter'] and available.get(point['cut']['index']) == point,
             'joining continuation source retirement coverage')
        retired.add(identifier)
    if retired and retiring is not None: retiring(node, files, {n:group[n] for n in copies}, retired)
    files = {n: raw for n, raw in files.items() if not (n.startswith('sources/') and n.split('/')[1] in retired)}
    # Remove only complete obsolete source groups. Adopted fences and the
    # current generation's original promise remain pinned.
    kept = []; discard = False
    for kind, raw, value in rows:
        if kind == 'PROMISE':
            discard = value['basisId'] in retired or (retired and value['basisId'] is None
                and raw != members['promise.gsr'] and value['ballot'] != latest)
        if not discard: kept.append(raw)
    files['grants.gsr'] = b''.join(kept)
    return files


def install(files, sources, selection):
    """Derive selected retention intent, reachable packet and generation bytes."""
    chosen = f.decode(selection, 'records', 'SELECTED'); names = sorted(sources)
    need([v['voter'] for v in chosen['sources']] == names, 'joining continuation exact selected cohort')
    s.catalog.majority(chosen['cut']['view'], names)
    owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']; node = owner['node']
    prefix, old, previous = disk.current(files); basis, raw = sources[node]
    packets={n:disk.p.decode(v[1]) for n,v in sources.items()}
    longest=min(names,key=lambda n:(-packets[n]['capsule']['cut']['index'],n))
    packet=packets[longest]
    need(chosen['cut'] == packet['capsule']['cut'] and chosen['nextEntry'] is None, 'joining continuation selected original cut')
    peer_rows = []; learner_rows = []; peer_raw = []; learner_raw = []
    for n in names:
        b, data = sources[n]; p = disk.p.decode(data); value = f.decode(b, 'records', 'BASIS')
        ref = next(v for v in chosen['sources'] if v['voter'] == n)
        need(ref == dict(voter=n, basisId=value['basisId'], basisDigest=sha(b)), 'joining continuation selected source binding')
        pw, ps = init.retention.source(p, value, 0x47535250, 65536)
        lw, ls = init.retention.source(p, value, 0x47534c46, 32768)
        peer_rows.append((b, p, pw)); learner_rows.append((b, p, lw))
        peer_raw.append(peers.frame(ps)); learner_raw.append(learner.frame(ls))
    objects = t.reachable.prefix(packet, files['root.gsr'])
    for value in (t.selected.intent(owner, selection, files[PEERS], peer_rows), learner.intent(owner, selection, files[learner.FILE], learner_rows)):
        objects[sha(value)] = value
    promise = next(raw for kind, raw, value in reversed(disk.journal(files['grants.gsr'], chosen['root'], node)) if kind == 'PROMISE')
    members = {'promise.gsr': promise, 'basis.gsr': basis, 'selected.gsr': selection,
        'selected-sources.gsr': b''.join(sources[n][0] for n in names),
        'source.gscp': disk.packet_bytes(packet['capsule'], objects, packet['images'])}
    for digest,size in packet['images'].items():
        raw=old.get(digest+'.image')
        need(raw is not None and len(raw)==size and sha(raw)==digest,'joining same-view original application image')
        members[digest+'.image']=raw
    points = [p for row in peers.decode(files[PEERS])['plan']['peers'] for p in [*row.get('renewals', []), *row['possible']]]
    local_learner = learner.decode(files[learner.FILE])['plan']
    points += [*local_learner.get('renewals', []), *local_learner['possible']]
    points += [disk.anchor(disk.p.decode(raw)['capsule']) for name, raw in files.items()
               if name.startswith('sources/') and name.endswith('/source.gscp')]
    points += [disk.anchor(previous['capsule']),*[disk.anchor(v['capsule']) for v in packets.values()]]
    direct=t.confirmation.endpoints(packet,b'')
    required = {p['cut']['index'] for p in points if p['cut']['index'] not in direct}
    need(all(p['cut']['index'] not in direct or direct[p['cut']['index']]==p for p in points),'joining same-view conflicting selected parent')
    # The already derived ancestry groups retain only locally required lower
    # endpoints. The adopted joining owner need not inherit old voters' debts.
    groups = []
    for raw in s.frames(old['ancestry.gsr']) if old.get('ancestry.gsr') else ():
        if int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['CHECKPOINT']['id']: groups.append([raw])
        else:
            need(groups, 'joining continuation orphan ancestry'); groups[-1].append(raw)
    ancestry = b''.join(raw for rows in groups if f.decode(rows[0], 'records', 'CHECKPOINT')['start']['index'] in required for raw in rows)
    available=t.confirmation.endpoints(packet,ancestry)
    need(all(available.get(point['cut']['index'])==point for point in points),'joining same-view complete installation ancestry')
    if ancestry: members['ancestry.gsr'] = ancestry
    selector, generation = disk.generation(members, packet['capsule'], node, 'b' if prefix == 'generations/a/' else 'a', None)
    state = peers.decode(files[PEERS]); registry = s.catalog.identities(f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG')['identities'])
    points = [p for raw in [files[learner.FILE], *learner_raw] for p in learner.decode(raw)['plan']['possible']]
    plan = t.confirmation.merge([peers.decode(raw)['plan'] for raw in [files[PEERS], *peer_raw]], packet, registry, points)
    merged = files[PEERS] if plan == state['plan'] else peers.frame(dict(state, revision=state['revision']+1, previous=sha(files[PEERS]), plan=plan))
    return dict(files, **generation, **{'selector.gsr': selector, 'grants.gsr': files['grants.gsr']+selection,
        PEERS: merged, learner.FILE: c.merge_learner(files[learner.FILE], learner_raw, packet)})


class Retirements(retirement.Retirements):
    def compare(self,node,files,copies,identifiers):
        files=covering_floor(files,copies,node)
        for identifier in sorted(identifiers):
            position=self.positions.get(node,0)
            need(position<len(self.by_node[node]),'joining retirement original transaction absent')
            row=self.by_node[node][position];authority,compact=retirement.decision(files,node,identifier)
            self.floors.add((node,retirement.floor_order(self.events,node,row['steps'][0]['event'])))
            initial={n:dict(directory=True) if raw is None else retirement.observed.release.r.entry(raw) for n,raw in files.items() if n!='.'}
            self.prefixes+=retirement.observed.compare(row,initial,authority,compact,identifier)
            self.positions[node]=position+1;self.transactions+=1
            files={n:raw for n,raw in files.items() if not (n=='sources/'+identifier or n.startswith('sources/'+identifier+'/'))}
            files['grants.gsr']=compact


class History(p.History):
    def __init__(self,root,replay,captures,retirements):
        self.retirements=retirements;super().__init__(root,replay,captures)

    def maintain(self):
        self.group=t.maintenance(self.group,self.retirements.compare,voters=self.voters)


class Initialization(p.Initialization):
    def __init__(self,root,handoff,captures,retirements):
        self.retirements=retirements;super().__init__(root,handoff,captures)

    def maintain(self,copies):
        self.group=t.maintenance(self.group,self.retirements.compare,copies,voters=self.voters)


class Continuation(profile.Continuation):
    def __init__(self,root,initialization,captures,retirements):
        self.retirements=retirements;super().__init__(root,initialization,captures)

    def maintenance(self,group,node):
        return maintenance(group,node,self.retirements.compare,voters=floor_voters(group,node))

    def prefix(self,events):
        self.joining_snapshot('joining-before-final-prefix')
        before=self.group[self.joining]
        self.group[self.joining],members,detail=profile.adopt(self.replay,before,self.group['node-1'])
        profile.adoption_order(events,self.joining,members,detail['promiseAppended'])
        self.joining_snapshot('joining-after-final-prefix')
        return detail

    def recover(self,events):
        self.joining_snapshot('joining-before-final-recovery')
        ballot=init.next_ballot(self.group[self.joining]);selected_path=self.root/'joining-final-recovery-selection.gsr'
        selected=f.decode(selected_path.read_bytes(),'records','SELECTED',self.replay.root)
        names=tuple(v['voter'] for v in selected['sources'])
        need(self.joining in names and set(names)<=set(self.replay.targets),'joining same-view selected identities')
        s.catalog.majority(self.replay.states[11]['cut']['view'],list(names))
        # The original known-voter order chooses the first complete covering
        # majority. The remote up-to-date voter has a separate local cut.
        self.group[self.joining]=self.maintenance(self.group,self.joining)
        sources={}
        for node in (self.joining,*[n for n in names if n!=self.joining]):
            if node!=self.joining:
                self.group[node]=self.maintenance(self.group,node)
            captured=self.captures.original(node,ballot)
            self.group[node],sources[node]=init.prepare(self.group[node],ballot,captured['grants.gsr'],self.identifiers)
            self.prepared(node,self.group[node])
        longest=min(names,key=lambda n:(-disk.p.decode(sources[n][1])['capsule']['cut']['index'],n))
        cap=disk.p.decode(sources[longest][1])['capsule']
        expected=f.encode('records','SELECTED',dict(root=self.replay.root,view=s.catalog.authority(self.replay.root,cap['cut']['view']),
            ballot=ballot,cut=cap['cut'],nextEntry=None,sources=[dict(voter=n,basisId=f.decode(sources[n][0],'records','BASIS')['basisId'],
            basisDigest=sha(sources[n][0])) for n in names]))
        need(expected==selected_path.read_bytes(),'joining same-view derived selected bytes')
        maintained={node:self.maintenance(self.group,node) for node in names}
        for node in names:self.group[node]=install(maintained[node],sources,expected)
        self.joining_snapshot('joining-after-final-recovery')
        for node in self.replay.old:
            need(disk.inventory(self.root/'same-view-installed'/node)==self.group[node],'joining same-view installed old owner: '+node)
        return dict(fromCut=10,toCut=11,selectedVoters=list(names),proposer=self.joining,longest=longest)

    def run(self):
        events=s.collection.read_json(self.root,'events.json',s.collection.EVENT_BYTES)
        boundary=self.preparation();counter=boundary['ballot']['counter']
        self.campaign(9,counter+1);self.slot(10);adoption=self.prefix(events)
        for node in self.voters:self.group[node]=self.maintenance(self.group,node)
        self.campaign(10,counter+2);self.slot(11)
        recovery=self.recover(events)
        self.match('after-close');self.joining_snapshot('joining-originals-stable-cold')
        c.cold_order(events,joining=self.joining)
        retired=self.captures.retirement_order(events,self.group,owners=(*self.initialization.voters,self.joining))
        self.retirements.complete()
        return dict(status='PARTIAL',scope='original-same-view-selected-recovery',profile='3-REPLACE',
            capturedGrantComparisons=self.captures.comparisons,ownerSnapshotComparisons=self.comparisons,
            sourceRetirementLocalOrderSegments=retired,finalCut=11,adoption=adoption,recovery=recovery,
            sourceRetirementTransactions=self.retirements.transactions,sourceRetirementPrefixes=self.retirements.prefixes,
            governingFloorForceWindows=len(self.retirements.floors),
            sameViewStorageQualified=True,sameViewPhysicalQualified=False,
            phase3Complete=False,completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False)


def validate(root):
    root=Path(root);before=s.collection.inventory(root);semantic.validate(root,'3-REPLACE')
    events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES);observed=p.Captures(root,events)
    retirements=Retirements(root,events)
    c.t.publication.validate(root,size=3,kind='REPLACE');replay=s.Replay(root,size=3,kind='REPLACE')
    for index in range(1,12):replay.step(index)
    replay.publication_receipts=c.t.publication.CheckpointReceipts(root,replay)
    history=History(root,replay,observed,retirements);history.run()
    owner=init.placement.Placement(root,history);owner.run()
    handoff=init.retirement.Retirement(root,owner);handoff.run()
    initialized=Initialization(root,handoff,observed,retirements);initialized.run()
    result=Continuation(root,initialized,observed,retirements).run()
    need(s.collection.inventory(root)==before,'joining same-view physical original changed')
    return result


NEGATIVES={
    'prefix-extra-allocation':'joining continuation exact family: joining-after-final-prefix: replica',
    'recovery-peer-debt-lost':'joining continuation exact family: joining-before-final-recovery: replica',
    'recovery-original-source-lost':'joining continuation exact family: joining-after-final-recovery: replica',
    'recovery-prior-generation-lost':'joining continuation exact family: joining-after-final-recovery: replica',
    'installed-old-extra-allocation':'joining same-view installed old owner: node-1',
    'covering-floor-local-cut':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'covering-floor-peer-catalog':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'covering-floor-source-member':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'covering-floor-early-journal':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'covering-floor-missing-force':'joining retirement governing floor force order',
    'covering-floor-early-release':'joining retirement released governing floor',
    'cold-force-omitted':c.NEGATIVES['cold-force-omitted'][2],
}


def mixed_retirement(root,events):
    for row in retirement.observed.collect(root,events):
        files=row['steps'][0]['files'];floor=f.decode(files['floor-copies/floor.gsr'],'records','FLOOR')
        if any(f.decode(files['floor-copies/'+v['generation']+'/generation.gsr'],'records','GENERATION')['cut']['index']>
               floor['cut']['index'] for v in floor['sources']):return row
    raise ValueError('joining same-view negative requires original mixed floor')


def mutate(root,name):
    root=Path(root);need(name in NEGATIVES,'joining same-view unknown physical mutation')
    if name=='recovery-peer-debt-lost':
        snapshot=root/'joining-before-final-recovery';path=snapshot/'replica'/PEERS
        state=peers.decode(path.read_bytes());changed=False
        for row in state['plan']['peers']:
            if row.get('renewals'):row.pop('renewals');changed=True
            if len(row['possible'])>1:row['possible']=row['possible'][-1:];changed=True
        need(changed,'joining same-view negative requires original peer debt')
        path.write_bytes(peers.frame(state));profile.refresh_snapshot(snapshot);return
    if name.startswith('recovery-') or name=='cold-force-omitted':profile.mutate(root,name);return
    if name in ('prefix-extra-allocation','installed-old-extra-allocation'):
        snapshot=root/'joining-after-final-prefix'
        path=(snapshot/'replica' if name.startswith('prefix') else root/'same-view-installed/node-1')/'allocator.gsr'
        value=f.decode(path.read_bytes(),'records','ALLOCATOR');value['counter']+=1
        path.write_bytes(f.encode('records','ALLOCATOR',value))
        if name.startswith('prefix'):profile.refresh_snapshot(snapshot)
        return
    events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES);row=mixed_retirement(root,events);node=row['node']
    first=row['steps'][0]['event']
    if name in ('covering-floor-missing-force','covering-floor-early-release'):
        start=retirement.floor_order(events,node,first)
        at=next(i for i in range(start,first) if events[i].get('node')==node and events[i]['event']=='FLOOR_AUTHORITY_FORCED')
        if name.endswith('missing-force'):events.pop(at)
        else:events.insert(first,dict(node=node,scope=events[start].get('scope'),event='FLOOR_RELEASE_CLEARED'))
    else:
        step=next(v for v in row['steps'] if v['point']=='SOURCE_RETIREMENT_WRITTEN')
        event=events[step['capturedEvent']];path=root/event['capture'];meta=json.loads(path.read_bytes())
        files={v['name']:v['identity'] for v in meta['files']};objects=root/retirement.observed.DIRECTORY/'objects'
        def store(n,raw):
            (objects/sha(raw)).write_bytes(raw);files[n]=dict(size=len(raw),sha256=sha(raw))
        if name in ('covering-floor-local-cut','covering-floor-peer-catalog'):
            floor=f.decode(step['files']['floor-copies/floor.gsr'],'records','FLOOR')
            if name.endswith('local-cut'):floor['cut']['index']+=1
            else:next(v for v in floor['sources'] if v['voter']!=node)['catalog']='f'*64
            raw=f.encode('records','FLOOR',floor)
            store('floor-copies/floor.gsr',raw);store('floor-copies/proposal.gsr',raw)
            authority=step['files'][retirement.observed.release.AUTHORITY];length=48+int.from_bytes(authority[12:16],'big')
            record=f.decode(authority[:length],'records','RETIREMENT');record['floor']=sha(raw)
            store(retirement.observed.release.AUTHORITY,f.encode('records','RETIREMENT',record)+authority[length:])
        elif name.endswith('source-member'):
            floor=f.decode(step['files']['floor-copies/floor.gsr'],'records','FLOOR')
            peer=next(v for v in floor['sources'] if v['voter']!=node)
            member='floor-copies/'+peer['generation']+'/promise.gsr'
            value=f.decode(step['files'][member],'records','PROMISE');value['ballot']['counter']+=1
            store(member,f.encode('records','PROMISE',value))
        else:
            later=next(v for v in row['steps'] if v['point']=='SOURCE_RETIREMENT_JOURNAL_PRUNED')
            store('grants.gsr',later['files']['grants.gsr'])
        meta['files']=[dict(name=n,identity=v) for n,v in sorted(files.items())]
        raw=f.canonical(meta);path.write_bytes(raw);event['sha256']=sha(raw)
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root,progress=None):
    root=Path(root);before=s.collection.inventory(root);original=validate(root);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-same-view-physical-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            # Every physical mutation still has a valid semantic history and
            # complete hash-bound capture collection; neither can mask a failure.
            semantic.validate(changed,'3-REPLACE')
            retirement.observed.validate(changed)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'joining same-view unrelated physical negative: '+name+': '+str(error))
            else:raise ValueError('joining same-view physical mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason,semanticAndCaptureGates='PASS'))
        if progress:progress(results[-1])
    need(s.collection.inventory(root)==before,'joining same-view physical qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root),sort_keys=True))
