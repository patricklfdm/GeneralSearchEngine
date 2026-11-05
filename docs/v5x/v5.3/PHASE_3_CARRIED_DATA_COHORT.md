# Native carried DATA admission

Phase 3 remains **OPEN**. The [entry](../../../scripts/v53/carried_data_history.py)
now declares twelve complete public-bootstrap TCP histories for an old DATA entry. The
old vote, higher-ballot activation, carried completion and following fresh
BARRIER stay in one original. It complements the existing
[carried BARRIER and stable rounds](PHASE_3_NATIVE_ROUND_COHORT.md) and
[ACCEPT/PROOF rename process matrix](PHASE_3_NODE_RENAME_MATRIX.md).

## Declared histories and physical result

| Case | Original DATA state before the new campaign | Negative checks |
| --- | --- | ---: |
| `data-accept` | Durable ACCEPT | 32 |
| `data-proof` | Durable PROOF | 32 |
| `data-certificate` | Durable CERTIFICATE | 32 |
| `data-applied` | Certificate and staged native application | 33 |

The v2 cohort retains those four cases and adds eight
[whole-group recovery cases](PHASE_3_NATIVE_CARRIED_RECOVERY.md):

| Case suffix after `data-applied-` | Original group cut | Checks per mode |
| --- | --- | ---: |
| `cleanup-halt` / `cleanup-kill` | Carried certificate retirement | 57 |
| `accept-rename-halt` / `accept-rename-kill` | ACCEPT rename before parent force | 58 |
| `proof-rename-halt` / `proof-rename-kill` | PROOF rename before parent force | 58 |
| `application-force-halt` / `application-force-kill` | Application ACK directory force | 56 |

Each `V53NativeCarriedProcessTest` method keeps both child lives in one original:
all three original owners die, their locks release, and a new JVM opens the same
directories without a client resubmission. Original DATA publishes once and a
fresh BARRIER restores readiness. The capture invokes that exact single method
once; neither death nor recovery is a separate execution/member. The eight
cases add 458 exact negatives, for **587 across the complete twelve-member set**.

`V53CarriedDataDriverTest` uses the existing native owners, three voters, real
TCP and default resource/request bounds. Each method runs exactly once in a
fresh copy of the same recorded source. The original DATA contains document
`303:admitted-original`. Completion must preserve its original entry, ballot
origin and payload bytes. The selected pair publishes cut 1, then the fresh
BARRIER advances to cut 2 while application sequence and last DATA index remain
1. Both selected typed images contain exactly the one original document. The
unselected voter's current image remains at the original cut; its old staged
authority is retained according to the existing reader's rules.

This result means one DATA application in the published state. It does not
claim that no derived image was ever rematerialized after the old staged
application was cleaned up. No client request is replayed. Existing 5-second
request and 180-second round limits are unchanged, with no native retries.

## Independent admission

The reader takes an explicit `DATA` scope and requires the exact original
marker. It derives the binary payload and ENTRY, old ACCEPT/PROOF/CERTIFICATE,
selected owners, new activation, both certified slots, current-copy retention,
floor authority and network observations. For APPLIED it also decodes the
original staged image and derives the corresponding catalog and checkpoint.
Application sequence is derived from each predecessor catalog. A subsequent
BARRIER must preserve the exact application bytes and last DATA index.

The complete original must pass before mutations run. The existing 26
current-retention negatives remain required. DATA adds wrong scope, changed
payload, changed original ballot, reverted post-BARRIER image, inconsistent
peer image and reverted final image; APPLIED also requires rejection of a
reverted old staged image. Each check requires its exact rejection reason.
Together the original four histories require **129 negative results**. Invalid original
evidence cannot count as successful negative qualification.

Process cases must use `native_carried_network`, including its independent
physical/process preconditions and all original request/delivery/force checks.
Their collection records remain nonqualifying and bind the exact cut/mode and
complete original process result. A successful no-crash history, a normally
exited first child or a surviving original owner cannot fill a process case.
The returned result must retain both child lives, the five network phases,
recording majority and unchanged limited scope. Complete exact negative vectors
are required; partial replay and unrelated rejection reasons cannot substitute.

Collection returns only `PARTIAL`. Full component admission binds the exact
single unretried JUnit method, process and collection exits, source manifest,
actual class bytes, portable toolchain identity, reader identity and raw
inventory. All twelve producer directories and bootstrap plans must be distinct.
An aggregate requires every original and complete negative vector, preserving
failed originals and checking identities/inventories again after replay.
One to four replay workers are supported; no ownership history is split.
The entry reports progress once per minute and refuses existing output paths.

The component result separately reports `processCases=8` and
`declaredWholeGroupCarriedRecoveryQualified=true` only when the complete declared
set passes. Broader process-death, all membership profiles, combined
peak resources, competing owners, complete physical fault coverage, power-loss
qualification and Phase 3 closure remain false. Other payloads/profiles and
remaining process cuts are separate work. Existing
conditional Phase 2 process fixtures do not satisfy these native obligations.
Execution and cohort schemas are now v2; old v1 producer receipts cannot be
promoted by changing their case names or copying their hashes.

## Local execution

Use new paths and preinstalled offline Maven dependencies:

```bash
python3 -B -m scripts.v53.carried_data_history plan
OUT=target/v53-carried-data/manual-001
mkdir -p "$OUT/inputs"
python3 -B -m scripts.v53.carried_data_history capture "$OUT/inputs/data-applied" \
  --case data-applied --maven /opt/maven/bin/mvn
for CASE in $(python3 -c 'from scripts.v53.carried_data_history import CASES; print(" ".join(c for c in CASES if c != "data-applied"))'); do
  python3 -B -m scripts.v53.carried_data_history capture "$OUT/inputs/$CASE" \
    --case "$CASE" --maven /opt/maven/bin/mvn \
    --source-from "$OUT/inputs/data-applied" || break
done
```

Review and freeze the first producer's source/build/reader hashes. Derive the
portable toolchain pin with `scripts.v53.process_toolchain.pin` from its
`toolchain.json`; this differs from its host-specific file hash. Pass those
expected pins without substituting values from later members:

```bash
python3 -B -m scripts.v53.carried_data_history aggregate "$OUT/aggregate" \
  --inputs "$OUT/inputs" --workers 2 \
  --source-sha256 "$SOURCE_SHA256" --build-sha256 "$BUILD_SHA256" \
  --toolchain-sha256 "$TOOLCHAIN_SHA256" --reader-sha256 "$READER_SHA256"
```

The earlier [development receipt](phase3-evidence/carried-data-cohort.json) records
actual execution, independent and relocated replay, hashes and test results.
It does not fill a future final-source slot. No new hosted adapter is included
in that original batch; its development receipt retains the eight-subset /
456-history inventory. The later [hosted adapter](PHASE_3_CARRIED_DATA_HOSTED.md)
initially added four planned histories and now carries the twelve-member v2 set.
Runtime Java, persistent formats, budgets, Required and V5.2 experiments are
unchanged. The [v2 integration receipt](phase3-evidence/carried-process-cohort.json)
separates synthetic twelve-member orchestration, retained-original adapter checks
and relocated archive replay from final-source execution. No historical original
is relabelled as a newly captured source-bound member. Rollback restores the v1
four-member entry and its matching hosted/catalogue contracts together; preserve
all v1 and v2 evidence separately.
