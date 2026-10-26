"""Conditional stable-view retention research, not a runtime or authority verifier.

Integers denote already authenticated endpoints of one consistent stable history.
The model assumes atomic retention-intent persistence before any publication can
reach a peer, exact complete-generation observations, and safe selected-source
maintenance. Implementing/proving those assumptions remains Phase 3B/3D work.
"""
import argparse
from dataclasses import dataclass, replace
import itertools
import json

from .membership_model import need

BRIDGES = 6


@dataclass(frozen=True)
class Peer:
    known: int
    pending: int | None = None

    def possible(self):
        return {self.known} | (set() if self.pending is None else {self.pending})


@dataclass(frozen=True)
class State:
    tip: int
    selected: int
    first: int | None
    peers: tuple[Peer, ...]
    # Environment truth is deliberately separate from the controller's knowledge.
    physical: tuple[int, ...]

    def check(self):
        need(3 <= len(self.peers) <= 5 and len(self.peers) == len(self.physical), 'stable peer count')
        need(0 <= self.selected <= self.tip and (self.first is None or self.selected < self.first <= self.tip), 'round coverage order')
        for peer, actual in zip(self.peers, self.physical):
            need(0 <= peer.known <= self.tip and (peer.pending is None or peer.known < peer.pending <= self.tip), 'peer progress order')
            need(actual in peer.possible(), 'forgot possible durable peer endpoint')
        return self

    def required(self):
        self.check()
        # Genesis is a direct anchor. Every other endpoint is hidden by the next
        # enlarged stable RANGE. The real implementation must also size bytes.
        points = {self.tip, self.selected}
        if self.first is not None:
            points.add(self.first)
        for peer in self.peers:
            points.update(peer.possible())
        return frozenset(points - {0})

    def observe(self, peer):
        """Actual complete-generation observation, NOT STATUS/HEARTBEAT."""
        self.check()
        need(0 <= peer < len(self.peers), 'observation peer')
        before = self.peers[peer]
        if before.pending is None or self.physical[peer] == before.known:
            # Seeing the old generation cannot cancel an in-flight publication.
            return self
        need(self.physical[peer] == before.pending, 'observation outside original uncertainty')
        peers = list(self.peers)
        peers[peer] = Peer(before.pending)
        return replace(self, peers=tuple(peers)).check()

    def deliver_pending(self, peer):
        self.check()
        need(0 <= peer < len(self.peers) and self.peers[peer].pending is not None, 'no pending delivery')
        physical = list(self.physical)
        physical[peer] = self.peers[peer].pending
        return replace(self, physical=tuple(physical)).check()

    def transfer(self, peer, delivered=False):
        """Conditionally install the authenticated current tip on a lagging peer.

        Persist both endpoints before the transfer can change its selector. The
        model assumes actual adoption/install eligibility and proof checks.
        """
        self.check()
        need(type(peer) is int and 0 <= peer < len(self.peers) and type(delivered) is bool, 'transfer peer/delivery')
        before = self.peers[peer]
        need(before.pending is None and before.known < self.tip, 'unresolved or current transfer peer')
        peers = list(self.peers)
        physical = list(self.physical)
        peers[peer] = Peer(before.known, self.tip)
        if delivered:
            physical[peer] = self.tip
        return replace(self, peers=tuple(peers), physical=tuple(physical)).check()

    def publication(self, acknowledged, uncertain=()):
        """One certified publication followed by exact majority generation copies.

        uncertain is a tuple of (peer, actually_delivered). Both old and target
        remain possible until exact progress is observed, regardless of truth.
        """
        self.check()
        acknowledged = tuple(acknowledged)
        waiting = tuple(peer for peer, _ in uncertain)
        need(len(set(acknowledged)) == len(acknowledged) and len(acknowledged) > len(self.peers)//2, 'complete-copy majority')
        need(len(set(waiting)) == len(waiting) and not set(waiting) & set(acknowledged), 'duplicate publication peer')
        targets = (*acknowledged, *waiting)
        need(all(type(peer) is int and 0 <= peer < len(self.peers) for peer in targets), 'publication peer')
        need(all(type(delivered) is bool for _, delivered in uncertain), 'delivery boolean')
        need(all(self.peers[p].pending is None and self.peers[p].known == self.tip for p in targets), 'unresolved or lagging publication peer')
        need(len(self.required()) <= BRIDGES, 'ancestry headroom: consolidate before new work')
        tip = self.tip + 1
        peers = list(self.peers)
        physical = list(self.physical)
        # The atomic pre-dispatch persistence here is an explicit assumption.
        for peer in targets:
            peers[peer] = Peer(self.tip, tip)
        for peer in acknowledged:
            physical[peer] = tip
        for peer, delivered in uncertain:
            if delivered:
                physical[peer] = tip
        result = replace(self, tip=tip, first=tip if self.first is None else self.first,
                         peers=tuple(peers), physical=tuple(physical)).check()
        for peer in acknowledged:
            result = result.observe(peer)
        return result

    def consolidate(self, copies):
        """A fresh selection after real majority installation at the SAME tip.

        Does not drop peer obligations. Actual floor/source retirement, ballots,
        carried values and disk crash ordering are outside this conditional model.
        """
        self.check()
        copies = tuple(copies)
        need(len(set(copies)) == len(copies) and len(copies) > len(self.peers)//2, 'consolidation majority')
        need(all(type(p) is int and 0 <= p < len(self.peers) and self.peers[p] == Peer(self.tip)
                 and self.physical[p] == self.tip for p in copies), 'consolidation complete tip copies')
        return replace(self, selected=self.tip, first=None).check()


def fixture(size=5, delivered=()):
    """Conditional valid-prefix endpoints, not a fabricated distributed run."""
    majority = size//2 + 1
    missing = size-majority
    if not delivered:
        delivered = (False,)*missing
    need(len(delivered) == missing, 'fixture delivery count')
    state = State(0, 0, None, (Peer(0),)*size, (0,)*size)
    voters = tuple(range(majority))
    for slot in range(1, 10):
        # All peers reach 1, only the second eventual laggard reaches 2.
        recipients = tuple(range(size)) if slot == 1 else voters + ((majority+1,) if slot == 2 and missing == 2 else ())
        state = state.publication(recipients)
        if slot == 5:
            state = state.consolidate(voters)
        if 7 <= slot < 7+missing:
            peer = majority+slot-7
            state = state.transfer(peer, delivered[slot-7])
    return state, voters



def run(rounds=1000):
    need(type(rounds) is int and 2 <= rounds <= 10000, 'research round count')
    rows = []
    for size in (3, 4, 5):
        for delivered in itertools.product((False, True), repeat=size-(size//2+1)):
            state, majority = fixture(size, delivered)
            original_peers = state.peers[len(majority):]
            consolidations = 0
            peak = 0
            for _ in range(rounds):
                if len(state.required()) > BRIDGES:
                    state = state.consolidate(majority)
                    consolidations += 1
                peak = max(peak, len(state.required()))
                state = state.publication(majority)
                need(state.peers[len(majority):] == original_peers, 'offline obligations changed')
            rows.append(dict(size=size, pendingDelivered=list(delivered), publications=rounds,
                             consolidations=consolidations, maximumRequiredBridges=peak,
                             retainedOfflineEndpoints=sum(len(p.possible()) for p in original_peers)))
    return dict(status='PASS', scope='conditional-stable-retention-research', histories=len(rows),
                publications=sum(r['publications'] for r in rows), cases=rows,
                productionRuntime=False, crashQualification=False, jointTransitions=False,
                metadataBytesQualified=False, phase3Complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(run(args.rounds), sort_keys=True))
