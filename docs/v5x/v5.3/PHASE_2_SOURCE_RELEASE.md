# Phase 2C4c4b — durable original-source retirement

Status: **locally qualified for completed obsolete BASIS sources**. The explicit
private `openReclaiming` owner integrates the prior
[decision checks](PHASE_2_SOURCE_RETIREMENT_PLAN.md). Incomplete source captures,
maximal coordinated staging and the full storage/runtime phases remain OPEN.

## One serialized transaction

1. Recheck exact original PROMISE/BASIS/packet/images, strictly newer durable
   promise, current selector and complete retained governing floor. Current and
   local floor references cannot retire; preserve exact above-floor bytes and
   unresolved ownership.
2. Force `sources.retirement.gsr` and its parent before changing any reference.
   It contains the exact RETIREMENT, original PROMISE/BASIS and original CAPSULE
   frames, bounded to **1,138,688 bytes** inside the existing MISC reservation.
3. Force and atomically replace the compact grant journal, removing only that
   obsolete original group. Preserve the highest durable promise, surviving source
   groups and any higher concurrent volatile observation. Force the parent before
   source deletion.
4. Delete only listed, unchanged source members and the empty directory, forcing
   each directory update. Recheck current/floor/owner/inodes between boundaries.
   Return only the obsolete source/image reservations, preserving the identities
   of every surviving reservation; clear the retirement authority last.

The decision plus worst-case compact journal, floor records and local authorities
fit within the existing **2 MiB MISC** bound. No second 32 MiB journal or copied
source/image is reserved. Actual duplicate images elsewhere still count separately.
A shared-capacity test retires at all six SOURCE/seven APPLICATION slots without
an additional slot. This does not prove another floor can be staged at that peak.

The initial implementation reconstructed all source reservations after deletion.
An isolated regression showed that this replaced still-live leases. The correction
releases only the retired source leases; the regression fails on the original and
passes on the corrected implementation. The earlier process matrix is retained as
historical evidence, separately from the corrected-source qualification.

## Reopen and refusal

A complete retained decision resumes on reclaiming open. The original journal may
still require the complete original source; once its group is removed, the decision
admits only the exact remaining source-file subset, never a usable BASIS or vote.
The saved original capsule binds the old cut/catalog/application to current/floor
ancestry even after the original packet is removed. Current/floor references,
original tail ownership and every remaining hash/inode are checked before deletion.

An incomplete unforced decision leaves all original files intact. Reclaiming open
blocks other mutations; explicitly resuming the named original source reconstructs
and matches the same prefix before forcing it. A partial decision cannot authorize
recovery after the original journal group or source is lost. Earlier open modes
reject the new pending authority. There is no fallback to metadata-only ownership,
no new ballot retry, and no source deletion merely to bypass capacity.

## Retained qualification

All **297 cases / 1206 fresh JVMs**, **15 exact negatives** and portable
replay passed in **958.164 seconds**. The focused reactor passed
**209 Java tests**, including all 14 source-release tests. **41 Python/build
contract tests** passed normally and under `-O`. The
[source/build/hash index](phase2-evidence/source-release.json) records the complete
raw inventory and logs under `target/v53-source-release/`.

The independent Python replay derives the original full floor and source bytes,
expected RETIREMENT and exact reduced journal, then predicts every observed crash
inventory and force event. It rejects missing/early force, retained obsolete source,
lost current/source/floor, changed journal/selector, wrong returned bindings and
false scope. Original evidence must pass before a mutation can count as a rejection.
Relocated replay must produce the identical result.

The physical matrix covers sizes 3/4/5 and old/joint/new cuts, halt and external
SIGKILL at fifteen boundaries (including both source members), plus a second
interruption during recovery. Historical membership observations and application
images remain fixtures. These are local process-death results, not power-loss,
network consensus or public runtime acceptance.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.source_release_qualification target/v53-source-release-new
```

## Still open

- A physical source captured before its BASIS frame needs its own safe lifetime
  rule; this transaction requires a completed original BASIS.
- Six retained sources can occupy the seven-image envelope with current. Full
  floor staging and coordinated immutable image lifetimes still need integration;
  successful deletion under an already-retained floor does not solve that peak.
- Actual ACCEPT/PROOF/certificate/application storage, complete offline bootstrap,
  complete-store recovery and the Phase 2 closure audit remain pending.

No public API, frozen format/limits, workflow, push or V5.2 experiment is changed.
