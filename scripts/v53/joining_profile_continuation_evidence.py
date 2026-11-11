"""Original selected-cohort continuation and joining recovery for explicit profiles."""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import wire_archive
from . import joining_preparation_evidence as preparation
from . import joining_profile_initialization_evidence as preceding
from . import joining_transcript as transcript
from . import generation_install_evidence as generation
from .grant_evidence import order as ballot_order
from .joining_profile_evidence import PROFILES, topology

p = preparation; c = p.c; init = p.init; s, f, disk, need, sha = p.s, p.f, p.disk, p.need, p.sha


def adopt(replay, files, donor):
    """Derive the newer-authority generation, preserving exact local obligations."""
    prefix, local, before = disk.current(files); _, remote, incoming = disk.current(donor)
    cap = incoming['capsule']; root = replay.root
    identity = f.decode(files['node.gsr'], 'records', 'NODE', root)['identity']
    need(files['root.gsr'] == donor['root.gsr'] and cap['root'] == root and
         s.catalog.identities(replay.states[-1]['identities'])[identity['node']] == identity,
         'joining profile adoption permanent identity')
    need(cap['cut']['index'] > before['capsule']['cut']['index'] and cap['cut']['view'] != before['capsule']['cut']['view'],
         'joining profile adoption newer authority required')
    need(files['pending.accept'] == disk.EMPTY and not any(n=='applied-end' or n.startswith(('applied-end/','floor-copies')) for n in files),
         'joining profile adoption unsettled local authority')
    c.t.publication.phases.empty_future(files[c.future.FILE],files)
    direct = c.t.confirmation.endpoints(incoming,b'')
    remote_bridges = c.t.publication.original_bridges(replay,remote)
    local_bridges = c.t.publication.original_bridges(replay,local)
    required = [disk.anchor(before['capsule'])]
    for row in c.peers.decode(files[c.PEERS])['plan']['peers']:
        required += [*row.get('renewals',[]),*row['possible']]
    learner = c.learner.decode(files[c.learner.FILE])['plan']
    required += [*learner.get('renewals',[]),*learner['possible']]
    required += [disk.anchor(disk.p.decode(raw)['capsule']) for name,raw in files.items()
                 if name.startswith('sources/') and name.endswith('/source.gscp')]
    needed = {v['cut']['index'] for v in required if v['cut']['index'] not in direct and v['cut']['index'] not in remote_bridges}
    inherited = [rows for at,rows in local_bridges.items() if at in needed]
    ancestry = b''.join(raw for rows in [*remote_bridges.values(),*inherited] for raw in rows)
    need(len(ancestry)<=96*1024, 'joining profile adoption ancestry capacity')
    available = c.t.confirmation.endpoints(incoming,ancestry)
    need(all(available.get(v['cut']['index'])==v for v in required),'joining profile adoption missing original parent')
    certificates = [incoming['objects'][v['certificate']] for v in cap['items'] if v['kind']=='MEMBERSHIP']
    need(certificates,'joining profile adoption missing membership fence')
    cert = max(enumerate(certificates),key=lambda v:(ballot_order(f.decode(v[1],'records','CERTIFICATE')['ballot']),v[0]))[1]
    value = f.decode(cert,'records','CERTIFICATE',root)
    journal = disk.journal(files['grants.gsr'],root,identity['node'])
    prior = next(raw for kind,raw,_ in reversed(journal) if kind=='PROMISE')
    promise = prior
    if ballot_order(f.decode(prior,'records','PROMISE')['ballot']) < ballot_order(value['ballot']):
        promise = f.encode('records','PROMISE',dict(root=root,view=value['authority'],ballot=value['ballot'],basisId=None))
    members = {'source.gscp':remote['source.gscp'],'promise.gsr':promise,'adopted-certificate.gsr':cert}
    if ancestry:members['ancestry.gsr']=ancestry
    for digest,size in incoming['images'].items():
        raw = remote[digest+'.image'];need(len(raw)==size and sha(raw)==digest,'joining profile adoption image binding')
        members[digest+'.image']=raw
    slot = 'b' if prefix=='generations/a/' else 'a';new_prefix='generations/'+slot
    need(not any(name==new_prefix or name.startswith(new_prefix+'/') for name in files),'joining profile adoption inactive slot occupied')
    manifest = dict(root=root,node=identity['node'],generation=slot,cut=cap['cut'],catalog=cap['catalog'],application=cap['application'],
        capsule=sha(incoming['capsuleBytes']),promise=sha(promise),basis=None,selection=None,ownedTail=None,
        files=init.placement.inventory(members))
    members['generation.gsr']=f.encode('records','GENERATION',manifest)
    selector=f.encode('records','SELECTOR',dict(root=root,node=identity['node'],generation=slot,digest=sha(members['generation.gsr'])))
    result=dict(files,**{new_prefix:None,**{new_prefix+'/'+name:raw for name,raw in members.items()},'selector.gsr':selector,
        'grants.gsr':files['grants.gsr']+(promise if promise!=prior else b'')})
    return result,members,dict(inheritedLocalBridges=len(inherited),remoteBridges=len(remote_bridges),
        requiredParents=len({f.canonical(v) for v in required}),promiseAppended=promise!=prior)


def adoption_order(events,joining,members,promise_appended):
    positions=[i for i,v in enumerate(events) if v['event'] in ('ADOPTION_INSTALL_VALIDATED','ADOPTION_INSTALL_BEFORE_RETURN')]
    need(len(positions)==2,'joining profile original adoption transaction count')
    first,last=positions
    need(all(v.get('node')==joining and v.get('scope')=='continuation-owner' for v in (events[first],events[last])),
         'joining profile original adoption owner')
    expected=['ADOPTION_INSTALL_VALIDATED']
    if promise_appended:expected+=['PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED']
    expected+=['ADOPTION_INSTALL_FENCED',*generation.transaction(members)[0],
        'CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED',
        'ADOPTION_INSTALL_BEFORE_RETURN']
    observed=[v['event'] for v in events[first:last+1] if v.get('node')==joining and v.get('scope')=='continuation-owner']
    need(observed==expected,'joining profile original adoption force order')
    return first,last


def prepared_exchanges(root, group, ballot, sources, voters, *, replay=None):
    """Bind every old-majority preparation to the independently derived grants."""
    rows = wire_archive.read(root,'wire.json') if replay is None else wire_archive.from_model(root,replay)
    def decoded():
        for row in rows:
            yield row,*c.exchange.wire(row['request']),*c.exchange.wire(row['response'])
    proposer = ballot['proposer']; ids = {n:f.decode(v['node.gsr'], 'records', 'NODE')['identity'] for n,v in group.items()}
    own = f.decode(sources[proposer][0], 'records', 'BASIS')
    promise = f.encode('records', 'PROMISE', {k:own[k] for k in ('root','view','ballot','basisId')})
    observed=[]; attempts={}
    for row,kind,q,answer,a in decoded():
        # Check both frames of every original exchange, but retain only the
        # bounded current PREPARE set. Other transfers may contain large images.
        if kind=='PREPARE' and q['ballot']==ballot:
            peer=q['recipient']['node']
            identity=(row['request'],row['response'],row['withheld'])
            if peer in attempts:
                original,count=attempts[peer]
                # The physical grant is counted once. Preserve every original
                # attempt for the separate causal/network gate; only identical
                # bounded retries can refer to the same prepared grant here.
                need(identity==original and count<3,'joining profile preparation changed/excess retry')
                attempts[peer]=(original,count+1)
                continue
            need(len(observed)<len(voters)-1,'joining profile preparation response count')
            attempts[peer]=(identity,1)
            observed.append((row,q,answer,a))
    need(len(observed) == len(voters)-1, 'joining profile preparation response count')
    need({q['recipient']['node'] for _,q,_,_ in observed} == set(voters)-{proposer},
         'joining profile preparation exact peers')
    sequences = {}
    for _, q, _, _ in observed: sequences.setdefault(q['trace'], []).append(q['sequence'])
    need(all(sorted(values) == list(range(1, len(values)+1)) for values in sequences.values()),
         'joining profile preparation original correlation')
    used = set(); exchanges = 0
    for row,q,answer,a in observed:
        peer = q['recipient']['node']
        need(peer in voters and peer != proposer and peer not in used and row['withheld'] is False and answer == 'PROMISE',
             'joining profile preparation exact peers')
        used.add(peer)
        # A native multi-peer round shares a trace and increments sequence;
        # older fixtures allocated a separate trace per peer. In either case
        # require the complete contiguous original request sequence.
        fields = dict(root=own['root'], view=own['view'], ballot=ballot, trace=q['trace'], sequence=q['sequence'])
        need(q == dict(fields, sender=ids[proposer], recipient=ids[peer], payload=dict(promise=sha(promise))) and
             a == dict(fields, sender=ids[peer], recipient=ids[proposer], payload=dict(basis=sha(sources[peer][0]))),
             'joining profile preparation original correlation')
        offered=[]
        for _,_,q2,answer,a2 in decoded():
            if (answer=='CHUNK' and q2['ballot']==ballot and q2['sender']==ids[peer] and q2['recipient']==ids[proposer]
                    and base64.b64decode(a2['payload']['bytes'],validate=True)==promise):
                need(not offered,'joining profile preparation original promise transfer')
                offered.append(q2['trace'])
        need(len(offered) == 1, 'joining profile preparation original promise transfer')
        trace = offered[0]
        positions=[i for i,(_,_,q2,_,_) in enumerate(decoded()) if q2['trace']==trace]
        # Keep row positions rather than every decoded transfer or its payload.
        # The unchanged transcript reader still checks exact length and order.
        class Session:
            def __len__(self):return len(positions)
            def __getitem__(self,index):
                row=rows[positions[index]]
                return {k:row[k] for k in ('request','response')}
        session=Session()
        c.transfer.transcript(session, [(sha(promise),promise,'RECORD')], own['root'],own['view'],ballot,
                             ids[peer],ids[proposer],'joining profile preparation promise',chunk_bytes=4*1024*1024)
        exchanges += len(session)
    return dict(ballot=ballot, oldPeers=sorted(used), originalPromiseTransferExchanges=exchanges)


def deferred(files,ballot):
    """Derive the fresh-PROMISE reclaim case from preceding original ownership."""
    _,members,packet=disk.current(files);cap=packet['capsule'];node=f.decode(files['node.gsr'],'records','NODE')['identity']['node']
    rows=disk.journal(files['grants.gsr'],cap['root'],node)
    sources={name.split('/')[1] for name in files if name.startswith('sources/') and name.endswith('/source.gscp')}
    if len(sources)<2 or [v[0] for v in rows[-2:]]!=['PROMISE','BASIS']:return False
    promise,basis=rows[-2:]
    return (ballot_order(promise[2]['ballot'])<ballot_order(ballot) and basis[2]['accepted'] is None and
            basis[2]['cut']==cap['cut'] and promise[1]!=members['promise.gsr'] and basis[1]!=members.get('basis.gsr') and
            files['pending.accept']==disk.EMPTY)


def retirement_end(events,node,start):
    for i in range(start+1,len(events)):
        row=events[i]
        if row.get('node')!=node:continue
        if row['event']=='GRANT_CAPTURED':return None
        if row['event']=='SOURCE_RETIREMENT_BEFORE_RETURN':return i
    return None


def maintenance_copies(rows,events,node,ballot,start,before,installed,voters):
    """Select only independently derived generations seen in original replies.

    A slow unselected grant can acquire some peers before selected installation
    and others after it. The enclosing network/export/floor gates still require
    complete original transfers and durable floor authority. No ledger or final
    snapshot is used to manufacture a matching confirmation.
    """
    end=retirement_end(events,node,start)
    need(end is not None,'joining profile unselected retirement completion')
    floors=[i for i,v in enumerate(events) if start<i<end and v.get('node')==node and v['event']=='FLOOR_RESERVED']
    need(len(floors)==1,'joining profile unselected original floor')
    received={(v.get('request'),v.get('response')) for v in events[start+1:floors[0]]
              if v.get('node')==node and v['event'] in ('NETWORK_RECEIVED','AFTER_RESPONSE_READ')}
    wanted=set(voters)-{node};copies={node:before[node]}
    generation_id=f.catalog()['records']['GENERATION']['id']
    for row in rows:
        request=base64.b64decode(row['request'],validate=True);response=base64.b64decode(row['response'],validate=True)
        if (sha(request),sha(response)) not in received:continue
        _,q=c.exchange.wire(row['request']);answer,a=c.exchange.wire(row['response'])
        if answer!='CHUNK' or q['ballot']!=ballot or q['sender']['node']!=node:continue
        raw=base64.b64decode(a['payload'].get('bytes',''),validate=True)
        if raw[:4]!=b'GSER' or int.from_bytes(raw[8:10],'big')!=generation_id:continue
        peer=q['recipient']['node']
        need(peer in wanted and row['withheld'] is False,'joining profile unselected copy peer')
        candidates=[]
        for group in (before,installed):
            files=group[peer];prefix=disk.current(files)[0]
            if files[prefix+'generation.gsr']==raw:candidates.append(files)
        need(candidates,'joining profile unselected copy not independently derived')
        if peer in copies:
            prefix=disk.current(copies[peer])[0]
            need(copies[peer][prefix+'generation.gsr']==raw,'joining profile unselected conflicting copies')
        copies[peer]=candidates[0]
    need(set(copies)==wanted|{node},'joining profile unselected missing original copy')
    return copies


class Continuation(p.Continuation):
    preparation_label="joining profile"
    def __init__(self, root, initialization, originals, *, old_owner_lifetimes=None):
        super().__init__(root, initialization, originals)
        self.old_owner_lifetimes = old_owner_lifetimes
        self.unselected_maintenance = {}
        self.events = s.collection.read_json(self.root,'events.json',s.collection.EVENT_BYTES)

    def match(self,label):
        # An unselected PREPARE can finish its post-grant maintenance after
        # the selected majority is installed. Derive it from original generation
        # copies, then apply it only after its original retirement completes.
        # Snapshot bytes remain comparison targets, never input to this choice.
        if label.startswith('continuation-installed-'):
            cut=int(label.removeprefix('continuation-installed-'))
            digest=sha(self.replay.phases[cut]['SELECTED'])
            boundaries=[i for i,v in enumerate(self.events) if v['event']=='JOINING_ROUND_INSTALLED' and v.get('record')==digest]
        elif label.startswith(('applied-','published-')):
            kind,index=label.split('-');point='JOINING_SLOT_'+kind.upper()
            boundaries=[i for i,v in enumerate(self.events) if v['event']==point and v.get('index')==int(index)]
        else:boundaries=[]
        if self.unselected_maintenance and boundaries:
            need(len(boundaries)==1,'joining profile unselected maintenance snapshot boundary')
            stop=boundaries[0]
            for node,(start,before,after) in list(self.unselected_maintenance.items()):
                local=[v['event'] for v in self.events[start+1:stop] if v.get('node')==node]
                if 'SOURCE_RETIREMENT_BEFORE_RETURN' not in local:continue
                p.retirement_order(local,p.source_deletions(before,after))
                need(self.group[node]==before,'joining profile unselected maintenance owner changed')
                self.group[node]=after;del self.unselected_maintenance[node]
        super().match(label)

    def prepare(self,node,ballot):
        files=self.group[node];actual=self.captures.original(node,ballot)
        if deferred(files,ballot):
            prefix,_,packet=disk.current(files)
            need(not any(n.startswith('generations/') and n!=prefix[:-1] and not n.startswith(prefix) for n in files),
                 self.preparation_label+' deferred predecessor still owned')
            rows=disk.journal(actual['grants.gsr'],self.replay.root,node)
            need([v[0] for v in rows[-2:]]==['PROMISE','BASIS'],self.preparation_label+' deferred captured suffix')
            identifier=rows[-2][2]['basisId']
            promise=f.encode('records','PROMISE',dict(root=self.replay.root,
                view=s.catalog.authority(self.replay.root,packet['capsule']['cut']['view']),ballot=ballot,basisId=identifier))
            need(rows[-2][1]==promise,self.preparation_label+' deferred original promise')
            # No BASIS/source exists yet. The higher promise releases only an
            # obsolete unselected source; the installed current stays pinned.
            staged=dict(files,**{'grants.gsr':files['grants.gsr']+promise})
            if node==ballot['proposer']:
                staged['allocator.gsr']=f.encode('records','ALLOCATOR',dict(root=self.replay.root,node=node,counter=ballot['counter']))
            group=dict(self.group,**{node:staged});files=self.maintenance(group,node)
            need(files['grants.gsr'].endswith(promise),self.preparation_label+' deferred promise preserved')
            files=dict(files,**{'grants.gsr':files['grants.gsr'][:-len(promise)]})
        self.group[node],source=init.prepare(files,ballot,actual['grants.gsr'],self.identifiers)
        self.prepared(node,self.group[node]);return source

    def preparation(self):
        ballot = init.next_ballot(self.group['node-1'])
        need(ballot['counter'] == self.captures.counter, 'joining profile preparation next ballot')
        sources = {node:self.prepare(node,ballot) for node in self.initialization.voters}
        boundary = prepared_exchanges(self.root,self.group,ballot,sources,self.initialization.voters,replay=self.replay)
        for node in self.initialization.voters: self.group[node] = self.maintenance(self.group,node)
        return boundary

    def campaign(self,cut,counter):
        selected=self.replay.phases[cut]['SELECTED'];value=f.decode(selected,'records','SELECTED')
        self.voters=tuple(v['voter'] for v in value['sources'])
        s.catalog.majority(self.replay.states[cut]['cut']['view'],list(self.voters))
        need(set(self.voters)<=set((*self.initialization.voters,self.joining)),'joining profile selected reachable owners')
        self.install_campaign(cut,counter,selected)

    def install_campaign(self,cut,counter,selected):
        ballot=dict(counter=counter,proposer='node-1',incarnation=f.decode(self.group['node-1']['node.gsr'],'records','NODE')['identity']['storage'])
        # A slower peer may force its grant even though the proposer selects a
        # different majority. Derive every observed grant from preceding state,
        # but install only the immutable selected cohort. Captures supply UUIDs
        # and exact comparison targets; they never replace derived owner files.
        prepared={node for node,key in self.captures.by_ballot if key==f.canonical(ballot)}
        need(set(self.voters)<=prepared<=set((*self.initialization.voters,self.joining)),
             'joining profile campaign prepared owners')
        sources={node:self.prepare(node,ballot) for node in sorted(prepared)}
        self.unselected_maintenance={};unselected={};before_group=copy.deepcopy(self.group)
        for node in sorted(prepared-set(self.voters)):
            before=copy.deepcopy(self.group[node]);after=self.maintenance(self.group,node)
            if p.source_deletions(before,after):
                captured=self.captures.by_ballot[node,f.canonical(ballot)]['capturedEvent']
                unselected[node]=(captured,before)
        sources={node:sources[node] for node in self.voters}
        maintained={node:self.maintenance(self.group,node) for node in self.voters}
        for node in self.voters:self.group[node]=c.install(maintained[node],sources,selected)
        for node,(captured,before) in unselected.items():
            # An interrupted/unfinished maintenance does not authorize deletion.
            if retirement_end(self.events,node,captured) is None:continue
            copies=maintenance_copies(wire_archive.from_model(self.root,self.replay),self.events,node,ballot,
                                      captured,before_group,self.group,self.voters)
            after=self.maintenance(copies,node)
            self.unselected_maintenance[node]=(captured,before,after)
        self.match('continuation-installed-'+str(cut))
        for node in self.voters:
            need((self.root/f'continuation-grants-{cut}-{node}.gsr').read_bytes()==self.group[node]['grants.gsr'],
                 'joining continuation exact standalone grants')


    def recover(self,events):
        before=self.group[self.joining];self.joining_snapshot('joining-before-final-recovery')
        lower=max(block['PUBLICATION_BEFORE_RETURN'] for (index,_),block in c.t.publication.phases.blocks(
            events,self.replay,old_owner_lifetimes=self.old_owner_lifetimes).items() if index==11)
        starts=[i for i,v in enumerate(events) if v['event']=='ADOPTION_INSTALL_VALIDATED' and v.get('node')==self.joining]
        need(len(starts)==1,'joining profile recovery requires original newer-authority adoption')
        upper=starts[0];identities=s.catalog.identities(self.replay.states[-1]['identities'])
        wire=wire_archive.from_model(self.root,self.replay)
        rows=transcript.causal(events,wire,identities,self.replay.root,transfer_only=True);contents=[]
        transcript.transfers(rows,contents=contents)
        transfers=[v for v in contents if v['offer']['request']['sender']['node']==self.joining and
                   lower<v['offer']['sent']<v['commit']['delivered']<upper]
        capsules=[v for v in transfers if v['kind']=='CAPSULE']
        need(len(capsules)==1,'joining profile recovery original capsule count')
        donor=capsules[0]['offer']['request']['recipient']['node']
        need(donor in self.voters,'joining profile recovery derived donor')
        files=self.group[donor];prefix,remote,packet=disk.current(files);cap=packet['capsule']
        expected=[('CAPSULE',sha(f.canonical(cap['cut'])),remote['source.gscp'])]
        expected += [('APPLICATION',h,remote[h+'.image']) for h in sorted(packet['images'])]
        expected += [('RECORD',sha(f.canonical(dict(root=self.replay.root,cut=cap['cut'],scope='retained-current-ancestry'))),files[prefix+'generation.gsr'])]
        if remote.get('ancestry.gsr'):expected.append(('RECORD',sha(remote['ancestry.gsr']),remote['ancestry.gsr']))
        need(len(transfers)==len(expected),'joining profile recovery complete transfer count')
        for value,(kind,reference,raw) in zip(transfers,expected):
            q=value['offer']['request']
            need(value['kind']==kind and value['raw']==raw and q['payload']['digest']==reference and
                 q['recipient']['node']==donor,'joining profile recovery original transfer content')
        self.group[self.joining],members,detail=adopt(self.replay,before,files)
        start,end=adoption_order(events,self.joining,members,detail['promiseAppended'])
        need(start==upper,'joining profile recovery original adoption boundary')
        self.joining_snapshot('joining-after-final-recovery')
        expected_result=dict(before=disk.current(before)[2]['capsule']['cut'],after=cap['cut'],adopted=True,installed=False,publicReady=False)
        need(s.collection.read_json(self.root,'joining-final-recovery.json',8192)==expected_result,'joining profile recovery result disagrees with derivation')
        return dict(**detail,donor=donor,fromCut=expected_result['before']['index'],toCut=cap['cut']['index'],
            originalTransfers=len(transfers),adoptionStart=start,adoptionEnd=end,sameViewInstallation=False)

    def run(self):
        boundary = self.preparation(); counter = boundary['ballot']['counter']
        self.campaign(9,counter+1); self.slot(10)
        for node in self.voters:self.group[node] = self.maintenance(self.group,node)
        self.campaign(10,counter+2); self.slot(11)
        events=s.collection.read_json(self.root,'events.json',s.collection.EVENT_BYTES)
        recovery=None
        if disk.current(self.group[self.joining])[2]['capsule']['cut']['index'] < 11:recovery=self.recover(events)
        self.match('after-close'); self.joining_snapshot('joining-originals-stable-cold')
        c.cold_order(events,joining=self.joining)
        retired=self.captures.retirement_order(events,self.group,owners=(*self.initialization.voters,self.joining))
        return dict(status='PARTIAL',scope='profile-selected-continuation',profile=str(self.replay.size)+'-'+self.replay.kind,
            capturedGrantComparisons=self.captures.comparisons,ownerSnapshotComparisons=self.comparisons,
            sourceRetirementLocalOrderSegments=retired,finalCut=11,recovery=recovery,phase3Complete=False,
            completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False)


def validate(root,profile):
    size,kind,old,_=topology(profile);root=Path(root);inventory=s.collection.inventory(root)
    events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
    observed=p.Captures(root,events,voters=old[:size//2+1])
    c.t.publication.validate(root,size=size,kind=kind)
    replay=s.Replay(root,size=size,kind=kind)
    for index in range(1,12):replay.step(index)
    replay.publication_receipts=c.t.publication.CheckpointReceipts(root,replay)
    history=p.History(root,replay,observed);history.run()
    owner=init.placement.Placement(root,history);owner.run()
    handoff=init.retirement.Retirement(root,owner);handoff.run()
    initialized=p.Initialization(root,handoff,observed);initialized.run()
    result=Continuation(root,initialized,observed).run()
    need(s.collection.inventory(root)==inventory,'joining profile continuation original changed')
    return result


# Only continuation-local mutations are used: the independently replayed
# placement/retirement/initialization prefix must still pass on each copy.
COMMON_NEGATIVES = {
    **{name:p.NEGATIVES[name] for name in ('intermediate-extra-file', 'intermediate-frozen-ledger')},
    **{name:c.NEGATIVES[name][2] for name in ('joint-peer-revision', 'joint-learner-confirmation-lost',
        'joint-inactive-generation-lost', 'stable-peer-revision', 'standalone-grant-changed',
        'cold-peer-revision', 'cold-force-omitted')},
    'cold-owner-substituted':'joining continuation original cold owner',
}
RECOVERY_NEGATIVES = {
    'recovery-before-extra-allocation':'joining continuation exact family: joining-before-final-recovery: replica',
    **{name:'joining continuation exact family: joining-after-final-recovery: replica' for name in (
        'recovery-ancestry-lost', 'recovery-peer-debt-lost', 'recovery-extra-allocation',
        'recovery-original-source-lost', 'recovery-prior-generation-lost')},
    'recovery-result-claims-install':'joining profile recovery result disagrees with derivation',
    'adoption-force-missing':'joining profile original adoption force order',
    'adoption-selector-before-generation':'joining profile original adoption force order',
    'adoption-owner-substituted':'joining profile original adoption owner',
}


def refresh_snapshot(root):
    """Rehash a disposable snapshot, retaining original identities of survivors."""
    path = root/'inventory.json'; rows = json.loads(path.read_bytes())
    for family in rows:
        if not family['present']:continue
        directory = root/family['name']; kept = []
        for row in family['files']:
            member = directory/row['name']
            if not member.exists():continue
            if member.is_file():row['identity'].update(size=member.stat().st_size,sha256=sha(member.read_bytes()))
            kept.append(row)
        family['files'] = kept
    path.write_bytes(f.canonical(rows))


def mutate(root, name):
    root = Path(root)
    if name in COMMON_NEGATIVES and name != 'cold-owner-substituted':
        p.mutate(root,name);return
    if name.startswith('adoption-') or name == 'cold-owner-substituted':
        path = root/'events.json'; events = json.loads(path.read_bytes())
        if name == 'cold-owner-substituted':
            next(row for row in events if row.get('scope')=='stable-cold-owner')['node']='node-1'
        elif name == 'adoption-owner-substituted':
            next(row for row in events if row['event']=='ADOPTION_INSTALL_BEFORE_RETURN')['node']='node-1'
        else:
            first = next(i for i,row in enumerate(events) if row['event']=='ADOPTION_INSTALL_VALIDATED')
            node = events[first]['node']
            positions = {row['event']:i for i,row in enumerate(events[first:],first)
                         if row.get('node')==node and row.get('scope')=='continuation-owner'}
            if name == 'adoption-force-missing':events.pop(positions['CURRENT_FILES_FORCED'])
            else:
                a,b = positions['INSTALL_GENERATION_FORCED'],positions['INSTALL_SELECTOR_WRITTEN']
                events[a],events[b] = events[b],events[a]
        path.write_bytes(f.canonical(events));return
    if name == 'recovery-result-claims-install':
        path=root/'joining-final-recovery.json';value=json.loads(path.read_bytes());value['installed']=True
        path.write_bytes(f.canonical(value));return
    snapshot=root/('joining-before-final-recovery' if name=='recovery-before-extra-allocation' else 'joining-after-final-recovery')
    replica=snapshot/'replica';files=disk.inventory(replica);prefix,members,_=disk.current(files)
    if name.endswith('extra-allocation'):
        path=replica/'allocator.gsr';value=f.decode(path.read_bytes(),'records','ALLOCATOR');value['counter']+=1
        path.write_bytes(f.encode('records','ALLOCATOR',value))
    elif name=='recovery-peer-debt-lost':
        path=replica/c.PEERS;value=c.peers.decode(path.read_bytes())
        changed=False
        for row in value['plan']['peers']:
            if row.get('renewals'):row.pop('renewals');changed=True
            if len(row['possible'])>1:row['possible']=row['possible'][-1:];changed=True
        need(changed,'joining profile negative requires original peer debt')
        path.write_bytes(c.peers.frame(value))
    elif name=='recovery-original-source-lost':
        source=next((replica/'sources').glob('*/source.gscp'));shutil.rmtree(source.parent)
    elif name=='recovery-prior-generation-lost':
        shutil.rmtree(replica/'generations'/('b' if prefix=='generations/a/' else 'a'))
    elif name=='recovery-ancestry-lost':
        # A self-consistent new manifest/selector is still not the expected
        # adoption: the donor alone does not cover every local obligation.
        need('ancestry.gsr' in members,'joining profile negative requires inherited ancestry')
        (replica/prefix/'ancestry.gsr').unlink()
        path=replica/prefix/'generation.gsr';manifest=f.decode(path.read_bytes(),'records','GENERATION')
        manifest['files']=[row for row in manifest['files'] if row['path']!='ancestry.gsr']
        raw=f.encode('records','GENERATION',manifest);path.write_bytes(raw)
        path=replica/'selector.gsr';selector=f.decode(path.read_bytes(),'records','SELECTOR');selector['digest']=sha(raw)
        path.write_bytes(f.encode('records','SELECTOR',selector))
    else:raise ValueError('unknown joining profile continuation mutation: '+name)
    refresh_snapshot(snapshot)


def qualify(root,profile,progress=None):
    root=Path(root);inventory=s.collection.inventory(root);original=validate(root,profile);results=[]
    if progress:progress(dict(stage='original',status='PASS',profile=profile))
    cases=dict(COMMON_NEGATIVES)
    if original['recovery'] is not None:cases.update(RECOVERY_NEGATIVES)
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-profile-continuation-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            preceding.validate(copied,profile)
            try:validate(copied,profile)
            except ValueError as error:
                need(str(error)==reason,'joining profile continuation unrelated negative: '+name+': '+str(error))
            else:raise ValueError('joining profile continuation accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason,initializationGate='PASS'))
        if progress:progress(results[-1])
    need(s.collection.inventory(root)==inventory,'joining profile continuation original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--profile',required=True,choices=PROFILES)
    parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    result=qualify(args.root,args.profile,lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))
