# Phase 3 — native activation-to-slot dispatch

The typed native `MembershipActivationEndpoint` now retains the same listener,
original grant deadline and source registry from PREPARE/SELECTED through incoming
ACCEPT, PROOF, APPLY and PUBLISH, and into a subsequent stable slot. Only an actual
installed selection admits voting. A changed installed cut replaces the derived
slot scope; it cannot revive an expired or abandoned campaign. Completed-only
publication acknowledgement retains its separate native restart path.

Identical controls share the existing bounded control task, including initial
maintenance. Reverse source transfers continue through the grant's original
registry, preserving failed trace tombstones. A higher authenticated PREPARE
observes its fence before waiting for any control writer. Close cancels maintenance
and child scopes, attempts every cleanup, and drains control work without holding
journal monitors. A failed drain retains scratch ownership until the workers have
actually stopped; a later close can complete the release.

## Actual generation maintenance

Before a new native slot needs an inactive generation's space,
`MembershipGenerationMaintenance` captures the actual installed owner/cut and
acquires complete original copies satisfying both governing majorities. It uses
STATUS only as a hint, then verifies the prefix, images, generation manifest and
original members. Source pins and reservations remain owned through the durable
floor, peer observations, inactive retirement and floor release. Only transport
I/O, deadline or capacity failures can skip a candidate peer; protocol failures
cannot become fallback success. Every step retains the original scope deadline
and ballot fence.

The complete copies also reconcile previous possible peer endpoints before the
next publication intent. Neither a STATUS hint nor PUBLISH_ACK narrows that
retention ledger. The outgoing owner explicitly invokes the same maintenance path
before its own local vote. This batch does not retire frozen historical sources or
rotate their grant journal automatically.

## Qualification boundary

The [local receipt](phase3-evidence/native-dispatch.json) binds 39 passing Java
tests, followed by five current-source checks after tightening failed-drain
ownership. Those include the new blocked-worker ownership regression. All 675
Python tests pass; the final reader has separate optimized original-first testing.
Two independently recorded continuous histories and all 50 exact negative variants
pass original-first physical/network replay and archive relocation with assertions
disabled. These are local component results, not protected CI or public runtime
acceptance. The original failed publication attempts and their
service-side errors are retained under `target/v53-native-dispatch`. They exposed
the missing inactive-generation maintenance and unresolved prior dispatch; two
other development attempts corrected test invocation and decoding before running.
There is no measurement retry or relabeling of failed evidence.

The independent reader starts from actual public bootstrap, derives original
source captures and selected installation, then reconstructs both complete slot
histories, typed image semantics, peer/future ledgers and final physical files.
Wire replay binds original bytes to permanent owners, original copy delivery to
floor force, phase receipts to their dependent writes, and recording/checkpoint
receipts to actual publication. Exact evidence mutations run only after the
unaltered history passes, including after archive relocation with assertions off.

The end-to-end profile is one three-voter stable configuration with two selected
voters and an unchanged third voter, followed by BARRIER and DATA on the same
listener. Cancellation, higher-ballot fencing, expiry, abandoned scopes, lost ACK
and poisoned original transfer traces have separate Java regressions. Those
regressions are not represented as independently replayed end-to-end histories.

Autonomous election/discovery ownership, outgoing whole-slot coordination and
restart reconciliation, repeated-campaign maintenance, carried-entry readiness,
learner/joint lifecycle across all seven profiles, maximum combined resource
headroom and the complete 3B–3E gates remain open. No public membership API,
wire/storage format, frozen workload, cloud workflow or release pin is changed.
