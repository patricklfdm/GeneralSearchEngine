# Phase 3 direct local export ownership

This follows [session export ownership](PHASE_3_SESSION_EXPORT_OWNERSHIP.md).
The [development index](phase3-evidence/direct-export-ownership.json) records a
new native execution whose 45 export allocations all have observed owners.
Phase 3 remains OPEN; this is the existing three-node stable/two-slot profile.

## Actual local owners

The six previously unattached allocations have three different owners:

| Operation | Borrow | Release boundary |
| --- | --- | --- |
| Proposer activation round | Its original local BASIS source | The round's original export-close call, after selected installation |
| Receiver SELECTED assembly | Its original local BASIS source | The assembly's original export-close call, after local installation |
| Generation maintenance | Its current generation prefix | The lexical copy/maintenance scope, through forced floor release |

The new history has one activation borrow, one SELECTED borrow and four
maintenance borrows. The receiver is not mislabeled as a second proposer round.

With export observation enabled, the existing resource recorder captures
`*_BORROW_ACQUIRED`, `*_BORROW_CLOSE_BEGIN` and `*_BORROW_RETURNED`, using the
exact original handle. The phase is supplied at the actual owning call site.
These annotations do not establish voting or installation authority.

The optional wrapper forwards every original close call, including repeated
ones. Only the first observed invocation receives a cleanup interval. An original
exception leaves no successful return marker; a later retry cannot erase that
failed observation. Try-with-resources preserves the original primary exception
and suppressed cleanup exception. Export callbacks run outside the resource
monitor. Early owner revocation is observable without inventing a new handle.

When observation is disabled, the factory returns the original exporter itself
without inspecting or wrapping it. Existing close order, deadlines, limits and
wire/disk formats are unchanged. No workflow or paid execution is added.

## Independent original binding

The stable physical reader first re-derives the admitted installation and both
complete slots. The direct-export reader then derives each expected reservation:

- Source identity and extent come from that node's original forced PROMISE and
  BASIS in the selected ballot. The proposer determines activation versus
  receiver SELECTED ownership. The reservation follows the original grant
  return and spans the original installation return.
- Prefix identity comes from the original current generation manifest before
  each maintenance pass. Its CONTROL extent remains 4096 bytes. Acquisition
  precedes floor reservation, and ownership spans the original forced floor
  release return.

Every expected local owner must be observed exactly once, with the original
digest, bytes and resource/event interval. A handle cannot simultaneously belong
to a network session and a local operation. Session and direct ownership together
must account for every export allocation in the admitted original.

This binds the six direct CONTROL reservations; it does not prove independent
heap peaks, every image pin or every other resource class. Normal direct cleanup
does not imply that an enclosing operation returned successfully or that every
listener drained. Those remain separate obligations.

## Retained validation

- 37 Java tests pass: eight new observer regressions, the existing session/close/
  capture tests, one actual TCP native history and four existing activation/
  SELECTED cancellation, failed-cleanup and image-borrow regressions.
- 133 related Python tests pass, including thirteen new direct-owner tests.
- The new native history has 39 session-owned and six directly owned export
  reservations. All 45 are bound, with no unattached export inventory.
- Twelve direct-owner mutations and twelve session-ownership mutations reject
  after original validation. Digests, extents, phase identity, call markers and
  original operation intervals are separate obligations.
- The previous native capture remains PARTIAL with six missing direct-owner
  observations. Strict replay still rejects it. New readers do not upgrade old
  evidence merely because final counters are zero.

The native execution takes about one minute locally. No full reactor, long
hosted cohort or cloud experiment was rerun for this batch. Exact source/report
hashes, JUnit reports and the raw inventory are retained in the development index.

```bash
python3 -m scripts.v53.native_resource_evidence RAW --control-closes --export-ownership --direct-exports
python3 -m scripts.v53.direct_export_negatives RAW
python3 -m scripts.v53.session_export_negatives RAW
```

The new `--direct-exports` option requires the explicit export/close options and
the stable profile. It cannot silently substitute that profile for joining or
required-four evidence. Complete nested/joining histories, constructor and
abnormal-close composition, physical custody/peaks and final-source cohort
admission/execution remain pending. The frozen 544 planned Phase 3 hosted
histories and later Phase 5's 3310 S cases are unchanged.
