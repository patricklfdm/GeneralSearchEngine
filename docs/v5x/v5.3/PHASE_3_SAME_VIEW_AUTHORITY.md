# Phase 3 — same-view export, maintenance and peer-ledger composition

The [network and ACK reader](PHASE_3_SAME_VIEW_NETWORK.md) establishes the
original storage and attempted transport precondition. The new
`scripts.v53.joining_same_view_authority` then qualifies the capabilities used
by that same indivisible `3-REPLACE` execution. No captured PASS label supplies
expected storage, and no second native history supplies missing events.

## Original generation and export lifetimes

The explicit recovery path adds two different generation boundaries: adoption
of FINAL and the later selected installation of the same-view BARRIER. Each
uses its own physically derived snapshot, selector rename and completed return.
The old generation stops being exportable at the rename; the successor cannot
be exported before its completed return. The ordinary ADD reader still rejects
these extra transitions unless the recovery is explicitly supplied.

Frozen BASIS exports bind the original source, promise, view, ballot and source
retirement boundary. Journal and pending/publication capabilities bind their
original force/return windows. The later recovery SELECTED record participates
in the exact per-owner journal timeline. Generation metadata, packets, ancestry
and images must match the actual current owner, including original image bytes
borrowed by packet-only acquisition. A matching digest alone is insufficient.

The control reader checks root, pending INTENT, preparation hints, retained
fragments and completion exports against the original catalog and grants.
Learner data requires the original delivered retention quorum or retained-head
confirmation. Joining-owner exports additionally require a live original owner
scope: a later exporter cannot impersonate an earlier closed endpoint merely
because its permanent identity is unchanged. The total authorized committed
content and session counts must equal the independently checked transport totals.

The composed original has 40 generation windows, 19 frozen-source windows and
361 record-capability windows. All 524 committed contents in 280 successful
sessions are accounted for; the two rejected transfer sessions remain separate.
The eight control exports are explicitly consumed after the general-content
reader, not silently promoted from its unqualified remainder.

## Governing copies and durable peer state

Every original STATUS reply is checked as a hint. Where prefix recovery and
maintenance probe the same owner within one generation, acquisition binds the
most recent original probe before fetching the packet. An undelivered or
inconsistent latest probe cannot fall back to an older convenient response.

Each network FLOOR requires delivered original packet and generation metadata,
matching correlation, complete borrowed images and both governing majorities.
A newer same-view copy must contain the exact local cut, catalog and application
ancestor. The local FLOOR keeps its own cut, while remote copy references retain
their actual generations. Both direct fixture floors remain identified as direct
copies and are not counted as network acquisition.

Force and release sequences are derived from all copied members, including images
and ancestry, with exact multiplicities and owner scopes. Generation and source
retirement stay inside that forced FLOOR's lifetime. All original FLOOR events
must be consumed, including the final release. This original contains 36 network
floors, two direct floors, 78 complete copies and 2,940 floor events.

The peer reader derives every revision from bootstrap through maintenance,
selection, publication, original grants and cold reopen. Stable FINAL may remove
the replaced identity only after its retained endpoints are covered. A future
covering copy does not become a local same-cut observation. Every actual peer
write and completion must correspond to the exact derived revision and original
force window. The original has 84 writes (50 maintenance, 12 selected merges and
22 publications), 93 ledger comparisons and eight open reseals. The inactive
old voter remains at revision zero.

The older ADD fixture retains its original exact-count checks. This explicit
same-view reader consumes all observed actions and derives the expected writes
and member forces instead of transplanting that fixture's numeric totals.

## Qualification and retained evidence

```bash
python3 -B -m scripts.v53.joining_same_view_authority /original/raw \
  --qualify --workers 4
```

The untouched original must pass every prerequisite first. Independent disposable
evidence copies may run in up to four worker processes; this does not split or
retry a native history. Only observation files may change, and all other hashes
and directory entries must stay identical before the original physical derivation
can be reused. Every negative requires its preceding layers to pass and then the
exact designated rejection. A wrong error is retained as a failed qualification.

The matrix includes general export, control, floor and peer-write negatives plus
specific adoption-return, latest-probe, future-copy, recovery-write and closed-owner
cases. The pending-ACK export negative runs only if that session exists in the
original. Its absence is reported explicitly; no fabricated exchange counts as
qualification. The [batch receipt](phase3-evidence/same-view-authority.json) binds
actual outcomes, original input, reader source, tests and portable replay.

The frozen reader passes 483 joining-related Python tests. The complete older
ADD replay still equals its previously retained result, including its exact count
guards; the four shared reader files are byte-identical between that legacy
check and this batch’s final frozen reader. The first frozen 65-case matrix is
retained as failed: `completion-closed-owner` was rejected by the earlier export
layer, while its declared target was still controls. Its target now explicitly
belongs to exports, with the original control mutation preserved and two focused
regressions. An earlier rejection is not silently counted as a passing negative.

The corrected frozen qualification completed in 437.445 seconds: 15 export,
13 control, 15 maintenance and 22 peer negatives all reached their exact expected
rejection after passing the preceding layers. Five joining export sessions are
bound to their original owner lifetimes. This original has no pending-ACK export
session, so that conditional negative is explicitly absent.

The 30,720,459-byte archive retains 13,099 files and 1,489 directories, including
empty directories and the failed first reader. Every member hash and directory
entry was checked after extraction. Relocated replay with `python -O -B` completed
in 37.422 seconds and produced exactly the original qualified result; both the
reader source and raw input remained unchanged.

## Remaining closure

The result remains **PARTIAL**. This batch qualifies observed export authority,
maintenance forces and the peer-ledger chain. It does not yet compose every
learner/future ledger write, all process-death cuts, the complete current-source
profile cohort including REMOVE, or the frozen acceptance mapping.
`sameViewPhysicalQualified`, `completePhysicalQualified`, `forceAndNetworkQualified`,
`processDeathQualified` and `phase3Complete` remain false.

No production Java, wire format, workflow, POM, resource or timing changes, and no
native workload rerun, push, workflow dispatch or paid cloud operation.
