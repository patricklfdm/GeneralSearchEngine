# Original joining controls and learner retention authorization

`scripts.v53.joining_control_evidence` composes the remaining eight control
exports and six learner-content authorizations on the same `9136083f` native
`3-ADD` history. It requires the complete physical, network and
[export-lifetime replay](PHASE_3_JOINING_EXPORT_REPLAY.md) first. A transcript,
lookup alias, hint or completed initialization response cannot supply replacement
storage authority. No native execution or measurement is repeated.

## Distinct control capabilities

| Family | Original sessions | Required authority |
| --- | ---: | --- |
| Learner ROOT | 1 | Exact active, nonvoting, pre-JOINT reservation and current original ROOT |
| Pending INTENT metadata | 2 | Original SEALED request and completed local native application, before publication/fencing |
| Preparation hint | 1 | Current old proposer, unselected settled grant and delivered original old-peer grant |
| Retention fragment | 2 | Actual old owner's latest settled grant, exact packet envelope and frozen peer/learner ledgers |
| Completion observation | 2 | Original joining initialization, three durable ledgers, current cut/fence and live endpoint owner |

The ROOT request uses its reservation-specific alias and learner correlation.
It cannot enroll an existing voter, a removed identity or a completed/cancelled
operation. Pending INTENT metadata is independently assembled from the original
ENTRY, ACCEPT, PROOF, CERTIFICATE, reduced CATALOG, checkpoint and command bytes.
Its parent and target are the actual adjacent endpoints; it cannot outlive that
pending application or turn into a complete JOINT source.

The preparation hint's sources come from captured original grants in the same
ballot. Each advertised remote grant must have reached the original proposer
before the hint request. The hint remains routing information: it neither proves
an installed selection nor creates a new voting member. Each retention fragment
independently names its owner's still-current original BASIS and the exact
envelope and frozen ledger wrappers. A new local PROMISE invalidates that grant;
retaining old bytes somewhere is insufficient.

A completion transfer requires the original initialization transaction to finish,
plus the relevant owner's ledger recovery. The original endpoint scope is bounded
by subsequent native reopen: an initial endpoint cannot impersonate a later owner
merely because both generations have the same cut. Each transfer also remains
inside the current generation and its original fence interval. Completion is an
initialization observation, not public READY, a grant, vote or read barrier.

## Learner exports and actual retention

Four pre-JOINT content sessions depend on two original retention rounds. For each
round, the reader derives the exact offered ledger from the previously checked
current storage, compares the peer ACK's intent/revision/ledger digest, and binds
both local and peer force sequences. The local force precedes the peer request;
the peer force precedes its response. Distinct original voters satisfy the stable
majority. The proposer must receive that ACK before emitting a source offer.
The recording expires at the next pending slot, local PROMISE or generation
replacement. An offered object does not itself establish a recording.

Two post-JOINT content sessions use the locally published joining configuration
and original retained learner request. In this history, two actual retained-head
exchanges precede them. Their replies identify the original sealed source, and
the retained joining handoff must already have completed. Each old owner forces
its exact derived confirmation before that confirmation is used. The checked
current capsule/ancestry must still cover the resulting retention obligations.
This is the published-source route; it does not reinterpret the joining member
as an earlier stable voter or create another pre-JOINT recording.

## Coverage, validation and limitations

The composed result covers all **361 content-bearing sessions and 686 committed
contents** in this one healthy execution. The previous reader bound 353 sessions;
this reader covers the other eight and supplies the six explicit learner
authorization checks. The network reader separately retains two rejected-only
sessions. They are not successful content coverage.

The [receipt](phase3-evidence/joining-control-replay.json) binds the producer,
source/build, tests, original-first result, negative replay and portable archive.
The 14 negative variants preserve all physical files and directories and must
still pass both the network and preceding export readers. Only the exact declared
control failure counts. They exercise altered aliases/control bytes, false
retention ledger/revision, missing local/peer force, late ACK delivery, early head
access, missing confirmation force, early completion and a closed endpoint owner.
Malformed original evidence, accepted mutations and unrelated failures fail the
qualification driver.

Initial retained diagnostics concern the new reader's callback-scope lookup and
an inspection script's name collision with Python's `inspect` module. They are
reader/tooling failures, not new runtime observations. The final reader obtains
the server scope from the already paired original request-read event.

`observedControlExportsQualified` and `observedLearnerRetentionQualified` describe
this healthy history only. `allExportFamiliesQualified`,
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
and `phase3Complete` remain false. Expiry/cancellation and loss cases, remaining
maintenance/control composition, process cuts, all seven profiles and the frozen
acceptance mapping remain required. No production Java, POM, workflow, toolchain,
frozen format or workload/timing bound changes are included.

```bash
python3 -B -m scripts.v53.joining_control_evidence <collection-v3-raw> --qualify
```
