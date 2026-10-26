# V5.3 Phase 3 entry and closure checklist

Status: **OPEN**, entered on 2026-10-25 after local Phase 2 closure at `f0d4dca`.
The operator authorized pushing that branch and starting the first Phase 3 batch.
The Phase 2 audit remains a historical, source-bound storage qualification.
The subsequent operator goal authorizes continuous local work through this whole
checklist, with a local commit after each validated batch and no automatic push.

## Implementation order

| Batch | Deliverable | Frozen obligations | Closure evidence still required |
| --- | --- | --- | --- |
| 3A | [Private durable activation](PHASE_3_ACTIVATION.md), locally qualified | S02, S07, S09, S10; N04/N05/N08–N11/N17/N18 feed into later complete gates | Own grant, fixed eligible sources, exact installations, retries/deadline/fencing pass component checks; complete network/process qualification remains 3B/3E |
| 3B | [TCP transport](PHASE_3_TRANSPORT.md), [source export](PHASE_3_SOURCE_EXPORT.md), [receiving scratch](PHASE_3_SOURCE_RECEIVE.md), [complete source exchange](PHASE_3_SOURCE_EXCHANGE.md), [referenced records](PHASE_3_RECORD_EXCHANGE.md) and [runtime-scoped transfer service](PHASE_3_TRANSFER_SERVICE.md) components locally qualified; full runtime integration/discovery remain open | S02/S04/S10 | Root-bound STATUS/SOURCE, bounded authenticated transfers, newer-prefix adoption and fresh ballot, failed-source rotation, original deadline, physical/network/process traces |
| 3C | Learner preparation and joint transition | S01/S03/S05/S09 | Real nonvoting ADD/REPLACE learner, exact image/receipt/revision, SEAL/INTENT eligibility, separate old/new majorities, FINAL and new-view barrier; all seven profiles |
| 3D | Generalized vote/publication and automatic continuation | S01/S02/S07/S10 | Carried entry first, ACCEPT then PROOF, exact certified application, fresh barrier before service, stable round reuse, removal fencing and restart |
| 3E | Protocol closure audit | S01–S05/S07/S09/S10 and relevant N01–N24 | Deterministic faults plus fresh-process halt/SIGKILL and network cases, independent original-first physical/history replay, complete requirement mapping |

The exact axes and negative families are in [the acceptance register](ACCEPTANCE_REGISTER.md)
and [machine plan](acceptance-plan.json). Their 3,310 S rows and 24 N families remain
PLANNED until their owning complete qualification passes. A component test does not
close an S family. Phase 4 owns enabled public operations/reads and Phase 5 owns
combined hardening; this phase must provide their real protocol dependencies.

Within 3B, [original network PROMISE binding](PHASE_3_PROMISED_SOURCE.md) now feeds
complete verified received sources into fixed quorum selection. It retains receive
ownership through selected installation and rejects missing historical provenance.
The real TCP trace ends at selection; complete network installation, historical
witness delivery and the remaining discovery/recovery work are still open.

## First batch boundary

Implement an internal activation controller over `MembershipGrantJournal`, using
the existing PREPARE/PROMISE/SELECTED/INSTALL_ACK envelopes and contextual verifier.
Exercise actual admitted storage at sizes 3/4/5, plus joint-quorum and adverse
delivery component tests. Preserve original disk bytes and failed local runs.

No socket service, learner transfer, public READY, client retry, automatic FINAL,
paid cloud or protected acceptance is claimed by this batch. Source packets passed
to the controller must already be verified and staged by their owner; transport
authentication and staging lifetime integration belong to 3B. Existing bytes,
resource bounds, legacy runtimes, workflows and the V5.2 runner are unchanged.

## Exit and rollback

Each batch requires focused tests against its actual source/build, retained logs,
documented limits and a coherent local commit. Phase 3 closes only after every
row above has concrete evidence; failed attempts cannot be replaced by green
retries. Rollback of 3A removes its internal controller and journal adapter methods;
no public factory or persisted format depends on it at this point.
