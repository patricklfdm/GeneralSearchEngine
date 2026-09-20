# Phase 3C: retained-voter rejoin and recovery-source exchange

**Status:** Phase 3 accepted in PR #191 with exact-master CI `35542143840`;
see the [checklist](PHASE_3_CHECKLIST.md). PR #190's failure and its correction are retained below.
**Implementation base:** [PR #189](https://github.com/patricklfdm/GeneralSearchEngine/pull/189),
master `bc78f6587fee2c3c80ce3198230cfcfb13316f9f`,
[CI 35527143425](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35527143425).
All six jobs passed, including the actual real TCP runtime gate.
The user entered `feat/v5.1-phase3-rejoin` and authorized this batch.

## Runtime behavior

`AutomaticRejoin` runs one maintenance pipeline per runtime. Each leader periodically
probes both fixed peers. Status only schedules work. A higher observed promise
retires the campaign; a lower peer must durably prepare the current ballot before
receiving recovery data. The original selected quorum remains unchanged.

A stable, published leader cut supplies a complete IMAGE with a proven SNAPSHOT and
no introduced acceptance. The existing snapshot offer/chunk storage path forces
each acknowledged byte range. The receiver checks the exact transfer identity,
ballot, complete image digest, local proven history and generation capacity before
installing. A retained unresolved next acceptance above that cut defers installation.
Installation preserves root promises, does not manufacture an acceptance receipt,
and does not enable a public follower read. Application reconstruction uses the
existing V4 path when a future election requires that state.

Repeated installation of the exact current snapshot does not consume another
generation. A new checkpoint waits when the inactive slot still requires retirement;
ordinary capacity pressure is rejected before the ambiguous storage-I/O path.
Missing or corrupt authority still fails closed. No disk-loss re-enrollment is added.

## Explicit additive wire decision

The original selected-quorum install cannot represent passive proven-state
installation, and the frozen catalog has no complete generation-source packet.
The [separate extension catalog](../../../general-search-engine-replication/src/test/resources/replication/v51/rejoin-wire-extension.json)
adds these messages:

| ID | Message | Meaning |
| --- | --- | --- |
| 25 | `REJOIN_INSTALL` | Proposer requests exact staged-image installation; receiver echoes the identity after the durable boundary |
| 26 | `SOURCE_OFFER` | Any current-ballot peer requests a complete source at one exact snapshot cut; response binds a finite immutable packet |
| 27 | `SOURCE_CHUNK` | Request/data ranges bound to that source identity, owner, ballot, length and whole-packet digest |

`REJOIN_INSTALL` does not carry a selected-next choice. Its transferred image must
contain no acceptance and must already prove its prefix. `SOURCE_OFFER` is the
explicit peer-to-peer exception to proposer-only snapshot directions. Neither is a
vote or leader readiness proof. Status and source responses keep request correlation.

The request's SOURCE_OFFER `transferId` is a correlation nonce. The source assigns
the response's immutable lease ID, which subsequent SOURCE_CHUNK requests use.
After expiry a new offer can only receive a new lease identity; it cannot resample
bytes or restart the lifetime under the expired identity. Snapshot offers additionally
retain a per-ballot trace/sequence watermark to reject retired requests.

The source packet is canonical JSON: one `files` array, sorted by `name`, containing
exactly `current.gsr`, `generation.gsr`, `snapshot.gsr`, `accepted.gsr`, and `proofs.gsr`.
Each element contains only `name` and base64 `bytes`. Source validation checks the
selector, seal inventory, complete journals, prefix and unresolved slot rules.
The offer hashes the entire packet with SHA-256; image identities retain the existing
framed-record digest convention. Unknown fields, duplicate files and changed bytes
reject. Original Phase 1 and Phase 3B catalogs, vectors and checksums stay unchanged.
New [vectors](../../../general-search-engine-replication/src/test/resources/replication/v51/rejoin-wire-fixtures.json)
and [checksums](../../../general-search-engine-replication/src/test/resources/replication/v51/rejoin-wire-fixtures.sha256)
have independent Python and Java checks. This is an unreleased homogeneous 1.2
extension requiring protected review; it does not qualify mixed artifacts.

## Two-source retirement

Every peer may retrieve one other peer's complete, re-forced generation at its own
current snapshot cut. The requester independently decodes the packet and checks the
source owner, exact cut and shared ancestry. It then rechecks its own active generation
on the control dispatcher before persisting both source inventories and the FLOOR.
Only the existing storage cleanup implementation may delete the inactive generation
or truncate covered root journals. A local checkpoint or a status index alone never
authorizes deletion. Identical already-cleaned source pairs avoid repeated writes.

Generation installation, floor publication and physical deletion retain the Phase 2
interruption boundaries and independent retained-directory checks. Full ancestry and
promise ceilings remain finite; reclamation does not remove those lifetime limits.

## Bounds, stale work and shutdown

### Different snapshot cuts (PR #190 follow-up)

[Master CI 35533377860](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35533377860)
failed after retained-node restart: the three active snapshot cuts were 6, 7 and 4,
while the full voters could not checkpoint again before reclaiming an inactive
generation. Each requested its own exact cut from another voter's current
generation. No pair matched, so retries could not make progress. Push CI did not
encounter this ordering; raising the convergence timeout would not remove the cycle.

The homogeneous, unreleased SOURCE exchange now also supports a bounded upload:

1. A zero-byte `SOURCE_OFFER` keeps its download meaning. An unavailable current
   cut returns `NOT_READY`; only that response triggers the upload fallback.
2. A positive `sourceBytes` offers the requester's complete, hashed source packet.
   The receiver must already prove through the requested cut in the current ballot.
   It assigns a fresh upload ID and receives `SOURCE_CHUNK DATA`, replying with
   exact `ACK` ranges. Intermediate ACKs acknowledge buffered bytes, not authority.
3. After validating the whole packet, owner and local proven ancestry, the receiver
   forces a complete locally owned copy at `transfer/witness/<requester>/`.
   This optional directory has exactly the five source files, one bounded slot per
   fixed peer. Its nested selector describes the packet; it never replaces the root
   selector, contributes a vote, changes a promise or rolls back application state.
   Interrupted auxiliary copies are never used as startup authority.
4. Only after the complete copy is forced does the receiver create an export lease,
   with a different immutable ID. The original zero-byte offer then downloads that
   locally owned source through the normal hash-checked path. Upload and download
   share the original finite deadline. The requester still needs its unchanged
   active source plus the downloaded peer source at the exact same cut before FLOOR
   publication and deletion. No floor, proof or journal-retirement check is relaxed.

There is at most one incoming source upload per runtime in addition to the existing
two peer export leases and one snapshot transfer. Each has the existing quarter
staging cap; uploads cannot replace an unread export. Same-ID retries cannot change
bytes or renew a deadline. An expired/restarted transfer must receive a new server
identity. Auxiliary copies are retained independently of active generation cleanup;
replacement is limited to a fresh exchange from the same requester after its prior
export is consumed or expired, and requires a locally proven prefix again.

This explicitly extends the semantics of the existing Phase 3C fields/directions;
it changes no frozen catalog, record or vector bytes. Java and the independent
Python inventory checker recognize only the bounded auxiliary paths. The evidence
checker reconstructs the upload, checks its durable boundary, and separately checks
the download used by each floor. Witness events bind both upload and export IDs:
a SIGKILL after forcing a copy but before tracing its final ACK may leave an unused
copy; a downloaded export always requires complete upload evidence. Unused,
unacknowledged copies do not count toward witness qualification.
Public bootstrap and mixed-version compatibility
remain outside this qualification.

### Common limits

- One maintenance pipeline is admitted, so its executor cannot accumulate work.
  Network waits stay outside the authority dispatcher and retain transport limits.
- At most one incoming image and one immutable source lease per requesting peer
  exist. New identities reject while an incomplete lease is active.
- Each image/source packet is capped at one quarter of the configured staging bound
  and at the format maximum. Existing storage inventory enforces aggregate disk bounds.
- Transfer and source lifetimes use monotonic elapsed time and the sealed operation
  timeout. Retries cannot refresh the original lifetime. Chunk hashes/ranges and
  exact duplicate bytes are checked; completed identities may be replaced by new work.
- Higher promises retire leases and all old completions. Restart does not revive
  an in-memory lease; retained staging alone cannot authorize installation.
- Close retires maintenance admission and drains the pipeline before releasing the
  store. A timed-out close retains exclusive ownership.

## Qualification

The Java regressions exercise repeated three-voter catch-up and generation reuse,
retained restart, loss of an install reply and source-chunk disconnect. Focused
exchange tests cover fixed lifetime, duplicate chunks, competing lease identities,
higher promises and incomplete source inventories.

`scripts/verify-v51-phase3-rejoin.sh` runs concurrent real JVMs, repeated all-voter
floor advancement, two leader SIGKILL events and retained-node reopen. A test-worker
fault briefly holds outgoing passive snapshot offers while a new mutation commits;
the peers prove the new cut while retaining older snapshots. The gate requires an
actual exact-cut witness upload before releasing the hold and checking convergence.
This hook exists only in the test worker, and the 45-second limits remain unchanged.
It retains
wire frames, source packets, storage boundaries, application publications and the
source/JAR/test-report identities. The independent checker verifies chosen history
and V4 application bytes, reconstructs downloaded source packets and checks that
deletion follows a durable floor. Missing transfer/force evidence and forged source
inventories must fail. The witness path adds mandatory missing-upload and
missing-witness-force negatives. CI always retains the evidence directory.

Full Phase 3 acceptance still requires protected merge and exact-master CI. Public
bootstrap, façade, fresh read barriers/pins and lifecycle admission remain Phase 4.
This batch makes no cloud, mixed-version or public readiness claim.

## Local validation (2026-09-20)

- Full reactor `package` passed: core 549 tests (four existing skips), replication
  259, processor five. The final expired-offer refinement then passed all 14 runtime,
  wire, rejoin and lease regressions; the fixed-trace lease test was verified again.
- All 46 Python tests passed, as did documentation and shell checks.
- Foundation gate passed at `target/v51-foundation/run.I01vYk/evidence`.
- Protocol gate passed six scenarios and seven negative variants at
  `target/v51-protocol/run.kW3l5y/evidence`.
- Final rejoin gate passed at `target/v51-rejoin/run.xWdOfi/evidence/receipt.json`:
  three concurrent voters and two retained restarts (five JVM identities), nine
  chosen slots/publications, six acknowledged mutations, 12 passive installs,
  18 floor advances, 20 transferred sources and 96 observed deletion boundaries.
  All five original history negatives and five rejoin negatives were rejected.
- The first storage interruption run retained a barrier-wait failure at
  `target/v51-storage/run.nqJhdb/recovery/halt-selected_write_chunk` (20-second
  harness limit; no worker stderr). Its ledger cuts had passed. The full unchanged
  gate then passed outside the filesystem sandbox at `target/v51-storage/run.DW9Lzk`:
  all 36 ledger cuts and 72 recovery cuts passed. The initial failed attempt remains
  retained; no timeout or product logic was weakened to obtain the passing result.

These are local worktree receipts based on `bc78f6587fee2c3c80ce3198230cfcfb13316f9f`,
not protected-master or public-service acceptance.

## Recovery-floor correction validation (2026-09-20)

- Reactor package passed. Current test reports: core 549 (four existing skips),
  replication 264, processor five, with no failures/errors. The full-suite attempt
  found a missing parent directory in the new interruption-test fixture; correcting
  that fixture and rerunning its tests completed qualification. Later tracing-only
  refinements were packaged and exercised by the final real-JVM gate.
- New Java coverage includes three different full-generation cuts over real TCP,
  exact-cut source upload/download, immutable retries/expiry, retained higher proof
  and unresolved acceptance, and 16 interrupted witness writes/acknowledgments.
- All 47 Python tests passed. Foundation passed at
  `target/v51-foundation/run.ebbOFg/evidence`.
- Storage passed all 36 ledger and 72 recovery process cuts at
  `target/v51-storage/run.jNNcQZ`. Protocol passed six scenarios and seven negatives
  at `target/v51-protocol/run.XmY0kG/evidence`.
- Final rejoin gate passed at `target/v51-rejoin/run.ZSDVID/evidence/receipt.json`:
  five JVM identities, nine chosen slots/publications, six acknowledged mutations,
  three qualified witnesses, 19 floors, 21 downloaded sources and 98 deletion
  boundaries. All five history negatives and seven rejoin negatives were rejected.
  The forced witness scenario and the original convergence limits both passed.
- The earlier enhanced run `target/v51-rejoin/run.Rp4BJJ/evidence` retained an
  evidence-validation failure for a copy forced immediately before SIGKILL, without
  a final ACK. Export-ID correlation fixes this accounting boundary; the failed
  attempt remains preserved alongside the final passing run.

These local receipts were followed by protected acceptance in
[PR #191](https://github.com/patricklfdm/GeneralSearchEngine/pull/191), master
`263c488fa3d1b0f78ff8a4a4454d7b3b7ff0bfab`.
[Exact-master CI 35542143840](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35542143840)
passed all six jobs and executed the rejoin gate. Phase 3, including kinds 25–27,
is accepted; PR #190's failed result remains historical evidence.
