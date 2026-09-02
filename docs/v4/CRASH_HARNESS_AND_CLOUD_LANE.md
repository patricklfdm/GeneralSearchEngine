# V4.0 crash harness and cloud durable lane contract

## First-class status

The local crash harness and cloud durable benchmark lane are V4.0 architecture, not
post-implementation test utilities. Phase 0 freezes their control, oracle, artifact,
failure, and lifecycle contracts. Phase 1 implements executable scaffolding before the
production WAL. Every durability phase then extends the same harness and evidence
family alongside production code.

Production persistence may not introduce an untestable crash boundary. A new WAL,
checkpoint, recovery, generation, or cleanup transition is incomplete until it has a
named harness barrier and a frozen expected outcome.

## Local process-crash harness

The harness has a parent controller, one isolated child JVM, an engine-owned test
directory, an independent history oracle, a byte-level inspector, and a separate
recovery verifier. It never simulates a crash by calling `close()`.

Each case follows this protocol:

```text
create isolated workspace and immutable case manifest
  -> launch child JVM with exact source/config/seed/barrier
  -> wait for a machine-readable barrier-ready acknowledgement
  -> trigger internal hard halt or external process kill
  -> verify that no graceful shutdown path ran
  -> inspect storage bytes independently
  -> launch a new recovery-verifier JVM
  -> compare recovered state with the independent durable-prefix oracle
  -> write checksummed evidence and clean the workspace
```

Internal deterministic barriers use `Runtime.halt` after acknowledging the exact
location. External-kill cases use an OS-level abrupt termination. Neither path may run
shutdown hooks, engine close, test cleanup in the child, or an in-process reopen.

## Stable crash-point identity

Crash barriers have versioned lowercase hyphenated IDs, not source line numbers. The
initial families cover candidate preparation, WAL header/payload/trailer, before/after
force, before/after publication, Future completion, checkpoint generation cut, staging
data/manifest force, authoritative manifest rename/directory force, and WAL cleanup.

Moving code cannot silently move a barrier's semantic meaning. Removing or redefining
an accepted ID requires a contract amendment and fixture migration. Unsupported or
unreached barriers fail the case rather than being reported as a passing crash.

## Independent expected-state oracle

The case manifest records submitted logical units and observed Future outcomes. The
byte inspector identifies the structurally valid durable prefix without invoking
production recovery. The expected set is then:

- every successfully completed logical unit must be present;
- a failed pre-sequence unit must be absent;
- an incomplete Future may be present only when its complete valid unit is in the
  inspected durable prefix; and
- a bulk is always wholly present or wholly absent.

The recovery verifier compares canonical slots/IDs, `nextDocId`, documents, sequence,
index configuration, query truth, score bits, order, and applicable V3.4 behavior. A
child exit code or successful engine open alone is never sufficient evidence.

## Local artifact contract

Every run produces a checksummed, schema-versioned bundle containing at least:

- source commit and dirty-state policy;
- OS, architecture, Java, JVM arguments, filesystem and device identity;
- codec/schema/storage identities and all configured limits;
- case ID, seed, submitted history, barrier ID and acknowledgement;
- child PID, start/end timestamps, termination mechanism and exit status;
- Future outcome journal captured by the parent protocol;
- pre-recovery storage inventory and independent inspection result;
- recovery result, replay/checkpoint metrics, oracle comparison and primary failure;
- stdout/stderr logs with bounded size; and
- artifact manifest plus SHA-256 checksums.

Partial evidence is retained as failed evidence. Missing acknowledgement, timeout,
unexpected graceful exit, corrupt artifact metadata, checksum mismatch, or cleanup
failure cannot be classified as PASS.

## CI integration from Phase 1

Phase 1 supplies the manifest model, parent/child protocol, fake storage fixtures,
artifact validator, and a no-production-WAL scaffold. Pull-request CI runs a bounded
deterministic subset. Exact-master CI runs the broader local matrix as its cost permits.
Long crash loops remain explicit local/nightly or manual gates, but use the same bundle
and validator.

Phase 2 cannot close until every production WAL boundary is reachable through the
harness. Phases 3–5 add recovery, checkpoint, lifecycle, corruption, capacity, and
repeated-crash cases incrementally. Phase 6 aggregates final-source evidence; it does
not invent a replacement harness.

Phase 3 adds three stable production recovery barriers without redefining the ten
accepted writer barriers:

- `v4-recovery-after-tail-truncate-v1` — permitted newest incomplete tail was
  truncated and the new boundary was forced;
- `v4-recovery-after-replay-v1` — all accepted WAL units were replayed into private
  canonical state, before index rebuild and engine exposure; and
- `v4-recovery-before-ready-publication-v1` — replay and derived-index rebuild
  completed, immediately before normal writer admission and engine exposure.

The local matrix uses internal hard halt for all three and external kill after replay.
It then launches a distinct recovery process, verifies the durable prefix, performs a
new post-recovery write, and reopens again. The fake-cloud `phase3-recovery` failure
drill carries the same recovery identity and sequence evidence without provisioning
paid resources.

## Cloud durable lane architecture

The cloud lane is independent from all V3 families:

- suite: `v4.0-durable-single-node-suite-v1`;
- preset: `v4.0-durable-single-node-v1`;
- eventual baseline: `v4.0.0-durable-cloud`.

It has a local/fake control path from Phase 1 and manual paid execution only after
local gates. Cloud orchestration separates compute lifetime from durable-device
lifetime: writer VM, persistent data disk, abrupt instance termination, recovery VM or
replacement boot, reattached same disk, verification, artifact upload, and explicit
disk/VM cleanup are independently recorded steps. A run using only an auto-deleted
boot disk cannot support a machine-failure durability claim.

## Cloud workflow contract

The workflow pins exact source commit, suite/preset version, image identity, machine,
zone, Java/JVM, filesystem and mount options, disk type/size, codec/corpus/seed,
checkpoint/retention limits, crash schedule, timeouts, maximum cost envelope, and
artifact retention. The workflow refuses a moving branch as evidence source.

Profiles are separated:

- `experiment`: one bounded diagnostic member, never baseline-eligible by itself;
- `canonical`: at least three identical eligible members on final source; and
- `failure-drill`: preserved-disk VM termination/recovery cases, reported separately
  from throughput cells.

GCS is the durable evidence store for canonical and failure-drill runs. GitHub
artifacts may mirror a bounded bundle but their shorter retention is not the canonical
authority. Upload receipts, object inventory, checksums, cleanup status, and any
exclusions are part of the evidence set.

## Safety, cost, and cleanup

Paid execution is manually initiated by the user. Dry-run and fake-cloud validation
must resolve resources and budgets before provisioning. Every created VM, disk,
temporary image/snapshot, IP, and object prefix receives an exact run identity and a
bounded lifetime. Cleanup runs on success and failure, reports leftovers explicitly,
and is independently verifiable. Automatic deletion must not destroy the evidence disk
before recovery verification.

## Acceptance boundary

Phase 0 accepts the design above, not a working harness or paid run. Phase 1 must make
the local protocol, artifact schema/validator, and fake cloud lane executable. No paid
cloud execution is expected before production behavior exists, but the lane must be
ready to receive Phase 2+ artifacts without redesigning evidence semantics.
