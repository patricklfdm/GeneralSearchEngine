"""Original-byte reduction of a whole-group native carried DATA restart.

No Java result supplies expected storage. Process observations and full network
qualification are separate obligations; this physical reducer cannot admit a
Phase 3 cohort by itself.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import uuid
from . import carried_slot_evidence as old
from . import node_current_evidence as current
from . import covered_staging_evidence as staging

b, c, d, e, f, need = old.b, old.c, old.d, old.e, old.f, old.need
NODES = ('node-1', 'node-2', 'node-3')
CUTS = ('NATIVE_RETIREMENT_CERTIFICATE_RETAINED', 'ACCEPT_RENAMED',
        'PROOF_RENAMED', 'APPLY_ACK_DIRECTORY_FORCED')


class View:
    """Read-only naming of retained snapshots, without copying or rewriting."""
    def __init__(self, root, life):
        self.root, self.life = root, life

    def __truediv__(self, name):
        if name == 'selected-1.gsr': name = f'life-{self.life}-installed-1.gsr'
        elif name.startswith(('installed-', 'applied-', 'published-')): name = f'life-{self.life}-'+name
        return self.root/name


def pending(files):
    raw = files['pending.accept']
    if raw == c.EMPTY: return {}, ()
    for phases in (('PROOF', 'CERTIFICATE'), ('PROOF',), ()):
        try: return c.pending(raw, phases)[0], phases
        except ValueError: pass
    raise ValueError('native carried exact pending phases')


def vote(files, entry, payload, extra=()):
    _, members, packet = c.current(files)
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    value = f.decode(entry, 'records', 'ENTRY')
    need(selected['nextEntry'] == e.digest(entry) and selected['cut'] == packet['capsule']['cut']
         and value['index'] == selected['cut']['index']+1 and value['previous'] == selected['cut']['entry']
         and value['kind'] == 'DATA' and value['payload'] == e.digest(payload), 'native carried exact successor')
    accept = f.encode('records', 'ACCEPT', dict(root=selected['root'], authority=selected['view'],
        ballot=selected['ballot'], index=value['index'], entry=e.digest(entry)))
    raw = e.container([files['selector.gsr'], members['promise.gsr'], members['selected.gsr'], entry, accept], payload)+b''.join(extra)
    return raw[:8]+struct.pack('>I', len(raw))+raw[12:]


def cold(group, entry, payload):
    result = copy.deepcopy(group)
    for node, files in group.items():
        frames, _ = pending(files)
        if not frames or frames['SELECTOR'] == files['selector.gsr']: continue
        _, members, packet = c.current(files)
        selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
        need(frames['ENTRY'] == entry and frames['PAYLOAD'] == payload and selected['nextEntry'] == e.digest(entry)
             and packet['objects'].get(e.digest(entry)) == entry and packet['objects'].get(e.digest(payload)) == payload,
             'native carried cold original entry')
        # Retirement of an old derived end needs the exact original certificate
        # in this owner's newly frozen source. Never manufacture an old ACK.
        if 'applied-end' in files:
            need('CERTIFICATE' in frames and files['applied-end/certificate.gsr'] == frames['CERTIFICATE'],
                 'native carried cold original certificate')
            basis = f.decode(members['basis.gsr'], 'records', 'BASIS')
            source = e.p.decode(files['sources/'+basis['basisId']+'/source.gscp'])
            e.p.bind(source, members['basis.gsr'])
            need(all(source['objects'].get(e.digest(frames[k])) == frames[k]
                     for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')),
                 'native carried cold retained certificate')
        result[node] = dict(staging.without_staging(files), **{'pending.accept':vote(files, entry, payload)})
    return result


def maintain(group, owners):
    """Exact installed carried votes may pin tails while their old sources retire."""
    result = copy.deepcopy(group)
    for node in owners:
        files = group[node]; frames, _ = pending(files)
        if 'applied-end' in files: continue
        _, members, packet = c.current(files)
        selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
        if frames and not (frames['SELECTOR'] == files['selector.gsr']
                and frames['PROMISE'] == members['promise.gsr'] and frames['SELECTED'] == members['selected.gsr']
                and selected['nextEntry'] == e.digest(frames['ENTRY'])): continue
        voters = tuple(v['voter'] for v in selected['sources'])
        need(node in voters and len(voters) in (2, 3), 'native carried maintenance original cohort')
        copies = copy.deepcopy(group); copies[node]['pending.accept'] = c.EMPTY
        changed = current.current.maintenance(copies, voters, owners=(node,))[node]
        if frames:
            current.retained_carried_sources(files, changed, node, frames, packet)
            changed['pending.accept'] = files['pending.accept']
        result[node] = changed
    return result


def campaign(root, group, life, counter, entry):
    snapshot = f'life-{life}-installed-1'
    chosen = (root/(snapshot+'.gsr')).read_bytes()
    observed = f.decode(chosen, 'records', 'SELECTED')
    voters = tuple(v['voter'] for v in observed['sources'])
    need(voters in (('node-1','node-2'), ('node-1','node-3')), 'native carried selected majority')
    ballot = dict(counter=counter, proposer='node-1', incarnation=d.future.identity(group['node-1'])['storage'])
    prepared, grants, sources, identifiers = dict(group), {}, {}, set()
    for node, files in group.items():
        actual = c.inventory(root/snapshot/node)
        if node not in voters and actual['grants.gsr'] == files['grants.gsr']: continue
        _, members, packet = c.current(files); cap = packet['capsule']
        prior = c.journal(files['grants.gsr'], cap['root'], node)
        rows = c.journal(actual['grants.gsr'], cap['root'], node)
        need(rows[:len(prior)] == prior and [v[0] for v in rows[len(prior):]] ==
             ['PROMISE','BASIS']+(['SELECTED'] if node in voters else []), 'native carried original grant extension')
        identifier = rows[len(prior)][2]['basisId']
        need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
             and all(v[2].get('basisId') != identifier for v in prior), 'native carried fresh source identity')
        identifiers.add(identifier)
        raw, tail = old.old.captured(files, pending(files)[1]); captured = e.p.decode(raw)
        value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
        promise = f.encode('records', 'PROMISE', value); wrapper = d.s.s.wrap(promise, files[d.s.FILE])
        raw = c.packet_bytes(cap, dict(captured['objects'], **{e.digest(wrapper):wrapper}), captured['images'])
        frozen = e.p.decode(raw)
        basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'], capsule=e.digest(frozen['capsuleBytes']),
            inventory=e.digest(frozen['indexBytes']), accepted=tail))
        source = 'sources/'+identifier
        changed = dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':raw},
                       **{source+'/'+h+'.image':members[h+'.image'] for h in captured['images']})
        if node == 'node-1': changed['allocator.gsr'] = f.encode('records','ALLOCATOR',dict(root=cap['root'],node=node,counter=counter))
        prepared[node], grants[node], sources[node] = changed, (promise,basis), (basis,frozen,wrapper)
    _, installed = old.install.install(prepared, sources, grants, voters, ballot, {}, {}, selected_prefix=d.slot.prefix)
    need(c.current(installed['node-1'])[1]['selected.gsr'] == chosen and observed['nextEntry'] == e.digest(entry),
         'native carried original selected entry')
    b.match(root, snapshot, installed)
    return installed, voters


def interrupted(group, voters, entry, payload, point):
    need(point in CUTS, 'native carried declared cut')
    if point == CUTS[0]: return copy.deepcopy(group)
    changed = dict(group)
    accepting = ('node-1',) if point == 'ACCEPT_RENAMED' else voters
    for node in accepting:
        # This is exact typed reacceptance; old staging cannot be inherited as
        # an acknowledgement of the new vote.
        changed[node] = dict(cold({node:group[node]}, entry, payload)[node],
                             **{'pending.accept':vote(group[node], entry, payload)})
    if point == 'ACCEPT_RENAMED': return changed
    # Local proof creation performs maintenance before the peer receives PROOF.
    # Its ACCEPT response does not retire that peer's old generation.
    changed = maintain(changed, ('node-1',) if point == 'PROOF_RENAMED' else voters)
    frames, _ = pending(changed['node-1']); accept = frames['ACCEPT']
    def witnesses(raw, phase):
        return [dict(voter=n, incarnation=d.future.identity(changed[n])['storage'],
            receipt=e.digest(f.canonical(dict(root=f.decode(accept,'records','ACCEPT')['root'], voter=n,
                incarnation=d.future.identity(changed[n])['storage'], phase=phase, record=e.digest(raw))))) for n in voters]
    proof = f.encode('records','PROOF',dict(f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
    changed['node-1']['pending.accept'] = vote(changed['node-1'],entry,payload,(proof,))
    if point == 'PROOF_RENAMED': return changed
    for node in voters: changed[node]['pending.accept'] = vote(changed[node],entry,payload,(proof,))
    certificate = f.encode('records','CERTIFICATE',dict(f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
    files = changed['node-1']; files['pending.accept'] = vote(files,entry,payload,(proof,certificate))
    end = {k.removeprefix('applied-end/'):v for k,v in group['node-1'].items()
           if k.startswith('applied-end/') and k != 'applied-end/plan.json'}
    need(end and end['catalog.gsr'] and end['application.image'], 'native carried retained logical DATA end')
    end.update({'selector.gsr':files['selector.gsr'],'certificate.gsr':certificate})
    end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3',root=f.decode(certificate,'records','CERTIFICATE')['root'],
        node='node-1',files=[dict(path=k,**e.info(v)) for k,v in sorted(end.items())]))
    files.update({'applied-end':None, **{'applied-end/'+k:v for k,v in end.items()}})
    return changed


class Service(current.Service):
    def data_documents(self): return [(303,'admitted-original')]

    def entry_bytes(self, fields):
        if fields['index'] != 1: return f.encode('records','ENTRY',fields)
        need(dict(f.decode(self.carried,'records','ENTRY'),origin=fields['origin']) == fields,
             'native carried unchanged recovered entry')
        return self.carried

    def snapshot(self, label, group):
        if label == 'slot-1-accepted':
            cleaned = {n:staging.without_staging(v) if n in self.voters else v for n,v in group.items()}
            self.group = maintain(cleaned, self.voters)
        return super().snapshot(label, group)


def physical(root, point):
    root = Path(root)
    need(point in CUTS, 'native carried declared cut')
    group, entry = old.prelude(root, 'APPLIED', kind='DATA')
    payload = d.fixture_data((303,'admitted-original'))
    b.match(root,'life-1-opened',group)
    group, voters = campaign(root, group, 1, 3, entry)
    interrupted_group = interrupted(group,voters,entry,payload,point)
    b.match(root,'at-cut',interrupted_group); b.match(root,'before-reopen',interrupted_group)
    opened = cold(interrupted_group,entry,payload); b.match(root,'life-2-opened',opened)
    prepared = maintain(opened, NODES)
    group, voters = campaign(root, prepared, 2, 4, entry)
    service = Service(View(root,2),group); service.carried = entry
    service.voters = voters; service.active = list(voters); service.selection_anchor = c.anchor(c.current(group['node-1'])[2]['capsule'])
    service.publish('DATA',payload); service.group = maintain(service.group,voters); service.publish('BARRIER')
    b.match(root,'life-2-ready',service.group); b.match(root,'after-close',service.group)
    return dict(status='PARTIAL', scope='native-carried-whole-group-physical', physicalReplay=True,
                cut=point, campaigns=2, dataApplications=1, publishedSlots=2,
                fullWireReplay=False, processHistoryQualified=False, phase3Complete=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--cut',choices=CUTS,required=True)
    args=parser.parse_args();print(json.dumps(physical(args.root,args.cut),sort_keys=True))
