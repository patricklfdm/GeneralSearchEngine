# Phase 1 deterministic protocol composition

Historical batch record. Later completion and remaining runtime gates are recorded
in the [Phase 1 closure audit](PHASE_1_CLOSURE_AUDIT.md); pending statements below
refer to this batch, not the final local Phase 1 state.

This qualification joins global promises, frozen-source selection, stable rounds,
operation catalogs, learner preparation, membership transitions and compacted
recovery in one causal execution. It is a deterministic model, not an enabled
Java runtime or a physical crash experiment. The separate [byte selection gate](PHASE_1_SELECTION.md)
qualifies the Java packet/certificate readers.

## What is composed

- A durable allocation precedes a fresh ballot. A local durable grant and original
  basis precede remote PREPARE. Separate delivery, stage, force and ACK actions
  permit crashes or higher promises between those boundaries.
- The proposer belongs to the exact immutable selected quorum. All selected
  installations must be forced and acknowledged before proposing. A missing
  selected source requires abandoning the ballot, not substituting a new source.
- A fresh current-ballot BARRIER activates a stable round. Sequential DATA,
  BARRIER and CONTROL then reuse the round while certifying every exact forced
  parent with separate ACCEPT and PROOF majorities. READY is not a time lease;
  activation and each entry still retain their original finite request deadline.
- RESERVE, PREPARE, READY, SEAL, INTENT, FINAL and RETIRE update the same catalog
  observed by the protocol. DATA invalidates stale preparations. A learner must
  own the exact prepared image before admission, and cannot vote in the old view.
  INTENT ends the old round; a fresh joint ballot completes FINAL; a fresh new
  stable barrier is required before service resumes.
- Recovery consumes each node's original canonical basis bytes and compacted
  packet. It cannot query the complete audit history. Ordinary entries and old
  full catalogs are absent from the base; original membership entries, sealed
  descriptors, certificates, endpoint catalog/application hashes and checkpoint
  endorsements remain. An un-compacted suffix retains its original certificates.
- Heterogeneous frozen cuts require actual source-side ancestry checkpoints. A
  missing bridge causes refusal even when the audit observer knows the history.
  Duplicate PREPARE after progress still returns the original basis. Covered
  minority tails are evidence, not a competing proven prefix.
- Accepted values retain their original entry bytes through a newer proving
  ballot. A recovered value alone never establishes READY. A proof-derived promise
  floor is forced before importing newer certified state; it is not a new grant.
- A new generation, selector, floor, exact retirement inventory and deletion are
  separate events. Restart preserves forced authority but never restores READY.
  The root-owned promise, basis and unresolved tail remain separate from retired
  generations. Physical files, copy ownership and deletion ordering remain Phase 2.

## Finite matrix and independent observer

The declared matrix has **112 histories**: seven membership profiles times sixteen
schedules. Per profile it contains the full transition, heterogeneous compacted
source recovery, five DATA force cuts, and three cuts each for SEAL, INTENT and
FINAL (accepted, proven, and locally applied before response).

The observer replays messages, local ownership, grants, parents, certificates and
catalog transitions independently of `composition_model`. It uses the independent
operation reducer, and retains the whole audit history to check what each compacted
statement actually covered. It also requires the decision itself to possess the
bounded source-side ancestry proof. Shared canonical encoding and hashing are
utilities, not a shared protocol decision implementation.

Case coverage is derived from actual original proposals, force/ACK boundaries,
membership certificates and final publications. A label alone cannot stand for a
crash cut. All traces are serialized, independently replayed, compressed, inventoried
and hashed. The complete evidence is copied to another path and replayed again.

Seventeen reason-specific negative variants remove forces or installation,
rewrite catalogs/descriptors/learner identity/tails, resample a basis, skip proposer
ownership, reorder retirement and falsely advertise READY. Originals must pass
before any mutation. An unrelated rejection or programming exception fails the
qualification; it does not count as a successful negative.

Focused tests additionally cover selected-source loss, missing installation ACKs,
higher PREPARE during an unresolved force, lagging parent catch-up, grant without
basis after restart, three identical bounded retries, expired response deadlines,
stale learner revisions, cancelled-result retirement, known removal, missing
ancestry, selector restart and whole-group restart.

## Scope and commands

[Retained receipt](phase1-evidence/composition.json): all 112 histories and 159,286
events passed, including seventeen exact negative results and relocated replay.
Twenty-two focused tests passed. Raw evidence is at
`target/v53-phase1-composition/qualification-final/`. Earlier 49-case qualification
and exploratory test failures remain retained and are not substituted for this
complete matrix. Phase 1 closure still requires the separate final audit.

```bash
python3 -m unittest scripts.v53.test_composition_model \
  scripts.v53.test_composition_negatives scripts.v53.test_composition_qualification
python3 -m scripts.v53.composition_qualification target/v53-composition/run-UNIQUE
```

The output must not already exist. Failures retain their original traces and
receipt. Source hashes bind all V5.3 Python modules and the frozen acceptance plan;
the recorded HEAD plus dirty status are not relabelled as clean-source hosted CI.

Assumptions are authenticated exclusive identities, atomic abstract forces, explicit
source discovery, a six-identity finite domain and a small deterministic application
digest. Model bytes are canonical model records, not a replacement 1.3 production
wire format. These histories do not establish real disk/transport durability,
read/callback semantics, fair scheduling, a failover SLA, general state-space
exhaustiveness, physical byte/memory bounds or performance. Authentic event
registries and audit traces are verifier state, not proposed runtime storage.

The **3,310 S rows and 24 N families** in the [finite inventory](PHASE_1_CASE_INVENTORY.md)
remain PLANNED for physical qualification. They are not relabelled as these 112
histories or seventeen model mutations. Model limits do not relax the frozen runtime
resource limits. The new membership runtime remains disabled.
