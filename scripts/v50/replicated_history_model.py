"""Implementation-independent fixed-three-voter replicated-history model."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


VOTERS = ("node-1", "node-2", "node-3")
QUORUM = 2


@dataclass(frozen=True)
class Entry:
    index: int
    epoch: int
    operation: str
    payload_digest: str
    predecessor_digest: str

    @property
    def digest(self) -> str:
        material = (
            f"{self.index}\0{self.epoch}\0{self.operation}\0"
            f"{self.payload_digest}\0{self.predecessor_digest}"
        ).encode()
        return hashlib.sha256(material).hexdigest()


@dataclass
class Voter:
    promised_epoch: int = 0
    log: dict[int, Entry] = field(default_factory=dict)
    proofs: dict[int, str] = field(default_factory=dict)
    applied_index: int = 0


class ReplicatedHistory:
    """Small safety oracle; no production class imports this module."""

    def __init__(self) -> None:
        self.voters = {node: Voter() for node in VOTERS}
        self.active_epoch = 0
        self.commit_index = 0
        self.application_sequence = 0

    def promise(self, epoch: int, nodes: tuple[str, ...]) -> None:
        if len(set(nodes)) < QUORUM:
            raise ValueError("epoch activation requires a voter quorum")
        if epoch <= max(self.voters[node].promised_epoch for node in nodes):
            raise ValueError("epoch must be strictly greater than every promise")
        for node in nodes:
            self.voters[node].promised_epoch = epoch
        self.active_epoch = epoch

    def append(self, node: str, entry: Entry) -> str:
        voter = self.voters[node]
        if entry.epoch != self.active_epoch or entry.epoch < voter.promised_epoch:
            raise ValueError("stale or inactive epoch")
        existing = voter.log.get(entry.index)
        if existing is not None and existing != entry:
            raise ValueError("same-index different-content conflict")
        if entry.index > 1:
            predecessor = voter.log.get(entry.index - 1)
            if predecessor is None or predecessor.digest != entry.predecessor_digest:
                raise ValueError("missing or conflicting predecessor")
        elif entry.predecessor_digest != "GENESIS":
            raise ValueError("first entry must extend genesis")
        voter.log[entry.index] = entry
        return self.receipt(node, entry)

    @staticmethod
    def receipt(node: str, entry: Entry) -> str:
        return hashlib.sha256(f"ACK\0{node}\0{entry.digest}".encode()).hexdigest()

    def commit(self, entry: Entry, receipts: dict[str, str], proof_nodes: tuple[str, ...]) -> str:
        durable = {
            node for node, receipt in receipts.items()
            if node in self.voters
            and self.voters[node].log.get(entry.index) == entry
            and receipt == self.receipt(node, entry)
        }
        if len(durable) < QUORUM:
            raise ValueError("entry lacks durable quorum")
        if len(set(proof_nodes)) < QUORUM:
            raise ValueError("commit proof lacks durable quorum")
        if entry.index != self.commit_index + 1:
            raise ValueError("commit must extend the committed prefix")
        proof = hashlib.sha256(
            ("PROOF\0" + entry.digest + "\0" + "\0".join(sorted(receipts[node] for node in durable))).encode()
        ).hexdigest()
        for node in proof_nodes:
            if self.voters[node].log.get(entry.index) != entry:
                raise ValueError("proof voter lacks the exact entry")
            self.voters[node].proofs[entry.index] = proof
        self.commit_index = entry.index
        return proof

    def apply(self, node: str, through_index: int) -> None:
        voter = self.voters[node]
        if through_index > self.commit_index:
            raise ValueError("cannot apply an uncommitted entry")
        for index in range(voter.applied_index + 1, through_index + 1):
            if index not in voter.log:
                raise ValueError("cannot apply a missing entry")
        voter.applied_index = through_index
        if node == "node-1":
            self.application_sequence = through_index

    def truncate_uncommitted(self, node: str, from_index: int) -> None:
        if from_index <= self.commit_index:
            raise ValueError("committed history is immutable")
        voter = self.voters[node]
        for index in tuple(voter.log):
            if index >= from_index:
                voter.log.pop(index)
                voter.proofs.pop(index, None)

    def recovery_floor(self) -> int:
        recoverable = []
        for index in range(1, self.commit_index + 1):
            holders = sum(index in voter.log and index in voter.proofs
                          for voter in self.voters.values())
            if holders >= QUORUM:
                recoverable.append(index)
        return max(recoverable, default=0)
