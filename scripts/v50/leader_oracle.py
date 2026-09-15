"""Compare independently parsed production history with the Phase 1 safety model."""

from scripts.v50.replicated_history_model import Entry, ReplicatedHistory, VOTERS


def validate(reports, applied, successful):
    if set(reports) != set(VOTERS) or set(applied) != set(VOTERS):
        raise ValueError("oracle needs all three distinct voters")
    model = ReplicatedHistory()
    leader = reports["node-1"]
    previous = "GENESIS"
    for record in leader["entries"]:
        index, epoch = record["index"], record["epoch"]
        holders = tuple(node for node in VOTERS if reports[node]["lastLogIndex"] >= index)
        for node in holders:
            if reports[node]["entries"][index - 1] != record:
                raise ValueError("production entry histories disagree")
        if epoch != model.active_epoch:
            model.promise(epoch, holders, incarnation=record["incarnationId"])
        entry = Entry(index, epoch, record["operation"], record["payloadDigest"], previous, record["incarnationId"])
        for node in holders:
            model.append(node, entry)
        previous = entry.digest
        proofs = {node: next((proof for proof in reports[node]["proofs"] if proof["index"] == index), None) for node in VOTERS}
        proofs = {node: proof for node, proof in proofs.items() if proof is not None}
        if proofs:
            canonical = next(iter(proofs.values()))
            if any(proof != canonical for proof in proofs.values()):
                raise ValueError("production commit proofs disagree")
            proof = model.prepare_proof(entry, {node: model.receipt(node, entry) for node in canonical["receiptVoters"]})
            acknowledgements = {node: model.persist_proof(node, proof) for node in proofs}
            if len(acknowledgements) >= 2:
                model.complete_commit(proof, acknowledgements)
        if index in successful and model.commit_index < index:
            raise ValueError("successful application response has no durable proof quorum")
    for node in VOTERS:
        model.apply(node, applied[node]["appliedIndex"])
        if model.voters[node].application_sequence != applied[node]["applicationSequence"]:
            raise ValueError("application sequence differs from independent model")
    if any(index > applied["node-1"]["appliedIndex"] for index in successful):
        raise ValueError("successful response precedes leader publication")
    return {"status": "PASS", "modelCommitIndex": model.commit_index,
            "leaderAppliedIndex": model.voters["node-1"].applied_index,
            "leaderApplicationSequence": model.application_sequence}
