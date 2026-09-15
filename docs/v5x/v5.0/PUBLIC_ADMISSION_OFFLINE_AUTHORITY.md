# V5.0 public-admission Step B offline authority

- **Status:** Implementation candidate; protected PR and exact-master acceptance pending
- **Branch:** `feat/v5.0-offline-authority`
- **Starting master:** `855cfde29f3538121fa711e840f8701ded68c6a9`
- **Predecessor:** [Step A, PR #153](https://github.com/patricklfdm/GeneralSearchEngine/pull/153), [exact-master CI 35006998165](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35006998165)
- **Contract:** [Public admission](PUBLIC_ADMISSION_CONTRACT.md), [ordered acceptance plan](PUBLIC_ADMISSION_ENTRY_PLAN.md), [frozen 1.1 bytes](PUBLIC_ADMISSION_FORMAT_1_1.md)

## Delivered behavior

The core builder now captures its complete schema, canonical fields and text fields,
startup indexes, snapshot settings and planner settings without starting an engine.
`newBuilder()` restores that capture. Offline backup import reads a bounded, verified
V4 bundle without modifying its source. Export preserves the supplied history,
application sequence, live-document order and active indexes and uses the existing
V4 backup publisher. The materialization directory is only an exclusion anchor;
these operations do not open a V4 WAL or create another authority there.

Typed bootstrap implements `EMPTY` and all three supported V4 backup formats.
Planning binds the complete application/configuration, filesystem parents, source
inventory, genesis and all three local output inventories. Apply recomputes the
plan, acquires exclusive owners and prepares all three nodes before publishing a
single global receipt. It forces the COMMITTED row before delivering local seals.
No preparation can be opened by the historical 1.0 store as an initialized voter.

Exact resume checks complete records and known partial-file prefixes. Before
COMMITTING it revalidates the original source; afterward it uses the retained plan
and complete owned preparations, so loss of the source does not undo a decision.
It never recreates a lost prepared node or overwrites altered committed evidence.

Cleanup accepts only proven pre-commit attempts and an exact inventory-bound plan.
It forces ABORTING before deletion, protects the source, rejects unknown/changed
members, and retains its deletion authority until the original plan, journal and
ownership file have been removed. The cleaner holds the retained-record lock before
unlinking the original lock, so a second process cannot enter during that transition.
A partial deletion must be the exact authorized
prefix. Ambiguous remnants, including loss of the last cleanup record before the
coordinator directory disappears, fail closed rather than authorizing inferred deletion.

Replacement uses an intact, closed, exclusively owned source, verifies its genesis,
receipt and retained ancestry, and installs the approved identity with origin 1 and
`rebuilding.gsr`. It remains a non-voter and publishes no new group decision. Runtime
catch-up, leader recovery from two surviving peers and subsequent voting are Step C.

The public replicated builder and legacy bootstrap overloads still fail before
side effects. There are no new public descriptors beyond Step A, no changes to its
historical fixtures, and no Phase 6/cloud admission in this PR.

## Implementation and review map

| Files | Responsibility |
| --- | --- |
| Core `SearchEngineBuilder`, `SearchEngineConfiguration`, new `DurableApplicationTransfer` | Capture and bounded typed transfer |
| Core `DurableCheckpoint`, `DurableBackupWriter` | Shared canonical encoding and existing atomic backup publication |
| `AdmissionFormat`, `AdmissionConfiguration`, `AdmissionPlan`, `AdmissionJournal` | Frozen 1.1 records, complete descriptors, inventories and journal transitions |
| `AdmissionPaths`, `AdmissionIo` | Filesystem identity, exclusive ownership, force/rename and package-private test barriers |
| `AdmissionBootstrap`, `AdmissionCleanup`, `AdmissionNode`, `AdmissionReplacement`, `ReplicationStorageOperations` | Synchronous offline authority, inspection and public delegation |
| `V50ApplicationTransferTest`, `V50OfflineAuthorityTest`, `V50OfflineRejectionsTest`, `V50OfflineFixtureAgreementTest` | Configuration, transfer, recovery, rejection and production/frozen-byte agreement |
| `OfflinePublicConsumer`, `OfflineApplication`, `AdmissionSemanticModel`, `AdmissionV44Control`, `V50OfflineCrashWorker` | Test-only public consumers, separately compiled published control and owned-process barrier coordination |
| `scripts/v50/offline_format.py`, `test_offline_format.py`, `offline_harness.py` | Independent actual-file inspection, negative oracle tests and real SIGKILL matrix |
| `scripts/verify-v50-offline-authority.sh`, `.github/workflows/ci.yml` | Executed Step B gate and always-uploaded evidence |

`ReplicationBootstrapPlan` and the storage facade Javadocs describe typed apply.
The declaration test now checks enabled core capture and reserved legacy/runtime
entry points. The test-only JSON helper accepts integer report fields and supports
the production-reader agreement test. Step A's evidence label points to the separate
offline gate. Documentation entry points record PR #153 acceptance and this candidate.

## Independent evidence

`scripts/verify-v50-offline-authority.sh` builds the reactor; `--skip-build` requires
current production JARs and successful Java reports newer than their source files.
The harness compiles a consumer outside the replication implementation package
against those two production JARs. Its fault worker only installs a barrier and
delegates the actual operation to public APIs.

The published control is separately compiled against the exact V4.4 core JAR:

```text
0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5
```

Every interrupted JVM has its PID, arguments, barrier and SIGKILL exit code retained.
Before Java resume, Python archives the actual authority bytes and records their
hashes, then checks them without a product decoder or repair. The receipt binds
HEAD, the working diff, tracked/untracked source inventory and both candidate JARs.
Failures retain the same workspace and a failed receipt. CI always uploads
`target/v50-offline-authority` and Required depends on the executed reactor job.

The matrix includes 50 bootstrap cuts (including each pending seal and rename),
36 cleanup cuts, 17 replacement cuts and three published-source semantic cases.
Each source format is exported to all three output formats and restored by V4.4:
9 round trips compare document order, sequence, indexes, structured/text queries,
bit-exact rankings, phrase/fuzzy results, pages, explanations and highlight spans.

## Validation and acceptance

| Gate | Local result |
| --- | --- |
| Final reactor | PASS; 693 tests, 689 passed and 4 pre-existing opt-in skips; no failures/errors |
| Frozen Step A agreement | PASS; 5 positive + 48 negative independent byte cases, exact API inventories |
| Actual offline authority matrix | PASS; 106 cases: 50 bootstrap + 36 cleanup + 17 replacement cuts and 3 source-format cases (9 V4.4 round trips) |
| Phase 1–5 regression | PASS; Phase 4: 17 process + 6 corruption cases; Phase 5: 16 hardening cases |
| V5 Python + CI classifier + V4.4 release fixtures | PASS; 86 + 14 + 6 tests |
| Published compatibility | PASS; api-compat and artifact-compat including exact approved core delta |
| Independent V1–V5 consumers | PASS against installed artifacts |
| Release artifacts and reproducibility | PASS; nine JARs, no test assets, byte-identical across two clean release builds |
| Workflow/shell/documentation | actionlint, shell syntax, local links and whitespace checks pass |

The process harness compiles its public consumer and fault coordinator into separate
evidence directories; it does not depend on Maven test-class output. Final logs are
`/tmp/gse-offline-final-reactor.log`, `/tmp/gse-offline-final-matrix.log` and
`/tmp/gse-offline-final-phase-regression.log`. Compatibility and reproducibility logs
use the same `/tmp/gse-offline-` prefix. Earlier development evidence is retained at
`/tmp/gse-v50-offline-authority-evidence`. The accepted local Phase 1–5 run and its
raw workspaces were preserved in `validated-before-lock-hardening.tar.gz` before
the final clean rebuild. The final offline receipt is `target/v50-offline-authority/run.PEM2qu/evidence/receipt.json`;
its 106 cases pass against the final candidate JAR hashes. A copy of the complete
final offline/foundation evidence and Java reports is retained in
`/tmp/gse-v50-offline-authority-evidence/final-offline-evidence.tar.gz`.

Local evidence does not substitute for the protected PR or subsequent master CI.

- [x] Step A protected merge and exact-master CI verified before implementation.
- [x] Core transfer and typed offline implementation supplied against frozen bytes.
- [x] Complete local regression and packaging gates recorded.
- [ ] Protected Step B PR merged.
- [ ] Step B exact-master CI passed with the offline and Phase 1–5 gates executed.
- [ ] Step C public runtime begins after those two acceptance receipts.
