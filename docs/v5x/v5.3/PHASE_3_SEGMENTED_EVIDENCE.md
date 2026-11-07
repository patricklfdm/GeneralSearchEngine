# Phase 3 bounded segmented observation format

This is a development prerequisite for the
[native verified-backup history](PHASE_3_NATIVE_BACKUP_SEED.md). It is not an
execution receipt, protocol authority, or a new accepted cohort profile.

The maximum native image is 67,108,832 bytes. One outer base64 representation
alone exceeds the existing 64 MiB whole-wire bound. The new test-only
`V53SegmentedEvidence` collector and independent Python `segmented_evidence.Reader`
provide a separate bounded representation. Ordinary EMPTY collectors/readers
are unchanged and do not discover this representation automatically.

## Format and ownership

The caller creates a new exclusive directory containing `segments/`, `cuts/`
and, only after successful capture close, `complete.json`. Each segment is a
sequence of canonical object rows, each terminated by one LF. The complete
index has the exact fields `schema`, `rows`, `bytes`, `segments`; the schema is
`gse-v53-segmented-evidence-v1`. Ordered segment descriptors contain only
`path`, `rows`, `bytes`, `sha256`. Paths are derived consecutive names
`segment-0000.jsonl`, `segment-0001.jsonl`, etc., not arbitrary producer paths.

| Bound | Value | Meaning |
| --- | --- | --- |
| Encoded row | 16 MiB, excluding LF | Existing individual evidence-row/parser boundary |
| Rows in one complete lifetime | 65,536 | Existing history-count bound |
| Segment | 64 MiB, including LF | Fixed read/write file extent |
| Segment count | 4,096 | Bounded manifest and file inventory |
| Saved cuts | 16 | Bounded prefix metadata |
| One history payload ceiling | 128 GiB | New format ceiling; caller may select a smaller allowance |
| Index | 16 MiB, 16 levels, 65,536 tokens | Independent metadata bound |

The payload ceiling is **not** permission to allocate that space per observer
in a complete native run. Whole-original inventory, snapshot copies, build
artifacts and all other captures still need aggregate accounting at admission.
The 128 GiB maximum-original policy remains separate. Native/runtime resource,
frame and retry limits are untouched. No bound is taken from a producer index.

The collector holds row offsets/hashes and segment descriptors in memory,
not complete row bodies. A caller can read back one captured row before close.
Saving a named cut seals the current segment and writes its prefix index.
Subsequent observations begin a new segment. A later capture cannot append to a
segment named by an earlier cut. Segment/file identities, content hashes and
saved-cut contents are rechecked before final close. A capture failure remains
failed; closing preserves partial files and does not produce `complete.json`.
This records observations only and performs no protocol force or retry.

The Python reader requires the complete index even when selecting an earlier
cut. It bounds and validates all segments, canonical rows, hashes and counts
before exposing any row. Every cut must be an exact segment prefix of the
complete lifetime. Unknown, missing, linked or aliased files are rejected.
Readback checks row hashes and file identities; complete iteration also checks
all index digests and the unchanged inventory. The API is a sequence with
bounded single-row reads and iteration; whole-history slicing is disallowed.

JSON budget scanning checks nesting/tokens before object allocation. It finds
string ends without a backtracking frame per base64 character. Canonical ASCII
encoding, unique keys, key syntax and signed integer bounds are independently
checked. A manifest hash is never treated as a native semantic proof.

## Development evidence

The [development index](phase3-evidence/segmented-evidence-development.json)
retains source hashes, test logs and checksums of the Java output:

- 33 Java checks pass: nine new segmented collector checks and 24 existing spool
  checks. They cover ordered readback, mutable producer maps, prefix rotation,
  newline-inclusive byte refusal, unchanged row limits, invalid input,
  duplicate/escaped/excess cuts, content/cut tampering, replaced/linked files,
  failure cleanup and a retained bounded-heap child process.
- 53 Python checks pass, including 16 independent segmented-format regressions,
  18 existing explicit-source/orchestration checks and 19 contract/plan checks.
- A 32 MiB Java child heap records 1,600 rows of roughly 60 KiB each, producing
  98,323,200 bytes across three segments, with an immutable first-100-row cut.
  The independent Python reader validates that unchanged original and cut under
  a 128 MiB address-space ceiling. The retained current replay takes about
  1.33 seconds on this development machine; this is not a native performance
  measurement or a general memory bound for every allowed input.
- A separate synthetic reader boundary checks an exactly 16 MiB encoded row
  under the same 128 MiB address-space ceiling. It is not a maximum native
  application-image execution.

No original native workload was rerun. The first Python test invocation
expected only a file-attribute error for same-size tampering; the reader
rejected it by its row hash. The regression now permits either exact integrity
failure. That original diagnostic log is retained.

## Explicit native wire integration

The backup fixture now has an explicit `SEGMENTED_BACKUP` layout. The default
remains `JSON`; an EMPTY bootstrap cannot select the new layout. The registry
owns the main wire and the five existing auxiliary logical histories under
`segmented-wire/`. Each auxiliary snapshot records its original observed cut;
later rows remain in its complete lifetime. Missing cuts remain missing and
cannot be substituted with the later complete history.

One shared byte budget covers all six histories, their saved/final indexes and
the registry itself. The independent reader inventories and bounds the entire
registry before decoding any history. It requires exact logical names, index
hashes, inventories and cuts, and rejects legacy JSON aliases. The explicit
source/layout selection comes from the caller, never from a producer file.
Connection and causal readers now accept this checked sequence as well as the
original JSON list. They retain their existing frame, identity and event checks.

The [native integration index](phase3-evidence/segmented-wire-development.json)
records 30 passing Java checks, 118 passing wire/transport Python checks, and a
real five-node nonempty-backup/BARRIER run. Its unchanged original has 663 files,
5,521,102 bytes and 292 main wire records. Independent connection, transfer,
resource and owner-close replay passes, including eight exact negative checks.
This is a short startup history; the six-history snapshot tests are component
tests, not a complete native joining run.

## Remaining integration

The complete required-four consumers still need an explicit layout context at
their file-loading boundaries. Full-array assumptions and retained decoded
frames/transfer payloads must be bounded throughout those consumers, not just
in the raw format reader. The shared registry budget is only a sub-budget;
it does not establish the whole-original bound. The whole-original
inventory must count every segment and cut alongside lifecycle/copy snapshots;
per-archive ceilings cannot be added to invent a larger admitted budget.

After integration, replay a small complete backup original through the same
format and all independent semantic/physical/resource checks before attempting
the long physical maximum. Full backup, combined-resource, physical-maximum,
final-source and Phase 3 closure remain unqualified by this component.
