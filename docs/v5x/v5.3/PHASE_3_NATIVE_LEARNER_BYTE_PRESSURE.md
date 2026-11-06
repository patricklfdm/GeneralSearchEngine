# Actual learner cold recovery at a staging-byte boundary

Status: **PARTIAL**. This is a successor to the
[native learner resource history](PHASE_3_NATIVE_LEARNER_RESOURCES.md), not a new
voting authority, synthetic learner, whole-runtime maximum proof or Phase 3
closure. The complete original READY/CANCEL execution remains indivisible.

## Original and configured budgets

`V53NativeLearnerBytePressureQualification` first executes the entire existing
native learner history, including original voter TCP traffic, retained READY and
CANCEL, explicit close and same-file cold recovery. Only after that succeeds
does it open three further cold lifetimes on those same original directories.
Each lifetime has a new pool whose staging limit is fixed **before** opening.
No resource limit, lease or runtime counter is rewritten while the owner is live.

The independently derived steady charge `S` is the existing 64 MiB typed-backup
reservation, plus prepared application images, plus all retained terminal source
members. Prepared source metadata has already been transferred to GENERATION
and therefore is not charged again as staging. `P` is the original terminal
`source.gscp` length, and `I` is the sum of its original application-image lengths.

| Cold lifetime | Fixed staging limit | Real receiver result |
| --- | --- | --- |
| `pool-full` | `S` | Extra SOURCE is refused with `shared staging capacity` |
| `packet-short` | `S + P - 1` | Extra SOURCE is refused for exactly one missing packet byte |
| `source-exact` | `S + P + I` | Complete original packet and images are received, forced, validated and explicitly closed |

The extra receiver runs at the actual `LEARNER_CANCEL_BEFORE_RETURN` callback.
Rejections must return the temporary 4096-byte CONTROL reservation and remove
their scratch directory. The positive control must fill its pool exactly and
retain byte-identical original packet/images in the evidence before closing.
All three admitted learner lifetimes then return CANCELLED, preserve the typed
receipt, reject active service and close their cancel/typed/store owners to zero.
The positive receiver exists only during that bounded callback; it is not held
through the history to simulate persistent pressure.

## Independent checks

`scripts.v53.native_learner_byte_pressure` first replays the complete native
authority and the two original learner resource lifetimes. It then derives
every new budget and charge from those original files, checks the exact callback
order, one forced generation handoff per new lifetime, continuous selected and
terminal ownership, the actual receiver identity/transfer IDs, and all three
successful close intervals. Four snapshots per mode must contain the same
original bytes, paths and inode identities as the admitted cold-reopen snapshot.
Recorded paths are data and are never opened by replay.

Negative qualification first validates the unmodified original and all modes.
It then requires ten observation mutations and two copied-file mutations to
fail for their specific reasons, followed by all 50 existing resource/physical/
renewal negatives. A release/reacquire gap cannot hide behind equal before/after
totals. An unrelated error or invalid original gives no negative credit.

The 64 MiB typed-backup **reservation** is not a measurement of 64 MiB physical
backup data. These are caller-configured staging boundaries using real source
extents. The component does not prove simultaneous 384 MiB metadata pressure,
every GENERATION/SOURCE/APPLICATION count maximum, unobserved transient physical
maxima, autonomous learner recovery, process death or operation 231. Those
obligations and the exact-final-source cohort remain open.

## Explicit execution

Local development validation retained one unretried native execution (416.943
seconds including compilation) and original-first replay (97.154 seconds). All
three modes and all 62 evidence negatives passed; the original inventory stayed
unchanged. Two focused Java tests, 58 related Python tests and an overlapping
17-test run with Python assertions disabled also passed. The three initial
compile diagnostics remain retained. This is development evidence, not a
final-source cohort member; source, build, reader, toolchain and raw inventories
are indexed in `phase3-evidence/native-learner-byte-pressure-development.json`.

Run in an isolated source copy; preserve failures and use fresh output paths:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53NativeLearnerBytePressureQualification test
python3 -B -m scripts.v53.native_learner_byte_pressure \
  general-search-engine-replication/target/v53-native-learner-byte-pressure/run-UUID \
  --qualify --output target/v53-learner-byte-replay/new-run
```

Use the emitted `run-UUID`. Replay provides minute heartbeats. The qualification
class is opt-in and is not included in the default Maven test-name pattern.
No production runtime, POM, frozen limit, workflow or Required job is changed.
The [source-bound learner cohort](PHASE_3_LEARNER_HISTORY_COHORT.md) now requires
this exact method for its existing retained-cancellation slot. The 566-history
scheduling catalogue is unchanged. Admission retains the complete native
original and all three cold lifetimes together; modes from different native
histories cannot be combined. The retained local original supports development
adapter replay only, since its original source/readers predate this integration.
