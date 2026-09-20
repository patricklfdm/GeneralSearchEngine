# Phase 3B runtime: real transport and V4 application path

**Status:** implemented and locally validated; protected acceptance pending.
**Accepted base:** [PR #188](https://github.com/patricklfdm/GeneralSearchEngine/pull/188),
master `cf13a87e84a25ed1470f8e6de307e53b0d67424c`,
[CI 35507802486](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35507802486).
All six jobs passed, including the actual Phase 3A protocol evidence gate.

## Implemented batch

`AutomaticRuntime` connects the accepted transition kernel to real private/loopback
TCP and V4 application staging. Each node owns its sealed authority directory and
starts its own election timer. Application preparation/reconstruction and outbound
exchanges execute outside the serialized protocol dispatcher. Incoming workers wait
for protocol results without blocking that dispatcher.

The runtime checks manifest group, member order/endpoints, codec, captured application
configuration and the sealed timing policy. It is package-private and receives an
already admitted retained directory; the test harness supplies test-only bootstrap
bytes. Full public plan/apply/factory/lifecycle admission remains Phase 4.

`AutomaticWire` implements the frozen original 1.2 schema and the explicitly recorded
[selected-quorum extension](PHASE_3_WIRE_EXTENSION.md). The driver obtains complete
frozen images with bounded chunks and the receiving voter independently selects
before durable installation. Two admitted outbound lanes per peer permit reverse
basis retrieval while an installation response is pending.

## Application preparation and publication

The shared `ReplicaApplication` now exposes internal helpers for canonical application
bytes and operation payloads independently of a configured-mode authority record.
Its existing configured-mode entry/recovery methods delegate to those helpers.
Automatic 1.2 ENTRY/PROOF bytes are always validated by automatic codecs.

The manifest's schemaDigest binds canonical JSON containing `schemaIdentity` and
the complete `AdmissionConfiguration.application(captured)` descriptor; indexesDigest
uses the existing canonical index descriptor digest. Future public automatic
bootstrap must use the same derivation. This binds the declared application settings;
codec canonicality is additionally checked while encoding and reconstructing values.

Before submitting a mutation to the kernel, the application worker encodes canonical
bytes and validates the business operation on a private staged engine pair. Invalid
operations leave authority and the published application unchanged. The dispatcher
then rechecks the captured ballot, published index, deadline and cancellation state.
There is one admitted client operation; no automatic client-command replay occurs.

Proven application reconstruction consumes the store's verified snapshot and proven
tail using the genuine V4 codec/index/mutation path. After proof quorum, publication
checks the exact reconstructed image/cut and atomically replaces the application.
Control-only publications advance the logical cut on the existing live search state,
preserving its snapshot/cursor version. At most two current and two staged application
engines exist. No second live V4 WAL is opened.

`inspectLocal` is an internal qualification helper. It supplies no fresh read barrier
and is not exposed as a public automatic read service. Strong reads, pins, backups
and the public façade are still Phase 4 work.

## Bounds and shutdown

The dispatcher has 32 ordinary inputs and a reserved 16-completion mailbox. Outbound
pipelines use four workers/four queued slots; transport admits two exchanges per
peer, eight inbound connections and a bounded encoded-byte budget. The application
worker has four queued slots. Client future completion executes separately, and its
single admission permit remains occupied while completion callbacks run.

Network attempts retain exact request identity and finite retry/deadline bounds.
Each basis fetch checks byte limits, exact ranges and the finite transfer deadline;
kernel campaign/operation deadlines remain authoritative even when a late transport
completion arrives. Failed or late replies cannot manufacture readiness/success.

Shutdown first retires the kernel without unlocking authority. It then drains
admitted input, stops transport/pipelines and waits for private application work.
Only after those tasks quiesce does it release the directory lock. A timed-out close
retains ownership; a later close can finish. This includes slow codec/private
preparation that has not yet submitted an ACCEPT.

## Evidence and remaining Phase 3 work

Local runtime regressions exercise real TCP election, application writes, retained
survivor recovery, business rejection and lock retention across a slow preparation.
Wire tests compare all 19 original projections and both extension vectors with the
independent encoder. The original transition-kernel and configured leader tests
remain regression requirements.

The runtime verifier starts three concurrent JVMs with one runtime each. It writes
a multi-chunk document, kills the leader with SIGKILL, archives that directory before
reopen, verifies survivor queries, updates/adds documents, and restarts the old node
as non-ready. It retains wire frames, per-process force/publication traces and JAR/
source/report identities. Python independently checks exact receipt forces, remote
ACK before publication, reconstructed frozen bases/selection, chosen-value history
and the canonical V4 application projection. Evidence mutations must be rejected.

This batch qualifies the selected quorum and retained-survivor election path.
Periodic passive catch-up of the third voter, complete recovery-source exchange,
two-source floor advancement/physical reclamation, transfer-lifetime pressure and
the remaining concurrent fault matrix still require the next Phase 3 batch. No
complete Phase 3 acceptance, public automatic readiness or cloud result is claimed.
Generation/promise limits remain finite and exhaustion fails closed.

## Local validation (2026-09-20)

- Full reactor `package`: core 549 tests (four existing skips), replication 251,
  processor five; no failures. This included the first three runtime regressions.
- Final runtime suite: four tests passed, including a real higher PREPARE while
  private encoding is blocked. The unpublished mutation was rejected as NOT_SUBMITTED.
- Wire suite: three tests passed; all 19 original projections and two extension
  vectors agreed with independent bytes. Original fixture/checksum files are unchanged.
- Phase 1 foundation: all 43 Python tests and the independent foundation gate passed;
  evidence at `target/v51-foundation/run.ZVkquf/evidence`.
- Phase 3A gate: six scenarios passed; all seven corrupted-evidence variants rejected.
- Final runtime gate: three concurrent JVMs plus one retained restart (four process
  identities), five chosen slots/five publications, three acknowledged mutations
  and 20 observed chunk frames. All five corrupted-evidence variants rejected.
  Receipt: `target/v51-runtime/run.GVdXVe/evidence/receipt.json`.
- Documentation contract, shell syntax and `git diff --check` passed.

The runtime receipt binds the tested worktree inventory, JAR hashes and Java reports
to base HEAD `cf13a87e84a25ed1470f8e6de307e53b0d67424c`. It is a local qualification
receipt; protected-master acceptance will be recorded after merge and CI. No paid
cloud execution or public automatic factory was used.
