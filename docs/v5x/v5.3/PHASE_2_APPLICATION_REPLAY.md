# Phase 2C5d — private application replay

Status: **local component PASS; durable publication remains OPEN**.

The private replay adapter imports a complete [application image](PHASE_2_APPLICATION_IMAGE.md),
checks its full hash/history/sequence, then applies a bounded contiguous sequence
through the existing `ReplicaApplication` business operations. DATA retains the
existing one-byte operation discriminator (codes 1–8) plus the exact existing body.
NO_OP/SNAPSHOT_MARKER cannot masquerade as DATA. Existing canonical codec, atomic
bulk, index lifecycle and schema checks remain in force.

The full DATA payload including its discriminator remains within 8 MiB; the private
projection accepts at most 10,000 contiguous steps and 32 MiB of input payloads.
The older application's internal serialization allowance is 12 MiB solely to avoid
its legacy base64-overhead calculation shrinking the separately checked 1.3 payload
cap. This does not change any wire bound or old runtime configuration.

Application sequence advances exactly once per DATA and stops at the V5.3 counter
limit. Non-DATA steps are syntax checked and preserve the application sequence.
Control-only replay returns the **exact original image**, including its original
index order. A new DATA result is exported through the core backup writer with
active indexes ordered by field name; this makes its bytes independent of where
an intermediate replay was saved/reopened. Document order and codecs are unchanged.

## Authority and failure boundary

This is private application projection, not certificate verification or the
membership catalog reducer. The caller must separately verify selected ancestry,
phased ownership, control-state eligibility, current fences and all referenced
learner evidence. An existing certificate does not bypass these checks.

The private search engine's internal publication has no public handle or runtime
reader. Business rejection closes the private engines, leaves the original image
unchanged and produces no output image. Caller-owned absent scratch paths retain
input/output or failure evidence; no live WAL or recursive cleanup is introduced.
The integrating owner still must reserve full scratch/staging resources and force
the actual prefix/materialization/selector before service publication or an ACK.
No public runtime, READY, checkpoint endorsement or bootstrap is enabled here.

## Validation

**29 focused Java tests passed**, including five new replay tests, eight image
tests, core backup transfer, prior rebuild/version checks and a real V5.1 public
facade/backup execution. All eight application operation kinds plus BARRIER are
checked against expected documents, sequence and indexes. Replaying across each
of eight intermediate save/reopen boundaries yields byte-identical final images.
Negative cases retain originals and reject foreign identity/cut, invalid opcodes,
gaps, conflicting indexes, failed atomic bulks, sequence overflow and excess input.

The expanded old facade test initially failed twice **after its backup assertions**:
it expected NOT_LEADER without establishing that the nonleader had completed local
application recovery. V5.2's status mapping permits NOT_READY while that premise
does not hold. The test now waits at most 30 seconds for FOLLOWER and the captured
leader applied cut before its exact original rejection assertions. It does not
retry a business call or accept additional error codes; unavailable recovery still
fails with status details. The corrected test passed. Both original failures remain
retained; this is a fixture prerequisite correction, not a failover timing claim.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53Application*Test,V50ApplicationTransferTest,V51ApplicationRebuildTest,V51VersionBoundaryTest,V51PublicRuntimeTest#completeFacadeUsesOneEntryPerCallAndNoOpKeepsPageCursor' \
  -Dsurefire.failIfNoSpecifiedTests=false package
```

[Implementation/build/test index](phase2-evidence/application-replay.json).
Raw results: `target/v53-certified-publication/`. The earlier 293-test image gate
describes its earlier source; the 29-test focused gate describes this replay batch.
Full integrated storage/protocol/hardening/workload acceptance remains pending.
