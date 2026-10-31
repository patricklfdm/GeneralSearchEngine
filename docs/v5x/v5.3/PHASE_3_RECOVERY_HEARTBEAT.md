# Liveness during installed-campaign recovery

The retained successful three-owner producer subsequently receives independent
[whole-history physical/network replay](PHASE_3_COMPETING_REPLAY.md). Its original
`PARTIAL` receipt and the historical observations below remain unchanged.

Subsequent [original-copy observation replay](PHASE_3_OBSERVATION_REPLAY.md)
qualifies the retained component histories with an explicit current-semantics
reader. The original failed result below remains unchanged; whole automatic
competition still requires independent qualification.

Phase 3 remains **OPEN**. The preceding
[election/discovery qualification](PHASE_3_ELECTION_DISCOVERY.md) recorded
22–28-second intervals between installation and READY, with another automatic
owner starting a newer ballot during those intervals. The original driver only
enabled cooperative heartbeats after READY. This increment closes that scheduling
gap; complete competition and physical/history acceptance remain separate gates.

## Behavior and authority

An automatic round now takes its first heartbeat sample immediately after its
selected activation has completed installation and passed the original `current()`
guard. The same serialized coordinator services due samples during carried-entry
recovery and the initial fresh BARRIER, as well as during later slot work. A
configuration handoff can sample only after its new installation is validated.
The explicit, nonautomatic start path retains its original scheduling.

Each sample still requires the exact installed selection, original root/view,
proposer ballot and current local cut. It runs only at unlocked work boundaries;
peer workers and callbacks holding the journal writer cannot initiate a sample.
The existing `activated` hint says the campaign has installed, not that recovery
has completed. Neither that hint nor a responding majority creates a grant,
copied floor, read lease, client admission or READY. The carried-entry and
fresh-current-ballot BARRIER requirements remain unchanged. The explicit
`heartbeat()` and readiness APIs still require READY.

For joint views, a diagnostic contact requires a majority of **each** original
side. A majority of the voter union is insufficient when one side is a minority;
conversely, shared members can satisfy both sides without a union majority. The
sampler uses the exact voter union, at most five remote peers. Its existing
16-item reply queue covers all five peers and their three finite attempts. The
same original sample/round deadlines and resource reservations apply. No frozen
format, configured capacity, timing policy, public API, POM or workflow changes.

Higher-ballot fencing, failed contact and close retain the existing cancellation
and drain paths. A failed sample does not silently permit recovery to proceed or
replay a client mutation. Cooperative progress cannot preempt a synchronous file
operation, so this change does not establish a failover SLA under unbounded
storage or scheduler delays.

## Qualification boundaries

The new native component cases hold a real initial BARRIER response to exercise
due sampling, higher-ballot rejection and close before READY. A rejected selected
installation must send no activated heartbeat. Conditional original joint-view
fixtures check both-side quorum rules, all seven frozen profiles, unchanged
original bytes and released resources. Those fixtures do not establish complete
native joint activation or joining qualification.

The preceding READY-only heartbeat reader retains its exact ordering and original
physical checks. It is not relaxed to accept recovery traffic as proof of READY.
Complete automatic-history readers still need their own original-source replay,
including peer-confirmation provenance. Component success cannot waive that work.

The source-bound [receipt](phase3-evidence/recovery-heartbeat.json) separates:

- **65 passing Java checks**, with zero failures or skips: 12 initial recovery,
  joint and scheduling checks (166.102 seconds), then 53 related heartbeat,
  election, original-round and native cold-reopen regressions (1220.076 seconds).
  Both timings include their isolated builds. Seventeen Python contract/reader
  checks pass, including the unchanged original-first negative qualification.
- The new held-BARRIER regression **fails against `90182500`** because a due
  heartbeat is blocked behind recovery. All 318 production/POM inputs in that
  comparison match the base commit; only the new test is overlaid. The failed
  original execution is retained, not replaced by the passing candidate.
- One ungated default-bound three-owner execution **passes its producer** in
  101.834 seconds including its isolated build. All three owners remain in their
  first automatic round with no recorded losses. Node 1 reaches READY and
  completes the sole DATA; nodes 2 and 3 remain waiting in STARTING. Every owner
  closes without failure and with zero resource leases. No winner was chosen,
  client mutation retried, deadline enlarged or capacity raised.
- In that whole execution, the first retained heartbeat send is 0.084 seconds
  after installation. Eight sends occur before BEFORE_READY, 22.831 seconds after
  installation. These are one run's event timings, not a latency distribution or
  proof that every future competing history converges. The producer still reports
  **PARTIAL**, with `physicalReplay=false` and `phase3Complete=false`.

The additional unchanged READY-only physical reader **fails on its original**,
before running any evidence negatives. At `applied-1/node-1`, only
`peer-retention.gspr` differs: its derived plan is identical, but the actual
genesis ledger remains revision 0 while the reader predicts revision 2. Runtime
commit `bafce01e` already made genesis observations no-ops; the generic
`native_dispatch_evidence.maintenance` reconstruction still invents two writes.
The original file bytes, expected bytes, traceback and source blame are retained.
This pre-existing model mismatch must be corrected with source-bound no-op,
confirmation and force-order replay, not by ignoring revision fields or counting
unrelated failures as successful negatives. No reader has been relaxed here.

## Rollback and remaining work

Revert the automatic installed sample and RECOVERING scheduling branch together
to restore the earlier READY-only behavior. The joint quorum predicate can remain
independently correct. No persisted-state migration is needed. Keep every failed
original execution alongside its source snapshot. Full competition, native joint
continuation, joining, process death and all-profile Phase 3 gates remain open.
The next evidence task is to bring generic retention reconstruction into line with
the already implemented genesis no-op and original-copy confirmation semantics,
then independently replay this retained successful competition history.
