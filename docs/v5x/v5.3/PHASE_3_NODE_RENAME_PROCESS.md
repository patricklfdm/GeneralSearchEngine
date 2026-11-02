# Phase 3 — native pending-vote rename interruption

This implements four whole-process fixtures: `ACCEPT_RENAMED` and
`PROOF_RENAMED`, each with halt and external SIGKILL. It also fixes two stale
observation assumptions exposed by the new executions. **Complete qualification
remains OPEN**. The retained PROOF/SIGKILL original now passes the explicit
current physical/network/process reader and all 34 evidence negatives. The
retained ACCEPT/halt original still fails its startup deadline; two combinations
remain unexecuted. This is one qualified original, not a final-source matrix.

## Original process boundary

`V53NodeRenameProcessTest` reuses the existing
[in-flight process fixture](PHASE_3_NODE_INFLIGHT.md). The actual leader publishes
BARRIER 1 over TCP, then starts DATA 2. The crash callback occurs after atomic
replacement of `pending.accept`, before the subsequent parent-directory force.
An acknowledged pipe records the actual callback. The parent probes the original
lock before death, then observes halt exit 73 or SIGKILL exit 137 and lock release.
A fresh child opens the same original paths; both follower owners remain live.

Recovery must reaccept the original DATA under a new ballot and publish a fresh
BARRIER before READY. The interrupted client never resubmits its mutation. The
fixture retains the subsequent client write too. Current pre-command maintenance
can require another real campaign and readiness BARRIER before that write.
Process-visible renamed bytes do not establish host power-loss durability.

## Observation corrections

The first permitted execution exposed the old installation numbering: it used
the child lifetime as the installation number. A second installation in life 2
replaced `selected-2.gsr` and collided with the existing `installed-2` snapshot,
closing the observation pipe. The recorder now assigns consecutive installation
numbers within each lifetime. A focused regression reproduces the old duplicate
number and verifies that both original selections remain distinguishable.

The next original reached the final client DATA, but saving its longer event
array failed at the single-message JSON token limit. The fixture now uses the
existing `V53EvidenceArray` encoder, preserving the exact canonical array format,
16 MiB event cap and 32 MiB wire cap. Protocol token/depth checks still apply to
each row. The producer counts actual BARRIER starts rather than claiming two
when the original history contains three. Neither correction changes runtime
Java, protocol limits or retries an interrupted client operation.

## Retained startup failure and bounded diagnostics

The unchanged ACCEPT/halt original contains more detail than an undifferentiated
startup timeout. In life 2, ballot 3 publishes the carried DATA 2 and begins
BARRIER 3. Its three identical ACCEPT sends to node 2 have no intervening
node-2 ACCEPT force before the next campaign; node 2 is performing floor/source
maintenance during that interval. Ballot 4 then carries BARRIER 3 and starts
fresh BARRIER 4. The final recorded boundary is node 1's
`PUBLICATION_BEFORE_RETURN`, after its publication selector and future-retention
updates. There is no final `SLOT_COMPLETE`, `BEFORE_READY` or `second-ready`.
The worker exits 1 with `TimeoutException` from the unchanged 180-second startup
wait. Reaching a local publication boundary does not establish successful READY.

All 26 recorded heartbeat samples have a delivered peer response. The 630 wire
responses contain no REJECT, but failed transport exchanges have no response
row: this does **not** exclude a request deadline or another transport failure.
The original has neither monotonic observation durations nor a service failure /
typed recovery snapshot. Its event order cannot identify the duration of remote
maintenance or prove that instrumentation, scheduling or runtime code caused
the timeout. [The diagnostic receipt](phase3-evidence/node-startup-diagnostics.json)
keeps these observations separate from an unresolved root cause.

The test-only parent and worker now keep bounded observation counters. The
worker separates time waiting for the pipe monitor from write/ACK work, including
the currently blocked action. The parent measures action dispatch and actual
observation handling, including physical snapshots. These are overlapping
durations, not quantities to subtract from the original service deadline.

On an ordinary failure, reporting runs before close. It records the current
phase, exception causes, available node/service state and typed recovery losses,
and a limited platform-thread stack sample. Virtual I/O worker stacks are not
included. State sampling is non-atomic and gets at most 250 ms; an unavailable
sample stays explicitly unavailable and cannot prevent close. Reports have a
64 KiB limit, fixed action labels, at most 16 active observations, four cause
records and eight platform-thread stacks of at most twelve frames each.
Diagnostic and close failures are suppressed onto the original failure rather
than replacing it. A close-only failure still fails the producer.

Worker diagnostics go to the already retained `life-N.stderr`; parent diagnostics
go to the Maven/Surefire error log. Neither is a new observation action, ACK,
wire record, acceptance receipt or protocol authority. Successful child stderr
must still be empty. Halt and SIGKILL still bypass worker cleanup and reporting.
The failed original is unchanged; these diagnostics cannot retrospectively
recover its missing timestamps or promote it to PASS.

Eleven focused diagnostic regressions plus the existing seven observation/array
tests pass. The focused process/current-reader Python checks also pass normally
and under optimization. This batch has no new native history or same-source
retry. The 180-second service budget, 180-second call wait, 210-second parent
waits, request retry policy and all protocol/resource limits remain unchanged.
Root-cause resolution and final-source execution remain OPEN.

## Independent reader implementation and limits

The in-flight reader now recognizes only the two exact new cuts in addition to
the existing parent-forced cuts. For the interrupted local phase it requires:

```text
VALIDATED → CANDIDATE_CREATED → PREFIX_WRITTEN → CANDIDATE_WRITTEN
→ CANDIDATE_FORCED → CANDIDATE_PARENT_FORCED → RENAMED
```

A missing, duplicated or reordered event, another owner's force, a fabricated
post-rename directory force or a return after the declared cut is rejected.
The candidate file's force is distinct from forcing its new directory entry.
PROOF still requires the original remote ACCEPT and delivered receipt; it must
not have been dispatched at the cut.

Original-first qualification retains the existing twenty negative cases. Rename
histories add two mutations for an invented parent force and missing candidate
force. These change both the merged event stream and child transcript consistently,
so the exact-prefix rule must reject the semantics, not merely disagreeing copies.
The existing wrong-cut-event mutation also tests a premature return.

The initial legacy projection rejected the current PROOF original because it
invented two peer-ledger writes at genesis. The follow-up
[`node_current_evidence`](../../../scripts/v53/node_current_evidence.py) reader
must be selected explicitly; historical readers keep their default projection.
It independently derives genesis no-ops, confirmation/renewal debt, source
retirement, and the retained ancestry needed by a third installation. During
reaccept, the pending vote still owns its original sources; a later published
maintenance step may retire them. No recorded ledger counter supplies expected
bytes.

The same original now matches every snapshot through DATA 5. Whole-wire replay
accounts for 762 requests and 733 responses, including 25 heartbeat samples / 50
responses and 29 classified silent requests. Heartbeats bind their request and
reply cuts to original installation/publication selectors and prove contact only.
They cannot supply selection, voting, publication or READY. The third campaign
uses fresh ballot 4, changes the selected peer, publishes BARRIER 4, and precedes
the final client write. Child installation numbers 2 and 3 remain in lifetime 2.

Current qualification first accepts the unchanged original, then requires the
22 rename negatives plus 12 current-model mutations to fail with exact reasons.
These cover the reconciliation barrier/client vote, reused installation number,
invented genesis ledger force, missing source/selected-retention force, premature source
removal, lost retained ancestry, altered ledger, and stale/missing heartbeat
contact. Force and heartbeat mutations update the child and aggregate streams
consistently. The failed ACCEPT original remains rejected.

The current entry point qualifies this bounded three-campaign history. It does
not silently guess a model from a receipt, admit a partially pending maintenance
cohort, or promote an incomplete startup trace. Other complete layouts require
their own original-backed extension and replay.

## Validation and remaining work

The [receipt](phase3-evidence/node-rename-process.json) records exact attempts,
source/class inventories and local checks. In order, the retained executions are:

- The sandbox denied socket creation before bootstrap; all four cases errored.
- The permitted run exposed the duplicate installation snapshot. Its remaining
  shared-fixture cases were stopped after that cause was identified.
- The corrected single ACCEPT/halt history reached the later client write but
  failed aggregate trace encoding; it has no complete qualifying receipt.
- With both observation fixes, PROOF/SIGKILL completed its original two-JVM
  history, including reconciliation and the later DATA. ACCEPT/halt failed its
  unchanged 180-second startup bound after an additional recovery campaign.
  The combined Maven invocation therefore **failed**, despite seven unit tests
  and the PROOF case passing. No same-source retry replaced the failed original.

All seven retained historical histories still replay with their exact original
results and all 158 negative rejections: the four parent-forced cases, two
completed-DATA process cases and one cold-reopen history. They establish reader
backward compatibility, not execution of the current runtime. The final Python
suite passes all 2,012 tests; the 27 focused tests also pass under `python -O`. The two remaining
rename/mode combinations and the complete final-source matrix are deferred to
hosted acceptance; no workflow was dispatched in this batch.

The [current-model receipt](phase3-evidence/node-current-process.json) records
this replay separately from the original capture attempts. No native process was
rerun to repair the reader. The producer source/classes remain pinned to the
retained capture, while the new reader has its own manifest. This is not evidence
that the later source has executed the complete matrix.

Next, investigate the retained ACCEPT startup failure, finish the remaining
rename combinations and joining process composition, then execute final-source
hosted cohorts and the combined bounds / frozen S/N audit. Preserve all failed
originals. A whole history must stay on one filesystem/runner; independent
histories alone may run in parallel. The existing 180-second service budget and
210-second process waits are unchanged.

Rollback of this reader batch removes the explicit current model and its opt-in
hooks, leaving the already committed capture fixes and legacy readers in place.
Public API, production Java, POM, workflow, persisted format and frozen workload /
resource limits are unchanged. Full joining-process composition, final-source
cohorts, combined bounds and the S/N closure audit remain OPEN.
