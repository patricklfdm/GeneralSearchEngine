# Phase 3 runtime wire extension: selected quorum transfer

**Status:** implemented in the current development batch; protected review pending.
**Base:** the accepted [Phase 1 catalog](PHASE_1_FORMAT_CATALOG.md).
**Decision:** add automatic wire kind 24, `SELECTED_OFFER`, through a separate
[extension catalog](../../../general-search-engine-replication/src/test/resources/replication/v51/runtime-wire-extension.json).

## Concrete gap and decision

The receiving voter must independently reproduce the selection from both frozen
bases before adopting a prefix. The original `SNAPSHOT_INSTALL` carries only an
image digest and selected digest. `PROMISE` carries a descriptor but is constrained
to responder-to-proposer traffic. `BASIS_CHUNK` transfers an identified image, not
an unspecified descriptor or a second basis hidden inside application bytes.
Consequently those messages alone cannot communicate the proposer's frozen basis
descriptor and the exact selected pair to the receiving voter.

The explicit extension carries exactly `selected: frame:SELECTED`,
`bases: [frame:BASIS, frame:BASIS]` and `response: boolean` in the existing 1.2
envelope. Kind 24 was unassigned in the original wire catalog. Record kind 24
continues to mean storage ACCEPT; storage and wire namespaces are distinct.
The original 25 storage records, 19 wire projections and their checksum list remain
byte-for-byte fixed. The [extension fixtures](../../../general-search-engine-replication/src/test/resources/replication/v51/runtime-wire-fixtures.json)
and [checksums](../../../general-search-engine-replication/src/test/resources/replication/v51/runtime-wire-fixtures.sha256)
freeze request and response bytes separately.

## Mapping and force boundary

1. PREPARE/PROMISE establish the durable frozen descriptors. The proposer pulls the
   selected peer's IMAGE with bounded BASIS_CHUNK requests.
2. SELECTED_OFFER requests carry the ordered selected record and both descriptors.
   The recipient checks its descriptor against its actual current frozen basis,
   then pulls the proposer's frozen IMAGE by its basis ID. Reverse requests run
   outside the protocol dispatcher and have a separately admitted transport lane.
3. Both complete images must match descriptor lengths, hashes, inventories, ballot
   and accepted next value. The receiving voter recomputes selection and requires
   the exact selected bytes; duplicate voters, reordered/substituted descriptors,
   mixed ballots and stale identities reject.
4. Only then does the recipient persist selection and install a longer proven
   prefix. A successful `response=true` echoes the exact selected record and
   descriptors after that durable boundary. It grants no acceptance vote by itself.
5. ACCEPT/ACCEPT_ACK and COMMIT_PROOF/COMMIT_PROOF_ACK complete activation or mutation.
   A separate fresh NO_OP still follows any carried value from an earlier campaign.

Every exchange binds both endpoints, manifest, ballot, trace UUID and sequence.
Chunks bind basis identity, offset, requested range, actual count and digest. The
actual canonical encoded frame, including base64 expansion, must fit maxFrameBytes.
The offer contains descriptors rather than complete images; the stricter frame
or record limit can reject a large selected-next descriptor before transmission.

The codec understands all original families, but the current driver executes only
handshake, prepare/basis, selection, accept/proof and heartbeat exchanges. Other
families reject at the handler until their transition is implemented. Retained
peer source/floor exchange is a subsequent runtime obligation.

## Compatibility and verification

This is an explicit pre-release 1.2 extension for homogeneous qualified V5.1
artifacts. An older automatic implementation rejects kind 24; protocol-number
equality does not authorize mixing artifacts. Configured 1.1 remains a separate
codec/transport path. There is no mixed-version rollout or automatic migration.

Java reads and re-encodes all original messages and both new independent vectors.
Python independently verifies the schemas and rejects rechecksummed swapped bases,
duplicate voters, changed ballots and reversed request direction. The real runtime
evidence also reconstructs transferred images and repeats the selection decision.
The extension becomes accepted only after the protected PR and exact-master CI.
