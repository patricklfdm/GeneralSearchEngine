# Phase 3 — native pending-vote rename interruption

This implements four whole-process fixtures: `ACCEPT_RENAMED` and
`PROOF_RENAMED`, each with halt and external SIGKILL. It also fixes two stale
observation assumptions exposed by the new executions. **Complete qualification
remains OPEN**: one final-source local history passed its JVM assertions, one
failed its original startup deadline, and the existing physical reader does not
yet model the current history. Producer success is not independent acceptance.

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

These reader changes are locally unit-tested; they do **not** qualify the newly
executed whole histories. A diagnostic reader extension for the third campaign
rejected the passing PROOF original at `applied-1/node-1/peer-retention.gspr`:
the historical model inferred revision 2 while the current no-op observation
correctly retained revision 0. Current confirmation/renewal debt semantics and
pre-command reconciliation must be composed across the whole history first.
The diagnostic extension is retained under the evidence directory, outside the
committed reader. No raw original was rewritten to satisfy the old model.

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

All four retained historical parent-forced histories still replay with their
exact original results and all eighty negative rejections. They establish reader
backward compatibility, not execution of the current runtime. The two remaining
rename/mode combinations and the complete final-source matrix are deferred to
hosted acceptance; no workflow was dispatched in this batch.

Next, compose the current peer-observation and maintenance model into this
independent process reader; validate the unchanged successful raw history before
any negative; investigate the failed startup history without attributing it to
runner scheduling without evidence. Preserve all failures. Complete histories
must stay on one filesystem/runner; only independent histories may be parallelized.
The existing 180-second service budget and 210-second process waits are unchanged.

Rollback removes the new fixture/cut names and reader extension and restores the
old test-only observer. Public API, production Java, POM, workflow, persisted
format and frozen workload/resource limits are unchanged. Full joining-process
composition, final-source cohorts, combined bounds and the S/N closure audit
remain OPEN.
