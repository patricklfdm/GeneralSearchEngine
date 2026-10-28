# Phase 3 — departing FINAL application completion

Status: **locally qualified storage prerequisite**, 2026-10-28. The full native
[departing-owner path and Phase 3](PHASE_3_ENTRY_PLAN.md) remain open.

## Why the original path fails

The pending automatic REMOVE test reaches an actual original FINAL certificate
with node 4 as a joint-view proposer, then stops at `applied-end next-authority
identity`. The old storage API returns a new checkpoint endorsement for every
completed application. A departing joint voter still owes an exact local result,
but cannot endorse the successor configuration. This is an authority/type
mismatch, not a network timing failure. The original failed native history remains
under `target/v53-transition-round/builds/installationfixed-5c541611/`.

[A09](PHASE_3_CONTRACT_AMENDMENTS.md#a09--nonvoting-completion-of-an-original-final)
adds an explicit internal `Completion`: either the existing `Endorsement` or a
`Departure`. Only an exact original FINAL from a joint parent that includes the
same permanent identity on its old side but excludes it on its new side may
produce Departure. It retains the selector, certificate, catalog, statement,
application image and canonical plan after their required forces. It cannot
produce any successor or ancestor ACK, owned vote observation or public readiness.

`forceCompletion` returns the distinct type; the legacy `force` API continues to
reject departing owners before writes. Existing endorsed bytes and ordering are
unchanged. Complete-state checks, partial prefix recovery, owner/fence checks,
identity checks, capacities and explicit-authority staging retirement cover both
representations. No vote/quorum rule, wire format or resource/time limit changes.

## Source-bound local evidence

The [receipt](phase3-evidence/departing-end.json) identifies two immutable builds
from `97808824`, changing only the two storage/plan classes and the relevant new
tests. They exclude the pending round coordinator and unrelated reader work.

- 28 focused Java tests pass, including seven new tests covering both REMOVE
  sizes and all three REPLACE sizes, mandatory eligible-voter ACKs, refusal for
  unrelated nonvoters/changed identities, repeated interruptions, fencing,
  corruption, exact completion and explicit-authority staging retirement.
- Two additional process tests pass. All five departing profiles exercise 17
  cuts in halt and SIGKILL modes: 170 cases, each followed by another interrupted
  recovery and successful third process. The existing endorsed test adds 42
  cases. Total: 212 cases and 636 fresh JVMs. These are process crashes, not a
  claim of arbitrary physical power-loss testing.
- Independent normal and optimized readers replay every original case before
  evidence mutation. Twelve departing and seven unchanged endorsed mutations
  reject; the departing reader requires each exact rejection reason. Portable
  archived replay reproduces the complete results.
- All 704 V5.3 Python tests pass in the current worktree (including the pending
  transition reader); the five new reader tests also pass with assertions disabled.
  This is recorded separately from the isolated Java source.
- The original reader incorrectly assumed replacement identity `size + 1`; the
  existing fixture uses fresh `node-6`. Its first proof-negative also attempted
  to encode fewer witnesses than the format permits. Both failed reader versions
  and diagnostics remain retained. Corrected readers replay the unchanged raw
  histories; no successful Java process was rerun for either correction.

The historical certificate and external ownership/retirement authority in these
component tests are explicitly **conditional fixtures**. Actual forces and process
recovery are observed; this does not establish native certificate admission,
GSFT retention, publication or removal-service fencing. Those consumers still use
the endorsed API and must be integrated before the original native failure is
resolved. Learner ADD/REPLACE and complete Phase 3 qualification also remain open.
