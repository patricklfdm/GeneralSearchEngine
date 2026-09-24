"""Rich application projection from automatic 1.2 votes and snapshot bytes.

The caller must establish each vote's owner and force boundary from physical
observations. This helper checks values/quorums/prefix/application only; it cannot
qualify a running system, publication order, client outcomes or fresh read cuts.
"""
import base64
from . import format_inspector as fmt, performance_model as model


def raw(value):
    return base64.b64decode(value, validate=True)


def project(manifest_bytes, genesis_bytes, votes, *, maximum_slots=192):
    fmt.need(1 <= maximum_slots <= 192, 'rich voters/slot bound')
    return _project(manifest_bytes, genesis_bytes, votes, maximum_slots)


def project_cloud(manifest_bytes, genesis_bytes, votes):
    from . import cloud_workload_contract
    cloud_workload_contract.load()  # Reject changed or unsealed cloud limits.
    return _project(manifest_bytes, genesis_bytes, votes, 512)


def _project(manifest_bytes, genesis_bytes, votes, maximum_slots):
    manifest = dict(fmt.inspect(manifest_bytes, 'MANIFEST'), digest=manifest_bytes[16:48].hex())
    genesis = fmt.contextual_frame(genesis_bytes, 'GENESIS', manifest)
    nodes = {m['node'] for m in manifest['members']}
    fmt.need(manifest['genesisDigest'] == genesis_bytes[16:48].hex() and
             all(manifest[k] == genesis[k] for k in ('groupId', 'historyId', 'baseSequence', 'schemaDigest', 'indexesDigest')),
             'rich genesis/manifest binding')
    fmt.need(manifest['codecId'] == 'semantic-codec' and manifest['codecVersion'] == 1, 'rich codec identity')
    fmt.need(set(votes) == nodes, 'rich voters/slot bound')
    state = model.application(raw(genesis['application']), genesis['baseSequence'])
    expected_initial = model.State({i: model.document(i, 0) for i in range(1, 65)})
    fmt.need(genesis['source'] == 'VERIFIED_V44_BACKUP' and genesis['sourceDigest'] is not None and
             state.sequence == 4 and state.application() == expected_initial.application(), 'rich frozen source corpus')
    entries, accepted, chosen = {}, {}, {}
    observations = 0
    for node, records in votes.items():
        for record in records:
            # Repeated physical observations and re-proposals consume bytes but do
            # not create another voter or another logical slot.
            observations += 1
            vote = fmt.contextual_frame(record, 'ACCEPT', manifest)
            entry_bytes = raw(vote['entry'])
            entry = fmt.contextual_frame(entry_bytes, 'ENTRY', manifest)
            fmt.need(entry['index'] <= maximum_slots, 'rich logical slot bound')
            digest = entry_bytes[16:48].hex()
            entries[digest] = entry
            identity = (vote['epoch'], vote['proposer'], vote['incarnation'], entry['index'], digest)
            voters = accepted.setdefault(identity, set())
            voters.add(node)
            if len(voters) >= 2:
                fmt.need(entry['index'] not in chosen or chosen[entry['index']] == digest, 'conflicting rich chosen value')
                chosen[entry['index']] = digest
    fmt.need(chosen and sorted(chosen) == list(range(1, max(chosen) + 1)), 'incomplete rich chosen prefix')
    states, anchors = {0: state.copy()}, []
    previous_digest, previous_epoch = manifest['digest'], 1
    for index, digest in sorted(chosen.items()):
        entry = entries[digest]
        fmt.need((entry['previousIndex'], entry['previousDigest'], entry['previousEpoch']) ==
                 (index - 1, previous_digest, previous_epoch), 'rich entry predecessor')
        state.apply(entry['operation'], raw(entry['payload']))
        states[index] = state.copy()
        anchors.append({k: entry[k] for k in ('operation', 'originEpoch', 'originIncarnation', 'payloadDigest')} | {'entryDigest': digest})
        previous_digest, previous_epoch = digest, entry['originEpoch']
    return dict(manifest=manifest, genesis=genesis, states=states, anchors=anchors,
                accepted=accepted, chosen=chosen, entries=entries, observations=observations)


def snapshot(projection, encoded):
    value = fmt.contextual_frame(encoded, 'SNAPSHOT', projection['manifest'])
    index = len(value['anchors'])
    fmt.need(index in projection['states'] and value['anchors'] == projection['anchors'][:index], 'rich snapshot ancestry')
    fmt.need(value['baseSequence'] == projection['genesis']['baseSequence'], 'rich snapshot base sequence')
    wanted = projection['states'][index]
    actual = model.application(raw(value['application']), value['applicationSequence'])
    fmt.need(actual.sequence == wanted.sequence and actual.application() == wanted.application(), 'rich snapshot projection')
    if index:
        proof = fmt.contextual_frame(raw(value['terminalProof']), 'PROOF', projection['manifest'])
        identity = (proof['epoch'], proof['proposer'], proof['incarnation'], proof['index'], proof['entryDigest'])
        observed = projection['accepted'].get(identity, set())
        fmt.need({r['voter'] for r in proof['receipts']} <= observed, 'rich proof lacks exact observed votes')
        previous = projection['manifest']['digest'] if index == 1 else projection['chosen'][index - 1]
        fmt.need(proof['previousDigest'] == previous, 'rich proof predecessor')
    return actual
