# Authority retention and learner identity

Historical research note. Current decisions and local closure are recorded in
[PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md) and [the final audit](PHASE_0_CLOSURE_AUDIT.md).
Earlier open items, result counts and limitations below refer to that batch.

**Status:** Phase 0 candidate with isolated executable research. No production
capability is enabled. Reviewed parent: `93c61ae`, `feat/v53-cluster-operations`.

## Actual-source audit

Files below are under `general-search-engine-replication/src/main/java/`
`io/github/patricklfdm/generalsearch/replication/` and remain unchanged.

| Source read | Current behavior | V5.3 consequence |
| --- | --- | --- |
| `AutomaticReplicationGroupConfig.java` | Three distinct voters/endpoints; local node must be a voter | A learner needs a separate opening/admission path |
| `AutomaticBootstrap.java`, `AutomaticAdmission.java` | Manifest, genesis, node, target order and seal are bound together | Introduce reviewed new records; do not rewrite an existing manifest |
| `AutomaticWire.java` | Member-only sender/recipient; manifest, epoch, proposer/incarnation and reply correlation checks | Transfer permission must not grant voting authority |
| `AutomaticRejoin.java` | Manifest routes, immutable transfer IDs, exact ranges/digests, source owner/cut and current ballot guards | Preserve these bindings when adding learner transfer |
| `AutomaticStore.java` | Witness requester must be a member; transfer binds local identity, manifest and promise | Integrate the proposed global-promise adoption fence explicitly |
| `ReplicationReplacementPlan.java` | Fixed-manifest replacement result | Same-NodeId disk recovery is distinct from online membership replacement |

The earlier audit of `AutomaticRecoveryFiles` also found that above-floor
ACCEPT/PROOF deletion refuses. A compact authority proof does not override this.

## Candidate retention decision

Choose **complete membership history plus newly endorsed stable data ranges**.
Keeping every DATA certificate forever hits the prior research's 16-certificate
cap rapidly. Keeping only the latest configuration/hash loses the authority chain.

| Retained item | Binding |
| --- | --- |
| Immutable root | Group/history/genesis and initial membership |
| Stable-range endorsement | Starting authority, ending index/predecessor and before/after application digest; separate forced statements by a distinct majority of that stable configuration |
| INTENT and FINAL | Complete original certificates and both durable receipt phases; exact operation and predecessor |
| Operation/identity catalog | Full descriptors committed by operation hashes; initial/admitted/retired identities, endpoints and durable storage generations |
| Recovery state | Root promise, frozen basis, selection, unresolved ACCEPT/PROOF, floor and retirement inventory |

Only the first three rows have a representation model here. The identity catalog
is trusted research input; its replication, genesis binding and byte format are
still D01/D05/D08 work. Recovery state remains governed by its separate protocol.
A capsule is not an application image, recovery basis, read permission or floor.

A hash does not prove omitted entries were only data. The candidate requires a
**new endorsement record/message family**: a voter verifies the proven range,
then forces its statement. Existing ACCEPT/PROOF ACKs cannot be relabelled. The
receiver follows endorsed ranges and original transitions continuously from
genesis. No joint range qualifies. Duplicate owners, hidden transitions, missing
parents, changed state digests and foreign roots reject. Authentic identities and
crash faults are assumptions; this is not Byzantine authentication or a wire format.

With `M` changes, maximal stable intervals need at most `3M+1` logical items: two
configuration certificates per change and at most `M+1` ranges. This is not a byte
estimate. The model uses **four lifetime changes** and the earlier **32-slot**
execution bound; neither is a production constant. At the membership limit, reject
a new INTENT before voting; permit an already admitted FINAL. DATA/checkpointing
does not consume another change. A four-change walk plus eight further DATA
entries retains 13 items. New-group migration must never silently reset history.

Still required before freezing D06/D09:

- Incrementally extend an existing capsule from a proven suffix. This model builds
  from retained finite source history; it does not run unlimited writes after
  deleting that source.
- Obtain/copy endorsements before old witnesses depart. If unavailable, keep raw
  proofs and apply capacity backpressure; do not invent authority from status.
- Bind capsule and application bytes into selected generations and satisfy the
  floor before deletion. Preserve unresolved tails, promises and immutable bases.
- Freeze byte limits and bounds for descriptors, cancelled reservations, terminal
  records and grants. Membership count alone does not bound abandoned operations.

## Learner and replacement decision

Replacement uses a new voter ID, exact endpoint and **durable storage generation**.
A volatile connection session changes on restart while durable identity remains.
Compare all identity fields against live and retained retired entries; no endpoint
recycling, implicit disk reset or same-NodeId replacement in this path.

The prepared request binds root, caller operation ID, exact stable predecessor,
target voter set and joining descriptor. INTENT commits the hash of this **whole
request**, not just the caller ID. Changing a disk/endpoint under that caller ID
cannot adopt the certificate. Public expected-configuration semantics and prepared
revisions remain D05/D08 work: the exact-cut candidate cannot silently mutate a
reserved request when ordinary data advances during catch-up.

| Forced boundary | Result |
| --- | --- |
| Reservation | Exact duplicate may resume; different payload rejects; no voting/reads |
| Verified image | Exact prepared cut and abstract application digest retained; no voting |
| Materialization receipt | Request hash, full identity, image hash and cut bound; no voting |
| Matching certified INTENT installation | Joining identity eligible under joint membership |
| Matching FINAL installation | Eligible under new stable membership; rollback rejects |
| Separate global grant/selection/activation | Still required before actual votes or public service |

`eligible` means admission eligibility, not a PREPARE/ACCEPT/PROOF ACK or strong
read. Production must apply the global-promise and activation adapter afterwards.
Restart retains forced bytes and rejects old sessions. Disk loss or an altered
receipt fails admission. A receiver holding FINAL rejects removed voters, old
views and wrong descriptors. This does not remotely stop an isolated old voter
that has not learned FINAL; quorum fencing and read policy remain D02/D03/D07.
Identical byte-for-byte disk clones are not distinguishable by these checks:
exclusive ownership and authentic identities are explicit assumptions.

## Evidence and limits

Files: `scripts/v53/admission_model.py`, `admission_oracle.py`,
`admission_research.py`, `test_admission_model.py`.

Source history is pre-certified by **existing voters only**. The new learner has
neither voted nor installed a prefix in that fixture. Existing voters can satisfy
both majorities for all declared one-member add/replace profiles. Admission then
checks this independently verified history. It does not interleave live transfer
with elections or enforce readiness-before-INTENT in the consensus state machine;
that coupling with the transition/global-promise adapter is still required.

The observer validates original source events, independently reconstructs all
cuts/state digests, and checks endorsements and learner stage/force/crash events.
Per-event source watermarks prevent future endorsements validating earlier images.
It calls neither the live capsule verifier nor learner admission guards.

Matrix: five add/replace profiles × prefix lengths 1/8 × first/last minimal
endorsement quorum × eleven crash cuts = **220 cases**. Cuts are before/after
force of reservation, image, receipt, INTENT installation and FINAL installation,
plus healthy completion. Every case restarts and reaches final eligibility.
The 55 portable histories cover every profile/cut at length 1/first quorum;
all 220 traces contribute to the trace digest. This is not all interleavings.

Directed tests also cover all seven transition shapes, the lifetime change bound,
identity reuse, stale/foreign images, changed descriptors under the same caller ID,
premature eligibility, deleted forces, forged receipts and future endorsements.
Original histories must pass before their mutations are used as negative evidence.

```bash
python3 -m unittest discover -s scripts/v53 -t . -p 'test_*.py'
python3 -m scripts.v53.admission_research \
  --output "target/v53-admission-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

No Maven, network or cloud required. Output must be new; partial matrices return
`INCOMPLETE`. Receipts bind parent HEAD, dirty status and exact source/test hashes.
See [results](admission-research.json) and [development status](DEVELOPMENT_STATUS.md).
This advances D01/D04/D06/D09; **Phase 0 remains OPEN**.
