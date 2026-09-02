# V4.0 Phase 4 local checkpoint baseline

## Source boundary

Phase 4 is developed on `feat/v4.0-phase4-checkpoints` from protected-master merge
commit `266463851aff5b742f26338bc3b3c1867f247ea1`, the merge of Phase 3 PR #80.
Exact-master Phase 3 CI run `33589193180` completed successfully. No paid cloud
resource is required for Phase 4 acceptance.

## Implemented behavior

The durable engine now supports explicit asynchronous and WAL-threshold-triggered
checkpoints. The writer performs a short forced generation cut and immutable capture;
a separate single-thread executor writes and validates checkpoint bytes and publishes
the one authoritative manifest. Concurrent explicit requests coalesce while one
checkpoint is active. Ordinary mutation success never waits for automatic checkpoint
completion, while close drains already accepted checkpoint work and does not create a
new checkpoint.

Recovery supports WAL-only multi-generation history, checkpoint-only history and
checkpoint-plus-WAL history. Canonical sparse slots, `nextDocId`, business keys,
documents and built-in dynamic-index descriptors survive the checkpoint boundary;
derived indexes rebuild before publication. Cleanup begins only after manifest rename
and directory force. Authoritative checkpoint corruption fails closed without older
fallback, while staging and unreferenced data remain non-authoritative.

## Local evidence

- clean core reactor: 414 tests, zero failures, plus 5 processor tests;
- Phase 2 WAL, Phase 3 recovery/differential and Phase 4 checkpoint focused matrix:
  PASS;
- explicit, automatic, coalesced, sparse-slot, dynamic-index, post-cut replay and
  authoritative-corruption coverage: PASS;
- independent Phase 4 Python format fixtures: 3 tests, PASS;
- all eleven checkpoint generation/data/manifest/cleanup barriers under internal
  hard halt: PASS;
- external kill at partial manifest and post-directory-force: PASS; and
- fake-cloud `phase4-checkpoint` failure-drill evidence and artifact validation: PASS.

Published API/artifact compatibility, all three independent consumers, release
artifacts, strict Javadocs, reproducibility and the bounded JMH smoke also pass locally.
Protected PR and exact-master CI remain acceptance gates.
