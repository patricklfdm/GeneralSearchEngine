"""Research event model of ONE slot under an already certified configuration.

Not a GSE implementation, byte format, reconfiguration algorithm or liveness proof.
Messages, disk force and crashes are separate events. Only authentic messages
created by this model may be delivered; arbitrary Byzantine forgery is excluded.
"""
from dataclasses import dataclass, field
from itertools import combinations

from .membership_model import need, transition_kind


@dataclass(frozen=True, order=True)
class Ballot:
    counter: int
    proposer: str
    incarnation: str

    def __post_init__(self):
        need(type(self.counter) is int and 0 < self.counter < 2**63, 'ballot counter')
        for value in (self.proposer, self.incarnation):
            need(type(value) is str and 0 < len(value) <= 128 and value.isascii(), 'ballot identity')


def fresh_ballot(observed, local_counter, proposer, incarnation):
    need(type(local_counter) is int and 0 <= local_counter < 2**63, 'local ballot counter')
    return Ballot(max(local_counter, observed.counter if observed else 0) + 1, proposer, incarnation)


@dataclass(frozen=True)
class Context:
    root: str
    generation: int
    old: tuple
    new: tuple
    stage: str
    index: int
    predecessor: str

    def __post_init__(self):
        transition_kind(self.old, self.new)
        need(self.stage in ('old', 'joint', 'new'), 'configuration stage')
        for value in (self.generation, self.index):
            need(type(value) is int and 0 < value < 2**63, 'context counter')
        need(all(type(value) is str and 0 < len(value) <= 128 and value.isascii()
                 for value in (self.root, self.predecessor)), 'context identity')

    @property
    def voters(self):
        return frozenset(self.old if self.stage == 'old' else self.new if self.stage == 'new'
                         else self.old + self.new)

    def quorum(self, nodes):
        votes = set(nodes)
        if not votes <= self.voters:
            return False
        groups = (self.old, self.new) if self.stage == 'joint' else (tuple(self.voters),)
        return all(len(votes.intersection(group)) > len(group)//2 for group in groups)

    def oracle_quorums(self):
        """Independent construction, without calling quorum(). Includes supersets."""
        groups = (self.old, self.new) if self.stage == 'joint' else (tuple(sorted(self.voters)),)
        left = [frozenset(row) for row in combinations(groups[0], len(groups[0])//2 + 1)]
        if len(groups) == 1:
            return frozenset(left)
        right = [frozenset(row) for row in combinations(groups[1], len(groups[1])//2 + 1)]
        return frozenset(a | b for a in left for b in right)


@dataclass(frozen=True)
class Accepted:
    ballot: Ballot
    value: str


@dataclass(frozen=True)
class Message:
    kind: str
    voter: str
    ballot: Ballot
    context: Context
    value: str = ''
    accepted: Accepted | None = None
    evidence: tuple = ()


@dataclass
class Voter:
    promise: Ballot | None = None
    accepted: Accepted | None = None
    proofs: set = field(default_factory=set)
    bases: dict = field(default_factory=dict)
    pending: Message | None = None
    alive: bool = True


@dataclass
class Campaign:
    requested: str
    promises: dict = field(default_factory=dict)
    accepts: dict = field(default_factory=dict)
    proofs: dict = field(default_factory=dict)
    selected: str | None = None
    alive: bool = True


class SafetyViolation(ValueError):
    pass


class Model:
    def __init__(self, context, *, mutant=None):
        need(mutant in (None, 'ack-before-force', 'forget-on-crash', 'ignore-accepted',
                        'accept-stale', 'publish-accept-only'), 'unknown model mutant')
        self.context = context
        self.voters = {node: Voter() for node in sorted(context.voters)}
        self.campaigns = {}
        self.messages = {}
        self.authentic = set()
        self.events = []
        self.next_message = 0
        self.mutant = mutant

    def record(self, kind, **details):
        self.events.append(dict(event=kind, **details))

    def emit(self, message):
        self.next_message += 1
        self.messages[self.next_message] = message
        self.authentic.add(message)
        self.record('send', message=message)
        return self.next_message

    def start(self, ballot, value):
        need(ballot.proposer in self.context.voters, 'non-voter proposer')
        need(ballot not in self.campaigns, 'ballot reuse')
        need(type(value) is str and bool(value), 'proposal value')
        self.campaigns[ballot] = Campaign(value)
        self.record('start', ballot=ballot, value=value)

    def send(self, kind, ballot, nodes):
        need(kind in ('prepare', 'accept', 'proof'), 'request kind')
        campaign = self.campaigns[ballot]
        need(campaign.alive, 'crashed proposer')
        nodes = tuple(nodes)
        need(len(set(nodes)) == len(nodes) and set(nodes) <= self.context.voters, 'request voters')
        evidence = ()
        if kind != 'prepare':
            need(campaign.selected is not None, 'selection required')
        if kind == 'proof':
            need(self.context.quorum(campaign.accepts), 'accept quorum required')
            evidence = tuple(campaign.accepts[node] for node in sorted(campaign.accepts))
        return [self.emit(Message(kind, node, ballot, self.context,
                                 campaign.selected or '', evidence=evidence)) for node in nodes]

    def select(self, ballot):
        campaign = self.campaigns[ballot]
        need(campaign.alive and campaign.selected is None, 'selection fixed once per ballot')
        need(self.context.quorum(campaign.promises), 'prepare quorum required')
        accepted = [message.accepted for message in campaign.promises.values() if message.accepted]
        if accepted and self.mutant != 'ignore-accepted':
            highest = max(row.ballot for row in accepted)
            values = {row.value for row in accepted if row.ballot == highest}
            need(len(values) == 1, 'equal ballot conflicting values')
            campaign.selected = values.pop()
        else:
            campaign.selected = campaign.requested
        self.record('select', ballot=ballot, value=campaign.selected,
                    bases=tuple(campaign.promises[node] for node in sorted(campaign.promises)))
        return campaign.selected

    def duplicate(self, message_id):
        return self.emit(self.messages[message_id])

    def drop(self, message_id):
        self.record('drop', message=self.messages.pop(message_id))

    def certificate(self, rows, kind, ballot, value):
        voters = set()
        for row in rows:
            need(row in self.authentic and row.context == self.context and row.kind == kind
                 and row.ballot == ballot and row.value == value, 'foreign certificate')
            need(row.voter not in voters and row.voter in self.context.voters, 'certificate voter')
            voters.add(row.voter)
        need(self.context.quorum(voters), 'certificate quorum')

    def deliver(self, message_id):
        message = self.messages.pop(message_id)
        self.record('deliver', message=message)
        need(message.context == self.context, 'foreign message context')
        if message.kind.endswith('-ack'):
            campaign = self.campaigns[message.ballot]
            if not campaign.alive:
                return
            table = {'prepare-ack': campaign.promises, 'accept-ack': campaign.accepts,
                     'proof-ack': campaign.proofs}[message.kind]
            previous = table.get(message.voter)
            # First immutable basis wins; repeated PREPARE need not resample it.
            if previous is None:
                table[message.voter] = message
            return
        voter = self.voters[message.voter]
        if not voter.alive or voter.pending is not None:
            self.record('unavailable', message=message)
            return
        if message.kind == 'proof':
            self.certificate(message.evidence, 'accept-ack', message.ballot, message.value)
        stale = voter.promise is not None and message.ballot < voter.promise
        if stale and not (self.mutant == 'accept-stale' and message.kind == 'accept'):
            self.record('rejected', message=message)
            return
        if message.kind in ('accept', 'proof'):
            if voter.promise != message.ballot and self.mutant != 'accept-stale':
                self.record('rejected', message=message)
                return
            if message.kind == 'accept' and voter.accepted and voter.accepted.ballot == message.ballot:
                need(voter.accepted.value == message.value, 'same ballot changed value')
        if message.kind == 'prepare' and voter.promise == message.ballot:
            # Return the original durable frozen response, even after later ACCEPT.
            need(message.ballot in voter.bases, 'missing durable frozen basis')
            self.emit(voter.bases[message.ballot])
            return
        voter.pending = message
        self.record('stage', message=message)
        if self.mutant == 'ack-before-force':
            self.ack(message, voter.accepted)

    def ack(self, request, accepted=None):
        return self.emit(Message(request.kind+'-ack', request.voter, request.ballot,
                                 request.context, request.value, accepted))

    def force(self, node):
        voter = self.voters[node]
        need(voter.alive and voter.pending is not None, 'no pending durable operation')
        message = voter.pending
        voter.pending = None
        if message.kind == 'prepare':
            voter.promise = message.ballot
            self.record('promise-force', message=message, accepted=voter.accepted)
            voter.bases[message.ballot] = Message('prepare-ack', node, message.ballot,
                                                  message.context, accepted=voter.accepted)
            self.emit(voter.bases[message.ballot])
        elif message.kind == 'accept':
            voter.accepted = Accepted(message.ballot, message.value)
            self.record('accept-force', message=message)
            self.ack(message)
        else:
            voter.proofs.add(Accepted(message.ballot, message.value))
            self.record('proof-force', message=message)
            self.ack(message)

    def crash(self, node):
        voter = self.voters[node]
        voter.pending = None
        voter.alive = False
        for ballot, campaign in self.campaigns.items():
            if ballot.proposer == node:
                campaign.alive = False
                campaign.promises.clear(); campaign.accepts.clear(); campaign.proofs.clear()
                campaign.selected = None
        if self.mutant == 'forget-on-crash':
            voter.promise = None; voter.accepted = None; voter.proofs.clear(); voter.bases.clear()
        self.record('crash', voter=node)

    def restart(self, node):
        need(not self.voters[node].alive, 'voter already running')
        self.voters[node].alive = True
        self.record('restart', voter=node)

    def publish(self, ballot):
        campaign = self.campaigns[ballot]
        need(campaign.alive and campaign.selected is not None, 'inactive publication')
        rows = campaign.accepts if self.mutant == 'publish-accept-only' else campaign.proofs
        need(self.context.quorum(rows), 'proof quorum required')
        self.record('publish', ballot=ballot, value=campaign.selected)


def audit(context, events):
    """Replay force/ACK/publication history, independent of current model state.

    Historical acceptances remain visible after overwrite and process death.
    The oracle uses enumerated quorum families, not Model's vote predicate.
    """
    families = context.oracle_quorums()
    has_quorum = lambda votes: any(q <= votes for q in families)
    promises, accepted, proofs, bases, last_accepted = {}, {}, {}, {}, {}
    sent_acks = set()
    chosen = set()
    publications = 0

    def safe(value, why):
        if not value:
            raise SafetyViolation(why)

    for event in events:
        kind = event['event']
        message = event.get('message')
        if message is not None:
            safe(message.context == context, 'foreign event context')
            safe(message.voter in context.voters and message.ballot.proposer in context.voters,
                 'foreign event voter')
        if kind == 'promise-force':
            previous = promises.get(message.voter)
            safe(previous is None or message.ballot > previous, 'durable promise regression')
            promises[message.voter] = message.ballot
            safe(event['accepted'] == last_accepted.get(message.voter), 'basis differs from durable acceptance')
            bases[message.voter, message.ballot] = event['accepted']
        elif kind == 'accept-force':
            safe(promises.get(message.voter) == message.ballot, 'accept violates durable promise')
            key = message.ballot, message.value
            accepted.setdefault(key, set()).add(message.voter)
            last_accepted[message.voter] = Accepted(message.ballot, message.value)
            safe(not any(b == message.ballot and v != message.value for b, v in accepted),
                 'same ballot conflicting acceptance')
            if has_quorum(accepted[key]):
                chosen.add(message.value)
                safe(len(chosen) == 1, 'conflicting chosen values')
        elif kind == 'proof-force':
            key = message.ballot, message.value
            rows = message.evidence
            safe(all(row in sent_acks and row.kind == 'accept-ack' and row.context == context
                     and row.ballot == message.ballot and row.value == message.value for row in rows),
                 'proof certificate context/authority')
            safe(len({row.voter for row in rows}) == len(rows)
                 and has_quorum({row.voter for row in rows}), 'proof certificate quorum')
            safe(has_quorum(accepted.get(key, set())), 'proof without durable accept quorum')
            proofs.setdefault(key, set()).add(message.voter)
        elif kind == 'send' and message.kind.endswith('-ack'):
            sent_acks.add(message)
            key = message.ballot, message.value
            if message.kind == 'prepare-ack':
                safe((message.voter, message.ballot) in bases and
                     bases[message.voter, message.ballot] == message.accepted,
                     'promise ACK without frozen durable basis')
            else:
                journal = accepted if message.kind == 'accept-ack' else proofs
                safe(message.voter in journal.get(key, set()), 'ACK before durable force')
        elif kind == 'publish':
            key = event['ballot'], event['value']
            safe(has_quorum(proofs.get(key, set())), 'publication without durable proof quorum')
            safe(event['value'] in chosen, 'publication without chosen value')
            publications += 1
    return dict(chosen=sorted(chosen), publications=publications,
                durableAccepts=sum(map(len, accepted.values())), events=len(events))


def audit_slot_family(histories):
    """Detect a same-root/index fork even when each configuration passes alone.

    This is an observation checker, not proof that the supplied views were legally
    activated. Configuration generation and predecessor digest cannot be used to
    partition away a fork at the same logical slot.
    """
    slots = {}
    for context, events in histories:
        result = audit(context, events)
        chosen = slots.setdefault((context.root, context.index), set())
        chosen.update(result['chosen'])
        if len(chosen) > 1:
            raise SafetyViolation('cross-configuration conflicting chosen values')
    return len(slots)
