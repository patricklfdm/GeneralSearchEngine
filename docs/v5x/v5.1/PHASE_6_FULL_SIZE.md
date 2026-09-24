# V5.1 Phase 6C2: actual 512-slot component boundaries

**Status:** implementation candidate on the accepted PR #227 runtime. Protected
CI and integration with the public automatic runtime/guest lifecycle remain open.
This is an additional boundary gate under the [6B contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md),
not a replacement for the [rich tapes](PHASE_6_REMOTE_RICH.md) or
[twelve public fault cells](PHASE_6_REMOTE_FAULTS.md).

## What executes

The isolated Java consumer compiles against the packaged candidate JARs outside
production artifacts. It obtains the exact 64-document, seed-17 source through
the separately compiled published V4.4 consumer and public backup API, then uses
public V5.1 bootstrap to create three sealed authorities. It opens the production
`AutomaticStore`, `AutomaticApplication`, recovery and TCP transport components.
The controller schedules ballots explicitly in one JVM; automatic election and
public client dispatch do not execute in this gate.

The finite schedule is:

1. Force and prove slot 1 as NO_OP, then 510 deterministic rich UPDATE slots on
   node 1 and node 2. Sequence advances from the imported 4 to 514 at slot 511.
2. Force the original slot 512 acceptance on both voters, withholding its proof.
   A higher ballot freezes both complete 511-slot proven bases plus their actual
   accepted tail. Fetch the remote basis through real 4096-byte TCP chunks.
3. Production selection retains that same entry. Install the selected prefix,
   re-propose the identical slot 512 entry at the higher acceptance ballot, and
   force its proof on both voters. Re-proposal creates two additional force
   observations and zero additional logical slots.
4. Hold node 2's actual application reader at cut 511. Retain both generation 511
   and generation 512, fetch a complete proven 512-slot basis, and send the entire
   512-slot image through real TCP to the initially lagging third authority.
5. Establish two-source durable floors using actual forced source bytes, then
   reclaim old generations while the application reader is still held. Its
   before/after answers remain exactly the independent cut-511 projection.
6. Release the reader, publish the final image, close all three authorities and
   reopen their original sealed paths. All three materialized reads match cut
   512, sequence 515, including all four rich indexes in the physical projection.

The gate uses 512 actual entries, 1026 acceptance forces and 1024 proof forces.
It does not claim that encoded synthetic fixture rows are execution evidence.
No slot 513, extra activation, measured rich call or cloud scenario is appended.

## Limits and evidence

Application and replica bounds match the frozen cloud plan, including 1-MiB
frames, 4096-byte chunks, 64-MiB replica/staging limits, 1200-ms individual
transport requests and the original JVM flags. Bootstrap binding bytes are
checked against those limits. A 90-second JVM process backstop, 60-second reader
hold and 600-second outer local qualification backstop bound this additional
component test; they do not amend any cloud cell or production timeout.

Original vote/proof journals, pending and full bases, selected values, snapshots,
transfer bytes, pre/post-cleanup authorities, callback observations and process
results are retained. Both sender and receiver must observe each complete TCP
exchange. Acceptance/proof observations must match actual journal bytes and
preceding force callbacks; proof receipts require previously observed voter forces.
The Python oracle independently checks all 512 predecessors, exact rich updates,
quorums, immutable entry identity, application images, chunk coverage, source floors,
delete ordering, reader answers and reopened state.

Archived authorities are inspected as immutable copies using their original
sealed paths. They are never reopened at relocated paths. Binary collection
replay first requires an exact inventory and then reruns the same positive and
negative oracles; a failed original cannot count as successful negative testing.
The ten negative cases remove/change forces, receipts, peer observations, pinned
cuts/answers, reopened progress, floor ordering, the reproposal quorum, the final
snapshot and the basis owner. Exact rejection reasons are required.

Receipts identify `local-component-boundaries`, `paidCloud=false` and
`fullRemoteQualification=false`. Observed retained bytes are sampled at the
specified archive cuts; production admission continues enforcing limits between
those cuts. A local PASS is neither a cloud admission nor a throughput/failover SLA.

## Review boundary and next work

The explicit controller exercises actual storage, reconstruction and TCP paths.
It does **not** exercise automatic campaign selection, public strong-read capture,
whole-basis download deadlines or `AutomaticRejoin` transfer lifetime/admission as
one integrated 512-slot public execution. Holding the real application reader
checks that disk reclamation preserves its view; it does not establish a new
public read freshness guarantee. The [checklist](PHASE_6_CHECKLIST.md) keeps the
full runtime boundary and combined 6C2 acceptance open for that integration.
Then 6C3 must connect the V5.1 runner/admission/provider and fake failure matrix.
No paid dispatch is authorized by this component result.

Development evidence is retained, including an initial controller PREPARE timeout
caused by redundantly reconstructing all 511 applied entries inside the request.
The controller now supplies the current published application image when its cut
matches the store's proven prefix, and reconstructs only when the cuts differ.
The production timeout and runtime implementation are unchanged. A later local
negative-driver expectation mismatch was corrected to the earlier, more specific
`proof before acceptance quorum` rejection; the oracle was not weakened.

## Local validation record

The complete gate at `target/v51-full-size/run.nRRVM4/evidence` passed, including
all ten exact negative results and binary collection/replay. The actual Java
component run took 17.000 seconds. Observed values were 182618 bytes for the
pending-tail basis image, 182412 bytes for the complete basis/transfer image,
6159 bytes for the largest exchanged frame, and 1224648 bytes for the largest
retained authority at an archived cut. These are observations, not new limits.

All 450 V5.1 Python tests and 23 CI topology tests passed. The external driver
compiled and ran against the packaged candidate; production Java/POM files are
unchanged, and this batch did not repeat the complete Maven reactor locally.
Protected CI must still build/test the candidate and execute the new required
step. Original failed development workspaces remain under
`target/v51-full-size-boundaries` and `target/v51-full-size`.

## Commands and CI ownership

```bash
scripts/verify-v51-phase6-full-size.sh
# After a fresh reactor package:
scripts/verify-v51-phase6-full-size.sh --skip-build
python3 -m scripts.v51.full_size_evidence PATH_TO_RAW_EVIDENCE
```

The existing required `v51-reclamation` job runs this gate after public reclamation
using the verified shared build. It always retains `target/v51-full-size` for
fourteen days, including failures. No new CI lane or repeated prerequisite Maven
build is introduced; docs-only behavior remains unchanged. Commit, push and PR
remain operator actions.
