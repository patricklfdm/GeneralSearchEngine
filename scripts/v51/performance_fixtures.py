"""Synthetic rich automatic frames for testing the separate projection decoder.

These bytes are never labelled as runtime, force, measurement or cloud evidence.
"""
import base64
from . import format_encoder as enc, format_inspector as fmt, fixtures, performance_model as model


def b64(value):
    return base64.b64encode(value).decode('ascii')


def generate(plan):
    source, _, _ = fixtures.generate()
    genesis = fmt.inspect(source['GENESIS'], 'GENESIS')
    state = model.initial(plan)
    genesis.update(application=b64(state.application()), baseSequence=4, source='VERIFIED_V44_BACKUP',
                   sourceDigest=model.sha(b'synthetic-source-not-a-backup'))
    genesis_bytes = enc.encode('GENESIS', genesis)
    manifest = fmt.inspect(source['MANIFEST'], 'MANIFEST')
    manifest.update(baseSequence=4, codecId='semantic-codec', codecVersion=1,
                    genesisDigest=genesis_bytes[16:48].hex())
    manifest_bytes = enc.encode('MANIFEST', manifest)
    digest = manifest_bytes[16:48].hex()
    ballot = dict(epoch=2, proposer='node-1', incarnation=fixtures.UUID)
    votes = {f'node-{i}': [] for i in (1, 2, 3)}
    anchors, snapshots, entries, proofs = [], [], [], []
    previous_digest, previous_epoch = digest, 1
    calls = [dict(operation='NO_OP', payload=b'')] + list(model.program(plan))
    for call in calls:
        operation = model.OP_IDS.get(call['operation'], 9)  # each GET/QUERY adds a distinct NO_OP
        payload = call['payload']
        index = len(entries) + 1
        entry = dict(index=index, manifestDigest=digest, operation=operation, originEpoch=2,
                     originIncarnation=fixtures.UUID, payload=b64(payload), payloadDigest=model.sha(payload),
                     previousDigest=previous_digest, previousEpoch=previous_epoch, previousIndex=index - 1)
        entry_bytes = enc.encode('ENTRY', entry)
        entry_digest = entry_bytes[16:48].hex()
        acceptance = enc.encode('ACCEPT', dict(ballot, manifestDigest=digest, entryDigest=entry_digest, entry=b64(entry_bytes)))
        for rows in votes.values():
            rows.append(acceptance)
        proof = enc.encode('PROOF', dict(ballot, manifestDigest=digest, index=index, entryDigest=entry_digest,
                     previousDigest=previous_digest, receipts=[dict(voter=node,
                         digest=fixtures.fixture_receipt('ACCEPT_ACK', digest, node, 2, 'node-1', fixtures.UUID, index, entry_digest))
                         for node in ('node-1', 'node-2')]))
        state.apply(operation, payload)
        anchors.append({k: entry[k] for k in ('operation', 'originEpoch', 'originIncarnation', 'payloadDigest')} | {'entryDigest': entry_digest})
        snapshot = enc.encode('SNAPSHOT', dict(anchors=list(anchors), application=b64(state.application()),
                    applicationSequence=state.sequence, baseSequence=4, manifestDigest=digest, terminalProof=b64(proof)))
        snapshots.append(snapshot)
        entries.append(entry_bytes)
        proofs.append(proof)
        previous_digest, previous_epoch = entry_digest, 2
    return dict(manifest=manifest_bytes, genesis=genesis_bytes, votes=votes, entries=entries, proofs=proofs, snapshots=snapshots)


def encoding_report(plan, fixture):
    peaks = {kind: max(map(len, records)) for kind, records in
             [('ENTRY', fixture['entries']), ('ACCEPT', fixture['votes']['node-1']), ('PROOF', fixture['proofs'])]}
    fmt.need(max(peaks.values()) <= plan['encodingLimits']['entryAcceptProofBytes'], 'generated rich frame ceiling')
    return dict(execution='synthetic-rich-encoding-only', logicalSlots=len(fixture['entries']), recordPeaks=peaks,
                genesisBytes=len(fixture['genesis']), snapshotBytes=max(map(len, fixture['snapshots'])),
                base64SnapshotBytes=max(len(b64(v)) for v in fixture['snapshots']),
                runtimeRetentionAdmitted=False)
