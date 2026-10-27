"""Original-first model for inherited obligations crossing an actual REMOVE.

The only observed identifiers are bootstrap inputs and fresh source UUIDs. Vote,
application, source, selector and ledger bytes are derived before comparison.
This module is under qualification; no automatic runtime acceptance is implied.
"""
import copy
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from . import inherited_future_evidence as inherited
from . import admitted_cross_view_evidence as cross
from . import future_source_evidence as future_source

u, s, p, c, f, e, need = inherited.u, inherited.s, inherited.p, inherited.c, inherited.f, inherited.e, inherited.need


def state(files):
    _, members, packet = c.current(files)
    return members, packet, f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG')


def witness(group, names, raw, phase, root):
    return [dict(voter=n, incarnation=u.identity(group[n])['storage'], receipt=e.digest(f.canonical(
        dict(root=root, voter=n, incarnation=u.identity(group[n])['storage'], phase=phase, record=e.digest(raw))))) for n in names]


def bridges(members):
    result = {}
    for raw in cross.ancestry_frames(members['ancestry.gsr']) if 'ancestry.gsr' in members else ():
        if int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['CHECKPOINT']['id']:
            at = f.decode(raw, 'records', 'CHECKPOINT')['start']['index']
            need(at not in result, 'inherited adoption duplicate ancestry')
            result[at] = [raw]
        else:
            need(bool(result), 'inherited adoption orphan ancestry ACK')
            result[at].append(raw)
    return result


def anchors(packet):
    cap = packet['capsule']; result = {cap['cut']['index']: c.anchor(cap)}
    for item in cap['items']:
        row = f.decode(packet['objects'][item['statement']], 'records', 'CHECKPOINT')
        for edge, suffix in [('start', 'Before'), ('end', 'After')]:
            result[row[edge]['index']] = dict(cut=row[edge], catalog=row['catalog'+suffix], application=row['application'+suffix])
    return result


def required(files):
    """Actual frozen source cuts, round endpoints and recorded peer uncertainty."""
    members, packet, _ = state(files); result = anchors(packet)
    for rows in bridges(members).values():
        row = f.decode(rows[0], 'records', 'CHECKPOINT')
        result[row['start']['index']] = dict(cut=row['start'], catalog=row['catalogBefore'], application=row['applicationBefore'])
    cuts = [packet['capsule']['cut']]
    for raw in cross.ancestry_frames(members['selected-sources.gsr']):
        cuts.append(f.decode(raw, 'records', 'BASIS')['cut'])
    if c.COVERAGE in members:
        coverage = json.loads(members[c.COVERAGE])
        if 'first' in coverage:
            cuts += [coverage['first'][edge]['cut'] for edge in ('parent', 'end')]
    for peer in s.r.decode(files[s.FILE])['plan']['peers']:
        cuts += [a['cut'] for a in peer['possible']]
    for name, raw in files.items():
        if name.startswith('sources/') and name.endswith('/source.gscp'):
            cuts.append(s.p.decode(raw)['capsule']['cut'])
    need(all(cut['index'] in result and result[cut['index']]['cut'] == cut for cut in cuts),
         'inherited adoption authenticated parent')
    return {cut['index']: result[cut['index']] for cut in cuts}


class Walk:
    def __init__(self, root, *, selected_prefix=None):
        self.selected_prefix = selected_prefix
        self.root = Path(root); self.names = ['node-'+str(i) for i in range(1, 5)]
        self.group = s.initialize(p.original(self.root, 4, False))
        self.group = {n: dict(files, **{u.FILE: u.frame(u.initial(files), {})}) for n, files in self.group.items()}
        self.snapshots = set(); self.futures = {}; self.pending = {}; self.sources = {}; self.intents = {}; self.ends = {}
        self.observed = set()
        self.match('retaining-genesis')

    def match(self, label, group=None):
        p.match(self.root, label, self.group if group is None else group); self.snapshots.add(label)

    def settle(self, label, names):
        self.group.update(p.settled({n: self.group[n] for n in names})); self.match(label)

    def reconcile(self, names):
        for n in names:
            files = self.group[n]; old = s.r.decode(files[s.FILE]); cap = state(files)[1]['capsule']
            view = cap['cut']['view']; voters = set(view['old']) | set(view['new'])
            plan = dict(old['plan'], view=view, peers=[row for row in old['plan']['peers'] if row['identity']['node'] in voters])
            if plan != old['plan']:
                files[s.FILE] = s.r.frame(dict(old, revision=old['revision']+1, previous=e.digest(files[s.FILE]), plan=plan))

    def observe(self, n, raw, cut):
        self.observed.add(f.canonical(dict(voter=n,storage=u.identity(self.group[n])['storage'],record=e.digest(raw),parent=e.digest(f.canonical(cut)))))

    def campaign(self, counter, names, proposer, label, install_label=None):
        identity = u.identity(self.group[proposer]); ballot = dict(counter=counter, proposer=proposer, incarnation=identity['storage'])
        prepared = dict(self.group); grants = {}; sources = {}; identifiers = set()
        for n in names:
            files = self.group[n]; members, packet, _ = state(files)
            phases = () if files['pending.accept'] == c.EMPTY else ('PROOF', 'CERTIFICATE')
            raw, tail = inherited.carried.captured(files, phases)
            captured = s.p.decode(raw); cap = captured['capsule']
            history = c.journal(c.inventory(self.root/(label+'-prepared')/n)['grants.gsr'], cap['root'], n)
            prior = c.journal(files['grants.gsr'], cap['root'], n)
            need(history[:len(prior)] == prior and [v[0] for v in history[len(prior):]] == ['PROMISE', 'BASIS'], 'inherited adoption original grant extension')
            identifier = history[-2][2]['basisId']
            need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
                 and all(v[2].get('basisId') != identifier for v in prior), 'inherited adoption fresh source UUID')
            identifiers.add(identifier)
            fields = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
            promise = f.encode('records', 'PROMISE', fields); objects = dict(captured['objects'])
            wrapper = future_source.wrapper(promise, files[s.FILE], self.pending[n]) if n in self.pending else s.s.wrap(promise, files[s.FILE])
            objects[e.digest(wrapper)] = wrapper
            if n in self.pending: objects[e.digest(self.pending[n])] = self.pending[n]
            source = c.packet_bytes(cap, objects, captured['images']); frozen = s.p.decode(source)
            basis = f.encode('records', 'BASIS', dict(fields, voter=n, cut=cap['cut'], capsule=e.digest(frozen['capsuleBytes']),
                            inventory=e.digest(frozen['indexBytes']), accepted=tail))
            folder = 'sources/'+identifier
            prepared[n] = dict(files, **{'grants.gsr': files['grants.gsr']+promise+basis, folder: None, folder+'/source.gscp': source})
            prepared[n].update({folder+'/'+h+'.image': members[h+'.image'] for h in frozen['images']})
            if n == proposer: prepared[n]['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=n, counter=counter))
            grants[n], sources[n] = (promise, basis), (basis, frozen, wrapper)
        self.match(label+'-prepared', prepared)
        longest = max(names, key=lambda n: (sources[n][1]['capsule']['cut']['index'], n == proposer))
        cap = sources[longest][1]['capsule']; objects = (dict(sources[longest][1]['objects']) if self.selected_prefix is None
                else self.selected_prefix(sources[longest][1],self.group[longest]['root.gsr']))
        tails = [f.decode(grants[n][1], 'records', 'BASIS')['accepted'] for n in names]
        options = [(f.decode(sources[n][1]['objects'][h], 'records', 'ACCEPT')['ballot']['counter'], n, h)
                   for n, h in zip(names, tails) if h]
        choice = max(options) if options else None; entry = None
        if choice:
            _, from_node, tail = choice; packet = sources[from_node][1]
            accept = f.decode(packet['objects'][tail], 'records', 'ACCEPT'); entry = accept['entry']
            command = f.decode(packet['objects'][entry], 'records', 'ENTRY')
            objects.update({h: packet['objects'][h] for h in (tail, entry, command['payload'])})
        selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot,
            cut=cap['cut'], nextEntry=entry, sources=[dict(voter=n, basisId=f.decode(grants[n][1], 'records', 'BASIS')['basisId'], basisDigest=e.digest(grants[n][1])) for n in names]))
        chosen = dict(prepared)
        for n in names: chosen[n] = dict(prepared[n], **{'grants.gsr': prepared[n]['grants.gsr']+selected})
        self.match(label+'-selected', chosen)
        installed = dict(chosen)
        for n in names:
            files = self.group[n]; prefix, previous, _ = c.current(files)
            intent = s.intent(u.identity(files), selected, files[s.FILE], [sources[k] for k in names]); self.intents[n] = intent
            content = dict(objects, **{e.digest(intent): intent})
            content.update({e.digest(raw): raw for raw in self.pending.values()})
            if self.selected_prefix is not None and 'owned-tail.gsr' in previous:
                old_packet=c.current(files)[2];accept_raw=previous['owned-tail.gsr']
                old_entry=f.decode(accept_raw,'records','ACCEPT')['entry']
                payload=f.decode(old_packet['objects'][old_entry],'records','ENTRY')['payload']
                for h in (e.digest(accept_raw),old_entry,payload):content[h]=old_packet['objects'][h]
            source = c.packet_bytes(cap, content, sources[longest][1]['images']); local = dict(zip(('promise.gsr', 'basis.gsr'), grants[n]))
            local.update({'source.gscp': source, 'selected.gsr': selected, 'selected-sources.gsr': b''.join(grants[k][1] for k in names)})
            if choice: local['owned-tail.gsr'] = content[choice[2]]
            prior_basis = f.decode(previous['basis.gsr'], 'records', 'BASIS')['cut'] if 'basis.gsr' in previous else cap['cut']
            retained_cuts={prior_basis['index']}
            for peer in s.r.decode(files[s.FILE])['plan']['peers']:retained_cuts.update(a['cut']['index'] for a in peer['possible'])
            hidden=retained_cuts-set(anchors(sources[longest][1]))
            if hidden:local['ancestry.gsr']=b''.join(b''.join(bridges(previous)[i]) for i in sorted(hidden))
            local.update({h+'.image': previous[h+'.image'] for h in sources[longest][1]['images']})
            selector, generation = c.generation(local, s.p.decode(source)['capsule'], n, 'b' if prefix == 'generations/a/' else 'a', choice[2] if choice else None)
            installed[n] = dict(chosen[n], **generation, **{'selector.gsr': selector, s.FILE: s.merged(files[s.FILE], [self.group[k][s.FILE] for k in names])})
        self.group = installed; self.sources = sources
        self.match(install_label or label+'-installed')

    def publication(self, kind, command, names, label, original_entry=None, stop=False):
        before = self.group; first = names[0]; members, packet, catalog_before = state(before[first]); cap = packet['capsule']; root = cap['root']
        selected = f.decode(members['selected.gsr'], 'records', 'SELECTED'); slot = cap['cut']['index']+1
        body = b'' if kind == 'BARRIER' else f.canonical(command)
        entry = original_entry or f.encode('records', 'ENTRY', dict(root=root, authority=e.authority(root, cap['cut']['view']), index=slot,
            previous=cap['cut']['entry'], origin=selected['ballot'], kind=kind, payload=e.digest(body)))
        if label.startswith('slot-'):
            need((self.root/f'entry-{slot}.gsr').read_bytes() == entry and (self.root/f'payload-{slot}.bin').read_bytes() == body,
                 'inherited adoption original command')
        accept = f.encode('records', 'ACCEPT', dict(root=root, authority=selected['view'], ballot=selected['ballot'], entry=e.digest(entry), index=slot))
        proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witness(before, names, accept, 'ACCEPT', root)))
        certificate = f.encode('records', 'CERTIFICATE', dict(f.decode(proof, 'records', 'PROOF'), proofs=witness(before, names, proof, 'PROOF', root)))
        if label.startswith('slot-'):
            for n in names:
                for raw in (accept,proof): self.observe(n,raw,cap['cut'])
        phases = dict(before)
        for stage, extra in [('accepted', b''), ('proved', proof), ('certified', proof+certificate)]:
            for n in names:
                files = before[n]; local = state(files)[0]
                vote = e.container([files['selector.gsr'], local['promise.gsr'], local['selected.gsr'], entry, accept], body)+extra
                vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]; phases[n] = dict(files, **{'pending.accept': vote})
            if label.startswith('slot-') or stage == 'certified': self.match(label+'-'+stage, phases)
        image = members[cap['application']+'.image']
        after = cross.context.reduce_catalog(catalog_before, cap['catalog'], kind, command, e.digest(entry), root)
        cross.context.majority(cap['cut']['view'], names); cross.context.majority(after['cut']['view'], names)
        catalog = f.encode('records', 'CATALOG', after); target = dict(cut=after['cut'], catalog=e.digest(catalog), application=after['application'])
        items = list(cap['items']); membership = kind in ('INTENT', 'FINAL')
        start = dict(root=root, scope='MEMBERSHIP' if membership else 'RANGE', start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])
        if not membership and items and items[-1]['kind'] == 'RANGE': start = f.decode(packet['objects'][items.pop()['statement']], 'records', 'CHECKPOINT')
        statement = dict(start, end=after['cut'], catalogAfter=e.digest(catalog), applicationAfter=after['application'])
        statement_raw = f.encode('records', 'CHECKPOINT', statement); lower = {i: a for i, a in required(before[first]).items() if start['start']['index'] < i < slot-1}
        parents = [('ancestor-'+str(k), a) for k, (_, a) in enumerate(sorted(lower.items()))]
        if start['start'] != cap['cut']: parents.append(('parent', c.anchor(cap)))
        ends = {}; applied = dict(phases); acknowledgements = []; bridge_rows = {}
        for n in names:
            def ack(raw): return f.encode('records', 'CHECKPOINT_ACK', dict(root=root, voter=n, incarnation=u.identity(before[n])['storage'], cut=after['cut'], statement=e.digest(raw)))
            end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
                           (before[n]['selector.gsr'], certificate, catalog, statement_raw, image, ack(statement_raw))))
            acknowledgements.append(end['ack.gsr'])
            for name, anchor in parents:
                raw = f.encode('records', 'CHECKPOINT', dict(statement, start=anchor['cut'], catalogBefore=anchor['catalog'], applicationBefore=anchor['application']))
                end[name+'-statement.gsr'], end[name+'-ack.gsr'] = raw, ack(raw)
                rows = bridge_rows.setdefault(anchor['cut']['index'], [raw]); rows.append(ack(raw))
            if label.startswith('slot-'):
                for name,raw in end.items():
                    if name=='ack.gsr' or name.endswith('-ack.gsr'): self.observe(n,raw,after['cut'])
            end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=root, node=n, files=[dict(path=k, **e.info(v)) for k,v in sorted(end.items())]))
            ends[n] = end; applied[n] = dict(phases[n], **{'applied-end': None}, **{'applied-end/'+k:v for k,v in end.items()})
        self.match(label+'-applied', applied); self.ends = ends
        if stop: self.group = applied; return entry
        content = {e.digest(before[first][k]): before[first][k] for k in ('root.gsr', 'genesis.gsr')}
        for item in items: content.update(cross.retain_item(packet, item))
        content.update({e.digest(raw): raw for raw in (entry, body, accept, proof, certificate, catalog, statement_raw, *acknowledgements)})
        descriptor = None
        if membership:
            operation = next(row for row in catalog_before['results'] if row['request']['number'] == catalog_before['active'])
            raw = f.canonical({k: operation[k] for k in ('request', 'prepared', 'receipt')}); descriptor = e.digest(raw); content[descriptor] = raw
        for i, rows in bridges(members).items():
            if i in required(before[first]) and i not in anchors(packet) and i<=start['start']['index']: bridge_rows[i] = rows
        for rows in bridge_rows.values(): content.update({e.digest(raw): raw for raw in rows})
        item = dict(kind=statement['scope'], statement=e.digest(statement_raw), endorsements=[e.digest(raw) for raw in acknowledgements],
                    certificate=e.digest(certificate) if membership else None, descriptor=descriptor)
        coverage = dict(schema='gse-v53-selected-coverage/1.3', selection=e.digest(members['selected.gsr']), parent=c.anchor(cap), certificate=e.digest(certificate))
        if selected['cut'] != cap['cut']:
            previous = json.loads(members[c.COVERAGE]); first_end = previous.get('first') or dict(parent=previous['parent'], end=c.anchor(cap), certificate=previous['certificate'])
            coverage.update(schema='gse-v53-round-coverage/1.3', first=first_end)
            old_certificate = packet['objects'][first_end['certificate']]; val = f.decode(old_certificate, 'records', 'CERTIFICATE')
            old_entry = packet['objects'][val['entry']]; v = f.decode(old_entry, 'records', 'ENTRY')
            old_proof = dict(val); del old_proof['proofs']; old_accept = dict(old_proof); del old_accept['accepts']
            for raw in (old_certificate, old_entry, packet['objects'][v['payload']], f.encode('records','PROOF',old_proof), f.encode('records','ACCEPT',old_accept)): content[e.digest(raw)] = raw
        if lower: coverage['ancestors'] = [a for _,a in sorted(lower.items())]
        published = dict(before)
        for n in names:
            files = before[n]; prefix, local, _ = c.current(files); objects = dict(content); ledger = files[s.FILE]
            if label == 'carried':
                intent = self.intents[n]; completion = inherited.frame(0x47534643, bytes.fromhex(e.digest(intent))+s.part(ledger))
                objects.update({e.digest(raw): raw for raw in (intent, completion, *self.pending.values())})
                active = s.r.decode(ledger); plan = copy.deepcopy(active['plan'])
                for peer in plan['peers']:
                    if peer['identity']['node'] in ('node-2','node-3'): peer['possible'].append(target)
                ledger = s.r.frame(dict(active, revision=active['revision']+1, previous=e.digest(ledger), plan=plan))
            raw = c.packet_bytes(dict(cap, **target, items=items+[item]), objects, {target['application']: len(image)})
            new = {k:local[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
            new.update({'source.gscp': raw, c.COVERAGE: f.canonical(coverage), target['application']+'.image': image})
            # Publication writes newly endorsed RANGE bridges first, followed
            # by the retained original-era proofs. Preserve that derived order;
            # globally sorting both groups changes the manifest/selector bytes.
            if bridge_rows: new['ancestry.gsr'] = b''.join(b''.join(rows) for rows in bridge_rows.values())
            selector, generation = c.generation(new, s.p.decode(raw)['capsule'], n, 'b' if prefix=='generations/a/' else 'a', None)
            result = {k:v for k,v in files.items() if k!='applied-end' and not k.startswith('applied-end/')}
            result.update(generation); result.update({'selector.gsr':selector, 'pending.accept':c.EMPTY, s.FILE:ledger})
            if label == 'carried' and n in self.pending:
                result[u.FILE] = u.frame(dict(u.initial(files), revision=2, previous=e.digest(files[u.FILE])), {})
            published[n] = result
        self.group = published; self.match(label+'-published')
        if label == 'carried': self.pending = {}
        return entry


def prelude(root, *, selected_prefix=None):
    walk = Walk(root,selected_prefix=selected_prefix); names = walk.names; voters = names[:3]
    walk.campaign(2, names, 'node-1', 'round-1'); walk.settle('round-1-settled', names)
    entry = walk.publication('BARRIER', None, voters, 'slot-1', stop=True)
    walk.match('original-certified')
    for n, peer in [('node-1','node-2'), ('node-2','node-3')]:
        raw, _ = inherited.original.pending(walk.group[n], walk.ends[n], walk.group[peer])
        walk.pending[n] = raw; walk.group[n][u.FILE] = raw
        walk.futures[e.digest(raw)] = raw
    walk.match('two-futures')
    walk.campaign(3, names, 'node-4', 'round-3', 'inherited-installed')
    for n in voters:
        files = walk.group[n]; local = state(files)[0]; selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
        original = f.decode(entry, 'records', 'ENTRY')
        accept = f.encode('records', 'ACCEPT', dict(root=original['root'], authority=original['authority'], ballot=selected['ballot'], entry=e.digest(entry), index=1))
        cleaned = {k:v for k,v in files.items() if k!='applied-end' and not k.startswith('applied-end/')}
        cleaned['pending.accept'] = e.container([files['selector.gsr'],local['promise.gsr'],local['selected.gsr'],entry,accept],b'')
        walk.group[n] = cleaned
    walk.settle('inherited-maintained', names)
    walk.publication('BARRIER', None, voters, 'carried', original_entry=entry)
    walk.settle('survivors-published', voters)
    return walk


def adoption(walk):
    node = 'node-4'; files = walk.group[node]; prefix, _, _ = c.current(files)
    remote, packet, _ = state(walk.group['node-1']); cap = packet['capsule']
    cert = packet['objects'][cap['items'][-1]['certificate']]; certificate = f.decode(cert,'records','CERTIFICATE')
    promise = f.encode('records','PROMISE',dict(root=cap['root'],view=certificate['authority'],ballot=certificate['ballot'],basisId=None))
    intent = walk.intents[node]; completion = inherited.frame(0x47534643,bytes.fromhex(e.digest(intent))+s.part(files[s.FILE]))
    objects = dict(packet['objects'], **walk.futures, **{e.digest(raw):raw for raw in (intent,completion)})
    source = c.packet_bytes(cap,objects,packet['images'])
    slot = 'b' if prefix=='generations/a/' else 'a'
    new = {'promise.gsr':promise,'source.gscp':source,'adopted-certificate.gsr':cert}
    new.update({h+'.image':remote[h+'.image'] for h in packet['images']})
    if 'ancestry.gsr' in remote:new['ancestry.gsr']=remote['ancestry.gsr']
    manifest = f.encode('records','GENERATION',dict(root=cap['root'],node=node,generation=slot,cut=cap['cut'],catalog=cap['catalog'],application=cap['application'],
        capsule=e.digest(s.p.decode(source)['capsuleBytes']),promise=e.digest(promise),basis=None,selection=None,ownedTail=None,
        files=[dict(path=k,size=len(v),sha256=e.digest(v)) for k,v in sorted(new.items())]))
    new['generation.gsr'] = manifest; selector=f.encode('records','SELECTOR',dict(root=cap['root'],node=node,generation=slot,digest=e.digest(manifest)))
    active=s.r.decode(files[s.FILE]);plan=copy.deepcopy(active['plan'])
    # Both inherited proofs independently derive the same BARRIER-1 result.
    target=anchors(packet).get(1)
    if target is None:
        lower=f.decode(bridges(remote)[1][0],'records','CHECKPOINT')
        target=dict(cut=lower['start'],catalog=lower['catalogBefore'],application=lower['applicationBefore'])
    for row in plan['peers']:
        if row['identity']['node'] in ('node-2','node-3'):row['possible'].append(target)
    ledger=s.r.frame(dict(active,revision=active['revision']+1,previous=e.digest(files[s.FILE]),plan=plan))
    switched=dict(files,**{'selector.gsr':selector,'grants.gsr':files['grants.gsr']+promise,'generations/'+slot:None},
                  **{'generations/'+slot+'/'+k:v for k,v in new.items()})
    final=dict(switched,**{s.FILE:ledger});walk.group[node]=final
    walk.match('removed-1-adopted');walk.match('removed-1-refused')
    return files,switched,final


def validate(root, with_states=False, *, selected_prefix=None):
    walk=prelude(root,selected_prefix=selected_prefix);names=walk.names[:3]
    walk.campaign(4,names,'node-1','campaign-4');walk.settle('campaign-4-settled',names)
    _,packet,cat=state(walk.group['node-1']);cap=packet['capsule']
    request=dict(root=cap['root'],expected=e.authority(cap['root'],cat['cut']['view']),number=1,kind='REMOVE',target=[u.identity(walk.group[n]) for n in names])
    for slot,kind,command in [(2,'RESERVE',dict(request=request)),(3,'PREPARE',dict(number=1,revision=1)),(4,'READY',dict(number=1,receipt=None)),(5,'SEAL',dict(number=1))]:
        walk.publication(kind,command,names,'slot-'+str(slot));walk.settle('slot-'+str(slot)+'-settled',names)
    operation=state(walk.group['node-1'])[2]['results'][-1]
    walk.publication('INTENT',dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}),names,'slot-6')
    walk.reconcile(names);walk.settle('slot-6-settled',names)
    walk.campaign(5,names,'node-1','campaign-5');walk.settle('campaign-5-settled',names)
    walk.publication('FINAL',dict(binding=operation['binding']),names,'slot-7');walk.reconcile(names);walk.settle('slot-7-settled',names)
    walk.match('before-inherited-adoption');walk.match('rejected-inherited-adoption');originals=adoption(walk)
    walk.campaign(6,names,'node-1','campaign-6');walk.settle('campaign-6-settled',names)
    walk.publication('BARRIER',None,names,'slot-8');walk.settle('slot-8-settled',names)
    walk.publication('RETIRE',dict(through=1),names,'slot-9');walk.settle('slot-9-settled',names)
    observations=json.loads(p.t.plans.read(Path(root)/'observations.json',1024*1024))
    need(len(observations)==len(walk.observed) and {f.canonical(row) for row in observations}==walk.observed,
         'inherited adoption exact original observations')
    validate_calls(walk)
    need(json.loads(p.t.plans.read(Path(root)/'result.json',16384))==dict(status='PASS',originalVoters=4,survivingVoters=3,publicRuntime=False,independentReplay=False),
         'inherited adoption producer result')
    required_files={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json','result.json'}
    required_files|={f'{kind}-{slot}.{suffix}' for slot in range(1,10) for kind,suffix in [('entry','gsr'),('payload','bin')]}
    p.selection.layout(Path(root),required_files|walk.snapshots,'inherited adoption complete history')
    result=dict(status='PASS',originalVoters=4,survivingVoters=3,inheritedProofs=2,slots=9,snapshots=len(walk.snapshots),
                originalFirst=True,automaticDispatch=False,publicRuntime=False,phase3Complete=False)
    return (result,originals) if with_states else result


def validate_calls(walk):
    rows=json.loads(p.t.plans.read(walk.root/'calls.json',8*1024*1024));names=walk.names;voters=names[:3]
    need(all(set(row)=={'node','operation','events'} and row['node'] in names and isinstance(row['events'],list)
             and all(isinstance(event,str) for event in row['events']) for row in rows),'inherited adoption call schema')
    def phase(operation,owners,events,exact=False):
        calls=[row for row in rows if row['operation']==operation]
        need([row['node'] for row in calls]==owners,'inherited adoption owner calls: '+operation)
        for row in calls:
            if exact:need([event for event in row['events'] if event in events]==events,'inherited adoption exact force order: '+operation)
            else:s.ordered(row['events'],events,'inherited adoption '+operation)
    phase('initialize-retention',names,['RETENTION_PARENT_FORCED','FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED'])
    for counter in (1,3,4,5,6):
        owners=names if counter in (1,3) else voters
        phase('prepare-'+str(counter),owners,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'])
        phase('select-'+str(counter),owners,['SELECTED_FORCED','SELECTED_BEFORE_RETURN'])
        phase('inherited-install' if counter==3 else 'install-'+str(counter),owners,['INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
    for slot in range(1,10):
        for name,events in [('accept',['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']),
                ('proof',['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN']),
                ('certificate',['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN']),
                ('apply',['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'])]:
            phase(name+'-'+str(slot),voters,events,True)
        if slot>1:phase('publish-'+str(slot),voters,['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],True)
    phase('original-future',names[:2],['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_BEFORE_RETURN'])
    phase('carried-accept',voters,['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN'])
    phase('carried-proof',voters,['PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'])
    phase('carried-certificate',voters,['CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'])
    phase('carried-apply',voters,['NATIVE_CERTIFICATE_RETAINED','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'])
    phase('carried-publish',voters,['PUBLICATION_SELECTOR_FORCED','RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'])
    phase('inherited-adopt',['node-4'],['ADOPTION_INSTALL_VALIDATED','PROMISE_FORCED','ADOPTION_INSTALL_FENCED','INSTALL_SELECTOR_FORCED',
          'INSTALL_PARENT_FORCED','RETENTION_PARENT_FORCED','INHERITED_FUTURE_RETENTION_PROMOTED','ADOPTION_INSTALL_BEFORE_RETURN'])
    phase('inherited-adopt-reopen',['node-4'],[])
    phase('inherited-adopt-missing-ancestry',['node-4'],[])
    for row in rows:
        if row['operation'] in ('inherited-adopt-reopen','removed-refusal-1','inherited-adopt-missing-ancestry'):
            need(not any(event.startswith(('PROMISE_','BASIS_','SELECTED_','INSTALL_','ADOPTION_')) for event in row['events']),
                 'inherited adoption reopened or removed owner wrote authority')


def qualify(root, *, selected_prefix=None):
    root=Path(root);result=validate(root,selected_prefix=selected_prefix);negatives=[]
    paths=[('original-admission','initial/target-0/bootstrap-admission.gsbp','admitted original public bootstrap'),
           ('original-target','two-futures/node-1/'+u.FILE,'admitted exact two-futures: node-1'),
           ('carried-selection','inherited-installed/node-4/selector.gsr','admitted exact inherited-installed: node-4'),
           ('carried-result','carried-published/node-1/'+s.FILE,'admitted exact carried-published: node-1'),
           ('joint-publication','slot-6-published/node-1/selector.gsr','admitted exact slot-6-published: node-1'),
           ('final-publication','slot-7-published/node-1/selector.gsr','admitted exact slot-7-published: node-1'),
           ('rejected-adoption','rejected-inherited-adoption/node-4/selector.gsr','admitted exact rejected-inherited-adoption: node-4'),
           ('adopted-selector','removed-1-adopted/node-4/selector.gsr','admitted exact removed-1-adopted: node-4'),
           ('inherited-promotion','removed-1-adopted/node-4/'+s.FILE,'admitted exact removed-1-adopted: node-4'),
           ('removed-refusal','removed-1-refused/node-4/grants.gsr','admitted exact removed-1-refused: node-4'),
           ('retired-publication','slot-9-published/node-1/selector.gsr','admitted exact slot-9-published: node-1'),
           ('force','calls.json','selected retention force order: inherited adoption inherited-adopt'),
           ('observations','observations.json','inherited adoption exact original observations'),
           ('result','result.json','inherited adoption producer result')]
    for name,relative,reason in paths:
        with tempfile.TemporaryDirectory(prefix='v53-inherited-adoption-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);path=target/relative;raw=path.read_bytes()
            if name=='force':
                rows=json.loads(raw);row=next(v for v in rows if v['operation']=='inherited-adopt')
                row['events'].remove('INHERITED_FUTURE_RETENTION_PROMOTED');raw=f.canonical(rows)
            elif name=='observations':
                rows=json.loads(raw);rows.pop();raw=f.canonical(rows)
            elif name=='result':
                value=json.loads(raw);value['publicRuntime']=True;raw=f.canonical(value)
            else:raw=raw[:-1]+bytes([raw[-1]^1])
            need(raw!=path.read_bytes(),'inherited adoption ineffective negative');path.write_bytes(raw)
            try:validate(target,selected_prefix=selected_prefix)
            except ValueError as error:need(str(error)==reason,'inherited adoption unrelated negative: '+name+': '+str(error))
            else:raise ValueError('inherited adoption accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(result,negatives=negatives)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');parser.add_argument('--reachable-selection',action='store_true');args=parser.parse_args()
    from .selected_prefix_evidence import prefix
    print(json.dumps((qualify if args.qualify else validate)(args.root,selected_prefix=prefix if args.reachable_selection else None),sort_keys=True))
