"""Abstract two-generation checkpoint/floor/retirement research.

Atomic file force and immutable authenticated source packets are assumptions.
This compacts the journal into a snapshot; it does NOT truncate configuration
ancestry. Complete proof metadata is bounded and retained, rather than inventing
an unverified latest-configuration trust anchor. No production files are touched.
"""
from dataclasses import dataclass
import hashlib

from . import ballot_model as b
from . import transition_model as t
from .membership_model import need

FILES = ('snapshot', 'journal', 'seal')
MAX_CERTIFICATES = 16
MAX_CHANGES = 4
MAX_PACKET_BYTES = 131072
MAX_RETAINED_BYTES = 2097152


def raw(value):
    return t.encoded(value).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Tail:
    owner: str
    authority: t.Authority
    ballot: b.Ballot
    value: str


@dataclass(frozen=True)
class Packet:
    owner: str
    generation: str
    snapshot: tuple
    suffix: tuple
    tail: Tail | None

    @property
    def chain(self):
        return self.snapshot + self.suffix

    @property
    def identity(self):
        return sha(self.files()['seal'])

    def files(self):
        parts = {'snapshot': raw(self.snapshot), 'journal': raw(dict(suffix=self.suffix,tail=self.tail))}
        parts['seal'] = raw(dict(owner=self.owner,generation=self.generation,
                                 inventory={name:sha(data) for name,data in parts.items()}))
        return parts


def equivalent(left, right):
    return tuple(c.entry_id for c in left) == tuple(c.entry_id for c in right)


class AuthoritySource:
    """Input is an already independently checked transition execution."""
    def __init__(self, world):
        t.check_history(world.root,world.initial,world.events)
        self.world = world
        self.root, self.initial = world.root, world.initial

    def validate(self, packet):
        need(packet.owner in self.world.nodes and packet.generation in ('a-0','b-1','a-2'), 'source identity')
        need(type(packet.snapshot) is tuple and type(packet.suffix) is tuple and
             len(packet.chain) <= MAX_CERTIFICATES, 'authority certificate capacity')
        need(sum(t.Entry.read(c.value).kind == 'INTENT' for c in packet.chain) <= MAX_CHANGES,
             'configuration history capacity')
        authority = t.fold(self.root,self.initial,packet.chain,self.world.verify)
        original = self.world.nodes[packet.owner].chain
        need(len(packet.chain) <= len(original) and equivalent(packet.chain,original[:len(packet.chain)]),
             'source differs from certified history')
        if packet.tail is not None:
            tail = packet.tail
            need(tail.owner == packet.owner and tail.authority == authority, 'tail owner/predecessor')
            voter = self.world.nodes[packet.owner].slots.get(authority.index)
            need(voter is not None and voter.accepted == b.Accepted(tail.ballot,tail.value),
                 'unobserved tail acceptance')
        need(sum(map(len,packet.files().values())) <= MAX_PACKET_BYTES, 'packet byte capacity')
        return authority


class Store:
    def __init__(self, source, owner, *, mutant=None):
        need(mutant in (None,'drop-tail','selector-before-force','delete-without-floor',
                        'reset-promise','reuse-retiring-slot'), 'unknown recovery mutant')
        self.source, self.owner, self.mutant = source, owner, mutant
        replica = source.world.nodes[owner]
        chain = replica.chain
        need(bool(chain), 'checkpoint requires proven prefix')
        authority = t.fold(source.root,source.initial,chain,source.world.verify)
        voter = replica.slots.get(authority.index)
        tail = None if voter is None or voter.accepted is None else Tail(owner,authority,voter.accepted.ballot,voter.accepted.value)
        initial = Packet(owner,'a-0',chain[:-1],chain[-1:],tail)
        source.validate(initial)
        promises = [slot.promise for slot in replica.slots.values() if slot.promise]
        self.promise = max(promises) if promises else None
        self.basis = raw(dict(promise=self.promise,prefix=tuple(c.entry_id for c in chain),tail=tail))
        self.baseline_promise, self.baseline_basis = self.promise,self.basis
        self.packets = {'a':initial}
        self.files = {'a':initial.files()}
        self.selector = 'a'
        self.pending_selector = None
        self.writing = None
        self.floor = None
        self.floor_plan = None
        self.floor_copies = {}
        self.retirement = None
        self.pending_retirement = None
        self.events = [dict(event='init',packet=initial,promise=self.promise,basis=self.basis.hex())]

    def record(self,event,**details):
        self.events.append(dict(event=event,**details))

    def usage(self):
        total=sum(len(data) for files in self.files.values() for data in files.values())
        total+=sum(len(data) for files in self.floor_copies.values() for data in files.values())
        total+=len(self.basis)
        if self.retirement:total+=sum(map(len,self.retirement[1].files().values()))
        return total

    def reserve(self, extra):
        need(self.usage()+extra <= MAX_RETAINED_BYTES, 'retained byte capacity')

    def current(self):
        need(self.selector in self.files and self.selector in self.packets, 'missing active selector/generation')
        packet=self.packets[self.selector]
        need(self.files[self.selector] == packet.files(), 'incomplete active generation')
        self.source.validate(packet)
        if packet.tail:
            need(self.promise is not None and self.promise >= packet.tail.ballot, 'tail exceeds root promise')
        return packet

    def begin(self, packet):
        self.source.validate(packet)
        active=self.current()
        slot=packet.generation[0]
        next_generation={'a-0':'b-1','b-1':'a-2'}.get(active.generation)
        need(packet.owner==self.owner and slot!=self.selector and packet.generation==next_generation,
             'checkpoint owner/generation')
        need(slot not in self.files and (self.retirement is None or self.mutant=='reuse-retiring-slot'),
             'inactive slot still owned')
        need(equivalent(active.chain,packet.chain), 'checkpoint changed proven prefix')
        need(packet.tail==active.tail or self.mutant=='drop-tail', 'checkpoint dropped/changed unresolved tail')
        self.reserve(sum(map(len,packet.files().values())))
        self.packets[slot]=packet;self.files[slot]={};self.writing=slot
        self.record('begin',packet=packet)

    def force_file(self, name):
        slot=self.writing
        need(name in FILES and slot in self.files and self.selector!=slot, 'inactive write')
        packet=self.packets[slot];data=packet.files()[name]
        if name=='seal':need(set(self.files[slot])=={'snapshot','journal'}, 'seal requires complete files')
        need(name not in self.files[slot], 'duplicate force')
        self.reserve(len(data));self.files[slot][name]=data
        self.record('file-force',slot=slot,name=name,data=sha(data))

    def stage_selector(self):
        slot=self.writing
        need(slot in self.packets and self.files.get(slot)==self.packets[slot].files(), 'selector requires complete generation')
        self.pending_selector=slot;self.record('selector-stage',slot=slot)
        if self.mutant=='selector-before-force':self.selector=slot

    def force_selector(self):
        need(self.pending_selector is not None, 'missing pending selector')
        self.selector=self.pending_selector;self.pending_selector=None;self.writing=None
        if self.mutant=='reset-promise':self.promise=self.baseline_promise
        self.record('selector-force',slot=self.selector)

    def prepare_floor(self, packets):
        packets=tuple(packets)
        active=self.current();authority=self.source.validate(active)
        need(self.floor_plan is None, 'floor already prepared')
        owners=set()
        for packet in packets:
            self.source.validate(packet)
            need(packet.owner not in owners and packet.owner in authority.voters, 'floor voter identity')
            need(equivalent(packet.chain,active.chain), 'floor prefix mismatch')
            owners.add(packet.owner)
        need(authority.quorum(owners), 'floor requires current configuration quorum')
        need(any(p.identity==active.identity and p.owner==self.owner for p in packets), 'floor lacks exact local generation')
        self.reserve(sum(len(data) for p in packets for data in p.files().values()))
        self.floor_plan=tuple(packets)
        self.record('floor-stage',packets=tuple(packets))

    def force_source(self, owner, name):
        need(self.floor_plan is not None and name in FILES, 'missing floor plan')
        packet=next(p for p in self.floor_plan if p.owner==owner)
        files=self.floor_copies.setdefault(owner,{})
        if name=='seal':need(set(files)=={'snapshot','journal'}, 'source seal before files')
        need(name not in files, 'duplicate source copy')
        data=packet.files()[name];self.reserve(len(data));files[name]=data
        self.record('source-force',owner=owner,name=name,data=sha(data))

    def force_floor(self):
        need(self.floor_plan is not None and all(self.floor_copies.get(p.owner)==p.files() for p in self.floor_plan),
             'incomplete durable floor sources')
        self.floor=(self.current().identity,self.floor_plan)
        self.record('floor-force',active=self.floor[0])

    def deletion_ready(self):
        active=self.current()
        if self.mutant!='delete-without-floor':
            need(self.floor is not None and self.floor[0]==active.identity, 'durable floor required')
            need(all(self.floor_copies.get(p.owner)==p.files() for p in self.floor[1]), 'lost floor source bytes')
        return active

    def stage_retirement(self):
        active=self.deletion_ready()
        need(self.selector=='b' and self.retirement is None, 'retirement must be inactive')
        old=self.packets['a'];self.source.validate(old)
        need(equivalent(old.chain,active.chain), 'retirement prefix mismatch')
        # Candidate rule: an above-floor acceptance can retire only with an EXACT
        # owned copy in the forced active generation, plus the unchanged promise.
        need(old.tail==active.tail, 'retirement loses unresolved tail')
        need(self.promise==self.baseline_promise or (self.promise and self.baseline_promise and self.promise>self.baseline_promise),
             'retirement promise regression')
        self.reserve(sum(map(len,old.files().values())))
        self.pending_retirement=('a',old);self.record('retirement-stage',slot='a',packet=old)

    def force_retirement(self):
        need(self.pending_retirement is not None, 'missing retirement inventory')
        self.retirement=self.pending_retirement;self.pending_retirement=None
        self.record('retirement-force',slot='a')

    def delete_file(self,name):
        self.deletion_ready();need(self.retirement is not None, 'durable retirement inventory required')
        slot,packet=self.retirement
        need(slot!=self.selector and name in FILES, 'delete active/unknown file')
        files=self.files[slot]
        need(all(data==packet.files()[key] for key,data in files.items()), 'retirement bytes changed')
        need(name in files, 'file already deleted')
        del files[name];self.record('delete-file',slot=slot,name=name)

    def delete_directory(self):
        self.deletion_ready();need(self.retirement is not None, 'retirement missing')
        slot,_=self.retirement;need(self.files.get(slot)=={}, 'directory not empty')
        del self.files[slot];self.record('delete-directory',slot=slot)

    def clear_retirement(self):
        need(self.retirement is not None and self.retirement[0] not in self.files, 'retirement still owns files')
        self.retirement=None;self.record('retirement-clear')

    def advance_promise(self, ballot):
        need(self.promise is None or ballot>self.promise, 'promise must advance')
        self.promise=ballot
        self.record('promise-force',ballot=ballot)

    def crash(self):
        self.pending_selector=None;self.pending_retirement=None;self.writing=None
        if self.floor is None:
            self.floor_plan=None;self.floor_copies={}
        self.record('crash')

    def reopen(self):
        active=self.current()
        self.record('reopen',active=active.identity,promise=self.promise,basis=self.basis.hex(),tail=active.tail)
        return active
