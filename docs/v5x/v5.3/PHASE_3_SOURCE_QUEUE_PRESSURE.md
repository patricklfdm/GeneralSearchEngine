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
