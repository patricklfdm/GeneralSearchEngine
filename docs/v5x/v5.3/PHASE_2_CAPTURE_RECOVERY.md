# Phase 2C4c5a — recover current-pinned original captures

Status: local component qualification PASS. This is a private storage mode, not public
runtime enablement or complete Phase 2 acceptance.

## Transaction and recovery

`MembershipGrantJournal.openCapturing` coordinates the original current generation,
retained sources, journal and existing maintenance owners under one root lock.
After reserving the complete source/image bytes and journal response capacity:

1. Force the new original PROMISE.
2. Force `source.capture.gsr` and its parent. Its at-most **28,672 bytes** are exact
   existing SELECTOR, PROMISE and proposed BASIS frames, within the current owner's
   existing 2 MiB MISC reservation. No new record or wire kind is introduced.
3. Write the original source packet and every application image; force each file
   and both directories. Keep every live source/image reservation continuously held.
4. Force the exact BASIS, then remove the capture intent and force its parent.
5. Recheck the root owner and higher-ballot observation before returning.

Before generic source admission, reopen and verify the unchanged current generation
and original new grant. The intent must be its exact complete bytes or an exact
prefix; a partial intent may not already own any source directory. The original
grant must be newer than the promise retained by the installed generation. An empty
intent cannot stand in for a missing grant. Every existing source member must be
an exact prefix of its corresponding original current bytes. Resume only missing
suffixes, preserving original grant ID, catalog, application and accepted tail.
A repeated interruption resumes the same transaction.

Once BASIS exists, ordinary complete-source validation applies: missing or changed
source files are corruption and cannot be reconstructed under the intent. A complete
BASIS plus a valid full source only requires clearing the pending intent. Other
grants, selection, adoption, floor and retirement mutations remain excluded while
capture is pending. A higher observed ballot prevents a response; any complete
forced original BASIS survives reopen without being rewritten under that ballot.

A crash after PROMISE but before creating an intent remains an incomplete original
grant. There are no source files to recover; the same ballot is refused and a fresh
ballot can capture the unchanged current authority. Legacy modes refuse the new
intent file. Unmarked historical partial sources and torn journal frames remain
explicitly rejected; this batch does not claim their operational repair.

## Qualification scope

The process matrix has 18 clean profiles (3/4/5 nodes, old/joint/new view, with and
without a tail), halt and external SIGKILL at all 23 intent/source/BASIS/clear
boundaries for a 3-node profile, and two repeated recovery deaths for a 5-node new
view. Packet, image and intent cuts include actual half-written bytes. This is
66 cases, not a Cartesian crash matrix across every profile. Joint-tail fixtures
use a concrete FINAL entry; ordinary DATA is invalid in that view.

The independent validator reconstructs the exact expected grant, intent, partial
files and force ordering from the retained original generation. It compares every
snapshot, process outcome and returned binding. Negative replay first validates
the unmodified evidence and requires the exact rejection reason. Portable replay
retains source/JAR/fixture bindings. Remote quorum ownership and historical
application bytes remain fixtures, not live network ACKs or power-loss evidence.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.capture_recovery_qualification target/v53-capture-recovery-new
```

### Retained results

All **66 cases / 266 fresh JVMs**, **14 exact evidence negatives** and portable
replay passed in **106.451 seconds**. The final reactor passed
**230 Java tests**, including 12 capture tests. **351 V5.3 Python tests**, **20 build
bundle tests**, and 33 focused Python/build tests under `-O` passed. The missing
grant development probe fails before the added check and passes after it; its
logs are retained separately from the source-bound process matrix.

The [hash index](phase2-evidence/capture-recovery.json) binds the tested source,
JARs, fixture classes and raw inventory. Raw results, preliminary failures and
receipts remain at `target/v53-capture-recovery/`. The preliminary fixture used
DATA in a joint view and was corrected to FINAL; a first Python discovery command
omitted the package top-level option and failed imports. Both original logs remain.

## Remaining work

Maximal SOURCE/APPLICATION staging, complete immutable-image/campaign/read/learner
lifetimes, torn journal recovery, actual pending ACCEPT/PROOF/certificate and real
application publication remain OPEN. Future pending votes must join this capture
binding; they cannot be omitted just because they are outside the generation.
Complete-store bootstrap, physical S/N mapping and the
[Phase 2 closure audit](PHASE_2_CLOSURE_CHECKLIST.md) are still required.

No public factory, frozen budget/byte catalog, workflow, paid cloud or separate
V5.2 Runner change is included. Work remains local.

The later [journal recovery batch](PHASE_2_CAPTURE_JOURNAL_RECOVERY.md) adds exact
torn BASIS suffix recovery under a complete intent; the results above retain their
original source and force-order attribution.
