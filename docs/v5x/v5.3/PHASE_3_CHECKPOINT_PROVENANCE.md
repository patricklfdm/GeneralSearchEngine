# Phase 3B — original checkpoint observations and compacted ancestry

Status: locally qualified. This is a component of the
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md), not autonomous membership or public READY.

## Original record authority

Record transfer now supports the existing CHECKPOINT and CHECKPOINT_ACK frames.
The journal serves only statements and endorsements actually authenticated by the
current capsule walk or its complete verified `ancestry.gsr`. An unused packet
inventory object is not sufficient. The retained file identities, bytes, view,
owner and original deadline are rechecked through the existing record export.
There is no new ACK force, persisted format, new wire opcode or cleanup authority.

A semantic checkpoint pull contacts the ACK's exact permanent voter identity and
checks the original record hash/bytes, root, storage incarnation, statement hash,
exact applied end and eligibility under that end's configuration. Validation is
before TRANSFER_COMMIT; the observation is returned only after committed transfer
and the final live guard. A node serving a copied ACK for another voter cannot
supply that other voter's observation. Generic record pulls still return bytes
only. This uses the existing trusted-private-network crash-fault model; it does
not add cryptographic signatures or Byzantine protection.

## Supplemental ancestry assembly

`MembershipCheckpointPull` accepts an already verified higher capsule, an exact
original lower anchor, and reference hints for a same-stable-era RANGE. It checks
both endpoints and a bounded ordered quorum before transferring. The statement is
fetched from retained storage, and every listed ACK is fetched from its actual
owner. If the local node is included, it reads its own verified retained storage;
it does not substitute a caller's Owned set or loop back through an invented peer.
The completed bridge is checked again against the exact endpoints and original
observations before use.

One invocation retains at most one statement and six endorsements in shared
CONTROL capacity. All pulls inherit the original start/deadline and guard. The
existing identical transport retries apply; explicit rejection, capacity,
corruption, fencing and cancellation do not restart the whole operation. Failure
closes all receiving buffers and local exports. Close cancels pending transfers;
no incomplete bridge can be retrieved. The runtime owns this borrow through its
use and must keep checking its campaign fence.

## Qualification scope

The real TCP scenarios use public offline bootstrap followed by actual journal
activation, BARRIER and typed DATA publication at stable sizes 3/4/5. The second
publication compacts away the intermediate anchor. Its supplemental original
checkpoint is then obtained over TCP from the actual retained owners. An independent
reader reconstructs bootstrap, every vote/application/publication and retained
state, validates typed application bytes, then checks the complete original
statement/ACK offer/data/commit transcripts and the resulting owner observations.
The entire authority directory is unchanged by these reads.

Focused tests additionally cover local/remote quorums, copied-owner refusal,
wrong incarnation/statement/endpoints, duplicate or insufficient owners, missing
records, original deadlines, fencing, cancellation, identical lost-commit retries,
non-retryable capacity, resource exhaustion and closed/replaced physical owners.
An adversarial model/storage fixture checks unused packet extras; it is kept
separate from actual TCP/bootstrap provenance evidence.

The final fresh isolated build passes 133 Java tests in fifteen suites, including
sixteen checkpoint tests. All 567 V5.3 Python tests pass in normal and optimized
modes. Independent normal, optimized and portable replay checks three actual TCP
histories, 33 exchanges and eight original ACK owners, with ten exact evidence
negatives. The [local receipt](phase3-evidence/checkpoint-provenance.json) binds
the inputs, artifacts and original-first activation/transport regressions.

Two new tests first reproduced missing local-owner fencing after a higher promise
and after owner close; the pull now rechecks the actual storage owner on use. An
unused-inventory test initially used a metadata-only storage adapter and failed
before the intended check. It now opens the generation owner, proves a valid ACK
can be exported, then requires both precise refusals. Restoring inventory-only
checkpoint export makes that regression fail. These failures, the earlier
seven-kind fixture mismatch and the first red-test compilation error remain
retained separately from final qualification.

## Remaining obligations

The higher capsule is still an authenticated prerequisite. This does not solve
full historical membership ACCEPT/PROOF provenance, unavailable historical owners,
newer-view discovery/adoption, or automatically finding arbitrary missing ancestry.
The activation driver and selected receiver still receive historical verification
inputs from their owner. Autonomous election, repeated-round source maintenance,
scratch restart recovery, learners/joint transitions, publication and full process/
network S/N qualification remain open. No public runtime, protected CI or cloud
acceptance is claimed; V5.2 and all frozen capacities/formats remain unchanged.
