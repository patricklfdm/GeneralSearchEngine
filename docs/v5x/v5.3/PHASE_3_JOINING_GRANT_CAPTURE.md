# Original joining grant capture

The [conditional continuation reader](PHASE_3_JOINING_CONTINUATION_REPLAY.md)
found a concrete gap: the original intermediate node-2 ballot-7 BASIS/source had
already retired before the next retained snapshot. Its response digest cannot
recover those original bytes. This batch adds test-only collection at
`GRANT_BEFORE_RETURN`, under the journal writer after PROMISE, source and BASIS
persistence, before the grant returns to the caller.

## Producer and collection

`V53GrantCapture` copies the complete local replica directory, including the
original grant journal, source packets/images, selected and inactive generations,
and all retention ledgers. It compares inventories before and after the copy,
then appends `GRANT_CAPTURED` to the existing shared event sequence with the
canonical manifest digest. Failed copies never get a completion marker. Each
observation gets a new directory; existing evidence is never overwritten.

Reads use the existing owned-descriptor file access. Opening and closing an
independent reader for a live lock inode could release the process lock on POSIX.
A separate JVM probes the original lock after the copies in the targeted test.

Only the full early-start joining fixture enables these captures, for its old
network owners and native joining owner. Ordinary fixtures keep the observer
disabled. Runtime Java, wire/storage formats, workflow, POM, resource limits and
protocol deadlines are unchanged. Diagnostic collection has separate bounds:
64 observations, 512 entries per replica, 64 MiB per file, 256 MiB total copied
bytes, and eight directory levels. These bounds do not grant runtime capacity.

`scripts.v53.joining_grant_captures` checks:

- Every observed grant return has one subsequent completed copy in the same
  owner/scope. Interleaving other owners is allowed. Missing, orphaned, reordered
  or unreferenced copies are rejected.
- Complete directory inventories, canonical metadata and event digests, original
  ROOT/NODE/allocator/selector identity, the final PROMISE/BASIS journal pair,
  source packet binding, exact image bytes and current generation inventory.
- Frozen peer and learner wrappers contain the original promise and the exact
  captured ledger bytes for that owner. Copies cannot mix roots or change a
  permanent identity. Reobserving the same original grant is allowed; reusing its
  source ID for a different grant is rejected.
- Full-history collection additionally derives the intermediate counter from
  the original `before-joint-continuation` allocator/journal. It requires both
  old-voter intermediate grants and the distinct following activation grants.

The whole-history collection schema is now
`gse-v53-joining-history-collection-v2`. Its result remains **PARTIAL**:
collection does not derive intermediate preparation/retirement, establish causal
force/network provenance, prove process recovery, or close Phase 3. Historical
v1 receipts and the unchanged `df22c398` archive retain their original meaning;
the new collector explicitly refuses that archive's missing captures.

## Executed checks and remaining execution

The small native writer exercise captures two real grants from an offline
bootstrap, verifies the first copy remains unchanged after the second grant, and
checks the live lock from another JVM. Together with the existing trace tests,
five Java tests pass. The independent reader accepts both original copies as
PARTIAL and rejects twelve exact mutations, including altered images, torn
journals, a foreign allocator owner and substituted frozen ledgers. Semantic
mutations refresh the copied inventory and event digest where necessary.
All 158 joining Python tests pass. The
[batch receipt](phase3-evidence/joining-grant-capture.json) records the source,
logs, original copies, portable replay and archive hashes.

The complete early-start history with these new hooks has **not run** in this
capture-implementation batch. Its later execution and replay are recorded in
[original joint preparation replay](PHASE_3_JOINING_PREPARATION_REPLAY.md).
The small writer exercise is not a replacement for that history. After finishing
the whole-history readers, execute one new uninterrupted source/build-bound
history, with minute-by-minute progress through the existing entry point:

```bash
python3 -B -m scripts.v53.joining_history_run \
  target/v53-joining-history/original-with-grant-captures --maven /opt/maven/bin/mvn
```

Use a new output path for each declared execution; preserve failures. Do not
combine old prefix snapshots with new captures. Replay the intermediate grant,
its retirement and following activation from that same history, then complete
force/network, process-death, all-seven-profile and requirement-mapping gates.
Independent histories may later run in parallel on hosted measurements; the
steps inside one joining history remain indivisible. Phase 3 is **OPEN**.
