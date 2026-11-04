# Actual lifecycle across one native automatic restart

Phase 3 remains **OPEN**. The existing
`V53AutomaticRestartTest#higherBallotAutomaticallyDrainsAndReactivatesBeforeNewData`
producer already retains two complete native campaigns, two fresh BARRIERs and
one subsequent DATA operation. Its physical and network readers derive all
snapshots, votes, source transfers, forces, original higher-ballot heartbeat and
correlated reply. They did not previously observe the automatic owner's actual
old-session close, replacement and subsequent start.

## Actual collection and unchanged protocol history

With `-Dv53.restart.lifecycle.captures=true`, the test attaches the existing
private automatic observer before start. An optional test-only recorder captures
construction, the original ordinal/time of each later protocol event, the
incoming heartbeat and every automatic lifecycle callback. Event hashes bind
the untouched trace; the already existing event prefix has its own digest and
attachment boundary. Nothing inserts or renumbers protocol events, supplies a
clock to the protocol, chooses another source pair or retries the client call.

The `restart-lifecycle-<run-name>` sibling contains exactly `capture.json` and
`automatic-lifecycle.json`. It records the original plan/trace digests, capture
and observation failures, actual owner drain and resource counts after all native
network owners close. Collection failures invalidate evidence without injecting
an error into an admitted protocol operation. Events are bounded to 65,536 and
lifecycle observations to 256. Writes use `CREATE_NEW`; old originals and their
sidecars are retained. The property is off by default, so other native histories
retain their existing layout and collection behavior.

## Independent original-first qualification

The [reader](../../../scripts/v53/automatic_restart_lifecycle.py) first runs the
[current restart composition](../../../scripts/v53/automatic_restart_current.py)
against the original raw directory. It explicitly reuses current peer-confirmation,
source-retirement and ancestry reducers, then checks all fourteen physical snapshot
groups and both campaign/three slot networks. Historical reducers keep their
original defaults; a failed historical interpretation never triggers a permissive
fallback. It then checks every recorded event digest, index, monotonic time and
lifecycle anchor. The existing lifecycle state machine verifies old-session
close before fresh construction, an unchanged original start, both actual
`ROUND_BEFORE_READY` callbacks, terminal drain and zero pending work. Its default
node-open requirement remains unchanged; this entry supplies a separately bound
actual owner-construction anchor instead of inventing a `NODE_OPEN` event.

The only observed LOSS must be `HIGHER_BALLOT` after the first READY and after
the recorded reception of the exact original fence frame. The network prerequisite
independently derives that frame from the peer's real allocator force and binds
its response and delivery between the physical campaigns. The second automatic
round must begin before the second actual installation; its READY must refer to
the new BARRIER. Every active callback remains within the same original 300-second
budget. Cleanup is checked for completion rather than treated as a new operation
with a renewed budget.

The 22 attachment mutations require their exact rejection reasons. They cover
missing/reordered/changed clocks, prefix and plan substitution, capture failure,
residual resources, invalid observation counters, renewed deadlines, reversed
session order, stale readiness, changed loss or fence, premature loss and an
operation outside its original deadline, including the final DATA completion after
the second READY. Mutations touch only copied sidecars;
physical/network bytes remain unchanged and are revalidated before each rejection.
An invalid original or unrelated validator failure cannot count as a successful
negative.

The current network composition validates actual contact replies against original
selector boundaries, bounded identical retries and a delivered responding majority.
These replies do not provide votes, installation or READY. This older producer
records responses rather than every attempted send, so the result explicitly keeps
`completeAttemptsQualified=false`. A nonselected source pull may end at any actual
validated prefix; it cannot become a completed source or change the selected pair.
The original first contact explains the unused peer's volatile fence before its
later refusal to record an intent without an installed selection. Selected peer
retention changes also require their original force sequence. The current
physical/network qualifier has 51 exact negative cases, including corrupt actual
contact cuts, missing contact majority, a changed unused source offer and missing
selected-retention forces.

```bash
python3 -B -m scripts.v53.automatic_restart_lifecycle "$RAW" "$SIDECAR" --qualify
python3 -B -c 'import json,sys; from scripts.v53.automatic_restart_current import qualify; print(json.dumps(qualify(sys.argv[1])))' "$RAW"
```

This adds no hosted subset or planned-history count. It qualifies the observed
restart's lifecycle once its original passes; it does not establish arbitrary
competition, expiry/close faults, process death, all membership profiles, a
final-source cohort or Phase 3 closure. Production Java, fixed protocol bounds,
Required CI and cloud execution are unchanged.

## Development observation

One unchanged native execution passed in 161.959 seconds including compilation,
with no native retry. Its 15 actual lifecycle callbacks, 3,305 event clocks and
one incoming higher-ballot fence are retained under
`target/v53-restart-lifecycle/input/`. The native source manifest is
`b2f902076a5fc574378fed57cdba824dcbf9b2da921de117d882f24b01613c29`.
Subsequent Python reader corrections were replayed against those same original
bytes; this is development replay, not execution of a final-source cohort.

All intermediate failed interpretations remain retained. The legacy physical
projection rewrote an unchanged genesis peer ledger, unlike the current reducer.
The legacy network projection omitted active contact replies, required a fixed
capsule-offer cancellation point, and assumed the unused peer had not yet observed
the first ballot. Current reducers and original wire observations resolve those
specific differences without changing the runtime or rerunning the native history.
Test-fixture and reader-development failures are recorded separately from the
successful native producer. The [tracked receipt](phase3-evidence/restart-lifecycle.json)
records final checks and their exact evidence hashes.

The retained original has 404 answered exchanges, 68 complete source transfers
and one unused incomplete prefix. Twelve contact samples account for 24 of those
exchanges. All 73 physical/network/lifecycle negatives also reject after packing
and relocation under Python optimization; the replay results match the originals.
The Java focused run passed ten tests in addition to the single native history.
