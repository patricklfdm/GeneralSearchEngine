# Phase 3 — inactive learner slot installation

[A23](PHASE_3_CONTRACT_AMENDMENTS.md#a23--bounded-inactive-learner-slot) adds the
first inactive member of the fixed pair after original predecessor retirement.
The current typed head authorizes transfer and original installation into slot B.
The received source becomes a second owned nonvoting GENERATION; its actual core
backup is decoded and its exact revision-bound LEARNER receipt forced separately.
It is **not selected as current** and cannot authorize another transfer or vote.

One sealed internal image-source interface lets the original successor and new
inactive slot use the same semantic preparation implementation. It does not let
plain capsules, receipts, callbacks or callers manufacture typed ownership.
Current and inactive handles remain distinct. An existing pending slot blocks a
new acquisition; resume must use the retained plan and matching current owner.

The original active head, receipt, terminal ancestor and reserved core path bind
every pending plan. On cold open, validate both sources and reserve their actual
retained resources before exposing a candidate. Read-only validation of the pending
source precedes retirement recovery writes. Re-force the original retirement and
release its conservative old charges before reserving the retained pending slot;
otherwise cold recovery could double-charge absent initial images alongside both
actual slots. No third generation, extra image allowance or timing extension exists.

The current head's terminal binding is computed once after full verification.
Every later use still rechecks source and metadata inodes, lengths and hashes and
all typed members. A fresh parsed map prevents caller mutation of that binding.
This avoids repeatedly decoding an identical history at every pending-file cut;
it does not skip physical checks or reuse a closed owner's capability.

## Verification scope

Focused results, failures and exact runtime identities are recorded in
[the component receipt](phase3-evidence/learner-slot.json). The suite covers actual
loopback TCP installation, semantic decode, cold reopen, no implicit selection,
interruption after source move, incomplete-plan refusal, source-inode replacement,
late current-member mutation and resource release. Its source voter histories are
conditional fixtures and do not establish native consensus qualification.

`V53LearnerSlotNetworkTest` contains one complete native PREPARE 1/2/3 history:
initial admission, first successor, retirement, cold reopen, third source transfer,
inactive installation, revision-three semantic decode and another cold reopen.
It is a separate final hosted unit, sharing the continuous history helper with
`V53CurrentHeadNetworkTest`. Neither compilation nor the component TCP run counts
as executing this native test or its independent physical replay.

## Remaining lifecycle

[A24 selection and retirement](PHASE_3_LEARNER_SLOT_HEAD.md) subsequently adds
the original selecting head, seed ownership and covered old-file removal. A23
installation alone still cannot treat B as current. The
[rolling plan](PHASE_3_LEARNER_ROLLING_PLAN.md) still requires alternate slot reuse.
Cancellation cleanup, matching forced INTENT, autonomous readiness, all five
joining profiles, maximal combined resource cases and native/process-death
qualification remain required. Phase 3 remains OPEN.

## Retained focused results

The final immutable build passes **11 methods**, zero failures/errors/skips, in
457.7 seconds: four slot lifecycle methods, five existing preparation
methods and two resource-owner methods. The slot histories use 3-voter ADD,
4-voter REPLACE and 5-voter REPLACE fixtures; this is not all-five-profile or
maximum-image acceptance. Actual loopback TCP, source inode ownership, typed
semantic decoding and original cold recovery are exercised. Late modification of
the current typed receipt invalidates the retained binding as well.

The earlier 11-method execution is retained with two assertion failures: its
negative callbacks treated `LEARNER_REPLICA_LOCKED` as a write. That event only
acquires an existing validated lock. The corrected callbacks allow that event
and still reject every recovery write/force before malformed originals fail.
The positive TCP/cold-reopen and interrupted-move cases already passed earlier.

The final runtime also caches only a fully verified immutable current-head binding
while retaining physical checks, and orders cold pending-resource reservation
after original retirement forces. Therefore the earlier runtime is historical,
not pooled with the final runtime as one result. Its complete logs and inputs are
preserved. The final build compiles both native three-revision classes without
running them; native replay, process death and full Phase 3 remain pending.
