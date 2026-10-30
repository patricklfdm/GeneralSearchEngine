# Independent service replay after heterogeneous discovery

Phase 3 remains **OPEN**. This reader completes the service portion of the
retained five-to-four native history previously inspected through installation.
It reuses the original successful `V53DiscoveredTransitionTest` execution; no
Java workload, timing retry or cloud experiment is run again for this batch.

## Authority and physical history

`scripts.v53.discovered_service_evidence` derives the bootstrap, seven preparation
slots, both adoptions, ballot 4 and the installation of nodes 1, 2 and 4 using
the existing independent readers. It also checks all 262 preparation calls,
their owners and order, and the required durable force boundaries.

From those installed originals it independently constructs BARRIER 8 and DATA 9:

- Complete copied floors, peer-ledger revisions and inactive-generation
  retirement before each new slot.
- Exact entry, ACCEPT, PROOF, certificate, applied-end and checkpoint records.
  DATA 9 must contain document 207, `discovered-survivor`; its retained image
  must decode to that document, original history, codec and sequence.
- Two future-retention recording rounds per slot, including exact per-owner
  frames and previous hashes, both recording majorities, publication, ledger
  promotion and future-state clearing.
- Every file and directory of all five final owners. Nodes 1, 2 and 4 reach cut
  9; unselected node 3 and removed node 5 remain at their original cut 7.

There are 56 independently matched physical snapshots. Intermediate BARRIER/DATA
states are derived in memory and checked against their original transferred
bytes and final inventories; no missing on-disk snapshot is manufactured.
The shared publication readers expose two overridable fixture expectations
(documents and checkpoint voters), retaining their previous defaults.

## Network and readiness

The service portion consumes 96 complete source-transfer traces and 499 wire
exchanges. Sources must arrive before the dependent floor, vote, proof,
certificate or checkpoint publication. Control messages bind permanent owners,
ballot, view, payload, trace and sequence. Each publication must reuse its own
future-recording trace; separate transfers and ordinary controls cannot reuse it.

Offered responses alone do not count as delivered replies. All 635 retained wire
responses are assigned to the two adoptions, installation, BARRIER or DATA;
all 620 received-response events require a preceding original offer. Up to three
byte-identical attempts may complete an exchange. Additional attempts, altered
replies, unclassified exchanges and foreign delivery events are rejected.

Both recording majorities must complete before any publication send. Remote
publication completion precedes local publication, and the exact local
completion precedes readiness. The only `ROUND_BEFORE_READY` must follow the
fresh BARRIER 8 and carry its exact completed publication record. This is private
round readiness, not acceptance of a public API or autonomous election service.

## Evidence and limits

The [source-bound receipt](phase3-evidence/discovered-service.json) retains the
unchanged native evidence, exact reader inputs, qualification results and logs.
Thirty-two new mutations cover final storage, original preparation, source
contents and delivery, retention majorities, publication, readiness, bounded
attempts and scope claims. Thirty-three focused Python tests also pass. An
initial mutation probe exposed two test-expectation issues: the layout rejection
message differed, and a source mutation selected an offer rather than a data
chunk. Both were corrected; those exploratory results remain retained.
The first full qualification passed all mutations but its local receipt writer
then rejected a relative path. That result and wrapper error are retained; the
corrected wrapper repeats qualification before recording source hashes and time.

The result is `PASS` only for `single-native-5-to-4-service-history`.
`phase3Complete`, `autonomousElection` and `publicRuntime` remain false. Earlier
scoped readers keep their PARTIAL results and historical limits. This completes
independent replay of this one retained successful service path, not the seven
membership profiles, process crash cases, automatic scheduling or Phase 3 gate.
The previous producer's timing margin and failed earlier runs remain unchanged.

The original log contains 30 rejected calls on node 3, grouped into ten bounded
exchanges. Their node, kind, request digest, exact diagnostic and attempt count
are checked, but their request bodies were not retained. These diagnostics
therefore grant no voting, floor or retention authority, and do not independently
prove failed-request payload semantics. The successful path derives all required
authority from the three original participating owners.

Replay with:

```bash
python3 -m scripts.v53.discovered_service_evidence /path/to/original/run --qualify
```

Rollback removes the new reader, negatives and tests and restores the two
private expectation hooks. Runtime Java, formats, limits, POMs, workflows and
original evidence are unchanged.
