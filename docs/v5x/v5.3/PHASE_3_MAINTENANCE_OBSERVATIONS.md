# Bounded maintenance observations in a continuous round

Phase 3 remains **OPEN**. The fresh native joining qualification of `7d6d4f09`
failed after PREPARE/READY at `peer retention pending renewal capacity`, before
reaching the earlier joint-continuation deadline. This is a separate reproduced
retention mechanism; it is not evidence that the earlier deadline is resolved.

## Cause and correction

A complete-copy observation narrows possible peer endpoints, but keeps older
endpoints as checkpoint renewal obligations. Other owners may still need their
original bridge acknowledgements. As described in
[peer confirmation](PHASE_3_PEER_CONFIRMATION.md), only verified selected-source
reconciliation can discharge these obligations across owners.

Continuous publications do not necessarily start another election. Observing
cuts 1 and 2 leaves possible `[2]` and renewals `[0,1]`. Observing cut 3 would add
a third renewal. The former maintenance path required this optional narrowing
and aborted after the complete governing floor had already been forced.

Maintenance now validates the original complete copy, permanent identity, root,
history and endpoint conflicts as before. If recording the observation would
require a third renewal, it keeps the exact previous ledger, revision,
confirmation, pending installation target and all checkpoint obligations. There
is no ledger write and no inferred newer observation. The independently forced
floor remains necessary for retirement. Other validation, capacity, fencing and
I/O failures still propagate; no exception-string retry or catch-all is added.

Deferral alone is insufficient for continuous service. The retained TCP probe
advanced past the original capacity exception, but the next READY command
reached `future intent earlier dispatch unresolved`: its earlier `[2,3]` target
still could not authorize another publication. That failed execution is retained
and is not reported as a successful joining qualification.

The explicit `retainPeerObservation` operation retains its strict rejection.
Only `retainMaintenancePeerObservation` uses the conservative deferral. After a
fresh verified selected-source merge releases older renewal debt, maintenance
can record a later original copy again. No endpoint, ancestry, image, journal,
time or activation-attempt bound changes.

The serialized round now performs maintenance before allocating a new client
entry. If any peer has two pending renewals, it closes the previous outgoing
activation, performs one fresh actual activation, and completes recovery and a
fresh BARRIER before the new command. All source selection, forced installation
and both governing quorum checks remain in their existing paths. This scheduling
hint supplies no authority itself. A failed refresh aborts the invocation; there
is no loop replaying the client command and no reset of its parent's start time.
If debt remains full after the refresh, the new command is refused before ACCEPT.
This conservative policy can refresh frequently during continuous writes. Its
extra selection and BARRIER cost is an explicit performance qualification item;
the component result is not a throughput claim.

Private lifecycle coordinators can use the same serialized `maintainReady`
boundary before stepping a separately instrumented transition. The joining
fixture retains every additional installation and selected record, and derives
PREPARE/SEAL/JOINT indices from those actual completed operations. It no longer
assumes that control operations always occupy cuts 3, 5 and 6. This preserves
the extra real BARRIER work rather than hiding it from evidence.

## Verification boundary

`V53MaintenanceObservationTest` uses public bootstrap, real phased publication,
cold native owners and actual complete-copy capabilities. It covers repeated
publication with full renewal debt, unchanged durable ledger bytes, a later
unresolved target, missing ancestry, strict refusal, selected-source discharge
and resumed observation after reopening. Foreign original copies still refuse.

`V53MaintenanceRoundTest` runs three distinct DATA commands through real TCP
endpoints. It requires three actual selections and fresh barriers, exactly three
business entries, the corresponding application sequence, and rejection at the
original deadline. This remains a private native-runtime fixture, not public
runtime or all-profile qualification.

The retained executions contain **16 distinct passing Java methods** across the
component, unchanged short-round, failure-injection, continuous-write and JOINT
publication groups; this is not one complete green reactor execution. The final
continuous TCP fixture completed three distinct DATA entries, three fresh
barriers and three actual selections, then rejected further work at the original
deadline. The shorter joining fixture completed actual JOINT publication at cut
9, retaining all four real installations. All **14** focused Python checks pass.

The original whole-history capacity failure, the intermediate unresolved-dispatch
failure, and the deliberately disabled-deferral control remain retained. The
first regression draft also failed because it expected an ancestry file at an
implicit capsule anchor; that fixture error is preserved and is not counted as
evidence for the runtime defect. The successful TCP build differs from the final
runtime only in a comment wrap; the failure-injection build matches all four
changed production files exactly. Each source inventory is retained.

The Python projection has an explicit `defer_renewal` mode. Default strict replay
and existing readers keep their original behavior; no failure-triggered fallback
accepts a new interpretation. Conditional projection tests do not establish
physical, force or network authority by themselves.

Execution records, source inventories, original failures and validation scope
are retained in [the batch receipt](phase3-evidence/maintenance-observations.json).
The complete joining/joint history and its independent physical/network reader
remain separate from these component checks. All-profile and process-death
qualification and the complete requirement mapping are still required.

## Rollback

Restore the strict maintenance observation call and remove the pre-command
refresh together to restore the previous refusal. No durable format or decoder changes need reversal. Preserve
existing confirmations, renewal obligations and failed evidence; do not discard
old ledger entries or enlarge capacity as a rollback substitute.
