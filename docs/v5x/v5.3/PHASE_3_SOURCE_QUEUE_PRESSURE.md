# Phase 3 original SOURCE queue byte pressure

Status: **COMPONENT ONLY**. This adds a reachable aggregate CONTROL-byte boundary
and recovery observation. It does not close `combined-resources`, complete a
membership operation, or enable public READY. Phase 3 remains OPEN.

## Reachable pressure

`V53SourceQueueQualification` creates a public, verified-backup bootstrap with
three identities and a 4,229,992-byte application image. One actual journal owner
creates a frozen BASIS. Two other members use real loopback TCP to open six
SOURCE sessions, commit the original BASIS record and request the first 4 MiB of
the same original application image. Each session retains its own exact encoded
CHUNK response. These are real exporter/session/transport allocations in one
shared resource pool; the test never inserts capacity ballast leases.

The test repeats five of those exact CHUNK requests and holds their real
`BEFORE_RESPONSE_WRITE` callbacks. This is an explicit bounded test scheduling
barrier, not an assertion about ordinary production traffic. Five response-send
buffers now overlap the six source-response caches. A sixth identical request
reaches the handler and obtains the original cached reply, but its additional
send-buffer reservation exceeds the unchanged **67,108,864-byte** queue bound.
The server records CAPACITY and the client observes IO without a fabricated ACK.
The CONTROL count and individual frame size remain below their own limits.

Releasing the five callbacks drains actual send buffers. The sixth request then
succeeds with identical cached response bytes. Every session fetches the tail and
commits the complete original application content. Service shutdown drains all
CONTROL allocations, and owner shutdown drains the full observed pool. Authority
files remain identical to the captured post-BASIS state throughout.

An earlier development attempt tried eleven exports and was rejected when opening
the seventh, at the independent **six-export owner bound**. Its failed original
and log remain retained. That attempt is not queue-bound evidence. The corrected
scenario respects the existing export bound, per-peer in-flight capacity and
4 MiB chunk/8 MiB frame limits. The fixture reads its exported evidence in legal
4 MiB chunks to avoid thousands of unnecessary repeated source validations; no
runtime implementation or frozen limit changes.

## Independent evidence

`scripts.v53.source_queue_evidence` first reconstructs the original public
bootstrap, grants, source packet, complete exported bytes and unchanged final
storage. It then validates the complete retained frame inventory and checks:

- Six original reader/trace-bound sessions and all 42 unique protocol requests;
  49 actual attempts include five held duplicates, one refused duplicate and
  one recovered identical retry.
- Complete event ordering, exact identities, ballot, authority, correlation,
  offsets and payload bytes independently derived from the original content.
- All resource transitions, source-response extents, session/trace handles,
  source exports, actual transport receive/send allocations and checkpoint usage.
- Six live large caches plus five live large send buffers at the same pressure
  checkpoint, and the next exact response exceeding only aggregate queued bytes.
- Buffer release and terminal zero reservations. Unexplained CONTROL ballast,
  missing observations, unrelated errors and changed retry bytes reject.

The eight evidence negatives require their exact rejection reasons; the original
must pass before mutations begin. The reader supports relocated raw directories
without changing original plan paths or authority bytes. It does not qualify
network authentication, abrupt process death, time-to-recovery, every possible
concurrent schedule, full application/metadata/staging pressure, or FINAL under
that combined pressure.

Local receipts, source hashes, preserved failures and replay results are indexed
in [source queue pressure evidence](phase3-evidence/source-queue-pressure.json).
They are development component evidence, not a final-source cohort admission.
The existing twelve cohort subsets and 566 planned whole histories are unchanged.

## Explicit execution

The qualification is excluded from the ordinary `*Test` discovery pattern. Run it
explicitly on Linux with loopback sockets, Java 21 and the existing Maven reactor:

```bash
mvn -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53SourceQueueQualification -Dsurefire.failIfNoSpecifiedTests=false test
```

Use the newly printed `v53SourceQueueEvidence` directory; preserve failed runs:

```bash
python3 -m scripts.v53.source_queue_evidence /absolute/path/to/new/run --qualify
```

The focused reader checks are:

```bash
python3 -m unittest scripts.v53.test_source_queue_evidence \
  scripts.v53.test_source_control_resource_evidence scripts.v53.test_resource_transitions
```

This is a supplementary component entry. Adding it to a final source-bound
supplementary admission set and executing that set remain separate work; a local
PASS here must not be substituted for those cohort requirements.

## Source-bound component execution

`scripts.v53.source_queue_run` now provides a separate `capture` / `collect` /
`verify` boundary for the complete six-session original. `capture` copies source
into a new workspace, records actual Java/Maven binary identities and the reader
manifest, and runs exactly one named JUnit method once with offline dependencies.
It records the compiled classes, exact command and JUnit report, source-bound
collection subprocess and complete bounded raw inventory. Failure preserves the
workspace and FAIL receipt; it never substitutes a retry or a shortened case.

The producer and collector return **PARTIAL** with `queuePressureQualified=false`.
Only the independent verifier checks the explicit source/build/toolchain/reader
pins, unchanged compiled and original bytes, full physical/queue replay and all
eight exact negative results. Its success is `scope=source-queue-component-only`;
`combinedResourcesQualified` and `phase3Complete` remain false. Missing or
multiple originals, linked parents, altered commands/tools/classes, failed or
retried tests, counts-only results, mixed source or incomplete negatives reject.
A qualified component is still not FINAL under combined pressure. The original
and the later membership transition must remain within their governing history;
this entry does not splice separate PASS receipts into such evidence.

After dependencies are available locally, use new output directories:

```bash
python3 -u -m scripts.v53.source_queue_run capture \
  target/v53-source-queue-admission/producer \
  --profile source-queue-64mib --maven /absolute/path/to/mvn

python3 -u -m scripts.v53.source_queue_run verify \
  target/v53-source-queue-admission/qualification \
  --profile source-queue-64mib \
  --producer target/v53-source-queue-admission/producer \
  --pins target/v53-source-queue-admission/producer/pins.json
```

The existing executor emits a progress heartbeat each minute. Execute verification
with the recorded reader source; a newer checkout's reader must not stand in for
that source. Portable replay keeps original recorded paths and rechecks all
inventories. The [source-bound execution index](phase3-evidence/source-queue-admission.json)
records local validation separately from final-source admission. No new workflow
or cloud dispatch is enabled here. The twelve-subset catalogue and its 566 whole
histories remain unchanged; a future supplementary cohort must explicitly include
this component with matching final source and execution evidence.

The first immutable local execution passed in **37.254 seconds**, including its
fresh reactor build; the separate collector passed in **0.515 seconds**. The
original and packed/unpacked producer both passed verification from their own
recorded workspaces, with identical receipts and unchanged source, classes and
raw inventories. The two replays plus packaging took **20.635 seconds**. Twenty
orchestration/reader tests pass normally and under `python3 -O`; 19 documentation
checks also pass. The initial synthetic command test incorrectly treated `Retry`
in the required method name as a retry option; its failing log is retained, and
the corrected check still rejects actual retry/timeout/skip overrides. No native
execution was retried.

These local source manifests include development changes on base `30955ba6`.
They bind the actual immutable bytes but do not attest a clean final Git commit,
GitHub run/attempt, complete supplementary set or full Phase 3 qualification.
