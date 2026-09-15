"""Replay logical fixture messages against the independent safety model.

This adapter has no sockets, Java imports or production storage. APPEND/proof
delivery represents a force; ACK delivery is a separate event and may be lost.
"""

from dataclasses import asdict

from scripts.v50.deterministic_transport import Delivery, DeterministicTransport
from scripts.v50.replicated_history_model import CommitProof, Entry, ReplicatedHistory


class ModelNetwork:
    def __init__(self, trace: DeterministicTransport):
        self.trace = trace
        self.history = ReplicatedHistory()
        self.entry_acks: dict[int, dict[str, str]] = {}
        self.proof_acks: dict[int, dict[str, str]] = {}
        self.proofs: dict[int, CommitProof] = {}

    def receive(self, event: Delivery):
        payload = self.trace.payload(event)
        model = self.history
        if event.source not in model.voters or event.target not in model.voters:
            raise ValueError("unknown voter")
        if event.message_type == "ACTIVATE":
            if event.source != "node-1" or event.target != "node-1":
                raise ValueError("activation must run at the configured leader")
            model.promise(payload["epoch"], tuple(payload["voters"]),
                          incarnation=payload.get("incarnation", "leader-1"))
            return model.active_epoch
        entry = Entry(**payload["entry"])
        if event.message_type in {"APPEND", "PREPARE_PROOF", "COMMIT_PROOF", "APPLY"}:
            if event.source != "node-1":
                raise ValueError("only the configured leader may send this message")
        if event.message_type in {"DURABLE_ACK", "COMMIT_PROOF_ACK", "COMMIT", "PREPARE_PROOF"}:
            if event.target != "node-1":
                raise ValueError("acknowledgements/commit belong to the configured leader")
        index = entry.index
        if event.message_type == "APPEND":
            return model.append(event.target, entry)
        if event.message_type == "DURABLE_ACK":
            if model.voters[event.source].log.get(index) != entry:
                raise ValueError("ACK precedes durable entry")
            model._active(model.voters[event.source], entry)
            self.entry_acks.setdefault(index, {})[event.source] = model.receipt(event.source, entry)
            return entry.digest
        if event.message_type == "PREPARE_PROOF":
            self.proofs[index] = model.prepare_proof(entry, self.entry_acks.get(index, {}))
            return self.proofs[index].digest
        proof = self.proofs.get(index)
        if proof is None or proof.entry != entry:
            raise ValueError("no prepared proof for the exact entry")
        if event.message_type == "COMMIT_PROOF":
            return model.persist_proof(event.target, proof)
        if event.message_type == "COMMIT_PROOF_ACK":
            if model.voters[event.source].proofs.get(index) != proof:
                raise ValueError("ACK precedes durable proof")
            self.proof_acks.setdefault(index, {})[event.source] = proof.digest
            return proof.digest
        if event.message_type == "COMMIT":
            if event.source != "node-1":
                raise ValueError("only configured leader completes commitment")
            model.complete_commit(proof, self.proof_acks.get(index, {}))
            return model.commit_index
        if event.message_type == "APPLY":
            model.apply(event.target, index)
            return model.voters[event.target].application_sequence
        raise ValueError("unsupported model message")

    def run(self) -> dict:
        transcript = self.trace.replay(self.receive)
        return {"transcript": transcript, "commitIndex": self.history.commit_index,
                "voters": {node: asdict(voter) for node, voter in self.history.voters.items()}}
