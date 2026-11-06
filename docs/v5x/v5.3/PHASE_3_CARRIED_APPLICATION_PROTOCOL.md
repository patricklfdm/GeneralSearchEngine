# Phase 3 — carried application callback and TCP replay

Phase 3 remains **OPEN**. This reader qualifies callback order and TCP protocol
components for the retained INTENT/halt and FINAL/SIGKILL originals from
[carried application recovery](PHASE_3_CARRIED_APPLICATION_RECOVERY.md). It runs
no new Java producer and changes no runtime code, resource ceiling, frozen
workload, timeout or hosted topology. Both originals belong to the runtime
correction committed as `cb48fb5c`; older process results are historical evidence.

## Original-first admission

`native_carried_application_protocol.validate` first requires the original process
reader and the independent full snapshot reconstruction. Bootstrap, original
membership commands, group death, zero surviving owners, same-directory restart,
fresh ballot and stable barrier are prerequisites. Callbacks cannot replace
missing physical authority. The legacy ACCEPT/PROOF entry points retain their
original cut restrictions and default replay behavior.

The new adapter uses the existing phase boundary/coverage walker. It additionally
tracks staged retirement callbacks, prohibits retirement during cold open or a
campaign, and rejects any unbound retirement following the validated prefix.
Its callback-only interface explicitly rejects transient capture collectors.

## Exact retirement and FLOOR order

Before the first recovered slot, the leader must force the retained old
certificate. The old applied end is then retired under the new selection using
its exact original certificate, selector, generation and frozen source. A new
claim references the old selector without changing the installed new selector.
The control replay consumes the retained old image, creates no output backup,
and deletes its scratch in the required order. Every retirement marker write,
force and deletion is checked before the fresh ACCEPT. An old ACK, premature
ACCEPT, missing force or repeated deletion is rejected.

The FLOOR model supports an explicit local original selector. It derives pinning
from the original two generations, retained sources and governing copy count:
three copies over three retained sources would exceed seven images, so the local
original is pinned instead of physically copied. Remote copies and the complete
logical FLOOR authority remain required. Local-original force, selector write,
selector force and parent force precede the proposal. Release clears the local
reference after the proposal and preserves the original generation. Existing
non-pinned callers retain the old transaction.

The interrupted first lifetime requires complete ACCEPT and PROOF writes for
all selected voters. Only the leader may retain the certificate and create its
applied end through `APPLY_ACK_DIRECTORY_FORCED`. No remote application, publication,
future-retention write or application ACK return can follow that crash cut.

## TCP replay

The shared transport reader checks wire encoding, identity, correlations,
bounded identical retries, actual request/response/delivery observations,
transfer reassembly, campaign activation, heartbeat contact, later applications,
retention and publication. The interrupted slot additionally binds every remote
ACCEPT and PROOF reply to its original record and storage identity, after its
force and before the leader enters the next phase.

Old application retirement is validated independently before it is excluded
from the fresh-slot callback projection. Projection preserves all event indices;
TCP observations are neither removed nor renumbered. Thus an old replay callback
cannot be mistaken for the new application, and an unvalidated prefix cannot
silently disappear.

## Validation and reproducibility

The retained index is
[`carried-application-protocol-development.json`](phase3-evidence/carried-application-protocol-development.json).
The two original histories contain 1,988 correlated exchanges and 608 committed
transfers. Eight interrupted remote vote replies are bound to their original
ACCEPT/PROOF records; five later slots cover thirteen voter transactions.
Both retained legacy ACCEPT/PROOF histories also pass their unchanged default
physical/callback/network entry points. The focused Python regression set has
544 passing tests; 22 focused tests also pass with assertions disabled.

The index records original inventories, positive results, exact negative results,
relocated optimized-Python replay, legacy regressions and reader fingerprints.
The qualification driver validates the unmodified original first. Each mutation
may alter only original observation transcripts and their derived event/wire
views; every storage member and producer receipt must remain byte-identical.
It then rechecks process bindings and the complete callback/TCP reader. An
unrelated rejection reason earns no credit.

```bash
python3 -m scripts.v53.native_carried_application_protocol ORIGINAL_DIRECTORY
python3 -m scripts.v53.native_carried_application_protocol ORIGINAL_DIRECTORY --qualify
python3 -m unittest scripts.v53.test_native_carried_application_protocol scripts.v53.test_native_replay_files
```

The new catalogue contains 42 exact negative variants per original, including
old certificate/retirement force omissions, early fresh voting, duplicate
retirement, old ACK emission, FLOOR pin/release omissions, interrupted application
force errors and forged PROOF receipts. Existing network corruption, delivery,
identity, heartbeat, quorum, retention and publication negatives remain included.
Original evidence and intermediate reader diagnostics are preserved.

## Remaining obligations

This is development component evidence, not final-source cohort admission.
`fullForceReplay`, `fullWireReplay`, `exportAuthorityQualified`,
`wholeRuntimeResourcesQualified` and `phase3Complete` remain false. Transient
application/retirement bytes, original export ownership/lifetimes, simultaneous
runtime resource bounds, remaining crash axes and DATA/internal-core write
interruptions still need their own qualification. Long native and final-source
acceptance remains deferred to the existing hosted measurement plan.
