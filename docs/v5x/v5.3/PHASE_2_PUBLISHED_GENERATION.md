# Phase 2C5d — complete first-slot generation materialization

Status: **local generation component qualified; journal publication remains OPEN**.
This continues [actual journal application/ACK](PHASE_2_JOURNAL_APPLICATION.md).

## Original selection and independently endorsed end

The private generation plan can now combine the exact original PROMISE, BASIS and
SELECTED with a complete checkpoint for the selected first slot. SELECTED retains
its original parent cut and original carried-entry choice. The new generation
retains the original ENTRY/payload/ACCEPT/PROOF/certificate in its bounded source
packet, including ordinary DATA, so reopening can verify the actual original
phased observations independently of checkpoint endorsements.

`selected-coverage.json` is private generation metadata (at most 4096 bytes), bound
by the existing generation inventory. It names the original selection, complete
parent anchor and certificate; it grants no authority by itself. The reader checks
the original election quorum/view, exact first-slot certificate/ballot/carried entry,
authenticated parent ancestry and exact new terminal entry. A later cut alone is
insufficient. Range compaction needs separately endorsed ancestry when it hides the
original parent; all bridges remain within six entries/96 KiB and must be validated
again on reopen. No record/wire kind or frozen size/count limit changed.

INTENT/FINAL materializations retain the original promise's governing view. Their
new checkpoint ACKs and floor copies use the successor view; the original selected
quorum still uses its original view. Tests explicitly cover an old election quorum
that is not itself a successor joint quorum. Complete copied generations retain and
check this representation before they can participate in floor admission.

## Resource lifetime and limits

Only the existing inactive generation slot can receive the plan. Its complete old
contents cannot be overwritten. The real-owner integration test establishes an
actual governing floor, retires the old generation and releases that floor before
admitting ACCEPT and its replay/end completion reservations. Floors include the
local owner and sufficient witnesses for both governing majorities.

Development runs exposed two genuine accounting constraints: admitting replay
completion before retiring the old generation can leave no capacity for floor
copies; retaining every available joint voter copy can leave no slot for the saved
retirement source. The test now uses a valid bounded maintenance order and sufficient
quorum. Full runtime admission must coordinate this order for every supported
profile. These observations do not establish complete-store lifetime closure.

## Validation

- All 63 first-slot projections across the seven member/change profiles preserve
  original selection bytes and exact phased proof. Missing bridge ownership,
  rewritten parents, substituted choices/ballots, malformed coverage, missing
  phases and skipped slots reject.
- Actual DATA, INTENT and FINAL tests use separately owned journals, real phased
  votes, typed core replay and forced checkpoint ACKs. Existing generation storage
  installs and reopens their resulting complete materialization under an exclusive
  allocator lock. Initial provisioning/history is still a private fixture.
- Every generation installation event has interruption/recovery coverage; recovery
  is interrupted again, and changed coverage preserves the original surviving bytes.
- Eight halt/SIGKILL component cases use 24 fresh JVMs, including repeated recovery.
  Their historical/phased observations are explicitly conditional fixtures.
  Independent Python derives the RESERVE command, catalog, certificate, capsule,
  ancestry, manifest and selector from the original parent rather than accepting a
  candidate manifest as the expected result. It verifies exact intermediate writes
  and force order. Five mutations reject, relocation passes, and Python `-O` gives
  the same result.
- Source, JARs, exact test totals, failed development logs and retained raw bytes are
  recorded in the [validation index](phase2-evidence/published-generation.json).

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53PublishedGenerationTest,V53CheckpointPlanTest,V53CurrentGenerationTest,V53GenerationInstallTest,V53FloorTest,V53FloorFilesTest,V53RetirementTest,V53FloorReleaseTest,V53SourceRetirementPlanTest,V53AdoptionInstallTest,V53CapsuleTest,V53SelectionTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.published_generation_evidence <v53PublishedGenerationEvidence-directory>
```

## Next integration

The component evidence above does not itself qualify journal publication. The
follow-on [actual journal transaction](PHASE_2_JOURNAL_PUBLICATION.md) binds the
staged end and original decision, forces publication and recognizes exact covered
vote/staging cleanup on reopen. Its evidence is recorded separately. Same-round subsequent
slots need a separate extension of first-slot coverage. Issuing additional ancestry
ACKs must use real forced ends, not inferred observations. These requirements, full
coordinated resource lifetime and public runtime remain OPEN. No push, protected CI
or paid cloud run was performed.
