"""Implementation-independent fixed-three-voter replicated-history model."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


VOTERS = ("node-1", "node-2", "node-3")
QUORUM = 2
MAX_EPOCH = (1 << 63) - 1
APPLICATION_OPERATIONS = frozenset({
    "ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL", "REMOVE_ALL",
    "INDEX_CREATE", "INDEX_DROP",
})
CONTROL_OPERATIONS = frozenset({"NO_OP", "SNAPSHOT_MARKER"})


@dataclass(frozen=True)
class Entry:
    index: int
    epoch: int
    operation: str
    payload_digest: str
    predecessor_digest: str
    incarnation: str = "leader-1"

    def __post_init__(self) -> None:
        if (type(self.index) is not int or type(self.epoch) is not int
                or not 1 <= self.index <= MAX_EPOCH or not 1 <= self.epoch <= MAX_EPOCH):
            raise ValueError("entry index/epoch must be positive signed 64-bit values")
        if self.operation not in APPLICATION_OPERATIONS | CONTROL_OPERATIONS:
            raise ValueError("unsupported operation (membership is fixed)")
        if not self.incarnation or not self.payload_digest or not self.predecessor_digest:
            raise ValueError("entry identities must not be empty")

    @property
    def digest(self) -> str:
        material = (
            f"{self.index}\0{self.epoch}\0{self.operation}\0"
            f"{self.payload_digest}\0{self.predecessor_digest}\0{self.incarnation}"
        ).encode()
        return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class CommitProof:
    entry: Entry
    receipts: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        material = "PROOF\0" + self.entry.digest + "\0" + "\0".join(
            f"{node}:{receipt}" for node, receipt in self.receipts)
        return hashlib.sha256(material.encode()).hexdigest()


@dataclass
class Voter:
    promised_epoch: int = 0
    promised_incarnation: str = ""
    log: dict[int, Entry] = field(default_factory=dict)
    proofs: dict[int, CommitProof] = field(default_factory=dict)
    applied_index: int = 0
    application_sequence: int = 0
    snapshot_index: int = 0


class ReplicatedHistory:
    """Small safety oracle; no production class imports this module."""

    def __init__(self) -> None:
        self.voters = {node: Voter() for node in VOTERS}
        self.active_epoch = 0
        self.active_incarnation = ""
        self.commit_index = 0
        self.application_sequence = 0

    def _quorum(self, nodes: tuple[str, ...]) -> None:
        if (len(set(nodes)) < QUORUM or len(set(nodes)) != len(nodes)
                or not set(nodes) <= set(VOTERS)):
            raise ValueError("requires a distinct configured voter quorum")

    def promise(self, epoch: int, nodes: tuple[str, ...], *,
                incarnation: str = "leader-1", leader: str = "node-1") -> None:
        self._quorum(nodes)
        if leader != "node-1" or not incarnation:
            raise ValueError("only the configured leader incarnation may activate")
        if type(epoch) is not int or not 1 <= epoch <= MAX_EPOCH:
            raise ValueError("epoch overflow or invalid epoch")
        if epoch <= max(self.voters[node].promised_epoch for node in nodes):
            raise ValueError("epoch must be strictly greater than every promise")
        for node in nodes:
            self.voters[node].promised_epoch = epoch
            self.voters[node].promised_incarnation = incarnation
        self.active_epoch = epoch
        self.active_incarnation = incarnation

    def _active(self, voter: Voter, entry: Entry) -> None:
        if (entry.epoch != self.active_epoch
                or entry.incarnation != self.active_incarnation
                or entry.epoch < voter.promised_epoch
                or (entry.epoch == voter.promised_epoch
                    and entry.incarnation != voter.promised_incarnation)):
            raise ValueError("stale or inactive epoch/incarnation")

    def append(self, node: str, entry: Entry) -> str:
        voter = self.voters[node]
        self._active(voter, entry)
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

    def prepare_proof(self, entry: Entry, receipts: dict[str, str]) -> CommitProof:
        self._active(self.voters["node-1"], entry)
        if self.voters["node-1"].log.get(entry.index) != entry:
            raise ValueError("leader must force its own entry before commitment")
        durable = {
            node for node, receipt in receipts.items()
            if node in self.voters
            and self.voters[node].log.get(entry.index) == entry
            and receipt == self.receipt(node, entry)
        }
        if len(durable) < QUORUM:
            raise ValueError("entry lacks durable quorum")
        if entry.index > self.commit_index + 1 or entry.index < self.commit_index:
            raise ValueError("commit must extend the committed prefix")
        return CommitProof(entry, tuple(sorted((node, receipts[node]) for node in durable)))

    def _validate_proof_target(self, node: str, proof: CommitProof) -> None:
        entry = proof.entry
        voter = self.voters[node]
        self._active(voter, entry)
        self._quorum(tuple(node for node, _ in proof.receipts))
        if any(receipt != self.receipt(voter_id, entry)
               for voter_id, receipt in proof.receipts):
            raise ValueError("invalid durable receipt digest")
        if voter.log.get(entry.index) != entry:
            raise ValueError("proof voter lacks the exact entry")
        existing = voter.proofs.get(entry.index)
        if existing is not None and existing.entry != entry:
            raise ValueError("conflicting commit proof")

    def persist_proof(self, node: str, proof: CommitProof) -> str:
        """One voter force barrier, independently schedulable from its ACK."""
        self._validate_proof_target(node, proof)
        self.voters[node].proofs[proof.entry.index] = proof
        return proof.digest

    def complete_commit(self, proof: CommitProof, acknowledgements: dict[str, str]) -> None:
        self._active(self.voters["node-1"], proof.entry)
        self._quorum(tuple(acknowledgements))
        if any(digest != proof.digest
               or self.voters[node].proofs.get(proof.entry.index) != proof
               for node, digest in acknowledgements.items()):
            raise ValueError("commit proof lacks durable quorum acknowledgements")
        if not self.commit_index <= proof.entry.index <= self.commit_index + 1:
            raise ValueError("commit must extend the committed prefix")
        self.commit_index = proof.entry.index

    def commit(self, entry: Entry, receipts: dict[str, str], proof_nodes: tuple[str, ...]) -> str:
        self._quorum(proof_nodes)
        proof = self.prepare_proof(entry, receipts)
        for node in proof_nodes:
            self._validate_proof_target(node, proof)
        # This model transition represents a completed proof quorum. Validate
        # every target before changing any state; per-force crashes are later
        # production-harness work, not implicit partial mutations of this helper.
        acknowledgements = {node: self.persist_proof(node, proof) for node in proof_nodes}
        self.complete_commit(proof, acknowledgements)
        return proof.digest

    def apply(self, node: str, through_index: int) -> None:
        voter = self.voters[node]
        if through_index < voter.applied_index:
            raise ValueError("applied index cannot regress")
        if through_index > self.commit_index:
            raise ValueError("cannot apply an uncommitted entry")
        for index in range(voter.applied_index + 1, through_index + 1):
            if index not in voter.log:
                raise ValueError("cannot apply a missing entry")
        if through_index > voter.applied_index and not any(
                through_index <= index <= self.commit_index for index in voter.proofs):
            raise ValueError("cannot apply without a local durable commit proof")
        voter.application_sequence += sum(
            voter.log[index].operation in APPLICATION_OPERATIONS
            for index in range(voter.applied_index + 1, through_index + 1))
        voter.applied_index = through_index
        if node == "node-1":
            self.application_sequence = voter.application_sequence

    def copy_committed_proof(self, source: str, target: str, index: int) -> None:
        """Durably propagate an already established proof to a caught-up voter."""
        sender, receiver = self.voters[source], self.voters[target]
        if index > self.commit_index or index not in sender.proofs:
            raise ValueError("source lacks a committed proof")
        if any(receiver.log.get(i) != sender.log.get(i) or i not in receiver.log
               for i in range(1, index + 1)):
            raise ValueError("proof receiver lacks the exact committed prefix")
        receiver.proofs[index] = sender.proofs[index]

    def install_snapshot(self, node: str, index: int) -> None:
        """Abstract verified snapshot install; does not delete physical log bytes."""
        voter = self.voters[node]
        if index < voter.snapshot_index or index > voter.applied_index:
            raise ValueError("snapshot cannot regress or exceed applied state")
        if index and index not in voter.proofs:
            raise ValueError("snapshot requires a local durable commit proof")
        voter.snapshot_index = index

    def truncate_uncommitted(self, node: str, from_index: int) -> None:
        proven_index = max((index for voter in self.voters.values() for index in voter.proofs), default=0)
        if from_index <= max(self.commit_index, proven_index):
            raise ValueError("committed history is immutable")
        voter = self.voters[node]
        for index in tuple(voter.log):
            if index >= from_index:
                voter.log.pop(index)
                voter.proofs.pop(index, None)

    def recovery_floor(self) -> int:
        # Choose the snapshot-only option of the contract's recovery-source rule.
        # A log/proof quorum alone never authorizes physical prefix removal here.
        return sorted(v.snapshot_index for v in self.voters.values())[-QUORUM]
