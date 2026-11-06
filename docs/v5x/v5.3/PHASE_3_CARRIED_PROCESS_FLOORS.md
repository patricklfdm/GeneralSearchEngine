# Phase 3 — carried-process FLOOR file prefixes

Phase 3 remains **OPEN**. This component adds original complete-copy FLOOR
creation and release bytes to the
[retirement-prefix process histories](PHASE_3_CARRIED_PROCESS_PREFIXES.md).
It covers the same INTENT/ACCEPT-rename halt and FINAL/PROOF-rename SIGKILL cases,
including whole-group death and successor completion on the original directories.
It does not claim a crash inside a FLOOR write, full transient-storage composition
or whole-runtime resource acceptance.

## Collection and identity

The [native fixture](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedFloorPrefixProcessTest.java)
retains an outer wrapper with `prefixes/` (the unchanged original history,
resource and retirement layouts) and `floors/life-1/`, `floors/life-2/`.
The existing writer-held file recorder has a separate floor-only mode with its
own capture and collection schemas. Existing default retirement formats remain
unchanged. The optional resource observer supplies the same original event
indices, PID, root, lifetime, event digest and terminal state to both recorders.

Each persistent FLOOR callback captures the complete replica inventory and actual
file bytes, including empty directories. Creation begins at `FLOOR_RESERVED` and
ends at `FLOOR_BEFORE_RETURN`. Release begins at
`FLOOR_RELEASE_AUTHORITY_CREATED` and ends at `FLOOR_RELEASE_BEFORE_RETURN`.
Transactions cannot overlap or finish with an incomplete active capture.
`FLOOR_COPY_BEFORE_RETURN` describes an original-copy observation and is not a
local FLOOR write; its authority and transport remain checked by the existing
original-history chain. It is excluded only from this file-write collector.

The first child retains **CUT_PREFIX** before the parent's death acknowledgement;
it supplies no post-cut bytes or normal-close claim. A cut before any FLOOR
transaction must retain an explicit empty collection, whose absence of callbacks
is checked independently. The successor may record **CLOSED** only after actual
owner closes and drained resource accounting. Collection bounds remain 2048
captures, 512 files per replica, 64 MiB per file and 256 MiB of objects/metadata
per child. This file observation adds test I/O, not performance evidence.

## Independent expectations and refusal

The [reader](../../../scripts/v53/native_carried_floor_prefixes.py) first requires
the complete original retirement/resource/process/storage/network/export/FLOOR
authority/continuous-ledger chain. It then derives every creation prefix from
the original selected copies, canonical FLOOR authority, file-write positions and
directory-creation positions. The existing release reducer derives the exact
release authority and successive file/directory removals. Expected inventories
come from those original inputs, never from the new captured objects.

Every child-local callback index must occur exactly once in both the independent
plan and the capture set. The shared bounded decoder checks schemas, original
identity/event bindings, object hashes and sizes, complete layouts, owner records
and declared callback kinds. Full replica inventories are compared, including
the files outside `floor-copies/`. Force callbacks retain the same expected bytes
as their preceding write; original callback ordering remains separately required.

FLOOR creation retains the original pre-reconciliation `peer-retention.gspr`.
The runtime persists the changed-view ledger only after `FLOOR_BEFORE_RETURN`,
before retirement. The continuous ledger replay independently requires that
ordering. The initial new file-prefix projection used the later ledger too early
and rejected 292 INTENT captures, all differing only in this file. Correcting the
projection preserves the runtime and the original evidence; a focused regression
checks this phase boundary. The failed reader output and byte-difference report
remain retained alongside the corrected replay.

Qualification first validates the unmodified complete original. It then mutates
only disposable copies of the FLOOR sidecars, holding the original history and
independently derived plan fixed. Generic identity/object/coverage mutations and
targeted proposal, generation, image, handoff, early authority, release authority,
early/late deletion, premature relinquishment, leftover-directory and unrelated
journal mutations must each fail for their exact declared reason. Unrelated
failures earn no negative credit. Original inventories are checked again afterward.

## Development evidence

The [development index](phase3-evidence/carried-process-floor-prefixes.json)
binds the original inventories, producer sources/classes, reader sources, logs
and qualification receipts. Both native JVM pairs pass without retries. Their
2479 FLOOR inventories match the independent transaction states, composed with
1572 retirement inventories and the complete original prerequisite chain. All
54 targeted mutations reject for their exact declared reasons.

| Original | First child | Successor child | Total FLOOR prefixes |
| --- | --- | --- | --- |
| FINAL / PROOF rename / SIGKILL | 102, CUT_PREFIX | 896, CLOSED | 998 |
| INTENT / ACCEPT rename / halt | 0, CUT_PREFIX | 1481, CLOSED | 1481 |

The focused Java suites pass twelve tests; the separate native suite passes two
tests. The related Python suites pass 418 tests, with 62 boundary tests also
passing under optimization. The existing default force receipts remain identical
when the new optional prefix projections are enabled. The earlier retirement-only
originals retain their exact receipts; no historical index is rewritten.
Both complete originals also replay from relocated directories under Python
optimization, producing receipts identical to their original qualification.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedFloorPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_floor_prefixes \
  general-search-engine-replication/target/v53-native-carried-floor-prefixes/run-<id> \
  --qualify
```

Original grant/installation/vote/application transient bytes, core scratch,
combined physical/accounting maxima, six other carried-process cuts,
application-ACK recovery and final-source cohort admission remain pending.
The twelve hosted subsets and frozen workload counts are unchanged. Receipts
remain **PARTIAL**, with `transientFloorBytesQualified=true`,
`fullTransientBytesQualified=false`, `postCutTailObserved=false`,
`wholeRuntimeResourcesQualified=false`, `cohortAdmitted=false` and
`phase3Complete=false`. This component changes test and reader code, not the
runtime protocol, configured limits, workflow or paid-cloud behavior.
