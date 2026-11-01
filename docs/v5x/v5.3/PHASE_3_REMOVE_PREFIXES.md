# Phase 3 — original REMOVE retirement file prefixes

This extends [observed REMOVE retirement callbacks](PHASE_3_REMOVE_RETIREMENT.md)
with actual writer-held inventories. Earlier histories retain their callback-only
scope. Missing original captures are never synthesized or added to those histories.

## Collection and independent comparison

The optional `--retirement-captures` producer mode records every generation/source
retirement callback, including source journal rotation, on both complete REMOVE
profiles. Each original callback keeps its index in the unchanged shared trace.
The collector writes a separate sibling directory, deduplicating original bytes
by SHA-256 and recording complete ordered inventories, including empty files and
directories. Completion binds the collection to the exact original event bytes,
result bytes and profile. The sidecar never supplies a runtime authority or changes
owned files; each capture occurs while the original journal writer is held.

The observation limits are 2,048 captures, 512 members per inventory, 64 MiB per
file and 256 MiB for all stored objects and metadata together. They are test
evidence limits, not changes to the production seven-image/six-source resource
limits or the existing 600-second native history lifetime. Interrupted collection
cannot publish a complete collection manifest.

`remove_retirement_prefixes` first validates the whole original physical, attempted
network, export/floor, continuous-retention and retirement-callback history. It
then reuses the independently derived transactions to compare **every** observed
inventory. Expected proposal, authority, partial borrowed-image binding, compacted
journal and deleted members come from the preceding original state and governing
floor; captured bytes never define their own expectations. Force boundaries with
identical bytes still require separate original observations. All observations
must map to exactly one derived callback, and every callback needs a capture.

Missing, linked, duplicate or extra metadata, missing/altered/unreferenced objects,
mixed profile/history, wrong owners, noncanonical inventories and incorrectly
counted storage are refused. Semantic negatives additionally alter the partial
borrow record, governing floor, original deletion, compacted journal and final
cleanup while keeping the same unmodified native history.

## Scope and reproduction

The [batch receipt](phase3-evidence/remove-prefixes.json) binds the two originals
to the same producer source, compiled build and toolchain, and records the
separately frozen corrected reader. The `4-REMOVE` history has 13 generation and
eight source retirements with 761 prefixes; `5-REMOVE` has 15 generation and nine
source retirements with 876 prefixes. All 1,637 original inventories match the
independent expectations, including 15 borrowed-image transactions. Sixteen
sidecar mutations per profile reject for their exact expected reason. No original
native execution was retried.

Three new Java collector tests and the two existing source-collector tests pass,
including real source retirement, a partial borrowed-image binding and independent
writer-lock probes. All 1,605 V5.3 Python tests pass, including ten new tests; the
focused suites pass 34 tests. The retained old callback-only history also returns
exactly its previous result and remains unchanged.

The initial reader incorrectly reused the parent peer-retention replay's `used`
set. It compared all original prefix bytes successfully but then rejected the
parent's 40 additional write indices as unbound observations in `4-REMOVE`; the
same collision rejected `5-REMOVE`. A separate `captured_used` set fixes the
reader. The new regression fails on the preserved original reader and passes
after the correction. Both initial failed reader logs remain retained. They are
not rewritten as successful producer receipts, and the native histories are
replayed without another execution.

The 43,358,423-byte archive retains 22,262 files and 2,664 directories, including
both original histories, sidecars, producer/build inputs and the two reader
versions with their diagnostics. Exact extracted member/hash checks pass.
Relocated `python3 -O -B` replays pass in 61.266 and 78.647 seconds, preserving
both positive and negative results exactly and leaving original/source inventories
unchanged. These are repetitions of the same 32 evidence negatives, not new
native executions or additional distinct cases.

```bash
python3 -B -m scripts.v53.remove_profile_run NEW_OUTPUT \
  --profile 4-REMOVE --retirement-captures --maven /opt/maven/bin/mvn
python3 -B -m scripts.v53.remove_retirement_prefixes ORIGINAL SIDECAR \
  --profile 4-REMOVE --qualify
```

Use `5-REMOVE` for the other original profile. Each producer freezes its source,
retains its exact build/toolchain and fails without retry. Its ordinary physical
qualification runs before the additional file-prefix comparison. The two profiles
may execute in parallel; stages within one history are never stitched together.

This qualifies observed file prefixes in complete healthy REMOVE histories, once
their source-bound executions and independent replay pass. It does not itself
qualify process death or recovery from those prefixes. The fresh-process matrix,
current-source seven-profile cohort, automatic lifecycle composition and frozen
acceptance mapping remain required; Phase 3 stays OPEN.

Rollback removes the opt-in collector, producer option and prefix reader, restoring
the previous callback-only qualification. Persisted runtime formats, production
Java, POMs, workflows and paid-cloud behavior are unchanged.
