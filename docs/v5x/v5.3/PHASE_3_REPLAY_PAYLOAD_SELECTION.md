# Select replica members before loading payloads

The [segmented replica envelope](PHASE_3_REPLICA_CAPTURE_ENVELOPE.md) and deferred
readers did not by themselves prevent every eager read. Iterating `Mapping.items()`
loads each value before a loop can filter its name. Three paths now select the
relevant metadata before loading payload bytes:

- `round_storage_evidence.current` selects the current generation's member names
  before reading them. The selected manifest, selector, packet, images, hashes and
  exact membership comparisons are unchanged. Its returned members remain a
  dictionary, preserving the ordinary replay callers' interface.
- `CheckpointReceipts` selects local applied-end ACK paths before reading their
  bytes. Other images and generation files cannot contribute an ACK.
- That receipt reader checks an already authenticated transfer's kind before
  requesting its assembled content. APPLICATION transfers are not assembled a
  second time merely to discover they are not CHECKPOINT_ACK records.

This changes observation work, not runtime Java, proof/publication semantics,
source policy, capacity budgets, workflow topology or required qualification.

## Integrity boundaries

The physical reader still inventories and hashes every member before returning a
deferred snapshot. It checks identities and digests on reads, and original-file
checks still cover the complete input at replay boundaries. The current-generation
routine has never been a standalone admission check for all unrelated replica
files. Its optimization does not replace the independent whole-history reader.

Checkpoint replay still runs the complete causal transfer verifier first.
`joining_transcript.transfers` authenticates offsets, chunks, lengths, digests and
commits for APPLICATION as well as RECORD transfers. Other independent export
and semantic checks still read required application content. The producer does
not get to classify unverified bytes as irrelevant to avoid validation.

## Evidence

The [development receipt](phase3-evidence/replay-payload-selection-development.json)
records these scopes separately:

- Three guarded-mapping regressions fail on the unchanged previous implementation
  and pass with the correction. They detect accesses to unrelated generation
  payloads, unrelated local images and non-record transfer contents.
- A synthetic snapshot contains a small parser-valid current generation and
  twelve unrelated sparse 64 MiB files. All 805,313,387 input bytes are inventoried
  and hashed. Under the same 64 MiB Python address-space limit, the old current
  routine raises `MemoryError`; the corrected routine derives the selected
  generation and rechecks the unchanged whole input. Both processes report the
  same 24,708 KiB peak RSS: the failing allocation was refused before becoming
  resident. This is not a measured reduction in a complete native reader's RSS.
- Changed selected image bytes still fail generation validation. A later change
  to an unread member still fails the complete original check.
- The retained short native verified-backup/BARRIER original has unchanged
  physical views, generation windows, 292 wire exchanges, 90 contents, six
  checkpoint bindings, resource accounting and close results. Its original
  inventory remains unchanged.
- All 4,369 V5.3 Python tests pass, including the original-first transcript,
  physical evidence and negative-driver checks. No Java runtime was changed;
  this batch does not rerun the reactor or a native maximum history.

The sparse files are not decoded maximum application images, and the short
native history is not a complete required-four or maximum-image cohort. Full
reader memory, maximum native composition, complete default-staging replay and
final-source execution remain open. The operator will arrange a qualifying
native Linux acceptance environment after development; the existing environment
checks remain enabled. All five Phase 3 closure gaps remain open.

Rollback restores the earlier value-first iteration. It does not change original
formats or require rewriting retained evidence, but would restore the unnecessary
payload allocations demonstrated by the regressions.
