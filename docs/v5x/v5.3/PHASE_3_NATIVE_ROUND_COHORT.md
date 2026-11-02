# Native carried and stable round admission

Phase 3 remains **OPEN**. The [entry](../../../scripts/v53/round_history.py)
collects seven existing public-bootstrap TCP histories with one recorded source,
actual build, portable toolchain and reader identity. Old entry completion and
its following fresh barrier stay in the same original. This entry is separate
from the Phase 2 conditional-fixture carried process tests; it does not promote
those fixtures into Phase 3 native process qualification.

## Declared histories

| Case | Existing native producer | Complete original |
| --- | --- | --- |
| `slot-accept` | `V53CarriedSlotDriverTest` | Old ACCEPT, reaccept, proof/application/publication, fresh BARRIER |
| `slot-proof` | `V53CarriedSlotDriverTest` | Old PROOF through carried completion and fresh BARRIER |
| `slot-certificate` | `V53CarriedSlotDriverTest` | Old CERTIFICATE through carried completion and fresh BARRIER |
| `slot-applied` | `V53CarriedSlotDriverTest` | Old applied certificate, authorized derived cleanup, carried completion and fresh BARRIER |
| `round-stable` | `V53RoundDriverTest` | Native activation, fresh BARRIER, internal readiness and serialized DATA |
| `round-discovered` | `V53RoundDriverTest` | Complete known-peer discovery before the stable round above |
| `round-carried` | `V53RoundDriverTest` | Old applied entry completed by the round owner before its fresh READY barrier |

The existing carried producers use an old BARRIER entry; the stable round adds
DATA after its fresh barrier. This catalogue does not claim carried DATA, control,
INTENT or FINAL payload coverage. Those protocol axes and native process cuts
remain required in the subsequent concrete coverage audit.

Each native method runs once in a fresh copy of the first producer's recorded
source. Its exact passing JUnit method, process exit, collection exit, class bytes
and original raw directory are required. No broad suite selection, native retry,
per-case budget override or evidence reconstruction is permitted. Capture retains
failed original files. Successful collection is `PARTIAL` and claims no replay.
The existing 30-second request profile of `round-carried` remains distinct from
the default request profile of the other six; original 180-second round bounds
are unchanged. The gate does not infer a response-time SLA.

## Independent original-first replay

Carried slots use the complete current-retention physical reader. Round histories
use both the lifecycle reader and the complete underlying physical reader. The
latter sees only the existing exact projection omitting `round-result.json`;
original files and events are never rewritten. Both physical derivations must
agree. Discovery, retention confirmation and predecessor source-retirement
negatives remain required alongside readiness/lifecycle negatives.

Stable owners maintain current copies before allocating the next command entry.
The physical reader therefore binds the second maintenance window to the first
original local `PUBLISH_ACK` completion, including its exact root, view, ballot,
identity, certificate, selection, published cut and generation. It still requires
one floor/publication per selected voter per slot, original copies before floor,
and business forces and control replies after slot admission. Nine additional
physical negatives reject missing, duplicated or forged completions, missing or
duplicated floor, premature floor, late completion and early business mutation or
control reply. No original event is moved to satisfy the reader.

The exact negative vectors contain 26 cases for each carried slot, 64 for the
ordinary stable round, 68 for the discovered round and 51 for the carried round:
**287 negative checks** for a complete seven-history cohort. Suite names distinguish
a physical mutation from the lifecycle check of the same name. Missing checks,
wrong reasons, boolean counts, weaker legacy retention semantics or an inflated
public/autonomous scope reject. An invalid original fails before its mutations.

Aggregation requires all seven distinct original plans and producer directories.
It verifies the immutable source, classes, tools, reader, process/JUnit receipts
and original inventories before and after replay. Failure of one original remains
failure while the other members can still be inspected. Independent complete
readers may run with one to four workers; ownership histories remain indivisible.
A heartbeat is emitted each minute. Existing output directories are never reused.

The resulting component PASS is not all-profile qualification, process-death
coverage, combined peak-resource qualification, automatic competition, public
readiness, complete physical fault coverage or Phase 3 closure. Control submissions
and authority-transition histories keep their separate required gates. The
[hosted adapter](PHASE_3_NATIVE_ROUND_HOSTED.md) is now prepared separately;
complete final-source admission remains subsequent work. The local development
receipt retains the seven-subset / 449-history inventory at its original source.

## Development evidence and source boundary

Seven native captures each completed once. The first original-source aggregate
remains **FAIL**: ordinary and discovered rounds were rejected by the old
`SLOT_BEGIN`-only maintenance window. Their original traces show the second local
floor after the completed first publication but before the second slot begins,
matching `MembershipRoundDriver.submit`'s pre-command maintenance. The other five
original members passed that aggregate.

The corrected reader replays all seven unchanged originals and all 287 negatives.
The migration check packs/unpacks complete producers, admits original provenance
using their frozen original reader, then separately runs the corrected reader
under Python `-O`. Identical derivations and unchanged inventories are required.
This does not rewrite the failed aggregate or pretend the old native captures ran
the corrected reader source. Corrected-source and final-source cohort admission
remain unexecuted. Runtime Java, native time budgets and protocol behavior did
not change. See the retained development receipt below for actual verification
status, hashes and original failure paths.

## Commands

Use a new output directory and preinstalled offline Maven dependencies:

```bash
python3 -B -m scripts.v53.round_history plan
OUT=target/v53-native-round-acceptance/manual-001
mkdir -p "$OUT/inputs"
python3 -B -m scripts.v53.round_history capture "$OUT/inputs/slot-applied" \
  --case slot-applied --maven /opt/maven/bin/mvn
for CASE in slot-accept slot-proof slot-certificate round-stable round-discovered round-carried; do
  python3 -B -m scripts.v53.round_history capture "$OUT/inputs/$CASE" \
    --case "$CASE" --maven /opt/maven/bin/mvn \
    --source-from "$OUT/inputs/slot-applied" || break
done
```

Review and freeze the first producer's source/build/reader pins and the portable
toolchain pin (`scripts.v53.process_toolchain.pin` on its `toolchain.json`). The
portable pin differs from the file's host-specific byte hash. Admission takes
those expected values; it never substitutes pins from a mismatching member.

```bash
python3 -B -m scripts.v53.round_history aggregate "$OUT/aggregate" \
  --inputs "$OUT/inputs" --workers 2 \
  --source-sha256 "$SOURCE_SHA256" --build-sha256 "$BUILD_SHA256" \
  --toolchain-sha256 "$TOOLCHAIN_SHA256" --reader-sha256 "$READER_SHA256"
```

The [development receipt](phase3-evidence/native-round-cohort.json) separates
actual native results from synthetic orchestration tests and final-source work.
Historical green receipts cannot fill a new cohort slot. No workflow, Required,
Java runtime, frozen format/bound or ongoing V5.2 experiment is changed here.
Rollback removes this optional local entry and navigation. Reverting the stable-round reader correction would again reject valid pre-command maintenance; preserve its regression evidence when changing that boundary.
