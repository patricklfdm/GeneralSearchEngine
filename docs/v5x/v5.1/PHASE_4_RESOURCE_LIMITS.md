# V5.1 Phase 4L: resource limits and public budget isolation

**Status:** Batch L accepted through PR #203 at master
`a5595f8efad34ec96a3f6e883e5c9c9491004279`, exact-master CI `35712922357`,
with all eleven full-CI lanes and Required passing. Complete Phase 4 remains open. [Batch K](PHASE_4_PUBLIC_PRESSURE.md) is accepted through
PR #202 at master `3bb84b250800c7871745450491e56b6821195d1d`, exact-master CI
`35705020751`; all eleven full-CI lanes and Required passed.

## Scope and evidence layers

`scripts/verify-v51-phase4-resources.sh --skip-build` runs six internal boundary
fixtures and two public runtime scenarios in distinct fresh directories, with
separate execution identities, candidate hashes and source inventories. It never
labels an internally constructed storage fixture as public bootstrap or election.
The [current E01–E12 map](PHASE_4_EVIDENCE_STATUS.md) records the remaining gaps.

### Six internal boundary cases

`resource_harness.py` compiles `V51ResourceWorker` against packaged candidate JARs
and existing test fixtures. Each case runs in its own JVM, archives the exact
node directory before a second JVM reopens it, and independently checks all retained
records. Test-only setup supplies a sealed storage fixture, not a public cluster.

| Case | Boundary and acceptance |
| --- | --- |
| `promise-count` | Force 9,999 new, ranked promises after genesis, reaching the real 10,000-row limit. Reject the next grant, allow an identical last-grant re-force without appending, and preserve count/epoch across reopen. |
| `retained-bytes` | Set the local retained bound to initial authority bytes plus exactly one valid grant. The grant fits; the next fails before write. An exact retry and a separate reopen preserve all bytes. |
| `transfer-staging` | Begin a transfer whose advertised full image is 128 KiB. Existing authority/metadata consumes part of that staging budget, so even a one-byte first chunk must be refused before data or progress writes. Reopen retains the zero watermark and existing authority. |
| `entry-count` | Reject an ACCEPT naming slot 1,000,001 before append, preserving the store and its promise. This does not fabricate a million-slot committed history. |
| `ancestry-count` | Reject a compact fixture expanded to 1,000,001 snapshot anchors at schema admission. It proves the over-count rejection, not that one million anchors fit the record/JSON byte and value budgets. |
| `epoch-overflow` | Persist the maximum signed 64-bit promise, then compare all three rank calculations at three near-maximum observations with the independent integer model. Representable results must match exactly; exhausted ranks return capacity failure without wraparound or reset. |

No fixture raises production constants. The entry and ancestry counts are distinct
limits. Byte limits and the shared JSON value budget can bind before the ancestry
count limit; this suite makes no usable-history-size or performance claim.
A process-local capacity failure is not evidence of physical disk exhaustion.

### Two public runtime cases

The external consumer uses public EMPTY bootstrap and seals either a **128-KiB
staging** or **128-KiB retained-byte** limit on node 3. Nodes 1/2 retain 64-MiB
budgets. Chunk size stays 4096 bytes, request timeout 1200 ms, and the Batch I/K
fixture election policies remain sealed. PREPARE request loss initially keeps
node 3 out of the selected write quorum, then the controller removes that rule.
No controller supplies an epoch, vote or activation.

All three public JVMs start normally. Three small tagged atomic bulks and a strong
read establish a prefix that node 3 must recover before pressure begins. A larger
public bulk then drives normal replication/recovery beyond node 3's budget.
The actual failed admission calculation is observed inside the serialized storage
operation, with its budget, limit, existing/replaced/requested bytes and a hashed
file inventory. The independent oracle verifies the sealed limit, inventory sum
and `requested > limit - retained + replaced`. The existing write/transfer
staging check conservatively charges the whole authority inventory, including
root metadata and generations; it is not just the size of the transfer directory.

The exhausted voter may become FAILED and must reject its public write/read calls
with conservative `NOT_SUBMITTED` / `NOT_APPLICABLE` outcomes. The healthy two-voter
quorum must acknowledge another bulk and strong read after the rejection. The
controller archives node 3, reopens its retained directory without changing the
sealed budget, and obtains another healthy-quorum read. It also restarts the leader
and requires subsequent strong-read recovery. Restart is not claimed to restore
service on the exhausted voter, and no authority is deleted to manufacture space.
Independent retained-prefix, raw force/quorum and client-history checks cover every
acknowledged bulk and exact read projection.

## Internal observation seam

`AutomaticStore.Faults` gains a package-private, default no-op `capacityRejected`
callback. `AutomaticRecoveryFiles` invokes it immediately before the existing
write/transfer capacity rejection. The comparison values, evaluation order,
exception reason/messages and capacity behavior remain the same. This observation
captures the first local recovery failure; a later wire response may only report
that the already quarantined store is unusable.

The test observer records actual file sizes/hashes while the store operation is
serialized. It does not change budgets, return an admission decision, supply data
or issue a retry. Production APIs, formats, constants, dependencies and versions
are unchanged; the added internal hook changes the replication JAR hash.

## Negative checks and CI

The oracle rejects missing capacity observations/restarts/later reads or writes,
forged occupancy, changed archives and successful calls attributed to the exhausted
voter. Existing history/physical negatives reject stale/partial/reordered reads,
borrowed barriers and missing proof forces. Internal negatives reject wrong failure
classification, changed limits, cleanup used to create room, missing epoch ranks,
wrong ranked successors and integer wraparound.

CI runs the gate in `v51-foundation-admission` and always retains
`v51-resources-${{ github.sha }}` for fourteen days. Existing verification steps,
eleven required lanes, documentation-only routing and paid-cloud behavior remain
unchanged. No cloud run or publication is part of this batch.

## Local validation

Base: `3bb84b250800c7871745450491e56b6821195d1d` plus this batch.

- Complete gate: `target/v51-resources/run.OnntmU/internal/receipt.json` and
  `target/v51-resources/run.OnntmU/public/receipt.json`, all six internal and two
  public cases passed. The public cases retain 22 application calls across ten
  runtime process identities. All 46 evidence-negative variants were rejected.
- Final review rechecked all eight retained cases with archive and capacity-context
  binding: `target/v51-resources/final-oracle-review.json` records receipt and final
  oracle source hashes.
- Targeted reactor package passed all 60 storage/recovery/protocol Java tests in
  `target/v51-resources/build-observer.log`. This is not a full local reactor run.
- Shared observer/configuration regression: Batch K `outbound-saturation` passed in
  `target/v51-resources/shared-pressure/receipt.json`; the complete existing public
  runtime gate passed in `target/v51-public-runtime/run.wpwFqZ/evidence/receipt.json`.
- All 177 V5.1 Python tests, including fifteen new resource-oracle tests, and 25
  CI/toolchain tests passed. YAML, 102 shell blocks, 31 unique artifact names,
  unchanged existing CI steps/required jobs, the historical 87-step map, the
  35-document contract, local links and whitespace checks passed.

Candidate JAR SHA-256:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `a00af22cb868218816bdb4c6f2476445be2a0b90b0c42ed5b6d6772adaad6bd7`.

Exploratory failed fixtures remain retained under `target/v51-resources`. They
identified illegal fixture chunk sizing, rejection observation after quarantine,
and a helper which treated the intentionally failed minority as whole-group
failure; the final scenarios observe the actual resource boundary and keep that
minority's rejection evidence. Existing runtime evidence also requires basis
transfer, supplied by the retained leader restart. Source inventories describe
execution-time files; final documentation and stricter oracle review followed.
Each protected CI lane retains its full reactor build/tests. The acceptance update
above records the subsequent hosted result.
