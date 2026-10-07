# V5.1 Phase 6C3C12 — authenticated source producer and download

**Status:** accepted through PR #243, master
`eb56fa6d2565770bd8aac7f76e484834f563a0f3`. Exact-master CI
[36407418156](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36407418156)
attempt 1 passed all 27 jobs, including three-receiver owned bootstrap with source
production and binary delivery. Native cloud writes and full Phase 6C remain open.
The [owned healthy extension](PHASE_6_OWNED_WORKLOAD.md) is a separate candidate.
The later [native source preparation correction](#native-source-preparation-correction)
is locally qualified; corrected-source protected CI and a fresh approved native
experiment remain required.

PR #243 also accepted the public hardening partition-evidence correction: either
endpoint may observe the partition drop, with original process, direction, cut
and filter provenance checked. CI `36400900510`'s original hardening failure and
automatic-healthy warmup `EXECUTOR_LATE` observation remain retained; the passing
exact-master run does not establish a timing root cause.

## Production and download boundary

[The source controller](../../../scripts/v51/guest_producer_source.py) invokes the
producer through the first member's authenticated, installed package. It receives
no producer filesystem path and reads no producer command store or export file.
The existing package wrapper verifies source, bundle, build, instance, disk,
access, node, package manifest and original boot-bound deadline before importing
[the producer module](../../../scripts/v51/guest_source_producer.py).

The request contains one local-control configuration or exactly three replication
configurations with one group, topology, mode, sealed destination path, source,
workload and attempt, differing only by node. Only the node-1 package can produce.
It exclusively claims `source-producer`
beside its installed package, then creates a private scratch cell within that
claim. The existing published V4.4 preparation command generates the initial
backup once, with the existing plan and JVM arguments. No service or voter is
started. The receiver's actual import path is untouched.

The source/topology exporter accepts a producer configuration only when it differs
from each intended receiver by the scratch path and producer node. It retains all
existing six-file, no-authority, unused-source, topology and byte checks. Each
receiver's export descriptor binds that receiver's original sealed destination.
Only immutable initial backup and topology bytes move; authority and local public
bootstrap seals remain receiver-local.

After verifying and forcing its exports, the producer publishes a terminal receipt
with each member's descriptor and transfer digests. Read-only manifest requests return
those exact descriptors. Chunk requests select a closed node/index pair and return
at most 1 MiB of binary stdout, with original inventory and byte digests rechecked.
No controller-supplied producer path, arbitrary command or part name is accepted.

The controller downloads all three archives to its private cache. It verifies
request/configuration binding, every chunk and part, the closed six-file inventory,
expanded bytes and common source/topology across all members. Only those completed
local caches feed the [accepted receiver transfer](PHASE_6_SOURCE_TRANSFER.md).
All downloads precede all receiver transfers; all imports precede local seals and
service admission. A fresh provider/host/mount check follows producer completion.

## Writes, reads and original deadlines

The controller requires an unused producer, forces a separate prepare intent and
submits preparation at most once. The producer consumes an exclusive directory
before generating any source bytes. A lost prepare response permits only queries
of the original request and terminal receipt. Absent/incomplete state is never
permission to regenerate. Failures retain their claim and diagnostics.

Immutable reads have a separate, bounded rule: at most three attempts per manifest
or chunk after connection loss/timeout. Failed chunk responses retain the exact
received prefix and diagnostic, and a fresh read requests the same bound index.
Corrupt bytes or a digest/identity mismatch fail immediately; they are not retried.
These are read retries, never source-generation, bootstrap or workload retries.

The original package/boot ticket and 600-second ordinary owned preparation deadline
cover production, all downloads, receiver transfers and local bootstrap. The
[native experiment amendment](PHASE_6_PREPARATION_BUDGET.md) uses its reviewed
1800-second profile across the same preparation stages. A reconnect cannot renew
either ticket. Existing per-JVM 90-second limits remain. The source
controller permits at most 1024 calls and 400 failed-read records; the package's
existing 4096 total-connection bound also applies. Reboot, deadline renewal, late
results, package/export tampering and foreign identities fail closed.

Per export, the accepted limits remain six files, 64 MiB expanded, 32 MiB per
member, 65 MiB compressed, 64 KiB transfer metadata and at most 65 one-MiB chunks.
Three completed controller caches use at most 195 MiB of archive bytes. Failed
read prefixes are bounded separately at 400 MiB across the preparation. Source
production creates one seed and three bounded exports; it does not copy a fourth
runtime package or introduce a new VM/disk. Existing admission and workload limits
are unchanged.

## Owned lifecycle and qualification

The existing owned-bootstrap CI command adds `--producer-source`; it uses node-1's
real SSH package endpoint instead of a fourth local producer mount view. Three
receivers still use independent native-UID mount views at the same sealed path.
The gate discards the completed preparation reply and interrupts each member's
first chunk download. It requires one prepare, two prepare queries (absence and
recovery), three manifests and exactly three extra chunk reads. It hides original
producer exports after download and before receiver delivery. Receiver/import/seal
reply-loss checks and the three idle service lifecycles remain required.

The producer/download adapter is offline-qualified. Native IAP/cloud writes are
still disabled. No timed engine window runs here. Preparation failure still enters
owned retention, charging and exact-ID cleanup before any service can launch.
The single-receiver real SSH gate supports the same producer option without sudo;
it downloads all three exports, but its local bootstrap seal does not substitute
for the protected three-receiver gate.

Closed controller retention adds plan, prepare intent, final receipt and three
transfer descriptors, plus at most 400 failed-read JSON records. Each main record
is bounded at 256 KiB, each descriptor at 64 KiB, each failed-read JSON at 4 KiB.
One extra readiness record covers producer completion. The complete CI artifact
also retains cache parts, partial downloads, received failure prefixes and producer
claims/exports. Bulk source/prefix bytes are not represented as modeled startup
JSON retention. Unknown files, names, links and oversized diagnostics reject.
Private SSH keys remain outside the artifact tree.

```bash
python3 -m unittest scripts.v51.test_guest_source_producer
python3 -m scripts.v51.guest_source_qualification target/v51-producer-ssh \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" --producer-source
python3 -m scripts.v51.guest_owned_qualification target/v51-owned-bootstrap \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" \
  --bootstrap --source-transfer --producer-source --allow-sudo-namespace
```

The existing foundation job, 720-second outer guard, required job graph, artifact
retention and measured windows remain unchanged. `paidCloud=false`,
`fullRemoteQualification=false` and `engineWorkloadExecuted=false` remain required.
Next connect owned workload windows and faults to the admitted services, then
independent physical history/backup/restore validation. Trusted preflight and
separate V5.1 workflows/configuration precede any separately confirmed,
user-triggered paid execution.

## Native source preparation correction

**Status:** local correction after PR #297; protected CI and successful paid
execution on the corrected source are pending. This does not close Phase 6C.

[Native run 37555787624](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37555787624)
used master `cdfb5af108c16c7bc01df98b74182a00db6396ee`, whose
[CI 37552754929](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37552754929)
attempt 1 passed all 36 jobs. All three native volumes, package installations and
sessions succeeded. The first published-V4.4 producer then failed with
`native session exact configuration`, before any workload cell ran. Preparation
used 1027.482 seconds of 1800; 772.532 seconds remained at producer submission.
This failure was not a preparation timeout or an IAP disconnect.

The old producer replaced the admitted root `/mnt/gse-v51/published-v4.4-local`
with its consumed `source-producer/cell` staging directory, then constructed a
persistent `Service`. Native session admission correctly rejected that changed
configuration. The earlier producer tests replaced the entire service, so they
could not expose this boundary. The retained request reproduces the same failure
locally; all three mode regressions reject the original producer for this reason.

The correction authenticates the original configuration, installed package,
consumed request and native session before source creation. It derives the
preparation deadline from the original package ticket, rather than substituting
the longer service lease. A shared seed helper writes topology and invokes the
unchanged published-V4.4 preparation command in the consumed staging directory.
It creates no daemon configuration, command store or service. Persistent service
admission still rejects that staging root. Replicated modes export the same seed
to exactly three intended members; the local control exports to node 1 only.

The extracted setup-process helper retains the 90-second per-process cap and the
earlier preparation deadline. It rejects cancellation/expiry before launch and
late completion, and kills/reaps an unfinished child on failure. Source generation
remains at most once: later prepare calls only return the consumed terminal state.
Transfer inventories, source digests, workload parameters and resource limits are
unchanged.

Local qualification covers all three native producer modes through real session
and producer admission, with only the Java seed command replaced by an explicit
synthetic child. It checks immutable exports, repeated prepare, changed roots,
package tampering, expiry, deadline substitution, generation failure and rejection
of a fault-cell producer. Service tests cover both the original setup deadline and
the 90-second cap, including completed-but-late children.

An additional offline check used the unchanged authenticated PR #297 Java package
with the candidate Python implementation. Real Temurin `21.0.12+8-LTS` ran the
published V4.4 seed command; independent backup replay verified sequence 4, 64
documents and four indexes, and a repeated prepare returned the original receipt.
Provider/OS context, mount location and the fresh local session clock were modeled;
this is not a corrected-source package build or a native-cloud acceptance result.
The complete storage preflight gate passed 188 tests and all 28 qualification cases.
Receipts and original failures remain under `target/v51-native-source-producer/`
and `target/v51-native-experiment-pr297/run-37555787624/`.

The failed run's immediate owner recovery passed in 339.570 seconds. Independent
exact-ID reads confirmed all thirteen resources absent, no active lease and
USD 67 / 200 retained in the ledger. Do not reset the failed attempt or reuse its
prepared request. After corrected-source CI, prepare and review a fresh request;
paid execution still requires separate confirmation and operator dispatch.
