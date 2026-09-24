# V5.1 Phase 6C2A: full rich JVM workload and concurrent cuts

**Status:** implementation candidate based on PR #223, master
`833da4947266b4edfbee2a0e6fe10055ed3be00c`. The preceding
[6C1 foundation](PHASE_6_REMOTE_FOUNDATION.md) passed exact-master CI
[35942555519](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35942555519)
with nineteen successful jobs and 25 successful V5.1 verification steps.
That result does not qualify these new adapters or diagnostic hooks.

This is the rich-workload part of 6C2. Its receipt says
`local-guest-rich-workload-only`, `paidCloud=false`, and
`fullRemoteQualification=false`. The twelve frozen fault cells, complete 512-slot
retention/transfer/pinning boundaries, and 6C3 provider integration remain open.
Full 6C acceptance still requires those results and protected exact-source CI.

## Complete frozen tapes

The [6B plan](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) retains SHA-256
`bee0b38ae20611a0d36259e554c5d03b1e1ebd87fc71ab648b3848681854754a`.
The gate runs all of the following on fresh stores:

| Cell | Runtime | Calls | Mutations / reads | Scheduled seconds |
| --- | --- | ---: | ---: | ---: |
| Healthy | Published V4.4 local | 260 | 208 / 52 | 260 |
| Healthy | Published V5.0 configured | 260 | 208 / 52 | 260 |
| Healthy | Candidate V5.1 automatic | 260 | 208 / 52 | 260 |
| Read-heavy | Candidate V5.1 automatic | 120 | 30 / 90 | 120 |
| Sustained | Candidate V5.1 automatic | 180 | 108 / 72 | 180 |

This is 1080 public calls and at least 1080 seconds of scheduled windows. Healthy
mode retains its 20-call warmup and four 60-second ABBA windows. Concurrent cells
retain four callers, four-second burst periods, 250 ms maximum dispatch lateness,
10 ms same-burst dispatch spread and ten-second drain. Each healthy mode has its
original 300-second ceiling; read-heavy has 180 seconds and sustained 240 seconds,
including startup, controls, final export/reopen and shutdown. No failed window is
replayed or converted to a passing summary.

The Python issuing guest schedules callbacks into persistent local JVM pipes.
Four prestarted Java caller lanes use the public API; the controller associates
out-of-order responses with their original operation IDs. One lane has at most
one outstanding operation. There is no SSH per application call, synthetic
mutation acknowledgement, changed arrival rate or shortened qualification window.
The original request, dispatch transitions, JVM API interval, original answer and
completion receipt are retained separately. Dispatch times use the issuing Python
clock; API latencies use each JVM's own clock. Cross-process timestamps are not
subtracted. Actual overlapping Java API intervals must be observed in each
concurrent cell, separately from the dispatch-spread check.

All three modes compile outside production JARs against isolated classpaths.
Published artifacts are pinned by the accepted hashes; the loaded code sources,
compiled class inventory, source inventory and candidate JAR hashes are retained.
The local source SHA identifies the checkout base; a dirty candidate is additionally
identified by its source inventory and actual JAR bytes, never called protected CI.

## Concurrent read ownership

The original 6A oracle assumed one outstanding command. A concurrent read cannot
be assigned whichever read-capture event happens to be most recent, or validated
using the before/after `durabilityMetrics().currentSequence()` diagnostic.

The existing package-private runtime observation hook now assigns a process-local
`readId` on the issuing public-read thread and carries it into capture validation,
capture and release events. The adapter records its current command ID at the
invocation event. When no observer is installed, it emits no event and allocates
no counter value. IDs are absent from public declarations, protocol messages,
authority records and durable formats. An observation failure before admission
cannot leak a public permit or create a read barrier.

The independent oracle requires, for every successful read:

1. An original command invocation and a unique corresponding read ID.
2. A fresh, uniquely consumed NO_OP accepted after that invocation.
3. Actual acceptance quorum, own forced proof, remote proof acknowledgement,
   publication and a validated election selection for that prefix.
4. Capture validation against the then-current promise and the exact published
   snapshot, followed by matching capture and release events.
5. The original GET/QUERY answer projected from that captured application, with
   release preceding the original client response.

Mutations require their exact encoded operation/payload and a unique publication
inside their invocation/response interval. Each automatic export consumes one
separately accounted auxiliary read. Every original failure remains a failure.
The common physical oracle still checks wire correlation, original forces, frozen
basis transfer/selection, publication, transport reservations and all three
retained durable prefixes. The separate cloud projection uses the sealed 512-slot
ceiling; the original 6A projection continues rejecting ceilings above 192.
This is per-call rich-state/physical validation, not a claim of exhaustive
concurrent rich-workload linearizability.

## Resources, durable state and portable retention

Every JVM retains the accepted Java flags, public admission, queue, frame, request,
election and operation bounds. Resource samples include their collection interval.
For this full guest adapter, read-only inspection is queued on the owning runtime
thread and bounded by the existing 9600 ms operation allowance. It does not reuse
the 1200 ms network-request wait. Sampling failure, missing scheduled ticks, leaked
reservations, or sampled limit excess fail qualification; delayed samples are
reported and do not establish unsampled hard peaks. The 6A observer path remains
unchanged.

Observations freeze their original values and timestamp/order on the issuing
thread, then enter one bounded evidence-writer queue per JVM. At most 256 records
and 16 MiB of logical JSON bytes, including the active record, may be outstanding.
Compression and file I/O run on that separate thread. The producer fails on overflow;
there is no event dropping or unbounded wait on the protocol thread. Resource
samples retain current and peak queue bytes/counts. Shutdown must drain within ten
seconds, terminate the writer and seal every gzip trailer; a background write or
close failure fails the original process and qualification. Isolated executable
checks hold the writer to verify both queue ceilings and ensure asynchronous
file-write failure cannot disappear at shutdown. These are labelled writer checks,
not engine evidence.

Stored observations use complete gzip segments bounded at 32 MiB per member
and 128 MiB per JVM and cell, including headers and trailers. A segment rotates
before its encoded JSON rows exceed 31 MiB, bounding incremental decompression
as well as stored bytes. The full healthy tape initially exhausted that bound because recovery
and wire observations repeatedly contained the same large encoded strings. The
external trace codec now stores each large string by exact UTF-8 SHA-256 with
bounded zlib bytes and uses hash references for repeats within that stream.
Definitions and references survive segment rotation. JSON object field order is
irrelevant, so same-row definitions are collected before references are resolved;
a reference to a later row, changed hash, duplicate definition, trailing compressed
data or expansion overflow fails. The decoder reconstructs the original fields
before physical validation. No event, raw payload byte or failed outcome is dropped.
Gzip truncation, CRC failure, mixed compressed/plain segments and oversized
decompressed members also fail. Each logical/encoded row retains the 4 MiB bound,
and decoded observation streams
share the original 6 GiB trace budget across the complete validation. The stored
128 MiB per-node/cell bound and 32 MiB member bound remain unchanged. All worker processes must
close and be reaped. The candidate/configured final backups are independently
decoded and restored using the published V4.4 consumer. The local V4.4 control
retains the [documented post-index-recreation backup limitation](PHASE_6_MODEL_FOUNDATION.md#published-control-limitation-found-during-implementation):
its actual final checkpoint and public same-store reopen are checked instead.
The initial verified source backup must remain byte-identical throughout.

After raw validation and physical evidence negatives, the 6C1 binary collector
packs immutable parts with complete member hashes. Extraction to a different
path must pass the same independent oracle again. Recorded process paths remain
identities; replay reads retained artifacts and authority bytes from the extracted
bundle, without starting copied voters or trusting files at the original path.
A retention/replay failure keeps the final qualification red.

## Encoding cost exposed by the full tape

The full automatic healthy window exposed delayed quorum responses after roughly
150 calls. These original outcomes remain failures. Later, after reducing encoding cost,
a full diagnostic reached call 240 before a follower exhausted the trace budget;
complete gzip segments address that separate evidence-size failure. JVM sampling of the retained diagnostic
run found repeated canonical string encoding and regular-expression compilation
on control threads. `ReplicaJson` now appends contiguous printable ASCII ranges
and writes hexadecimal escapes directly; JSON keys and automatic hash/identity
schemas validate their exact ASCII grammars without per-field regex machinery. Record verification still re-parses,
checks checksums, validates schemas and reads the original authority files.
No recovery exchange, durability force, quorum requirement or deadline is removed.

Compatibility tests compare every UTF-16 code unit with the prior canonical
encoding, check exact byte ceilings and every UTF-16 code unit against the original
key/scalar regex grammars, and retain the frozen
V5.0/V5.1 record fixtures. The retained 45,231-byte snapshot microbenchmark took
443 ms before and 189 ms after for 300 decodes with an unchanged digest. This is
one local encoding diagnostic, not a throughput claim or a failover guarantee.
The full tape and existing runtime gates must independently qualify the change.

## Completed recovery exchanges

The longer healthy tape also exposed repeated maintenance exchanges for an
unchanged local generation after its two-source floor and cleanup had already
completed. Each heartbeat could again force and download complete source packets,
including newly appended journal suffixes, although that generation's snapshot
and completed reclamation decision were unchanged. This added control-thread and
storage work to healthy requests; a missed frozen arrival remains a failed run.

The controller now remembers only the local generation digest after successful
floor establishment **and** cleanup. It still reads and validates current local
authority on the next cycle. With the same generation it avoids repeating the
outgoing source exchange. A changed generation or fresh controller runs the normal
exchange again, and incoming recovery/source requests remain available. No record,
force, acknowledgement, deadline, lease, peer selection or deletion rule changes.
The completion memory is neither persisted nor used as voting/read authority.

A deterministic regression fails on the previous implementation (two completed
source messages become six after two redundant cycles). It checks that appended
proofs remain intact without another download, a changed generation advances the
floor, a fresh controller exchanges again, and corruption of current bytes is
still rejected. Existing real-TCP catchup, lost-response and mismatched-generation
regressions remain required alongside the full rich gate.

The floor publication and cleanup also use separate control turns. Queued protocol
and client work may run between them; cleanup rechecks the original ballot and
local generation before deletion. Persisted floor/source validation, file forces,
retirement verification and deletion ordering are unchanged. A deterministic
interleaving regression appends a proven suffix between these turns and verifies
it survives cleanup; a second path observes a higher ballot and verifies that the
old exchange leaves the inactive generation intact. The previous combined turn
fails this regression because no control work can run at that boundary.

Splitting those turns alone was insufficient: retained run `run.rKLNQi` completed
both published controls, then an automatic call at ordinal 166 succeeded after
1.16 seconds and missed the next frozen arrival. The floor and cleanup could
still run on either side of private foreground preparation before its protocol
completion was ready. The run remains failed.

Background local maintenance now enters through the existing bounded input queue
and can leave one deferred control action. The dispatcher starts it only after
admitted foreground submission has completed and normal input/completion mailboxes
are empty. Incoming peer recovery and ordinary protocol requests keep their normal
control path. The original 1200 ms control wait still applies: an atomic claim
separates work already running from a queued action cancelled on timeout; an
expired queued action cannot execute later. Already started durable I/O completes
normally. Close rejects/drains the deferred work, and cloud resource samples
check the one-action bound and zero after close. Sustained foreground traffic can
defer reclamation; existing retained-byte admission remains fail-closed, and this
change does not promise unlimited foreground throughput or a maintenance SLA.

The dispatcher regression blocks an admitted private encoder, confirms that a
maintenance action expires without executing while normal control remains
responsive, releases the real mutation, and checks that only a fresh maintenance
action runs. The prior direct control path fails that regression.

## First-checkpoint interruption during recovery regression

The retained 6A run `target/v51-performance/run.MfOvMt/evidence` passed all three
healthy modes but failed SIGKILL/rejoin. The restarted voter retained only
`generation-a/accepted.gsr`, with no published selector; its authoritative root
journals were intact. The occupied generation slot prevented installing the newer
leader snapshot, and without a current generation it could not establish a floor.

Startup now checks for an interrupted first checkpoint after reconstructing the
root application and before accepting protocol work. It resumes only when every
existing generation file is an exact prefix of the files derived from that same
root proof, application and retained next acceptance. The existing installer still
forces the complete generation and publishes its selector. A different snapshot or
seal is left untouched; this path cannot overwrite an unrelated selection, bypass
an existing selector/started marker, delete files or authorize a recovery floor.
Both public pre-restoration and internal asynchronous reconstruction use this path.
Deterministic crash checks cover partial writes, forces and selector publication,
retained acceptance/promise preservation and refusal to rewrite conflicting bytes.
The original failed run remains evidence of the defect, not a passing qualification.

## Gate and review

```bash
scripts/verify-v51-phase6-remote-rich.sh --skip-build
```

Omit `--skip-build` when fresh reactor artifacts are needed. The gate has a
40-minute outer process-group backstop and preserves all raw/failed receipts under
`target/v51-remote-rich/run.*/`. The new `V5.1 full rich workload (no GCP)` CI job
builds/tests its own reactor, runs the full tape and always uploads evidence and
Java reports for fourteen days. It is an additional required lane; docs-only
changes still skip all Maven jobs. Existing lanes and paid V5.0 workflows retain
their commands and responsibilities.

Synthetic regressions exercise concurrent ownership with deliberately different
old/new captured states and reversed response order. They reject borrowed/reused
IDs, forged answers with recomputed hashes, missing capture/release, pre-invocation
barriers and changed promises. Real evidence mutations independently remove or
alter original invocation, read cut, release, answer, force and proof-ACK records.
Synthetic records are not labelled as runtime evidence.

Local validation passed on the candidate JARs recorded in
`target/v51-remote-workload/validation-summary.json`:

- Complete reactor package: 897 tests, four existing skips, no failures/errors.
- V5.1 Python suite: 422 tests; CI/toolchain/collection focused suite: 52 tests.
- Existing 6A gate: all three modes, nine SIGKILL/rejoin calls and 30 physical
  evidence negatives passed at `target/v51-performance/run.36fH6S/evidence`.
- Full rich gate: 1080 calls and all five cells passed at
  `target/v51-remote-rich/run.BBasys/evidence`; ten physical evidence mutations
  were rejected. Collection retained 921 files in 23 parts; independent validation
  after extraction to a different directory returned identical results.
- Final cell wall times were 261.38 / 263.20 / 268.21 seconds for the three healthy
  modes, 128.25 seconds for read-heavy and 199.50 seconds for sustained, each within
  its unchanged ceiling. These are local qualification observations, not a cloud
  performance result or a failover SLA.

Protected review and exact-source CI remain required. The retained local base SHA
and source/JAR inventories identify this uncommitted candidate; they do not claim
that master CI has already qualified it.
