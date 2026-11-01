# Phase 3 — complete storage transactions within original joining slots

The previous composed reader accepted three independently mutated copies of the
retained 3-REPLACE original: a missing publication `INSTALL_MEMBER_FORCED`, a
missing `COVERED_VOTE_PARENT_FORCED`, and a missing `COVERED_END_FILE_DELETED`.
Each copy changed only `events.json`. All original storage, wire evidence and
directory membership remained identical. These are reproduced validation gaps,
not observations that the runtime omitted the underlying storage operations.

## Shared transaction check

`joining_phase_evidence.phase_replay` now invokes `joining_slot_storage` for each
actual certificate voter and slot. The existing semantic/physical prerequisites,
force-before-ACK checks and future-retention checks remain enabled. The new check
requires the full ordered storage sequence, with exact node, owner scope and
event fields:

- ACCEPT, PROOF and CERTIFICATE candidate creation, prefix/full writes, file and
  parent forces, rename and return.
- Original application authority, replay reservation/claim, application boundary,
  scratch removal and the complete applied-end writes. Parent/ancestor statements
  and acknowledgements come from the independently reduced end inventory.
- Publication reservation, complete generation materialization and current
  resealing. Image/member write/force counts come from the original generation
  inventory rather than a fixed count of one image and unspecified members.
- Covered applied-end removal, directory removal and empty-vote replacement,
  including candidate and parent forces before retirement returns.

Unknown storage callbacks within these intervals, missing/duplicated events,
reordering or callbacks from another lifetime cannot satisfy the sequence.
Interleaved wire observations and another node's callbacks do not supply local
storage authority.

The scratch model is explicitly limited to this control/BARRIER history. Its
unchanged application produces an input bundle with three core members; input
and work directories plus the claim and replay directory require seven removals.
DATA projection and interrupted/resumed transactions require their own original
models; this gate rejects DATA instead of silently assuming the same scratch
shape. Generic deletion callbacks prove count/order, not filenames. Exact file
identity and post-state remain responsibilities of the physical replay; this
batch does not claim new intermediate crash snapshots or prove plan-last deletion
from anonymous callbacks alone.

## Qualification

The [batch receipt](phase3-evidence/slot-storage.json) binds the original input,
frozen previous/new readers, reproduced gaps, full composed replay, original-first
negative qualification, Python regressions and portable archive verification.
The 26 additional observation mutations retain the original physical bytes and
directory set. A rejection must have its exact expected reason; an unrelated
original failure cannot count as a successful negative.

All 553 joining Python tests pass, including twelve new transaction regressions.
The REPLACE original has eleven slots, 22 owned transactions and 3,400 checked
storage callbacks. Historical ADD compatibility has eleven slots, 24 owned
transactions and 3,680 callbacks. These are observations, not protocol limits or
new native profile executions.

All 77 original-first network/storage negatives passed exact rejection checks in
367.727 seconds. Full REPLACE composition passed in 52.260 seconds; historical ADD
replay passed in 23.078 seconds. The 34,247,997-byte archive preserves 13,149 files
and 1,504 directories, including both frozen readers and the original producer
metadata. All member hashes and the exact directory set were checked after
extraction. The extracted new reader passed full composition with Python
assertions disabled (`-O -B`) in 52.798 seconds, with an identical result and
unchanged source/input inventories.

The first development audit accidentally serialized pretty JSON and correctly
failed the canonical-input check. Its result is retained but is not evidence of
the callback gaps. The corrected canonical mutations each passed the frozen old
full reader. The initial new reader also rejected an incomplete control-name
declaration; it was corrected to the actual six frozen membership commands plus
BARRIER, with an explicit regression. These development failures are distinct
from the original runtime execution.

No native workload is rerun. Java, POM, workflow, timing/resource limits and paid
cloud behavior are unchanged. Whole-history callback/authority coverage,
current-source profiles including REMOVE, fault/process qualification and the
frozen acceptance mapping remain open. Full physical/network/process and Phase 3
completion flags remain false.
