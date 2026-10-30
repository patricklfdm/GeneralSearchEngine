# Actual joining voter continuation

Phase 3 remains **OPEN**. This component connects the actual joined native
owner, its original retention initialization and permanent TCP endpoint to the
existing round driver. Old node-3 stays offline; node-1, node-2 and the actual
new node-4 must supply the joint majority. FINAL changes the authority, so the
driver must activate the stable configuration again and publish a fresh BARRIER
before internal readiness. Public service, election scheduling and automatic
acquisition of the joining seed are separate work.

The first native attempt reached joint selection but failed before FINAL while
reserving its third governing floor image. Three retained source images, two
generation images and three floor images require eight APPLICATION slots;
the existing seven-slot bound correctly refused that peak. The failure remains
retained. Increasing the allowance would conceal an unnecessary intermediate
source, so continuation now schedules its retirement earlier.

A new durable PROMISE can supersede a settled source at the same current cut.
If neither the current manifest's PROMISE nor BASIS refers to that source, it
can request maintenance before the next generation is installed. A merely
observed higher ballot cannot create this condition. This predicate is only a
scheduling hint: actual retirement still requires complete original governing
floor copies, the existing ancestry/tail checks, a forced retirement decision
and exact journal replacement. Current and latest sources remain protected;
pending votes, context transactions and application work cannot borrow this
permission. The source and image counts, shared staging allowance and all
production deadlines remain unchanged.

The local endpoint checks after registering its fresh grant. An incoming
PREPARE checks after forcing/registering its new grant and before returning
PROMISE. The proposer waits for all selected grants before installation; this
avoids collecting a floor while another selected receiver replaces its source
generation. Both use the original scope's deadline, cancellation and higher-ballot fence; neither
restarts the campaign or substitutes a different selection. The retaining
cold entry remains mandatory for the actual new owner.

The next native attempt exposed two coupled lifetime problems in the initial
correction: maintenance at SELECTED could race with another receiver's
installation, and borrowed prefix/generation pulls left unused remote content
open until the service deadline. PREPARE now completes the sweep before its
reply. Read-only packet-only and generation-metadata aliases advertise exactly
the content those pulls consume. They use existing CHUNK/TRANSFER_COMMIT
frames, unchanged source/cut/reader checks and original deadlines. The final
commit closes the export; the existing bounded trace marker retains its exact
reply and rejects a changed retry. The packet-only receiver requires every
original image from its live local borrow. If a completed packet-only probe
finds a missing historical image, maintenance closes that receiving scratch
and performs one full-prefix pull under the original deadline and fence. This
is not a retry of a rejected or timed-out operation. The full pull stores only
missing images, streams and hashes borrowed image bytes without another disk
reservation, and commits every advertised member to release the remote export.
Ordinary full-prefix and full-generation aliases retain their existing contents.

The frozen native snapshot completed its six selected tests in 1658.984
seconds with no failures or skips. The actual history retains both installed
SELECTED records and each original voter's journal before later compaction:
joint cut 6, FINAL 7, new stable selection 7, BARRIER 8, internal readiness and
the same directory's cold reopen. Independent component replay checks those
original bytes first, then rejects five exact mutations (early readiness,
changed selection, old entry ballot, wrong barrier and public-readiness claim).
The same-cut scheduling regression fails against original production code.

The final missing-local-image fallback was added after that native snapshot.
All 68 final-source focused tests passed in 356.360 seconds, with no failures
or skips. They cover complete/partial image borrowing and lost final ACK,
repeated exact-last-commit release, source retirement/floor authority, corrupted
generation transfers, cancellation, higher ballots and original deadlines.
These tests and the original native result remain separately source-bound;
**the final-source whole native history is still a hosted acceptance item**.
The added scenario declares a 40-minute test-owner lifetime at its start;
older scenarios and production/RPC deadlines are unchanged. It does not change
the frozen measurement workload or confer a performance/availability result.

This component does not claim the complete physical, history and process-death
qualification. The full profile matrix, continuous
coordinator and maximum combined retention cases remain in the
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

The source manifests, all attempted runs (including compilation and native
failures), five negative results and archive digest are indexed in
`phase3-evidence/joining-continuation.json`. The raw portable archive and replay
tool remain under `target/v53-joining-continuation/`; no failed history was
replaced or counted as successful. No full reactor suite, hosted acceptance or
paid cloud experiment was run for this component increment.
