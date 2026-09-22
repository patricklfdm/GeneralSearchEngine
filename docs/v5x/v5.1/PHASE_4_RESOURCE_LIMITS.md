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
public bulk then exercises the declared resource boundary. Following the Batch M
CI correction below, the two public cases intentionally observe different checks:

- `snapshot-staging` uses two documents with 10,000 bytes of padding each. The resulting real IMAGE
  exceeds the **32,768-byte transfer allowance**, one quarter of the sealed 128-KiB
  staging budget. The oracle requires the exact `SNAPSHOT_OFFER` / `REJECT` exchange
  with reason `CAPACITY_EXCEEDED`, matching ballot/peers/correlation and a response
  observed by the proposer. It independently derives the offered image size/digest
  from an actual published snapshot containing the load write, and rejects any
  observed chunk/install attempt for that refused transfer.
- `retained-bytes` temporarily isolates node 3 after its seed recovery, then uses
  two legal atomic bulks, each containing two documents with 20,000 bytes of padding each. The
  leader retains the final cut before the controller heals the minority. The full
  offered image exceeds the entire 128-KiB retained budget, so its first chunk must fail
  reservation regardless of cleanup timing. It observes the actual failed
  storage admission inside the serialized operation, including budget,
  existing/replaced/requested bytes and hashed inventory. The oracle verifies
  `requested > limit - retained + replaced`, `requested > limit`, and the inventory sum.

The internal `transfer-staging` fixture still checks full-image reservation against
existing authority. The write/transfer staging check conservatively charges the
whole authority inventory, including root metadata and generations. The public
snapshot case now proves the earlier transfer admission boundary; it does not
claim deterministic exhaustion of that later aggregate-write boundary.

A refused snapshot offer need not quarantine the follower; a failed retained write
may do so. The bounded voter must reject its public write/read calls
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

## Transport completion correction after PR #204

The resource gate failed again on merged master `0725df1c003be74fb2047f066586ea2e6f9b7bfa`
in [CI run 35722871682](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35722871682).
This time `snapshot-staging` passed. The retained-byte case recorded the expected
146,760-byte reservation rejection against 131,072 bytes, and the healthy majority
completed the subsequent write/read and the read after node 3 restarted. Failure
came after the original leader restarted: the healthy voters repeatedly abandoned
campaigns while fetching the roughly 148-KiB frozen basis in 4096-byte chunks.
Most observed downloads stopped before the final chunk; increasing the scenario
wait alone would not address the exchange admission race found during diagnosis.

`AutomaticTransport` completed an exchange future before its `finally` block
released the peer permit and queued-byte reservation. A continuation could submit
the next chunk while the completed exchange still occupied one of the two peer
slots. With another exchange in flight, this returned a spurious capacity rejection.
The transport now closes the socket and releases the reservation before publishing
either success or failure. Cancellation still retains capacity until the actual
exchange exits. Peer limits, byte limits, retry counts and all deadlines are unchanged.

A deterministic TCP regression holds both peer slots, attaches a continuation to
one exchange, then releases only that exchange. The continuation must successfully
send a third request while the other original request remains held. Both the
successful and exceptional completion variants fail on the old implementation
with `peer in-flight limit reached`; they exercise the release ordering without
depending on scheduler speed or a probabilistic stress loop.

This changes the replication runtime JAR. Historical qualification hashes below
describe their original executions; they are not evidence for the corrected JAR.
The resource workload, its capacity assertions and leader-restart requirement remain
enabled. PR #205 merged the fix at `39332feb71f877d3cbd976631e8a26a9cf2f607c`;
[exact-master CI 35753082195](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35753082195)
passed all eleven full-CI lanes and Required. This accepts the correction and Batch M;
full Phase 4 acceptance remains open.

Local correction validation on `a5098c872dfc2f0eff08cf335da8ff86599f07a9` plus the fix
(PR #204's merged master contains that source):

- `target/v51-resource-recovery-fix/transport-before.log` retains both expected
  regression failures on the original transport. The corrected reactor package
  passed 32 Java tests in `target/v51-resource-recovery-fix/build.log`.
- The complete resource gate passed all eight scenarios at
  `target/v51-resources/run.RwaZBy`, including the unchanged large retained-byte
  load and strong read after the leader restart. Both public receipts rejected
  all fifteen negative variants each; all six internal boundary checks also passed.
- All five public transport-pressure scenarios passed at
  `target/v51-public-pressure/run.ZFMGkU/evidence`, including cancellation while
  reservations are held, saturation and slow storage/peer recovery.
- All 47 resource, public-pressure and backpressure Python tests passed, along
  with the 36-document / 209-link documentation contract and whitespace checks.
- Corrected replication JAR SHA-256:
  `2ff8fae57f0ee0ce09f2aefe80cfdba294c6f3599eb45823fd5df4fb327a996e`.
  Core remains `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.

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

## Batch M CI correction: deterministic snapshot admission

CI run [35717163313](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35717163313)
failed the original `snapshot-staging` witness. Its retained artifact shows 33
successful offers of the 25,452-byte load image, no storage capacity rejection,
and a final inventory of 120,333 bytes, below the 131,072-byte budget. Background
floor/generation cleanup had allowed the image to fit. The original local pass
instead observed a transient aggregate write reservation above the limit. Waiting
longer does not guarantee that the latter schedule will occur.

This correction changes the test load and the inspected boundary, leaving all
production bounds, timeout values and rejection requirements intact. Both raw
capacity rejection and published-image provenance are mandatory. The original
Batch L receipts above remain historical observations of the earlier workload.
The retained-write case receives the analogous cleanup-independent load; its
serialized inventory/reservation oracle and all six internal resource cases remain
enabled.

Correction validation on base `9846269b27098786f079976e787bd6f82472e073`:

- Full eight-case gate passed at `target/v51-resources/run.19qKEo`; its unchanged
  six internal-case validations remain applicable. The subsequently strengthened
  public workloads passed at `target/v51-resource-ci-fix/final-public/snapshot-staging/receipt.json`
  and `target/v51-resource-ci-fix/retained-final/retained-bytes/receipt.json`.
- Final images were 39,668 bytes against the 32,768-byte staging transfer allowance
  and 146,760 bytes against the 131,072-byte retained budget. All 48 negative variants
  across the six internal and two final public cases were rejected. Exact receipt
  paths/hashes are indexed in `target/v51-resource-ci-fix/validation-summary.json`.
- All 196 V5.1 Python tests passed, including 23 resource-oracle tests. New cases
  reject the actual CI image size as an exhaustion witness, exactly fitting images,
  borrowed/mismatched replies, wrong reasons and incorrectly enlarged budgets.
- Production sources, JAR bytes, limits and timeouts are unchanged. The larger
  retained image is built with two admitted commands; an exploratory single larger
  command hit the existing frozen-basis metadata limit before the intended test.
  That failed fixture is retained rather than relabelled as a pass.

The original CI failure evidence remains at
`target/v51-resource-ci-fix/ci-35717163313/run.fkADvj`. No paid cloud run is involved.
