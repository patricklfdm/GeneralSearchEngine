# Phase 2C4c5b — exact interrupted BASIS append recovery

Status: local component qualification PASS. Extends
[current-pinned capture recovery](PHASE_2_CAPTURE_RECOVERY.md); public runtime and
complete-store acceptance remain disabled/open respectively.

The capture owner can now recover a proper journal-tail prefix of the original
BASIS. It never truncates the journal or replaces the prefix with a new response.
Recovery requires the complete original capture intent, an intact journal prefix
ending in its exact new PROMISE, the unchanged selected generation, and complete
original source packet/images. Every suffix byte must equal the proposed BASIS.

The owner tracks the actual torn suffix during reopen. It validates the whole
source before any journal repair, appends only the missing bytes, forces the
journal and parent, then installs the in-memory BASIS and clears the intent.
A second crash during that append preserves the same original prefix. A complete
BASIS visible after a crash follows the existing complete-source validation rule.
Missing source files cannot be reconstructed after BASIS append has begun.

Other missing, corrupt, unknown, wrong-kind, stale or conflicting authority remains
unchanged and rejected. In particular a torn PROMISE has no complete capture intent
from which to recover; this implementation does not invent its ballot or source ID.
Legacy open modes retain their previous journal refusal semantics.

The extra half-BASIS cut is enabled only for the capture owner. Existing metadata,
retained-source, current-generation and reclamation modes preserve their write
paths. No frozen record/wire inventory, resource maximum or application semantics
changes. Journal bytes remain within the same 32 MiB reservation.

## Qualification scope

The matrix retains all 66 earlier capture profiles, adds halt/SIGKILL at the actual
half-BASIS append, and adds seven recovery boundaries under both modes, including
another half-suffix, force, directory force and intent removal. The resulting 82
cases include 3/4/5-node clean old/joint/new profiles, original DATA/FINAL tails,
source-prefix recovery and repeated journal recovery death. It is not the complete
Cartesian product of profiles and failure cuts.

Raw validation derives the expected partial journal from the original generation,
PROMISE and exact BASIS. It compares whole physical snapshots and process force
ordering. Original-first evidence mutations require exact rejection reasons.
Old retained evidence without the explicit `journalRecovery` field continues to
use its original force-order validator; newly produced evidence explicitly records
the extension. Earlier source/build provenance is not relabelled.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.capture_journal_qualification target/v53-capture-journal-new
```

### Retained results

All **82 cases / 344 fresh JVMs**, **18 exact negative results** and portable replay
passed in **138.375 seconds**. The reactor passed **235 Java tests**,
including five new journal-recovery tests and the 12 source-capture tests. The
31 focused Python/build tests passed normally and under `-O`.

The preceding `1f79818` journal implementation was compiled separately against
unchanged supporting classes and rejects the exact retained half-BASIS snapshot
with `torn grant journal body`, leaving its files unchanged. The corrected process
matrix recovers that same kind of original interruption. All **66 historical
capture cases** also replay through their original validator, with no workload
rerun or revised source attribution.

[Source/build/evidence index](phase2-evidence/capture-journal.json).
Raw snapshots, process logs and counterfactual implementation evidence remain
under `target/v53-capture-journal/`.

## Still open

Actual pending ACCEPT/PROOF/certificate and complete application/catalog storage,
maximal source/image completion headroom, coordinated campaign/read/learner
lifetimes, complete bootstrap/reopen, physical S/N mapping and the Phase 2 closure
audit remain required. Historical quorum ownership/application bytes are fixtures;
no live network ACK, public service or power-loss qualification is claimed.
No push, workflow dispatch, paid cloud or separate V5.2 Runner change.
