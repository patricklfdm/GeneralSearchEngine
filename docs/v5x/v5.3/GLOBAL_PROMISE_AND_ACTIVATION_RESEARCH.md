# V5.3 global promise, selected sources and activation

Historical research note. Current decisions and local closure are recorded in
[PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md) and [the final audit](PHASE_0_CLOSURE_AUDIT.md).
Earlier open items, result counts and limitations below refer to that batch.

**Status:** executable integration candidate for D02/D03/D06. Phase 0 is OPEN.
The preceding ballot, transition and checkpoint models remain separate evidence.
This adapter adds a root-wide durable grant boundary to their per-slot voting
model; it is not a change to the production engine or an accepted byte format.

## Source audit and concrete mapping

Reviewed parent: `aa69189`. The Java sources still match the V5.2 development
implementation. Paths below are relative to the replication package.

| Actual code | Preserved obligation | V5.3 candidate / remaining difference |
| --- | --- | --- |
| `AutomaticStore.prepare` | Force promise; freeze image and descriptor; never resample a missing same-ballot basis | Separate root grant force and basis force, with crash between them. Missing basis requires a higher ballot |
| `AutomaticProtocol.beginCampaign` | Own durable basis precedes outbound PREPARE | Retain proposer inclusion and own-basis ordering with variable stable/joint quorums |
| `AutomaticRecovery.select` | Two distinct complete bases including proposer; common proven ancestry; longest prefix; highest accepted tail | Select a configuration quorum including proposer, after explicit prefix synchronization. Mixed-prefix selection is deliberately refused here |
| `AutomaticProtocol` PREPARE / INSTALL responses | First selected pair stays fixed; installation binds exact selection and local frozen basis | Force one immutable selected set; all its sources must install and acknowledge before ACCEPT. No same-ballot peer substitution |
| `AutomaticProtocol` ACCEPT / PROOF handling | Distinct durable phases before publication | Reuse the transition model's complete, configuration-bound receipt quorums; add root promise and selected-install guards |
| `AutomaticProtocol.published` | Recover carried entry, then publish a fresh operation-9 barrier before `LEADER_READY` | Recovered DATA/INTENT/FINAL/old barrier does not activate. Only a current-ballot barrier plus completed local publication can do so |
| `AutomaticStore.installProven`, `checkRecovery` | Snapshot proof cannot exceed retained root promise; prefix install does not clear root voting history | Candidate prefix synchronization first forces a verified certificate-derived fencing floor if needed; it creates no PREPARE basis or vote |
| `AutomaticProtocol.abandon`, failed-peer preference | Failed source does not change the already selected pair; later campaign can prefer another peer | Test fresh-ballot alternative selection. Autonomous discovery, timeouts and fairness policy are not modeled |

Source links: [AutomaticStore](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/AutomaticStore.java),
[AutomaticRecovery](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/AutomaticRecovery.java),
[AutomaticProtocol](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/AutomaticProtocol.java).

The production code still uses ranked three-member epochs, two selected bases,
one quorum peer and fixed-format records. Increasing a count does not implement
the proposed mapping. No Java/POM/workflow/source pin is changed in this batch.

## Root-wide durable fencing and ballot allocation

Each identity retains a monotonic allocation counter independent of membership
position. Stage an allocation above the local counter, durable promise and observed
ballots; force it before starting a campaign. A crash burns a forced reservation.
It cannot restart that proposal under the same ballot, and counter exhaustion
refuses without wrapping. The research ballot remains `(counter, proposer,
incarnation)`; the incarnation is a fixed synthetic identity, not authentication
or same-identity disk-loss fencing.

Each voter has one root-wide promise and a volatile highest-observed fence.
Higher observed ballots fence pending leadership/publication immediately; force
makes that boundary survive restart. The durable grant also binds the exact
predecessor authority. Per-slot voting history remains retained beneath it.
An old slot's otherwise valid local promise cannot override the root grant.

PREPARE has two durable boundaries. If the promise is forced but the basis is not,
restart retains the promise and refuses same-ballot recovery sampling. A higher
ballot can freeze a new basis. A duplicate complete PREPARE returns the original
basis even after ACCEPT changes the current tail. Source fetch additionally checks
that this exact frozen basis is still current and its owner is available.

For synchronization, validate the entire certified chain before staging a prefix.
If its highest certificate ballot exceeds the local promise, force that ballot as
an **adoption fence**, bound to the certificate's original authority, before forcing
the new prefix. It supplies no basis, no receipt and no permission to vote at that
old ballot in the new configuration. Subsequent PREPARE requires a fresh ballot.
A crash after adoption force but before prefix force retains the higher promise
and old prefix; retry can install the same verified chain. The input histories
start with this verified-prefix fencing invariant already established.

This adoption record is a candidate new storage operation. Current Java rejects
an incoming proof above its promise; it does not expose this new operation.
Its eventual record bytes, source verification, I/O quarantine and physical crash
behavior still require D08 and storage qualification.

## Selection, failed sources and activation

The candidate uses a conservative synchronization boundary: all selected frozen
bases must describe the same certified predecessor authority. A lagging or newer
view cannot be counted merely because its configuration number is larger. Validate
and force the needed chain, preserve the root promise, then begin a fresh campaign.
This is an alternative to generalizing Java's longest-prefix selection inside an
already fixed mixed-prefix quorum; it makes fewer assumptions but may cost rounds.

Require complete fetched bases from a distinct old/stable or joint quorum,
including the proposer. Choose the highest accepted tail; equal-ballot conflicting
tails refuse. Force the exact selected set before sending installation requests.
Each source must match its own current immutable basis and force the same decision.
All selected installation ACKs precede the first ACCEPT. Late basis replies cannot
rewrite the selection. If a source becomes unavailable after selection, use a new
ballot and a newly verified quorum; successful selection alone is not activation.

After ACCEPT and PROOF quorums, force the certified local prefix and stage the
application-publication callback. The callback must still belong to the current
durable promise and observed fence. Only a BARRIER whose payload identifies this
ballot can set local READY. A recovered INTENT first enters joint authority; its
matching FINAL uses both majorities; a fresh barrier then uses new-stable authority.
A removed proposer cannot start the new-stable campaign. Crash loses READY even
when the old barrier/prefix was durable.

The model uses a fresh ballot per recovered slot and stops after activation. It
does not require a PREPARE round for every future client operation, nor implement
steady-state multi-slot leadership. Choosing the production fast path, revalidating
an existing leader across membership change and quantifying extra recovery rounds
remain open. Local READY is not a lease or a guarantee that an isolated leader
can successfully serve a strong read; the service path is excluded.

## Executable evidence

Implementation: [adapter](../../../scripts/v53/activation_model.py),
[independent root observer](../../../scripts/v53/activation_oracle.py),
[schedule driver](../../../scripts/v53/activation_research.py),
[tests](../../../scripts/v53/test_activation_model.py).

The transition oracle first validates every nested vote, certificate and forced
prefix. A separate chronological observer reconstructs root promises, observed
fences, allocator reservations, fetched bases, durable selections, installations
and publication callbacks. It never reads the live adapter's state. It independently
constructs old/new majority families and checks highest-tail selection. Shared
immutable record encoding is not an independent wire-format implementation.

Five deliberate faults must cause their specific safety error: start before
allocator force, resample an incomplete basis at the same ballot, change selected
quorum at the same ballot, let a per-slot grant bypass a newer root promise, and
activate after publishing a carried entry. Original histories pass before missing
durable-event mutations are tried. A subprocess confirms allocator rejection under
Python `-O`. Limited traversals return INCOMPLETE; failed executions preserve their
trace; output directories cannot overwrite previous evidence.

The finite matrix comprises seven add/remove/replace size profiles, old/joint/new
views, tail absent/present, and ten named cuts: **420 cases**. Cuts cover allocation
stage/force, root grant force, basis force, selection force, installation, ACCEPT,
PROOF, pending publication and successful publication. Each execution then restarts
all six identities and completes a bounded recovery to a fresh activation. The
driver supplies an observed upper ballot bound and explicit source choices; it
does not model an autonomous failure detector or establish a recovery-time SLA.

The first local-inclusive minimal quorum is used before interruption and the last
after recovery. This is not every quorum pair or every asynchronous interleaving.
Additional directed tests cover source loss, alternative recovery quorum, higher
ballots during pending install/publication, accepted INTENT, removed proposer,
unavailable complete sources/ACKs at the abstract boundary, and adoption-fence crash.
Sixty representative histories (all view/tail/cut combinations for the first size
profile) replay from compressed JSON. Every case contributes to the trace digest.

Results and exact parent/source binding: [activation-research.json](activation-research.json)
and [development status](DEVELOPMENT_STATUS.md). They are local model evidence,
not protected CI, real disks, application snapshots, production runtime or cloud
qualification. Serialization replays the originals; case labels do not substitute
for observed input view and acceptance state.

## Remaining decisions

D03 now has a concrete durable-allocator/global-promise/selection/activation
candidate, with explicit differences from the current Java implementation.
Phase 0 is not frozen. Before production declarations:

1. Decide the production recovery/steady-state round policy and exact adoption
   record, including bounded missing-source handling and I/O failure semantics.
2. Resolve retained authority lifetime/representation. The prior checkpoint model's
   16-entry/four-change caps are exploration bounds, not a usable long-lived engine.
3. Specify learner materialization and incarnation fencing; operation ID/query/
   cancellation; removed-node read policy; exact API, reason codes and byte limits.
4. Add independent byte fixtures and physical/public schedules before implementation
   can be called qualified. Keep the running V5.2 evidence as predecessor evidence.
