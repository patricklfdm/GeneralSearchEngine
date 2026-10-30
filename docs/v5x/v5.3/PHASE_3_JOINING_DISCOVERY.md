# Discovering an original old proposer's preparation

Phase 3 remains **OPEN**. `MembershipJoiningEndpoint.initialize()` now discovers
an existing preparation by reading the known old identities. It then uses the
same managed exact-source acquisition, native retention initialization and voting
handoff. The complete native history uses this entry instead of receiving either
the proposer identity or an in-memory hint from its test coordinator.

`MembershipJoiningPreparationDiscovery` makes one sorted pass over the current
JOINT cut's old identities. Each read uses the existing hint alias and bounded
transfer protocol. A valid first-request `NOT_READY` means that this endpoint has
no live published preparation; only then may discovery try the next identity.
The response must have exact root, identity, view, ballot, trace and sequence
correlation and a valid promised ballot. Reading that promise does not observe it,
allocate a ballot, grant a vote or select a source. A mid-transfer refusal stops
discovery instead of replacing a partially received hint.

Transport IO/deadline failures may move to another old identity only after the
existing pull exhausts its identical-request retries (at most three, or a stricter
caller bound). Capacity, closed transport, unclassified I/O, explicit non-absence
rejections, malformed correlation and invalid hint bytes stop the operation.
The transport can expose a remote handler disconnect as IO; discovery does not
claim to distinguish its internal cause from a broken connection. No failed peer
is treated as a vote or evidence of a majority.

The first complete valid hint fixes the routing result. There is no best-ballot
selection, hint union, new campaign, polling loop or renewed deadline. The actual
unused joined owner subsequently verifies every advertised original BASIS and
the conservative retention union before forcing initialization. If every old
identity is absent/unreachable, this initialization attempt fails; scheduling a
future attempt remains the runtime coordinator's responsibility.

The absent-publication response validates the initial read against the actual old
owner and exact joining identity, checks the endpoint's scratch ownership, and
retains its original request deadline/close guard. It creates no transfer or grant
and changes no persistent authority. Existing live transfers and exact completed
read-response caches keep their normal lifetime rules.

Discovery reserves 64 KiB of existing CONTROL capacity until its reader exits and
the discovery owner is closed. Managed initialization also retains its existing
64 KiB routing reservation through admitted force completion, including concurrent
close. All reads share the original joining start/deadline and unchanged local
cut/fence guard. Close cancels a pending read; it does not interrupt admitted
native force work. Resource bounds, frozen wire records and public APIs are
unchanged.

## Validation boundary

Focused tests use actual encoded frames, production handlers and conditional
original disk fixtures. They cover all five joining profiles, another original
old proposer, one-pass absence, identical transport retries, fatal/local failures,
mid-transfer refusal, malformed requests/correlation, original deadline/guard
revocation, cancellation, unchanged local authority and returned resource charges.
These fixtures do not qualify native initialization or public readiness.

The initial 24-test run passed in 42.460 seconds. The final-source run passed
**68 tests in 297.635 seconds**, with zero failures or skips; all main and test
sources compiled. Results, immutable inputs and the verified archive are recorded in
[`phase3-evidence/joining-discovery.json`](phase3-evidence/joining-discovery.json).
The affected endpoint/transfer regressions are included in that final run.

The complete TCP preparation/discovery/acquisition/initialization/FINAL/BARRIER
and retaining cold-reopen history is compiled and **deferred**, on the same
original owner/source/history throughout. Automatic old-side preparation/election
scheduling, complete learner orchestration, all-profile native/process cuts,
maximum combined resources and independent original-first replay remain required.
See the [hosted acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md). No workflow,
POM, paid cloud, V5.2 experiment or repository setting is changed.
