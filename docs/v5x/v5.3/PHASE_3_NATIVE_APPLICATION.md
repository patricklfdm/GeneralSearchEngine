# Phase 3 — native certified application recovery

This internal path removes caller-supplied historical voting observations from
application recovery. It is a prerequisite for a pending publication target; it
does not make that target a published generation or a durable peer obligation.

## Original authority and application boundary

The new native `MembershipGrantJournal.applyCurrent(configuration, storage)`
overload requires the actual native history owner. A private-constructor
`CertifiedCurrent` capability binds the complete local pending certificate to
the original selector, PROMISE, SELECTED and exact retained packet. The owner
revalidates those original bytes and the current ballot, re-forces the active
certificate and its parent directory, and checks the fence again.

Only that capability can attach the exact certificate as historical application
authority. It creates no remote ACCEPT/PROOF observations. The existing explicit
observation overload still requires its original separately owned phases; neither
an empty observation set nor a raw packet gains the new admission privilege.

Typed core replay derives the next application image and catalog from the
unchanged current prefix and original entry. The replay service seals its own
temporary-file inventory before the owner rechecks the capability. Checking that
inventory from inside the delegated writer would mistake legitimate core writes
for external interference. The existing guards remain active after replay and at
each applied-end force/ACK boundary.

Only the real newly forced local applied end returns a new local checkpoint
observation. The selector and published cut remain unchanged. Publication still
requires the complete checkpoint majority, exact original staging and generation
verification. Reopening and reapplying the same certificate reconstructs the same
end without relying on an old process's in-memory observation set.

No disk/wire format, resource ceiling, public factory, workflow or legacy entry
point changes. The capability is internal and cannot authenticate an arbitrary
received certificate. Existing trusted-storage/private-network assumptions remain.

## Qualification

The [source-bound receipt](phase3-evidence/native-application.json) records the
isolated source snapshots, tests and original evidence under
`target/v53-native-application/`.

- Six actual public-bootstrap histories cover 3/4/5 voters with EMPTY and backup
  sources. Each publishes BARRIER, DATA and a fresh-round BARRIER after reopening
  the owners. All 72 node publications, original votes and reclamation stages are
  independently reconstructed. Fresh voting/certification commands still receive
  their genuine observations; the absence of caller phased observations refers
  specifically to the new application overload.
- Ten halt/SIGKILL cases use one separate three-voter EMPTY certificate prelude,
  twenty fresh JVMs and five live lock probes. Recovery repeats the original
  application without an external certificate/observation input. Independent replay
  derives the exact interrupted and recovered files, original replay claim, local
  ACK and unchanged published cut. These are process crashes, not power-loss tests.
- Java-only rejection checks cover the old overload's missing observations,
  non-native owner, proof-only local state, insufficient checkpoint majority and
  higher-ballot observation during certificate reseal, replay and ACK production.
- The final source passes 13 selected Java tests. An earlier known-failed source
  separately passed eight application and three round-storage tests before its
  remaining build was stopped. Those eleven tests are not labelled final-source
  results. The initial callback-boundary and early test-hook failures are retained.
- All 658 Python tests pass normally and under `-O`. Original-first replay also
  requires eight exact evidence-negative rejections, including a premature ACK,
  lost force event, changed original certificate and substituted published cut.
  Normal, optimized and relocated replay must agree before finalization.

The DATA image's typed semantics are checked by the existing Java application
assertions; Python binds the exact resulting bytes and typed-inspection files.
This batch does not claim a new independent proof of the core serializer.

## Remaining integration

Pending future endpoints still need an explicit durable retention representation,
quorum recording, selection propagation and actual dispatch. The current GSPR
plan continues to require endpoints authenticated by its current published
history. Automatic owner lifecycle, the complete offline-survivor continuation,
cross-view pending contexts, learner/joint completion, generalized automatic
publication and the full [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remain open.
Local qualification is not protected CI, public-runtime or cloud acceptance.
