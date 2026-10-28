# Phase 3 implementation and deferred hosted acceptance

The operator authorized deferring expensive complete qualification on 2026-10-28.
Implementation continues on the local branch, with focused checks before each
commit. Phase 3 remains **OPEN** until the complete
[entry checklist](PHASE_3_ENTRY_PLAN.md) has its original required evidence.
This file is an acceptance queue, not an executed workflow or acceptance receipt.

## Current learner-store queue

| Gate | Unit of execution | Required final evidence |
| --- | --- | --- |
| `V53LearnerStoreTest` and preparation tests | Focused component suite | All assertions on the final source; explicitly conditional historical fixtures do not become native distributed evidence |
| `V53LearnerStoreRevalidationTest` | One actual TCP history | Normal original installation, disconnect, reopen and unchanged-byte refusal; independent original-first review reader |
| `V53LearnerStoreNetworkTest` | Twelve independent whole histories: six cuts × halt/SIGKILL | Original native source, interrupted process, normal resume, locks, forces and exact physical bytes; all twelve required |
| Store negative qualification | Complete unchanged matrix first | Every declared mutation rejected for its exact reason, including portable optimized replay |
| `V53LearnerMaterializationTest` and native smoke | Focused typed backup and READY receipt | Exact original PREPARE image, actual core semantic decode, forced receipt, reopen and independent original-first replay |
| Typed learner process-death qualification | Independent complete native histories | Halt/SIGKILL at typed plan, backup and receipt cuts, fresh-process semantic reopen and unchanged refusals; not replaced by synchronous exception cuts |
| Prepared learner selection and refresh | Focused components and complete native two-revision history | Original selection forces, same-pool coexistence and authenticated successor, full original-first wire/physical replay |
| Prepared selection process-death qualification | Independent whole halt/SIGKILL histories | Partial marker recovery, conservative reopen, live owner revocation and unchanged original source; no component exception substitution |
| Successor lifecycle | One continuous original learner history | Install, select and retire bounded originals across revisions, cancellation and locally forced matching INTENT before votes |
| Final Phase 3 protocol audit | Complete prescribed scenarios | Learner ADD/REPLACE, all seven transitions, alternative-leader continuation and maximum combined resource bounds; component results cannot substitute |

The process test supports one exact whole case through the Maven system property
`gse.v53.learnerStoreCase`. With no property it executes all twelve. Empty, unknown
or misspelled selections fail before starting the history. Allowed names are the
six constants in `V53LearnerStoreNetworkTest.CUTS`, each suffixed `-halt` or `-kill`.
For example, from an isolated source checkout with Java 21:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53LearnerStoreNetworkTest \
  -Dgse.v53.learnerStoreCase=LEARNER_SOURCE_MOVED-kill test
```

The test prints its raw evidence directory. From that checkout's root:

```bash
python3 -m scripts.v53.learner_store_evidence RAW_DIRECTORY \
  --case LEARNER_SOURCE_MOVED-kill
```

The reader independently validates the complete selected history and reports
`PARTIAL`, never complete matrix acceptance. The ordinary reader without `--case`
still requires all twelve. `--case` and `--qualify` cannot be combined.

## Hosted campaign requirements

The eventual workflow must bind every artifact to one exact source and build,
pin Java and retain raw evidence, failed attempts and independently replayable
inputs. A missing/failed shard blocks aggregate acceptance; an unrelated original
failure must not count as a successful negative test. Process IDs from different
runners may coincide and must be scoped by execution identity. Each interrupted
and resumed process still belongs to the same original filesystem history.

Do not split a source acquisition from its installation, an INTENT from its FINAL,
or a crash from its restart across runners. Parallelism applies to independently
bootstrapped histories only. A future aggregate must validate the exact declared
set rather than merge pass counts. Workflow wiring and that source-bound aggregate
are pending; this change does not dispatch GitHub Actions, alter Required or touch
the V5.2 hosted/self-hosted experiment.

Earlier locally completed runs remain source-bound historical results. Long
matrices must be run against the final runtime before phase closure; neither a
short smoke nor an earlier source's green matrix proves that final requirement.
