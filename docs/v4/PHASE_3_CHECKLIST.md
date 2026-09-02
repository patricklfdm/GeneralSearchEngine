# V4.0 Phase 3 checklist

**Status:** accepted through protected PR #80 at `2664638`; exact-master CI run
`33589193180` passed

## Entry and scope

- [x] Phase 2 protected PR #79 merged at
  `7056a5ad00d1f38757f984c51ad21d83ee922443`.
- [x] Exact-master Phase 2 CI run `33583721019` completed successfully.
- [x] Phase 3 changes no Phase 2 storage bytes or public API.
- [x] Checkpoints, manifests, rollover, cleanup and format migration remain absent.

## Startup and replay

- [x] Fresh and initialized directories are distinguished without empty fallback.
- [x] Lifetime ownership, exact members, metadata/history/config/index identities and
  retained capacity are validated before replay.
- [x] Generation header and every complete frame are validated with checked bounds,
  contiguous sequence and CRC32C.
- [x] Only a physically incomplete newest tail is truncated and forced; complete
  invalid data fails closed.
- [x] Two-pass replay retains at most one bounded frame rather than the whole history.
- [x] Canonical codec round trip and document/key identity precede logical application.
- [x] Single, bulk, no-op and supported dynamic-index units replay deterministically.
- [x] Canonical slots, IDs, `nextDocId`, indexes and durable sequence are restored.
- [x] Derived indexes rebuild before one process-local version-zero snapshot is exposed.
- [x] Continued writes and repeated reopen preserve contiguous sequence and state.

## Failure and equivalence

- [x] Metadata/configuration, WAL corruption, codec, replay and index-rebuild failures
  retain distinct stable categories.
- [x] Invalid short tail, checksum, sequence gap, malformed complete payload, duplicate
  logical add, history mismatch and unknown members fail closed.
- [x] Uninterrupted versus recovered comparison covers mixed history, sparse slots,
  dynamic equality/prefix/text/range indexes, structured and ranked truth, exact score
  bits/order, Explain, first page and exact totals.
- [x] A cursor captured before restart is rejected after reopen.

## Crash and evidence

- [x] All ten Phase 2 writer barriers remain passing.
- [x] Tail-truncated, replay-complete and ready-publication production recovery barriers
  are stable and reached through separate JVMs.
- [x] Internal hard halt covers all recovery barriers and external kill covers replay.
- [x] Recovery-after-recovery performs a new write and a second reopen.
- [x] Independent Python fixtures cover incomplete structural regions, valid-CRC
  invalid payload and valid-CRC sequence gap.
- [x] Fake-cloud `phase3-recovery` failure-drill evidence validates without GCP.
- [x] CI runs the bounded production Phase 3 verifier and independent fixtures.

## Acceptance

- [x] Focused recovery, corruption and differential tests pass locally.
- [x] Full local crash and fake-cloud matrix passes.
- [x] Full reactor passes (409 core and 5 processor tests, zero failures).
- [x] Published 1.0.0 through 3.4.0 compatibility and three consumers pass.
- [x] Strict Javadocs, six release JARs, JMH smoke and two-build reproducibility pass.
- [x] Required PR #80 and protected merge pass.
- [x] Exact-master Phase 3 CI run `33589193180` passed at
  `266463851aff5b742f26338bc3b3c1867f247ea1`.

Phase 4 may add checkpoint authority only after the open acceptance items close. It
must preserve WAL-only bootstrap and all accepted recovery fixtures.
