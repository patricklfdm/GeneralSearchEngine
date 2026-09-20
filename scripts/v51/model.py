"""Executable logical protocol, deliberately separate from the event oracle and product.

Atomic transitions below are durable actions. The process scaffold separately splits
write/force/ACK cuts; this model does not pretend an atomic action tests filesystem IO.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json


class Rejected(ValueError):
    pass


def need(value, message):
    if not value:
        raise Rejected(message)


def next_epoch(maximum, rank):
    need(type(maximum) is int and 1 <= maximum < 1 << 63 and rank in range(3), 'epoch inputs')
    result = 3 * (0 if maximum == 1 else (maximum - 2) // 3 + 1) + rank + 2
    need(result < 1 << 63, 'epoch exhaustion')
    return result


@dataclass
class Voter:
    promise: int = 1
    prefix: list = field(default_factory=list)
    accepted: dict = field(default_factory=dict)
    generation: int = 1
    sealed: bool = True
    promises: int = 1
    running: bool = True


class Cluster:
    def __init__(self, queue_limit=32, promise_limit=10000):
        self.voters = [Voter() for _ in range(3)]
        self.campaigns = {}
        self.messages = []
        self.events = []
        self.queue_limit = queue_limit
        self.promise_limit = promise_limit
        self.pins = {}
        self.reads = {}
        self.serial = 0

    def event(self, kind, node=None, **data):
        e = dict(event=kind, **data)
        if node is not None:
            e.update(node=node, generation=self.voters[node].generation)
        e['position'] = len(self.events)
        self.events.append(e)
        return e

    def identity(self, label):
        self.serial += 1
        return f'{label}-{self.serial}'

    def queue(self, kind, target, **data):
        need(len(self.messages) < self.queue_limit, 'queue capacity')
        self.messages.append(dict(kind=kind, target=target, **deepcopy(data)))
        self.account()

    def account(self):
        self.event('account', queued=len(self.messages), limit=self.queue_limit,
                   pins=len(self.pins), pinLimit=8)

    def prepare(self, node, ballot):
        v = self.voters[node]
        need(v.running and v.sealed, 'ineligible voter')
        need(ballot > v.promise and v.promises < self.promise_limit, 'stale or exhausted promise')
        v.promise = ballot; v.promises += 1
        self.event('promise-force', node, ballot=ballot, proposer=(ballot-2) % 3)
        basis = self.event('basis', node, ballot=ballot, id=self.identity('basis'),
                           prefix=list(v.prefix), accepted={str(i): list(a) for i, a in v.accepted.items() if i > len(v.prefix)})
        return deepcopy(basis)

    def campaign(self, proposer, ballot=None):
        ballot = ballot or next_epoch(self.voters[proposer].promise, proposer)
        need((ballot - 2) % 3 == proposer and ballot not in self.campaigns, 'ballot owner/reuse')
        own = self.prepare(proposer, ballot)
        self.campaigns[ballot] = {'node': proposer, 'bases': {proposer: own},
            'selected': False, 'retired': False, 'ready': False, 'round': None, 'quorum': None}
        for peer in range(3):
            if peer != proposer: self.queue('prepare', peer, ballot=ballot, proposer=proposer)
        return ballot

    def select(self, ballot, peer_basis):
        c = self.campaigns[ballot]
        need(not c['selected'] and self.voters[c['node']].promise == ballot, 'inactive selection')
        c['bases'][peer_basis['node']] = peer_basis
        bases = [c['bases'][c['node']], peer_basis]
        prefix = deepcopy(max((b['prefix'] for b in bases), key=len))
        need(all(prefix[:len(b['prefix'])] == b['prefix'] for b in bases), 'conflicting proof')
        tails = [(int(i), a) for b in bases for i, a in b['accepted'].items() if int(i) > len(prefix)]
        need(all(i == len(prefix)+1 for i, _ in tails), 'unproven suffix length')
        highest = max((a[0] for _, a in tails), default=0)
        choices = {a[1] for _, a in tails if a[0] == highest}
        need(len(choices) <= 1, 'conflicting same-ballot values')
        value = next(iter(choices)) if choices else f'NO_OP:{ballot}:activation'
        c['selected'] = True; c['quorum'] = [c['node'], peer_basis['node']]
        self.event('select', ballot=ballot, proposer=c['node'], bases=[b['id'] for b in bases], prefix=prefix, value=value)
        self.begin(ballot, prefix, value, activation=True)

    def begin(self, ballot, prefix, value, activation=False, read=None):
        c = self.campaigns[ballot]
        need(c['round'] is None and self.voters[c['node']].promise == ballot, 'not active/slot busy')
        c['round'] = {'slot': len(prefix)+1, 'value': value, 'accepts': {}, 'proofs': {},
                      'activation': activation, 'read': read, 'proof': None}
        for n in c['quorum']:
            self.queue('accept', n, ballot=ballot, prefix=prefix, value=value)

    def submit(self, ballot, value):
        c = self.campaigns[ballot]
        need(c['ready'], 'not ready')
        self.begin(ballot, list(self.voters[c['node']].prefix), value)

    def read(self, ballot, read_id):
        c = self.campaigns[ballot]
        need(read_id not in self.reads and c['ready'], 'read identity/role')
        self.reads[read_id] = ballot
        self.event('read-invoke', c['node'], read=read_id)
        self.begin(ballot, list(self.voters[c['node']].prefix), f'NO_OP:{ballot}:read:{read_id}', read=read_id)

    def finish_read(self, read_id):
        ballot = self.reads[read_id]; node = self.campaigns[ballot]['node']
        need(read_id in self.pins, 'not pinned')
        self.event('read-result', node, read=read_id, prefix=list(self.pins.pop(read_id)))
        self.account()

    def deliver(self, position=0):
        message = self.messages.pop(position); self.account()
        node, ballot, kind = message['target'], message['ballot'], message['kind']
        v = self.voters[node]; c = self.campaigns[ballot]
        try:
            need(v.running and v.sealed, 'ineligible voter')
            if kind in ('promise', 'accepted', 'proven'):
                need(not c['retired'], 'retired campaign after restart')
            if kind == 'prepare':
                basis = self.prepare(node, ballot)
                self.queue('promise', c['node'], ballot=ballot, basis=basis)
            elif kind == 'promise':
                if not c['selected']: self.select(ballot, message['basis'])
            elif kind == 'accept':
                need(v.promise == ballot, 'fenced accept')
                prefix = message['prefix']; slot = len(prefix)+1; value = message['value']
                need(prefix[:len(v.prefix)] == v.prefix, 'cannot erase proven prefix')
                if prefix != v.prefix:
                    v.prefix = list(prefix)
                    self.event('install', node, ballot=ballot, prefix=prefix)
                old = v.accepted.get(slot)
                need(old is None or old[0] < ballot or old == (ballot, value), 'same-ballot changed value')
                need(slot == len(v.prefix)+1, 'predecessor not proven')
                v.accepted[slot] = (ballot, value)
                e = self.event('accept-force', node, ballot=ballot, slot=slot, value=value, id=self.identity('accept'))
                self.queue('accepted', c['node'], ballot=ballot, receipt=e)
            elif kind == 'accepted':
                need(v.promise == ballot, 'fenced proposer')
                r = c['round']; receipt = message['receipt']
                need(r is not None and (r['slot'],r['value']) == (receipt['slot'],receipt['value']), 'stale receipt')
                r['accepts'][receipt['node']] = receipt['id']
                if len(r['accepts']) == 2 and r['proof'] is None:
                    p = self.event('entry-quorum', ballot=ballot, slot=r['slot'], value=r['value'],
                                   receipts=list(r['accepts'].values()), id=self.identity('proof'))
                    r['proof'] = p['id']
                    for peer in c['quorum']:
                        self.queue('proof', peer, ballot=ballot, proof=p['id'], slot=r['slot'], value=r['value'])
            elif kind == 'proof':
                need(v.promise == ballot, 'fenced proof')
                slot, value = message['slot'],message['value']
                need(v.accepted.get(slot) == (ballot,value) and slot == len(v.prefix)+1, 'proof acceptance/prefix')
                v.prefix.append(value)
                e = self.event('proof-force', node, ballot=ballot, slot=slot, value=value, proof=message['proof'], id=self.identity('proof-force'))
                self.queue('proven', c['node'], ballot=ballot, receipt=e)
            elif kind == 'proven':
                need(v.promise == ballot, 'fenced publish')
                r=c['round']; receipt=message['receipt']
                need(r is not None and (r['slot'],r['value']) == (receipt['slot'],receipt['value']), 'stale proof receipt')
                r['proofs'][receipt['node']] = receipt['id']
                if len(r['proofs']) == 2:
                    self.event('success', node, ballot=ballot, slot=r['slot'], value=r['value'], receipts=list(r['proofs'].values()))
                    c['round'] = None
                    if r['activation']:
                        if r['value'] != f'NO_OP:{ballot}:activation':
                            self.begin(ballot, list(v.prefix), f'NO_OP:{ballot}:activation', activation=True)
                        else: c['ready'] = True
                    if r['read'] is not None:
                        need(len(self.pins) < 8, 'pin bound')
                        self.pins[r['read']] = tuple(v.prefix)
                        self.event('read-pin', node, ballot=ballot, slot=r['slot'], barrier=r['value'],
                                   read=r['read'], prefix=list(v.prefix), proof=r['proof'])
                        self.account()
            else: raise AssertionError(kind)
        except Rejected as failure:
            self.event('reject', node, ballot=ballot, reason=str(failure))
        return message

    def drain(self):
        steps = 0
        while self.messages:
            self.deliver(); steps += 1
            need(steps < 256, 'nonterminating bounded exchange')

    def drop(self, position=0):
        message = self.messages.pop(position)
        self.event('drop', messageKind=message['kind']); self.account()

    def duplicate(self, position=0):
        message = self.messages[position]
        self.queue(message['kind'], message['target'], **{k:v for k,v in message.items() if k not in ('kind','target')})
        self.event('duplicate', messageKind=message['kind'])

    def restart(self, node, lost=False):
        v = self.voters[node]
        self.event('restart', node); v.generation += 1
        if lost:
            v.sealed = False; self.event('lost-disk', node)
        for c in self.campaigns.values():
            if c['node'] == node:
                c['ready'] = False; c['retired'] = True
        # Durable promise, accepted values and proofs survive; local campaign never resumes.
        v.running = True

    def checkpoint(self, node):
        v = self.voters[node]
        need(not any(i > len(v.prefix) for i in v.accepted), 'checkpoint cannot discard unresolved acceptance')
        self.event('checkpoint', node, prefix=list(v.prefix), promise=v.promise)

    def fingerprint(self):
        # Exploration contains no active reads; event serials bind queued receipts/bases.
        state = {'voters':[vars(v) for v in self.voters], 'campaigns':self.campaigns,
                 'messages':self.messages, 'serial':self.serial, 'pins':self.pins}
        return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
