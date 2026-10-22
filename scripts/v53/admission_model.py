"""Research-only authority capsules and durable learner admission.

Authentic records/identities and atomic force are assumptions. A capsule replaces
stable DATA/BARRIER ranges with NEW durable quorum endorsements, never with an
unattested hash. Configuration certificates remain complete. No production imports.
"""
import json

from . import transition_model as t
from .membership_model import need

MAX_CHANGES = 4  # Research lifetime membership budget, NOT a production constant.


def plain(value):
    return json.loads(t.encoded(value))


def state_root(root):
    return t.digest(dict(root=root, application='abstract-genesis'))


def next_state(state, certificate):
    entry = t.Entry.read(certificate.value)
    return t.digest(dict(previous=state, data=entry.payload)) if entry.kind == 'DATA' else state


class Source:
    def __init__(self, world, chain):
        t.check_history(world.root, world.initial, world.events)
        t.fold(world.root, world.initial, chain, world.verify)
        self.world, self.chain = world, chain
        self.root, self.old = world.root, world.initial
        self.certificates = {c.entry_id: c for c in chain}
        self.views = [t.genesis(self.root, self.old)]
        self.states = [state_root(self.root)]
        for certificate in chain:
            self.views.append(t.fold(self.root, self.old, chain[:len(self.views)], world.verify))
            self.states.append(next_state(self.states[-1], certificate))
        self.endorsed, self.pending, self.events = set(), {}, []

    def record(self, event, **values):
        self.events.append(plain(dict(event=event, **values)))

    def statement(self, first, end):
        need(0 <= first < end <= len(self.chain), 'gap range')
        need(all(t.Entry.read(c.value).kind in ('DATA', 'BARRIER') for c in self.chain[first:end]),
             'gap cannot hide configuration')
        return dict(start=plain(self.views[first]), after=plain(self.views[end]),
                    stateBefore=self.states[first], stateAfter=self.states[end])

    def stage_endorsement(self, node, statement):
        first, end = statement['start']['index']-1, statement['after']['index']-1
        need(statement == self.statement(first, end), 'incorrect gap statement')
        need(node in self.views[first].old and node not in self.pending, 'endorser/writer')
        replica = self.world.nodes[node]
        need(replica.alive and len(replica.chain) >= end and
             tuple(c.entry_id for c in replica.chain[:end]) == tuple(c.entry_id for c in self.chain[:end]),
             'endorser lacks durable verified prefix')
        self.pending[node] = plain(statement)
        self.record('endorsement-stage', node=node, statement=statement)

    def force_endorsement(self, node):
        need(node in self.pending, 'no staged endorsement')
        statement = self.pending.pop(node)
        self.endorsed.add((node, t.digest(statement)))
        self.record('endorsement-force', node=node, statement=statement)

    def crash_endorser(self, node):
        self.pending.pop(node, None)
        self.record('endorser-crash', node=node)

    def capsule(self, cut, *, last=False):
        need(type(cut) is int and 0 <= cut <= len(self.chain), 'capsule cut')
        items, start, changes = [], 0, 0
        while start < cut:
            certificate = self.chain[start]
            kind = t.Entry.read(certificate.value).kind
            if kind in ('INTENT', 'FINAL'):
                changes += kind == 'INTENT'
                need(changes <= MAX_CHANGES, 'membership history capacity')
                items.append(dict(kind='configuration', certificate=plain(certificate)))
                start += 1
            else:
                end = start+1
                while end < cut and t.Entry.read(self.chain[end].value).kind in ('DATA','BARRIER'):
                    end += 1
                statement = self.statement(start, end)
                voters = self.views[start].old
                owners = voters[-(len(voters)//2+1):] if last else voters[:len(voters)//2+1]
                for node in owners:
                    self.stage_endorsement(node, statement); self.force_endorsement(node)
                items.append(dict(kind='gap', statement=statement, owners=list(owners)))
                start = end
        packet = dict(root=self.root, initial=list(self.old), items=items,
                      next=plain(self.views[cut]), state=self.states[cut])
        self.verify(packet)
        self.record('capsule', packet=packet)
        return packet

    def verify(self, packet):
        """Consumer checks exact links + authentic certificates/endorsements.

        Does not reconstruct erased data entries; their new attestations supply
        the authority. The observer independently checks what each signer saw.
        """
        need(set(packet) == {'root','initial','items','next','state'} and
             packet['root'] == self.root and packet['initial'] == list(self.old), 'capsule root')
        view, state, changes = plain(t.genesis(self.root, self.old)), state_root(self.root), 0
        need(len(packet['items']) <= 3*MAX_CHANGES+1, 'capsule item capacity')
        for item in packet['items']:
            if item['kind'] == 'gap':
                need(set(item) == {'kind','statement','owners'}, 'gap fields')
                row, owners = item['statement'], item['owners']
                need(set(row) == {'start','after','stateBefore','stateAfter'} and
                     row['start'] == view and row['stateBefore'] == state and not view['operation'], 'gap start')
                after = row['after']
                need(set(after) == set(view) and type(after['index']) is int and after['index'] > view['index']
                     and all(after[k] == view[k] for k in view if k not in ('index','predecessor')), 'gap authority')
                need(len(set(owners)) == len(owners) and set(owners) <= set(view['old']) and
                     len(owners) > len(view['old'])//2 and
                     all((node, t.digest(row)) in self.endorsed for node in owners), 'gap durable quorum')
                view, state = after, row['stateAfter']
            else:
                need(item['kind'] == 'configuration' and set(item) == {'kind','certificate'}, 'capsule item')
                raw = item['certificate']
                identity = t.digest(dict(authority=raw['authority'], value=raw['value']))
                cert = self.certificates.get(identity)
                need(cert is not None and plain(cert) == raw and raw['authority'] == view, 'configuration proof/link')
                entry = t.Entry.read(cert.value)
                need(entry.kind in ('INTENT','FINAL'), 'explicit configuration required')
                changes += entry.kind == 'INTENT'
                need(changes <= MAX_CHANGES, 'membership history capacity')
                successor = t.successor(cert.authority, entry)
                view = dict(plain(successor), predecessor=cert.entry_id)
        need(packet['next'] == view and packet['state'] == state, 'capsule terminal binding')
        return view

    def evidence(self):
        return plain(dict(root=self.root, old=self.old, input=self.world.events, chain=self.chain, events=self.events))

    def admit_change(self, packet):
        view = self.verify(packet)
        need(not view['operation'] and view['generation'] < MAX_CHANGES, 'membership history capacity/busy')
        return True


def descriptor(node):
    return dict(voter=node, storage='durable-'+node, endpoint=node+':9000')


def validate_request(source, request, identities):
    need(set(request) == {'root','operation','expected','target','joining'} and
         request['root'] == source.root and isinstance(request['operation'], str) and
         0 < len(request['operation']) <= 128, 'request identity')
    expected = request['expected']
    need(expected in [plain(v) for v in source.views] and not expected['operation'], 'request stable predecessor')
    old, target = tuple(expected['old']), tuple(request['target'])
    from .membership_model import transition_kind
    transition_kind(old, target)
    joining = set(target)-set(old)
    need(len(joining) == 1, 'learner model requires add or replace')
    identity = request['joining']
    need(set(identity) == {'voter','storage','endpoint'} and identity['voter'] in joining and
         all(type(v) is str and 0 < len(v) <= 128 and v.isascii() for v in identity.values()), 'joining identity')
    need(set(old) <= {row['voter'] for row in identities}, 'missing old identities')
    for key in identity:
        values = [row[key] for row in identities]
        need(len(set(values)) == len(values) and identity[key] not in values, 'identity reuse: '+key)


class Learner:
    """One pre-certified input history; no public reads or automatic elections.

    Durable identity is separate from volatile connection session. Reservations
    and exact duplicate requests survive crash; all writes share one writer.
    """
    def __init__(self, source, request, identities):
        validate_request(source, request, identities)
        self.source, self.request, self.identities = source, plain(request), plain(identities)
        self.durable, self.pending, self.events = {}, None, []
        self.session, self.alive = 1, True

    def record(self, event, **values):
        self.events.append(plain(dict(event=event, sourceThrough=len(self.source.events), **values)))

    def stage(self, kind, value):
        need(self.alive and self.pending is None, 'learner writer busy/offline')
        self.pending = (kind, plain(value))
        self.record('stage', kind=kind, value=value)

    def force(self):
        need(self.alive and self.pending is not None, 'no learner pending write')
        kind, value = self.pending
        self.durable[kind] = value; self.pending = None
        self.record('force', kind=kind, value=value)

    def reserve(self, request=None):
        need((self.request if request is None else request) == self.request, 'changed duplicate request')
        if 'reservation' in self.durable:
            need(self.alive and self.pending is None, 'duplicate while busy/offline')
            return False
        self.stage('reservation', self.request)
        return True

    def image(self, packet):
        need('reservation' in self.durable and 'receipt' not in self.durable, 'image reservation/sealed')
        need(self.source.verify(packet) == self.request['expected'], 'image exact predecessor cut')
        self.stage('image', packet)

    def receipt(self):
        need('image' in self.durable, 'receipt before materialization force')
        self.stage('receipt', dict(request=t.digest(self.request), identity=self.request['joining'],
                                   image=t.digest(self.durable['image']), cut=self.request['expected']))

    def adopt(self, packet):
        need('receipt' in self.durable and self.durable['receipt']['image'] == t.digest(self.durable['image']),
             'adoption requires sealed materialization')
        view = self.source.verify(packet)
        expected = self.request['expected']; index = expected['index']-1
        # Only the exact INTENT then optional matching FINAL can promote this learner.
        cut = view['index']-1
        need(cut in (index+1,index+2), 'learner adoption range')
        intent = self.source.chain[index]
        entry = t.Entry.read(intent.value)
        need(plain(intent.authority) == expected and entry.kind == 'INTENT' and
             entry.operation == t.digest(self.request) and list(entry.target) == self.request['target'],
             'different operation/target/predecessor')
        need(view == plain(self.source.views[cut]) and
             (cut == index+1 or t.Entry.read(self.source.chain[index+1].value).kind == 'FINAL'), 'adoption chain')
        previous = self.durable.get('authority')
        need(previous is None or previous['next']['index'] <= view['index'], 'authority rollback')
        self.stage('authority', packet)

    def vote(self, view, identity, session):
        need(self.alive and self.pending is None and 'authority' in self.durable, 'learner cannot vote')
        need(view == self.durable['authority']['next'] and identity == self.request['joining'] and
             session == self.session and identity['voter'] in set(view['old']+view['new']), 'vote identity/view/session')
        # Eligibility only. Actual PREPARE/ACCEPT/PROOF additionally need global grant,
        # selected frozen basis and current ballot from the activation protocol.
        self.record('eligible', view=view, identity=identity, session=session)
        return True

    def crash(self):
        need(self.alive, 'already stopped')
        self.alive = False; self.pending = None; self.record('crash')

    def restart(self):
        need(not self.alive, 'restart running learner')
        self.alive = True; self.session += 1; self.record('restart', session=self.session)

    def evidence(self):
        return dict(source=self.source.evidence(), request=self.request, identities=self.identities, events=self.events)


def frame_allowed(view, known_identities, sender, expected_view):
    """Receiver already holding this view; does not remotely fence an isolated old voter."""
    return (view == expected_view and sender in known_identities and
            sender['voter'] in set(view['old']+view['new']))
