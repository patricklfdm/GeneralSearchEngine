# V5.1 Phase 4G: public two-source reclamation

**Status:** local qualification passed. Protected Batch G
and complete Phase 4 acceptance remain open. [Batch F](PHASE_4_PUBLIC_PROTOCOL.md)
is accepted through PR #197, master `764cbf4a41bd6afc79e39cb3f97e612a3d66d39d`,
exact-master CI `35591386329`.

## Public execution boundary

`scripts/verify-v51-phase4-public-reclamation.sh --skip-build` compiles an external
consumer against candidate JARs. Bootstrap, startup, atomic bulk writes, strong
reads and close use public APIs on three real TCP voters. The observer only drops
actual source-exchange traffic, captures bytes at existing serialized storage
hooks, and halts a worker or exposes the point for controller SIGKILL. It does not
call private activation, checkpoint, floor establishment or cleanup methods.

Each fresh scenario first blocks every peer SOURCE_OFFER/SOURCE_CHUNK exchange.
Three tagged writes and a strong read still succeed, but the observed interval
must contain actual source drops and no floor publication or physical retirement.
After healing, maintenance obtains a complete second source through the protocol.

## Twelve interruption cases

Each boundary runs with both `Runtime.halt(71)` and SIGKILL:

| Boundary | Required retained state |
| --- | --- |
| FLOOR_BEFORE_WRITE | The earlier durable floor and both of its sources remain authority; the new pending marker does not exist yet. |
| FLOOR_AFTER_FORCE | The new marker is completely forced in the pending file, with matching source copies; the earlier published floor remains authority. |
| FLOOR_BEFORE_ACK | The new floor has been atomically published and directory-synced, with both exact source inventories available. |
| DELETE_AFTER_FILE | The first inactive-generation file is gone; every remaining old file equals the durable retirement inventory. |
| DELETE_AFTER_DIRECTORY | All inactive-generation files and their directory are gone; complete retirement evidence still binds the removed data. |
| DELETE_AFTER_ROOT_TRUNCATE | A nonempty root acceptance journal becomes its original header; the root proof journal has not yet crossed its truncation boundary. |

The root truncation cases interrupt the first reclamation so the operation removes
real journal rows. Other cases follow an earlier completed floor/cleanup and then
advance the application through another acknowledged write. A fresh read may
remain pending at interruption; uncertain mutations are never replayed.

Every crash retains the exact requested/observed boundary, PID, generation, exit
code and a hash-verified pre-reopen archive. After public restart, a second leader
is stopped so the recovered disk must participate in a subsequent majority. The
group reads all acknowledged data, acknowledges more writes, and the recovered
voter must advance its floor using a new download in the reopened process. Each
case uses five voter JVM instances.

After restart, a role hint can race a higher ballot. The controller retains every
read rejection and permits at most four fresh read attempts for a stable result.
It never replays a write. These rejected reads remain part of the bounded history.

## Selection during interrupted retirement

The public matrix exposed a runtime defect when the recovered voter immediately
joins another election before its old generation is reclaimed. Adopting a newer
selected prefix attempted to overwrite the occupied inactive slot; the store
correctly rejected that write, but the protocol then quarantined the voter.

Selection adoption now checks generation capacity before installation. A candidate
abandons that campaign with capacity pressure; an INSTALL recipient rejects the
request with `CAPACITY_EXCEEDED`. Both preserve their retained authority and remain
available for normal two-source recovery and later elections. Equal-prefix
adoption still avoids a rewrite. Actual storage/integrity failures keep their
existing failure behavior. No floor is synthesized and no unqualified generation
is deleted to make room.

Two deterministic regressions cover the lagging candidate and INSTALL recipient.
Both failed against the previous implementation with `FAILED`. They require
unchanged generation bytes before authorized retirement, a retained higher
promise, and successful later activation preserving the newer selected prefix.
The public matrix retains the immediate second-failover schedule that found the
defect, rather than waiting for cleanup before allowing that election.

A second pair of regressions covers interruption after directory deletion and
after root-journal truncation. An absent directory is still reserved while
`transfer/retiring` remains: reusing it early can make the old retirement inventory
refer to a new generation. Generation admission now waits until normal cleanup
finishes and removes that inventory. Identical snapshots remain reusable without
a rewrite. Both regressions first failed on the earlier admission check, then
require safe rejection, successful cleanup, installation and retained reopen.

## Independent evidence and negative checks

The inherited history and physical oracles still check client intervals, actual
entry/proof quorums, frozen selection, canonical application bytes and fresh read
barriers. The additional reclamation oracle verifies:

- Two complete source packets with different owners, including the local voter,
  exact generation/snapshot digests and the same application/history cut.
- A complete, hash-bound peer download before each floor publication in the same
  process; copied descriptors or a download in an earlier JVM are insufficient.
- Pending versus published floor identity and unchanged pre-reopen bytes.
- Current-generation and promise-history preservation during deletion, exact
  inactive-file deletion progress and complete durable retirement inventory.
- Every retired acceptance/proof at or below the durable floor, with retired
  proof identities matching the retained snapshot.
- A new floor publication and source download after retained restart.

Negative variants remove download chunks, durable-floor observations, crash or
restart records, and corrupt or duplicate source material. Unit fixtures cover
missing files, swapped ownership/selector, pending-only markers, downloads from
the wrong process or time, incomplete downloads and tails above the retirement
floor. Both successful and failed case evidence is always retained by CI for
fourteen days.

## Coverage and remaining work

This batch extends E07/E08/E09 and I07 with public floor/deletion interruption and
retained recovery evidence. It preserves the original scope of internal Phase 2/3
qualification. Conflicting/ambiguous selection, capacity/promise exhaustion,
mixed-mode/wire/disk rejection and the remaining E11/E12 public mapping remain
open. This batch does not authorize Phase 5, cloud execution or publication.

## Local validation

Validation on base `764cbf4a41bd6afc79e39cb3f97e612a3d66d39d` plus this working
tree, 2026-09-21. Local results do not constitute protected Batch G acceptance.

| Check | Result / retained evidence |
| --- | --- |
| Targeted reactor package | 68 Java tests passed across protocol, automatic recovery, runtime, rejoin/witness, wire and checkpoint coverage; includes four new regression invocations. |
| V5.1 Python discovery | 102 tests passed, including 12 reclamation-oracle regressions. |
| Public reclamation matrix | All 12 cases passed; 60 JVM instances, 70 acknowledged atomic writes, 132 rejected negative variants. Receipt: `target/v51-public-reclamation/run.9sLTWT/evidence/receipt.json`. |
| Public protocol/recovery regression | All 11 cases passed: `target/v51-public-protocol/run.3FUxuj/evidence/receipt.json`. |
| Internal transition kernel | Passed: `target/v51-protocol/run.ytf6Hd/evidence`. |
| Internal real TCP/rejoin regression | Passed with five JVMs and all seven rejoin negatives rejected: `target/v51-rejoin/run.3znteH/evidence/receipt.json`. |
| Documentation and CI wiring | 29-document contract, changed Markdown links/anchors, workflow retention, executable shell entry and whitespace checks passed. |

Candidate JAR SHA-256:

```text
f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d  general-search-engine-5.1.0-SNAPSHOT.jar
c43a9088e99929faf8a2b8a7266967c27887a325926be3e1a6916a108a770ed4  general-search-engine-replication-5.1.0-SNAPSHOT.jar
```

The final process gates retain source inventory SHA-256
`3a4a36557ea52ddedc1775de1f119d13ba751fa6f3c10d06d59dc838616c623a`;
the public reclamation receipt is
`c822d7f1fe895f63b9fcf1ee60313f640475deda8c7c7d4a55792bc9b56b50bf`.
The source inventory predates this final documentation reconciliation; all Java,
Python, shell and workflow bytes used by the matrix match the final implementation.

Earlier diagnostic runs `run.gpWl7C`, `run.RADXKp` and `run.bppvtr` remain retained
with their failures/interruption records. They exposed the observer encoding issue,
generation-slot pressure and restart timing; they are not counted as passing runs.
The two candidate/recipient regressions and two interrupted-retirement admission
regressions also retain failing-before/fixed-after local test logs.
