# V5.0 Phase 6 cloud workload and evidence implementation

- **Status:** Implementation candidate; local qualification only
- **Branch:** `feat/v5.0-phase6-cloud-workload-evidence`
- **Starting master:** `29f3d8458d93023c5d4d86b6a22692b4e95d14f8`
- **Predecessor:** [PR #159](https://github.com/patricklfdm/GeneralSearchEngine/pull/159), [exact-master CI 35053778177](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35053778177)
- **Design:** [Full cloud workload plan](PHASE_6_CLOUD_WORKLOAD_PLAN.md)
- **Executable contract:** [phase6-cloud-workload-plan.json](phase6-cloud-workload-plan.json)
- **Local gate:** [verify-v50-phase6-cloud-workload.sh](../../../scripts/verify-v50-phase6-cloud-workload.sh)

## Delivered boundary

The separate, checksum-pinned plan materializes the accepted corpus, operation mix,
cloud cell order and 300/900/1800-second allocations, application/replication bounds,
JVM flags, resource ceilings and evidence budgets. The previous 6A/6B JSON plans and
validators keep their original contracts. Production Java, public API and storage
formats are unchanged; all new Java workers and observers live in test sources.

The public consumer supports the planned mutation, query, lifecycle and maintenance
operations. Its published-V4-compatible control is independently compiled with the
pinned 4.4.0 JAR; candidate and control classpaths remain separate. Control parameters
also resolve the three planned cloud profiles. The new local controller executes a
named reduced qualification preset with the full 4096-document corpus and 2-GiB heap.
It has no GCP adapter and cannot admit paid/cloud evidence.

The accepted runner still exposes only `admission-probe`. The next implementation
PR connects the full presets to its timed cloud cells, resource generations,
retention and admission controls. VM/disk ownership, cloud provenance and canonical
set acceptance remain that integration's gates. Local directories used to simulate
disk loss do not attest physical cloud-disk replacement.

## Public workload and local schedule

[CloudWorkload](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/CloudWorkload.java)
uses the published codec, query/index definitions and public engine interfaces.
It records scheduled arrival, start and completion, operation-specific document counts,
read-answer digests and publication sequence observations. Four independent client
lanes exercise the sustained UPDATE/QUERY mix; a pending lane cannot accumulate an
unbounded queue. A missed slot, unexpected rejection or incomplete window fails the
qualification. No throughput improvement target is asserted.

Public reads are bracketed by public sequence reads. Matching sequences establish
an unambiguous committed cut; changing sequences reject the sample. Independently
decoded committed payloads determine candidate mutation order. The control verifier
also rejects ambiguous mutation-sequence observations instead of guessing an order.
Instrumentation records force, quorum and publication timings in the issuing JVM's
clock. Controller timestamps establish process overlap and command chronology.

| Local qualification input | Value |
| --- | --- |
| Corpus/load | 4096 documents, seed 17, 256 batches of 16; independent corpus hash from the accepted plan |
| Warmup | One ten-call cycle, 200 ms spacing; excluded from measured totals |
| Healthy ABBA | One ten-call cycle in each of four windows, 200 ms spacing |
| Sustained | 32 calls, four lanes, 100 ms global spacing; three UPDATEs then one QUERY per lane |
| Fault reductions | Two updates during unavailable/incremental cells; two slow-follower updates; ten updates before snapshot transfer |
| Whole local run | 480-second ceiling including a 30-second cleanup reserve |
| Sampling | Every second plus window boundaries; heap/RSS/GC/CPU/IO, client/peer queues, retained bytes and network counters |

These rates and durations belong only to `v5.0-cloud-workload-local-qualification-v1`.
The cloud plan keeps 100 ms healthy arrivals, 50 ms sustained arrivals and the full
measurement windows. A local PASS cannot replace experiment or canonical evidence.

## Ordered failure and recovery qualification

The same owned three-JVM group traverses fourteen cells: healthy, sustained,
unavailable follower, slow follower, incremental catch-up, interrupted snapshot ACK,
entry-quorum cut, proof-quorum cut, restart/fencing, follower replacement, configured-
leader replacement, maintenance/cancellation, checkpoint capacity and no quorum.

The leader's public checkpoint moves its snapshot index beyond the isolated follower,
so public catch-up selects a snapshot without assuming old-log deletion. Snapshot
ACK loss exercises real transfer/retry. Both proof cuts stop the owned JVM at an
actual runtime barrier, preserve the pre-reopen authorities and independently inspect
proven history. Restart uses a higher epoch; an actual retained 1.1 request must fail
with `STALE_EPOCH`.

Replacement uses public offline planning/apply and runtime admission. Retained
pre-loss copies are inspected as evidence and are not recovery sources. Configured-
leader reconstruction rejects one available survivor and requires both. Maintenance
retains a completed backup, kills the leader after a second backup is published,
then exercises Future cancellation and close/restart. The first backup is restored
with published V4.4. Repeated local checkpoint must reject with `CAPACITY_EXCEEDED`
before overwriting protected generations. Final quorum loss cannot publish its
unproven write or change the committed leader read.

Test-only hooks coordinate cuts/network faults and record forces. A test-only observer
reads queue counters through reflection; it never changes private state or invokes a
private application operation. Every owned process generation records PID, Linux
start ticks, startup/exit times, commands and cleanup. Failures retain their evidence
and stop qualification.

## Independent evidence and bounds

The new `gse-v50-cloud-workload-evidence-v1` envelope currently accepts only
`local-cloud-workload-only`. Relabelling it as cloud, fake or canonical fails.
The [independent model](../../../scripts/v50/cloud_workload_model.py) reconstructs
application operations from encoded payloads and checks genesis, ancestry, proofs,
selected snapshots, ordered documents/indexes, read cuts and V4 results. It checks
all retained crash and replacement authorities against the final proven prefix.

[Bounded evidence IO](../../../scripts/v50/cloud_workload_io.py) hashes and copies
files incrementally into ordered parts. The immutable bundle is at most 4 GiB;
JSON members are at most 16 MiB, binary parts 32 MiB, JSON lines 1 MiB, stream parts
8 MiB and aggregate samples/traces 512 MiB. The manifest binds logical file size,
whole-file hash and ordered part hashes. Validation rejects duplicates, missing or
reordered parts, unlisted files, symlinks, traversal, nonfinite/duplicate-key JSON,
truncated streams and oversized source-archive expansion before extraction. It
reassembles into a fresh temporary directory and verifies the retained bundle is
unchanged afterward. The current runner's artifact/evidence limits are not changed
by this separate format.

State output uses bounded pages rather than the large 6A all-feature report.
`measurements.json` retains per-window/per-operation p50/p95/p99, counts, document
counts, offered/completed rates and scheduler delay. Instrumentation overhead uses
service times rather than equal fixed window lengths. Fault outcomes are separate,
including missing successes at killed-process cuts and no-quorum indeterminate tails.
The validator independently recomputes these summaries from raw samples.

## Usage and CI

```bash
scripts/verify-v50-phase6-cloud-workload.sh
# Reuse a reactor build from unchanged production inputs:
scripts/verify-v50-phase6-cloud-workload.sh --skip-build

# Read-only revalidation; the executable plan is checksum-pinned:
python3.11 -m scripts.v50.cloud_workload_evidence /path/to/evidence/bundle
```

`GSE_V50_CONTROL_JAR` can name a predownloaded control; its published checksum is
mandatory. The gate writes `target/v50-cloud-workload/run.*/evidence`, compiles both
consumers, runs the owned processes, validates the complete bundle and rejects
resealed semantic negatives. Required CI runs it after 6B and retains evidence with
`always()` for fourteen days. The no-GCP Python job discovers the contract/IO tests.
No IAM, cleanup enablement or paid dispatch is performed by this implementation.

## Validation and acceptance

- [x] Plan PR #159 and exact-master documentation CI verified; Change scope/Required passed and four full-build jobs skipped as intended.
- [x] Independent plan arithmetic and full 4096-document corpus/payload bounds validated.
- [x] Fourteen-cell development qualification and independent replay pass.
- [x] Resealed semantic negatives reject forged readings, success/proof/force observations, cells, resources, summaries, ownership/cleanup and replacement claims.
- [x] Final candidate build and local gate pass; regression receipts recorded below.
- [ ] Protected implementation PR and exact-master full CI accepted.
- [ ] Full runner preset integration and real cloud evidence provenance accepted.
- [ ] Fresh preflight, cloud setup, exact paid confirmation and staged 6C evidence accepted.
- [ ] Independent 6D review and baseline registration accepted.


### Final local receipts

| Check | Result |
| --- | --- |
| Reactor release verification | PASS; 705 Java tests, zero failures/errors/skips; about 90 seconds |
| Release artifacts | PASS; all nine JARs; core and replication bytes match the accepted predecessor |
| V5 Python suite | PASS; 129 tests, including thirteen new contract/stream/model tests |
| Final workload gate | PASS; 60.42-second owned run, 4096 documents, fourteen ordered cells, 72 measured calls and 56 durable measured mutations |
| Independent evidence | PASS; committed index 92, application sequence 340; all 22 resealed semantic negatives rejected |
| Capacity rejection | PASS; independently inspect retained before/after authorities and require identical recovery-source bytes |
| Existing 6A/6B regression | PASS; original 6A semantic gate and twenty negatives, plus the 6B fake lifecycle/offline volume-layout gate |
| Documentation/CI wiring | PASS; Phase 0 contract, fourteen classifier tests, local links/anchors, YAML/shell syntax, fences and whitespace; full CI selected |

The workload receipt records starting HEAD `29f3d8458d93023c5d4d86b6a22692b4e95d14f8`
with `sourceDirty=true` and the final source/build-input inventory. Its plan SHA-256
is `148e7808680b51f1427d9be535291ec7629c7a64eac59bf8ac96691b7a6086fa`.
The final local evidence is `target/v50-cloud-workload/run.3wxL5X/evidence`.
These results qualify the local workload/evidence implementation; clean-source
acceptance follows through the protected PR and exact-master CI.
