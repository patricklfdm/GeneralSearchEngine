# Native admitted learner resource lifetimes

This component observes the actual admitted learner through preparation, READY,
CANCEL, explicit close and reopening the same retained files. It extends
[learner history qualification](PHASE_3_LEARNER_HISTORY_COHORT.md); an extra
receiving copy or pressure reservation cannot stand in for this owner.

The result remains **PARTIAL**. It does not qualify the simultaneous runtime byte
limit, transient physical-file maximum, process death, autonomous membership,
operation 231 or the final-source Phase 3 cohort. The learner never votes and
never opens public service. The current catalogue still has 566 histories,
260 execution groups, 500 raw archives and 544 selected jobs; this development
execution has not been added to that source-bound catalogue.

## Original capture and independent replay

`V53NativeLearnerResourcesQualification` runs the existing cancellation fixture
with observation enabled. `V53LearnerResourceCapture` records checkpoints from
its one actual resource pool, original force callbacks and the entry/return of
six actual close calls. A throwing close has no successful return marker. The
fixture retains all original voter files, transfer records, learner snapshots
and original identities. Resource sidecars are outside that strict original
inventory. Observation adds no pressure reservation or extra close invocation.

The ordinary fixture keeps its original close order and disables observation.
The new long native entry is explicitly selected; its `Qualification` suffix
keeps it outside default Surefire test discovery. The small collector test
still runs normally. Production Java, limits, timeouts, POMs and workflows are
unchanged.

`scripts.v53.native_learner_resources` first validates the complete native
history, including both forced quorum retention rounds. Only then does it:

- Derive receiving owners from original SOURCE_OFFER transfer identifiers and
  exact received metadata/image bytes, and derive cold owners from original
  retained filenames and plan bytes.
- Replay every resource delta with the existing independent arithmetic reader.
  Checkpoint totals must match both that trace and the physical snapshots.
- Bind both zero-byte generation claims to their original LEARNER source and
  require the atomic handoff after forced prepared selection and before return.
- Preserve base ownership continuously from selection through the actual store
  close, and terminal ownership from forced cancellation adoption through its
  actual close. Releasing and reacquiring the same charge cannot hide behind
  unchanged snapshot totals.
- Require exact close order and deltas: cancellation releases its own terminal
  copy; typed close retains store-owned charges; store close releases those
  charges. Both completed lifetimes end with zero outstanding charges.

Physical snapshot extents include the typed backup and actual small metadata
files. These are checked against their existing reservations, without treating
reservation sizes as measured physical bytes or claiming unobserved transient
files are covered.

## Current renewal history

The first independent replay rejected the captured inventory because the legacy
reader expected one campaign and five publications. Current
`MembershipRoundDriver.maintainReadyRetention` reconciles full renewal debt with
a fresh campaign before PREPARE, READY and CANCEL. The original execution
therefore contains four campaigns and eight publications. This is an existing
runtime behavior, not a new retry introduced by this component.

The explicit `current_retention=True` reader profile derives all four campaigns,
frozen grants, selected retention merges, retained ancestry and eight physical
publications from admitted originals. It compares every extra snapshot and
selection; it neither deletes nor renames them to fit the old profile. Its
failure allowance is bound to eight original publication rounds, at most three
future-retention failures per original request, and the exact third-voter
requests derived from original wire records. The two learner-retention rounds
retain their own existing ACK and failure checks. The legacy profile is
unchanged; current retention requires original learner ledgers.

## Local development evidence

The [development index](phase3-evidence/native-learner-resources-development.json)
records one fresh native execution, its immutable source/build/toolchain,
complete retained original, reader manifest and all failed development replays.
The native run observed 485 accounting transitions, 216 original callbacks,
two generation selections and six close intervals. The producer used the
initial `V53NativeLearnerResourcesTest` name; the final entry was subsequently
renamed to the explicit qualification class without changing its body. A
separate fresh-source compilation and small collector test verify that rename.
This producer is development evidence, not an exact-final-source cohort member.

The composed negative pass requires the valid original and all sidecars before
crediting any rejection: 15 copied in-memory resource mutations, all 31 existing
physical/retention evidence mutations, and four new renewal-history mutations.
Each rejection must match its specific expected reason. Compact Python unit
fixtures test reader behavior only and do not claim native protocol authority.
The earlier inventory rejection and two negative-driver diagnostic failures
remain retained; they are not counted as successful qualification.

## Explicit execution

In a separate development checkout with the normal local Java/Maven toolchain:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53NativeLearnerResourcesQualification test
python3 -B -m scripts.v53.native_learner_resources \
  general-search-engine-replication/target/v53-native-learner-resources/run-UUID \
  --qualify --output target/v53-native-learner-resource-replay/new-run
```

Use the actual emitted `run-UUID`; output must not already exist. Replay emits a
minute heartbeat, preserves original files and retains failure receipts. A
failed original does not receive negative credit or an automatic rerun.
Source-bound catalogue integration, broader resource pressure and final-source
execution remain separate work. No hosted workflow or paid cloud was triggered.
