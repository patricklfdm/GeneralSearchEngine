# Native carried INTENT / FINAL admission

Phase 3 remains **OPEN**. The [cohort entry](../../../scripts/v53/carried_transition_history.py)
binds ten complete four-voter REMOVE histories to one recorded source, compiled
build, portable toolchain and reader. It composes the existing physical,
network, export, ledger, retirement and [actual-prefix readers](PHASE_3_CARRIED_TRANSITION_PREFIXES.md).
It does not turn older development receipts into final-source admission.

## Whole histories and exact checks

| Case | Original vote | Native continuation | Independent negative checks |
| --- | --- | --- | ---: |
| `intent` | INTENT at index 5 | Carried INTENT, FINAL, fresh stable BARRIER | 301 |
| `final` | FINAL at index 6 | Carried FINAL, fresh stable BARRIER | 301 |
| `intent-accept-halt` | INTENT at index 5 | Group halt after ACCEPT rename, reopen original disks, fresh BARRIER | 210 |
| `final-proof-kill` | FINAL at index 6 | Group SIGKILL after PROOF rename, reopen original disks, fresh BARRIER | 210 |
| Other six INTENT/FINAL × ACCEPT/PROOF × halt/SIGKILL combinations | Index 5 or 6 | Same full-capture fixture, exact original directories and fresh BARRIER | 210 each |

The first two histories use one exact, unretried `V53CarriedTransitionDriverTest` method
with `-Dv53.carried.retirement.captures=true`. The original vote, selected
sources, all native publications, continuous ledgers, file retirement and close
remain indivisible. Request and round limits, membership profile and workload
are unchanged. Capture creates a new workspace and preserves failure evidence.
It never cleans an existing producer or retries a failed history.

Collection binds the original result, entry, plan, events, exact node identities
and sidecar objects. It returns `PARTIAL`. Admission additionally requires the
exact command, a single passing JUnit method without reruns/skips, successful
native and frozen-source collection exits, actual compiled classes and immutable
source files. For an ordinary history, the raw parent contains exactly one original and
its own retirement sidecar. Each process history instead contains its full nested
seven-family capture tree under a single original root. Missing, swapped, linked or changed sidecars cannot be reconstructed
from callbacks or borrowed from the other case.

The complete unmodified composition must pass before **any** mutation runs.
Each of the following readers then runs its complete original-first vector:

| Reader | Checks per original |
| --- | ---: |
| Physical bytes and lifecycle | 30 |
| Attempted network and durable replies | 153 |
| Export authority and floor lifetimes | 22 |
| Continuous peer/future ledgers | 41 |
| Retirement transactions | 36 |
| Actual retirement prefixes | 19 |

The positive result from every stage must equal the corresponding prerequisite
inside the complete prefix result. Exact negative rows retain their original
reasons and prerequisites; truncation, unrelated failures, changed authority or
inflated scope block admission. Original and sidecar inventories are checked
again after replay. Distinct producer directories and bootstrap plans are
required. These first two histories retain **602 checks**. The [eight process
histories](PHASE_3_CARRIED_CAPTURE_COHORT.md) add 1,680 capture/owner checks after
the complete original process/storage/protocol/resource chain: **2,282 total**.

## Local entry

Use a fixed checkout, installed offline Maven dependencies and new output paths.
Do not edit source or readers while the cohort runs.

```bash
OUT=target/v53-carried-transition/manual-001
mkdir -p "$OUT/inputs"
python3 -B -m scripts.v53.carried_transition_history capture "$OUT/inputs/intent" \
  --case intent --maven /opt/maven/bin/mvn
python3 -B -m scripts.v53.carried_transition_history capture "$OUT/inputs/final" \
  --case final --maven /opt/maven/bin/mvn --source-from "$OUT/inputs/intent"
for CASE in intent-accept-halt final-proof-kill intent-accept-kill intent-proof-halt \
            intent-proof-kill final-accept-halt final-accept-kill final-proof-halt; do
  python3 -B -m scripts.v53.carried_transition_history capture "$OUT/inputs/$CASE" \
    --case "$CASE" --maven /opt/maven/bin/mvn --source-from "$OUT/inputs/intent"
done
```

Review and freeze the first producer's source, build and reader hashes. Derive
the portable toolchain pin from `toolchain.json` using
`scripts.v53.process_toolchain.pin`; its host-specific file hash is separate.
Pass those expected pins without adopting replacements from later members:

```bash
python3 -B -m scripts.v53.carried_transition_history aggregate "$OUT/aggregate" \
  --inputs "$OUT/inputs" --workers 2 \
  --source-sha256 "$SOURCE_SHA256" --build-sha256 "$BUILD_SHA256" \
  --toolchain-sha256 "$TOOLCHAIN_SHA256" --reader-sha256 "$READER_SHA256"
```

Replay workers operate on separate whole originals. The CLI emits a heartbeat
each minute and retains failed member results while checking all other members.
For long final-source qualification use the [hosted entry](PHASE_3_CARRIED_TRANSITION_HOSTED.md).

## Historical two-history development validation

The [development receipt](phase3-evidence/carried-transition-cohort.json) records
both retained prefix originals replayed through this complete six-reader entry:
301 exact negatives each, **602 total**, with unchanged raw and sidecar
inventories. INTENT took 1479.316 seconds and FINAL took 977.771 seconds on this
local machine. These are reader-composition timings, not hosted estimates or
native execution timings. The source that produced these originals predates
this entry; both historical producers are explicitly rejected by its new
cohort admission. No native history was rerun in this batch.

All 2525 V5.3 Python tests passed. The focused 59-test entry, hosted, workflow,
planning and contract suite also passed with normal Python and with assertions
disabled. YAML structure and all five workflow shell blocks were checked.
These orchestration checks and the retained-original replays do not replace
fresh source-bound capture or downloaded hosted qualification; both remain
pending for the final implementation source.

## Scope and rollback

A component PASS qualifies this declared ten-history set only. Public readiness,
process-death, other membership profiles, combined resource peaks, autonomous
competition, complete physical fault coverage, power loss and Phase 3 closure
remain false. Other carried payload/process axes remain separate obligations.
No runtime Java, POM, protocol limit, Required job or cloud workflow changes.
For the v3 expansion, rollback restores the previous four-case adapter, receipt
versions, tests and catalogue bindings together. Preserve the existing readers
and every original development receipt.
