# V5.0 Phase 6 runner preset qualification

- **Status:** Accepted through PR #161, correction PR #162 and exact-master CI 35069706211
- **Branch:** `feat/v5.0-phase6-cloud-runner-presets`
- **Starting master:** `cc46be814c23ea7544a0aafed30085f62c9de159`
- **Predecessor:** [PR #160](https://github.com/patricklfdm/GeneralSearchEngine/pull/160), [exact-master CI 35058372449](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35058372449)
- **Contract:** [Accepted cloud workload plan](PHASE_6_CLOUD_WORKLOAD_PLAN.md)

## Scope and delivery order

Runner integration is split into two reviewable changes. This change qualifies
preset selection, serial sequence and cost reservations, replacement disk ownership,
and the full public workload using an offline Java bundle and per-voter volume paths.
The next change connects remote guest operations, elapsed cloud fault cells, bounded
cloud collection and independent VM/topology/set provenance. Both must pass protected
PR and exact-master CI before 6C admission.

The manual runner exposes `experiment`, `failure-drill` and `canonical` for `plan`
and `fake`. The workflow rejects other modes for these profiles before credentials;
the CLI and Runner also reject paid execution. The accepted paid adapter continues
to support its original `admission-probe` contract. Neither earlier plan JSON is
changed. This PR creates no cloud resources and accepts no cloud performance result.

## Presets and sequence policy

[cloud_presets.py](../../../scripts/v50/cloud_presets.py) derives closed preset
descriptors from the checksum-pinned workload contract and binds the accepted runner
plan digest. Requests bind source, bundle, preset digest, sequence UUID, profile,
repetition and unique ownership nonce. Invalid ordinals and unknown profiles fail.

| Profile | Measurement seconds | Planned ceiling | Replacement order |
| --- | ---: | ---: | --- |
| Experiment | 300 | 2340 | None |
| Failure-drill | 900 | 3360 | Node 3, then node 1 |
| Canonical, each repetition | 1800 | 5400 | Node 3, then node 1 |

The fake adapter exercises all five fresh topologies through the existing Runner:
experiment, failure-drill, canonical 1, canonical 2, canonical 3. Cell timing uses
a virtual monotonic clock and preserves the exact ordered elapsed allocations;
these receipts contain no latency or throughput samples. Early completion waits
through the cell window; overrun fails.

The generation-conditional sequence ledger reserves a member before resource
creation. Each predecessor must have an immutable completion object whose hash,
request, successful cleanup and retention agree with the ledger. A missing receipt,
different source, skipped ordinal, duplicate repetition or failed/unresolved member
blocks progression. Reconciliation can release a resource lease; it cannot turn
a failed or incomplete sequence into a passing one. A new set starts with experiment.

The same global ownership lease serializes topology creation. Cost reservations use
the existing append-only sequence ledger with the [amended USD 100 ceiling](PHASE_6_BUDGET_AMENDMENT.md), including failed attempts and new
sets; cleanup never refunds them. The fake fixture uses USD 1 reservations to test
the arithmetic. That number is a test input, not a cloud price estimate or approval.

## Replacement ownership and cleanup

The Runner quiesces the probe, retains diagnostic pre-loss evidence, unmounts and
detaches the old disk, deletes its exact owned ID and reads back absence. Only then
does it append a fresh `-data-g2` intent and create request UUID to the same lease
before allocation. Replacement bootstrap uses the designated surviving node's
authority; the preserved diagnostic copy is never an input. After initialization,
the new disk moves from that survivor to its configured voter and obtains a new
mount receipt. The adapter interface is qualified with fake receipts in this PR;
physical deletion and public remote reconstruction still require the next gate.

Allowed inventories contain the initial thirteen resources followed by an ordered
prefix of at most two replacement disks. Arbitrary names, extra generations and
reordered nodes fail reconciliation. Old and new IDs remain in the journal and
cleanup read-back set. Cleanup deletes VMs before any disk generation, including
new disks appended after the original VM intents. Attached auto-delete disks are
still independently checked for absence. Fake allocation reaches, but never exceeds,
the frozen 450-GiB peak.

Failures include false/failed old-disk deletion, changed ownership or ID, lost
replacement create acknowledgement, unresolved insert, bootstrap failure, cancellation,
cell overrun and interrupted retention. Deletion continues after individual errors.
Ambiguous ownership/creation and incomplete retention retain the lease and block
the next topology.

## Offline bundle and public volume qualification

[cloud_bundle.py](../../../scripts/v50/cloud_bundle.py) can produce a separate
`gse-v50-cloud-workload-bundle-v1` offline bundle, containing the pinned V4.4 control,
exact production JARs, independently compiled public consumers/test observers and
a pinned Java 21 jlink runtime. Its schema and execution label differ from the paid
admission bundle. It has no remote guest entry point. Artifact expansion remains
bounded at 128 MiB; the separate workload evidence format retains its reviewed 4-GiB
bound, ordered 32-MiB parts and 16-MiB JSON limit.

The existing full-workload CI gate now uses this bundle for its three owned JVMs and
puts both authority and materialization under `volume-1`, `volume-2` and `volume-3`.
Public bootstrap, crash recovery, follower replacement and configured-leader
reconstruction retain these resolved paths. The independent validator checks the
sealed configuration paths, retained volume authorities, compiled class hashes and
bundle/source/JAR identities. The reduced local schedule still has fourteen cells;
it does not claim the 300/900/1800-second cloud timings.

The gate preserves the existing corpus, published-control restore, proof replay,
capacity-source comparison and semantic negative checks. Added negatives reject
changed compiled classes, forged bundle inputs, a false volume-layout claim and
missing retained volume authority. Production Java, public API and storage formats
are unchanged.

## Commands and acceptance

```bash
python3.11 -m scripts.v50.cloud_entry plan --profile canonical --output target/preset-plan
python3.11 -m scripts.v50.cloud_entry fake --profile canonical --output target/preset-fake
scripts/verify-v50-phase6-cloud-workload.sh --skip-build
```

The fake command exercises prerequisite profiles and replacement failure cases.
The workload gate reuses unchanged production JARs, builds the offline bundle,
executes the local volume qualification and independently rejects resealed negatives.
Required CI retains all these receipts in the existing workload artifact for fourteen
days. No-GCP Python discovery includes the new policy and failure tests.

- [x] Predecessor PR #160 and exact-master full CI verified; workload gate executed.
- [x] Final local policy, failure, bundle, volume and independent negative gates pass.
- [x] This implementation accepted through PR #161/#162 and exact-master CI `35069706211`.
- [ ] Remote preset execution, cloud collection/provenance and set validation accepted.
- [ ] Fresh preflight/cloud setup and exact complete-sequence paid confirmation.
- [ ] Staged 6C execution and separate 6D baseline registration accepted.

### Initial local receipts

| Check | Result |
| --- | --- |
| V5 Python discovery | PASS; 146 tests, including seventeen preset/sequence/replacement tests |
| Preset fake matrix | PASS; five serial topologies plus ten expected failure cases; 450-GiB peak |
| Offline bundle | PASS; 21478035 compressed bytes; independent candidate/control compilation and pinned jlink runtime |
| Volume workload | PASS; 61.34-second local qualification, fourteen cells, 4096 initial documents, 72 measured calls, 56 durable measured mutations |
| Independent replay | PASS; committed index 92, application sequence 340; 26 resealed semantic negatives rejected |
| Retained workload evidence | 19292218 logical bytes, within the separate bounded evidence format |
| Existing 6B regression | PASS; original fake failure matrix and offline volume-layout admission probe; sequence 76, committed index 73 |
| Release artifacts | PASS; nine JARs; production core and replication hashes unchanged from PR #160 |
| Documentation/CI wiring | PASS; Phase 0 contract, fourteen classifier tests, workflow YAML, shell syntax, local links/fences and whitespace |

The initial workload receipt is `target/v50-cloud-workload/run.TZdQWY/evidence`;
its sibling `presets` directory retains the fake matrix. The old 6B receipt is
`target/v50-cloud-local/run.pefStW`. Both record starting source
`cc46be814c23ea7544a0aafed30085f62c9de159` with `sourceDirty=true` and exact input
inventories. Clean-source acceptance remains the protected PR and exact-master gate.

### CI scheduling correction

[CI run 35061971394](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35061971394)
failed on the full-workload gate. Its retained `instrumented-a` call trace shows
`REMOVE_ALL` took 221566147 ns, crossing the next 200-ms arrival. The old scheduler
recorded call 6 as missed, skipped `INDEX_DROP`, then ran call 7 `INDEX_CREATE`.
The resulting `ALREADY_EXISTS` error obscured the original missed-slot failure.

Local qualification v2 now waits for the lane's prior completion, retains every
operation and spaces dispatches without a catch-up burst. Each window still has a
20-second ceiling; the original whole-run and process bounds remain. Candidate and
published V4 control use the same pacing policy. The separate experiment/failure-drill/
canonical schedules retain their fixed arrival rates and immediately abort on the
first missed slot. Seven virtual-clock regression tests cover the exact 222-ms
case, scheduler pauses, bounded four-lane dispatch, timeouts and strict cloud rates.

The independent validator verifies nominal/deferred/dispatch timestamps, minimum
dispatch spacing, same-lane completion, complete call counts and the window ceiling.
Summaries retain deferral, observed rate and maximum rate explicitly. Resealed
negatives reject altered pacing, nominal arrivals, overlong windows and lane overlap.
That correction changed only the local qualification section of the full-workload
JSON. Its plan SHA-256 was `b05ec5f6f6f6088eeed47841dc0adbb2527e1d30d4f3626f85deaa144cbd4241`;
the historical receipts retain that identity. The later
[budget amendment](PHASE_6_BUDGET_AMENDMENT.md) records the current reviewed hash.

Correction validation passed: seven deterministic Java scheduling tests, 147 V5
Python tests and the complete workload gate, including all fourteen cells and thirty
resealed semantic negatives. The 59.70-second local receipt is
`target/v50-cloud-workload/run.NQ2gji/evidence`, with source
`aa846e82584e0459e3ff8a7ad3b3558fffcd308e`, `sourceDirty=true`, 72 measured calls,
56 durable measured mutations, committed index 92 and application sequence 340.
The fake preset matrix also passed. A direct JSON comparison confirms every section
outside `localQualification` is unchanged. The failing CI receipt remains failure
evidence; acceptance requires a new passing protected CI run.

### Concurrent evidence validation correction

[PR #161](https://github.com/patricklfdm/GeneralSearchEngine/pull/161) merged as
`2ad57c19949f6a6c6b6af2e93a5520dfcb088677`. Its
[post-merge CI 35065417333](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35065417333)
passed all fourteen workload cells, then failed the independent validator with
`missing force timings`. Exact-master acceptance remains open.

The retained trace identifies sustained call 2, committed index 44: it started at
`681231651712` ns while index 43's PROOF force was still running
(`681174857082` through `681255568356` ns). The validator's client-time interval
therefore selected the preceding PROOF as well as index 44's ENTRY and PROOF.
Both required forces were present; the association was wrong.

Force observations now pair one-to-one with independently proven log entries in
serialized writer order within each instrumented window. The validator requires
the complete indexed quorum/publication stage sequence, exactly one ENTRY/PROOF
pair, positive durations, ENTRY after both client start and the previous commit's
success barrier, and PROOF between entry quorum and local proof completion.
Missing, duplicated, reordered, reused or out-of-window evidence still fails.
Client starts and completions may overlap without changing that writer ordering.

Revalidating the same artifact exposed a second serial-order assumption in the
published V4 control: sustained calls 17, 19 and 24 began before the previous write
completed, so their `beforeSequence` values legitimately lagged dispatch-order
replay. Control replay now assigns each mutation a unique publication sequence
inside its recorded public before/after bracket, choosing the eligible mutation
with the earliest upper bound. This is sufficient for this frozen workload:
cross-lane sustained updates use independent keys, same-lane calls do not overlap,
the sustained query's membership/order stays unchanged, and healthy operations
remain serial. Stable read cuts and complete final state
still use the independent model; impossible brackets, sequence regression after a
completed call, ambiguous reads and forged answers are rejected.

The correction changes the Python evidence validator and its tests. Seventeen
deterministic regressions cover overlapping force intervals, completion reordering,
force ownership, control publication brackets and invalid evidence. All 164 V5
Python tests pass. The original CI bundle passes read-only revalidation with its
original hashes and clean source identity; all 38 resealed semantic negatives are
rejected. This diagnostic replay does not change the failed CI run's status.

The fresh full gate also passed: 48 workload/preset unit tests, the fake preset
matrix, all fourteen three-JVM workload cells and 38 resealed semantic negatives.
Its 60.66-second workload receipt is `target/v50-cloud-workload/run.moicFu/evidence`,
with source `d25c9a10054053ff886b86bfe5a5dbe20e392819`, `sourceDirty=true`,
72 measured calls, 56 durable measured mutations, committed index 92 and application
sequence 340. Production core/replication JAR hashes and the workload plan digest
remain unchanged. A new passing protected PR and exact-master CI are still required.

### Exact-master acceptance

[PR #162](https://github.com/patricklfdm/GeneralSearchEngine/pull/162) merged the
correction as `a885bc7789a332525d3c375635ce35ce7bc15dec`.
[Exact-master CI 35069706211](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35069706211)
passed all six jobs and executed the full workload gate. This accepts the runner
preset/local qualification and closes the historical CI blockers above.
The next implementation is [remote workload execution and evidence](PHASE_6_REMOTE_WORKLOAD.md).
