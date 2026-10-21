"""Bounded, sequential certificate-chain research; no production GSE imports.

Each replica derives its NEXT slot's authority from its own forced certificate
chain. A leader cannot pipeline beyond an uncertified predecessor. This deliberate
restriction is part of the hypothesis, not a claim about current GSE behavior.
"""
from dataclasses import asdict, dataclass, field, replace
import hashlib
from itertools import combinations
import json

from . import ballot_model as b
from .membership_model import NODES, configuration, need, transition_kind

MAX_SLOTS = 32  # Research bound, not a production resource contract.


def encoded(value):
    return json.dumps(value, default=asdict, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


@dataclass(frozen=True)
class Authority:
    root: str
    index: int
    predecessor: str
    generation: int
    old: tuple
    new: tuple
    operation: str = ''

    def __post_init__(self):
        need(type(self.root) is str and 0 < len(self.root) <= 128 and self.root.isascii(), 'authority root')
        need(type(self.index) is int and 0 < self.index <= MAX_SLOTS+1, 'authority index')
        need(type(self.generation) is int and 0 <= self.generation <= MAX_SLOTS, 'authority generation')
        need(type(self.predecessor) is str and len(self.predecessor) == 64
             and all(c in '0123456789abcdef' for c in self.predecessor), 'authority predecessor')
        configuration(self.old); configuration(self.new)
        need(type(self.operation) is str and len(self.operation) <= 128 and self.operation.isascii(),
             'authority operation')
        if self.operation:
            transition_kind(self.old, self.new)
        else:
            need(self.old == self.new, 'stable authority configuration mismatch')

    @property
    def stage(self):
        return 'joint' if self.operation else 'stable'

    @property
    def voters(self):
        return frozenset(self.old + self.new)

    def quorum(self, nodes):
        votes = set(nodes)
        return votes <= self.voters and all(len(votes & set(group)) > len(group)//2
                                           for group in (self.old, self.new))

    def oracle_quorums(self):
        left = [frozenset(q) for q in combinations(self.old, len(self.old)//2+1)]
        right = [frozenset(q) for q in combinations(self.new, len(self.new)//2+1)]
        return frozenset(a | c for a in left for c in right)


@dataclass(frozen=True)
class Entry:
    kind: str
    operation: str = ''
    target: tuple = ()
    payload: str = ''

    def value(self):
        return encoded(self)

    @classmethod
    def read(cls, value):
        row = json.loads(value)
        result = cls(**dict(row, target=tuple(row['target'])))
        need(result.value() == value, 'noncanonical model entry')
        return result


@dataclass(frozen=True)
class Certificate:
    authority: Authority
    ballot: b.Ballot
    value: str
    accepts: tuple
    proofs: tuple

    @property
    def entry_id(self):
        # Ballot/receipt variants proving the SAME logical entry have ONE identity.
        return digest(dict(authority=self.authority, value=self.value))


@dataclass
class Replica:
    chain: tuple = ()
    pending_chain: tuple | None = None
    slots: dict = field(default_factory=dict)
    slot_authorities: dict = field(default_factory=dict)
    alive: bool = True


def genesis(root, voters):
    configuration(voters)
    need(type(root) is str and 0 < len(root) <= 128 and root.isascii(), 'genesis root')
    return Authority(root, 1, digest(dict(root=root, voters=voters)), 0, voters, voters)


def successor(authority, entry):
    """Proposed state machine. Stable INTENT, joint FINAL, then stable data."""
    need(authority.index <= MAX_SLOTS, 'research slot bound')
    need(type(entry.payload) is str and len(entry.payload) <= 128, 'research payload bound')
    if authority.stage == 'joint':
        need(entry.kind == 'FINAL' and entry.operation == authority.operation
             and entry.target == authority.new and entry.payload == '', 'joint accepts only matching FINAL')
        return replace(authority, index=authority.index+1, old=authority.new, operation='')
    if entry.kind == 'INTENT':
        need(type(entry.operation) is str and 0 < len(entry.operation) <= 128
             and entry.operation.isascii() and not entry.payload, 'intent identity/payload')
        transition_kind(authority.old, entry.target)
        return replace(authority, index=authority.index+1, generation=authority.generation+1,
                       new=entry.target, operation=entry.operation)
    need(entry.kind in ('DATA', 'BARRIER') and not entry.operation and not entry.target,
         'stable entry kind/metadata')
    return replace(authority, index=authority.index+1)


def fold(root, voters, chain, verify):
    need(type(chain) is tuple and len(chain) <= MAX_SLOTS, 'research chain bound/type')
    authority = genesis(root, voters)
    for certificate in chain:
        need(type(certificate) is Certificate and certificate.authority == authority,
             'certificate chain authority/predecessor')
        verify(certificate)
        authority = successor(authority, Entry.read(certificate.value))
        authority = replace(authority, predecessor=certificate.entry_id)
    return authority


class World:
    def __init__(self, voters, *, root='group-history-genesis', mutant=None):
        need(mutant in (None, 'install-before-force', 'bypass-local-prefix'), 'unknown transition mutant')
        self.root, self.initial = root, voters
        genesis(root, voters)
        self.nodes = {node: Replica() for node in NODES}
        self.slots = {}
        self.offsets = {}
        self.events = []
        self.counter = 0
        self.mutant = mutant

    def record(self, event, **values):
        self.events.append(dict(event=event, **values))

    def flush(self, authority):
        model = self.slots[authority]
        offset = self.offsets.get(authority, 0)
        for event in model.events[offset:]:
            self.record('slot', authority=authority, detail=event)
        self.offsets[authority] = len(model.events)

    def verify(self, certificate):
        need(certificate.authority in self.slots, 'unknown certificate authority')
        model = self.slots[certificate.authority]
        for rows, phase in ((certificate.accepts, 'accept-ack'), (certificate.proofs, 'proof-ack')):
            model.certificate(rows, phase, certificate.ballot, certificate.value)

    def authority(self, node):
        return fold(self.root, self.initial, self.nodes[node].chain, self.verify)

    def install(self, node, chain):
        replica = self.nodes[node]
        need(replica.alive and replica.pending_chain is None
             and not any(slot.pending for slot in replica.slots.values()), 'replica writer busy/offline')
        fold(self.root, self.initial, chain, self.verify)
        need(len(chain) >= len(replica.chain) and
             all(a.entry_id == c.entry_id for a, c in zip(replica.chain, chain)), 'prefix regression/fork')
        replica.pending_chain = chain
        self.record('install-stage', node=node, chain=chain)
        if self.mutant == 'install-before-force':
            replica.chain = chain

    def force_install(self, node):
        replica = self.nodes[node]
        need(replica.alive and replica.pending_chain is not None, 'no pending prefix')
        replica.chain, replica.pending_chain = replica.pending_chain, None
        self.record('install-force', node=node, chain=replica.chain)

    def start(self, node, entry):
        replica = self.nodes[node]
        need(replica.alive and replica.pending_chain is None, 'proposer offline/installing')
        authority = self.authority(node)
        need(node in authority.voters, 'proposer not current voter')
        successor(authority, entry)  # Validate requested operation, before recovery selection.
        self.counter += 1
        ballot = b.Ballot(self.counter, node, 'process-'+str(self.counter))
        if authority not in self.slots:
            self.slots[authority] = b.Model(authority)
        model = self.slots[authority]
        model.start(ballot, entry.value())
        self.flush(authority)
        return authority, ballot

    def send(self, handle, phase, nodes):
        authority, ballot = handle
        result = self.slots[authority].send(phase, ballot, nodes)
        self.flush(authority)
        return result

    def deliver(self, authority, message_id):
        model = self.slots[authority]
        message = model.messages[message_id]
        if not message.kind.endswith('-ack'):
            replica = self.nodes[message.voter]
            allowed = (replica.alive and replica.pending_chain is None and
                       not any(slot.pending for slot in replica.slots.values()) and
                       self.authority(message.voter) == authority)
            if self.mutant == 'bypass-local-prefix':
                allowed = replica.alive
            if not allowed:
                model.messages.pop(message_id)
                self.record('local-reject', node=message.voter, message=message)
                return False
            index = authority.index
            if index in replica.slot_authorities:
                need(replica.slot_authorities[index] == authority, 'local slot authority conflict')
            replica.slot_authorities[index] = authority
            model.voters[message.voter] = replica.slots.setdefault(index, b.Voter())
            self.record('local-admit', node=message.voter, authority=authority)
        model.deliver(message_id)
        self.flush(authority)
        return True

    def force(self, authority, node):
        replica = self.nodes[node]
        need(replica.alive and replica.pending_chain is None
             and self.authority(node) == authority, 'force requires installed predecessor')
        self.slots[authority].force(node)
        self.flush(authority)

    def select(self, handle):
        authority, ballot = handle
        value = self.slots[authority].select(ballot)
        successor(authority, Entry.read(value))
        self.flush(authority)
        return Entry.read(value)

    def certificate(self, handle):
        authority, ballot = handle
        model = self.slots[authority]
        campaign = model.campaigns[ballot]
        certificate = Certificate(authority, ballot, campaign.selected,
                                  tuple(campaign.accepts[n] for n in sorted(campaign.accepts)),
                                  tuple(campaign.proofs[n] for n in sorted(campaign.proofs)))
        self.verify(certificate)
        model.publish(ballot)
        self.flush(authority)
        self.record('certificate', certificate=certificate)
        return certificate

    def crash(self, node):
        replica = self.nodes[node]
        replica.alive = False
        replica.pending_chain = None
        for slot in replica.slots.values():
            slot.pending = None; slot.alive = False
        for authority, model in self.slots.items():
            if node in model.voters:
                model.crash(node)
                self.flush(authority)
        self.record('crash', node=node)

    def restart(self, node):
        replica = self.nodes[node]
        need(not replica.alive, 'already running')
        replica.alive = True
        for authority, model in self.slots.items():
            if node in model.voters:
                model.restart(node)
                self.flush(authority)
        self.record('restart', node=node)


def check_history(root, voters, events):
    """Independent certificate-chain/local-view oracle, using journaled ACKs.

    Does not call World.verify, fold, successor, or Authority.quorum. Ballot safety
    is separately checked with the previous history oracle, after chain replay.
    """
    known_acks = set()
    slot_events = {}
    prefixes = {n: () for n in NODES}
    pending = {}
    pending_votes = {}
    alive = {n: True for n in NODES}
    publications = 0

    def safe(condition, message):
        if not condition:
            raise b.SafetyViolation(message)

    def chain_view(chain):
        old = new = voters
        generation, operation = 0, ''
        parent = digest(dict(root=root, voters=voters))
        safe(len(chain) <= MAX_SLOTS, 'chain bound')
        for index, cert in enumerate(chain, 1):
            expected = Authority(root, index, parent, generation, old, new, operation)
            safe(cert.authority == expected, 'chain authority mismatch')
            for rows, phase in ((cert.accepts,'accept-ack'), (cert.proofs,'proof-ack')):
                safe(all(row in known_acks and row.kind == phase and row.context == expected
                         and row.ballot == cert.ballot and row.value == cert.value for row in rows),
                     'unproven chain certificate')
                witnesses = {row.voter for row in rows}
                safe(len(witnesses) == len(rows) and witnesses <= expected.voters,
                     'chain certificate voters')
                families = expected.oracle_quorums()
                safe(any(q <= witnesses for q in families), 'chain certificate quorum')
            entry = Entry.read(cert.value)
            if operation:
                safe(entry.kind == 'FINAL' and entry.operation == operation and entry.target == new
                     and not entry.payload, 'invalid joint successor')
                old, operation = new, ''
            elif entry.kind == 'INTENT':
                safe(bool(entry.operation) and not entry.payload, 'invalid intent')
                before, after = set(old), set(entry.target)
                safe(len(after) == len(entry.target) and tuple(sorted(after)) == entry.target
                     and 3 <= len(after) <= 5 and after <= set(NODES)
                     and (len(after-before),len(before-after)) in ((1,0),(0,1),(1,1)), 'invalid target')
                new, operation, generation = entry.target, entry.operation, generation+1
            else:
                safe(entry.kind in ('DATA','BARRIER') and not entry.operation and not entry.target,
                     'invalid stable successor')
            parent = digest(dict(authority=expected, value=cert.value))
        return Authority(root, len(chain)+1, parent, generation, old, new, operation)

    for event in events:
        kind = event['event']
        if kind == 'slot':
            authority, detail = event['authority'], event['detail']
            slot_events.setdefault(authority, []).append(detail)
            if detail['event'] == 'send' and detail['message'].kind.endswith('-ack'):
                known_acks.add(detail['message'])
            if detail['event'] == 'stage':
                node = detail['message'].voter
                safe(node not in pending_votes and node not in pending, 'overlapping durable writes')
                pending_votes[node] = detail['message']
            if detail['event'] in ('promise-force','accept-force','proof-force'):
                node = detail['message'].voter
                safe(pending_votes.pop(node, None) == detail['message'], 'vote force without staged write')
                safe(alive[node] and node not in pending and chain_view(prefixes[node]) == authority,
                     'vote without forced predecessor')
        elif kind == 'local-admit':
            node = event['node']
            safe(alive[node] and node not in pending and chain_view(prefixes[node]) == event['authority'],
                 'request without forced predecessor')
        elif kind == 'install-stage':
            node, chain = event['node'], event['chain']
            chain_view(chain)
            safe(alive[node] and node not in pending and node not in pending_votes, 'overlapping prefix installation')
            safe(len(chain) >= len(prefixes[node]) and
                 all(a.entry_id == c.entry_id for a,c in zip(prefixes[node],chain)), 'installed prefix fork/regression')
            pending[node] = chain
        elif kind == 'install-force':
            node = event['node']
            safe(alive[node] and node in pending and pending[node] == event['chain'], 'unprepared prefix force')
            prefixes[node] = pending.pop(node)
        elif kind == 'crash':
            alive[event['node']] = False; pending.pop(event['node'], None); pending_votes.pop(event['node'], None)
        elif kind == 'restart':
            safe(not alive[event['node']], 'restart without crash')
            alive[event['node']] = True
        elif kind == 'certificate':
            cert = event['certificate']
            safe(cert.authority in slot_events, 'unobserved publication')
            parents = [chain for chain in prefixes.values() if chain_view(chain) == cert.authority]
            safe(bool(parents), 'publication without installed parent')
            chain_view(parents[0] + (cert,))
            publications += 1
        elif kind != 'local-reject':
            raise b.SafetyViolation('unknown transition event')
    b.audit_slot_family(list(slot_events.items()))
    for chain in prefixes.values():
        chain_view(chain)
    return dict(slots=len(slot_events), publications=publications, events=len(events),
                longestPrefix=max(map(len,prefixes.values())))
