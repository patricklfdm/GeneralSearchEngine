# V4.0 Phase 5 local hardening baseline

## Source boundary

Phase 5 starts from protected-master merge
`32e9c84c944ebd4f5c0b9f2d69efd690d25058cc`, the merge of Phase 4 PR #81.
Exact-master Phase 4 CI run `33594843119` completed successfully. The working branch is
`feat/v4.0-phase5-lifecycle-hardening`.

## Implemented evidence

- seven focused Java lifecycle, concurrency, fault-injection, short-write and bounded
  retention cases pass;
- 400 concurrent producer operations retain one contiguous sequence while readers
  observe immutable snapshots;
- close rejects new admission and waits for accepted post-cut WAL work plus coalesced
  checkpoint completion;
- safe pre-authority failures, terminal post-manifest ambiguity and diagnostic cleanup
  failure all follow the frozen completion contract;
- 24 checkpoints under three-byte writes retain one WAL and one authoritative
  checkpoint within the configured 256 KiB limit;
- four independent checkpoint fixtures pass, including conservatively retained
  pre-manifest WAL history;
- eight same-history JVM hard halts each pass independent inspection, recovery and a
  second reopen; and
- the no-GCP `phase5-hardening` failure drill and evidence validation pass.

The repeated-crash diagnostic observed a bounded maximum of 1,274 engine-owned bytes
for its eight-operation fixture. This is a functional hardening result, not a Phase 6
performance baseline.

## Remaining gates

Clean reactor (421 core and 5 processor tests), published compatibility, all three
independent consumers, strict Javadocs, six release JARs, reproducibility and the
complete JMH smoke pass. Protected PR #82 merged as
`c9a8b4725f3c44bced40764d1a9b3e9a4eb37b51`; exact-master CI run `33597658600`
completed successfully on 2026-09-01T23:09:44-07:00.
