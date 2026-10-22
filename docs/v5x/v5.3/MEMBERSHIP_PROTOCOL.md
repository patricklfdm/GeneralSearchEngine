# V5.3 membership protocol

Normative Phase 0 algorithm; implementation and protected qualification are later
gates. This document resolves the proposals recorded in earlier research notes.
It assumes crash faults, authentic exclusive replica identities, atomic durable
forces as modeled, and eventual communication for progress. It does not tolerate
Byzantine nodes, concurrently cloned disks, arbitrary membership edits or permanent
loss of every required authority copy. Safety never depends on elapsed time.

## Root, views and entry authority

Bootstrap creates immutable group UUID, history UUID and genesis ROOT digest.
Current configuration is an ordered set of complete identities plus generation.
An identity consists of node ID, storage UUID and endpoint. Preserve descriptors of
all initial/reserved/removed members; new storage or endpoint requires a new node
identity. One add, remove or replacement changes exactly one old/new member at a
time, with stable sizes 3–5 and maximum union six. No learner contributes a vote.

Let O be old voters and N proposed voters. Stable authority requires more than
half of O. Joint authority requires more than half of O **and** more than half of
N from distinct eligible identities. Never use either side alone or a majority of
the union. A valid source quorum includes the proposer; 5→4 removal may therefore
need a removed proposer plus three survivors, even when another smaller quorum
exists without that proposer.

The next entry authority is derived only from a locally forced verified prefix.
An INTENT at index i is proposed/recovered under old stable authority. Once its
proof/prefix is forced, index i+1 has joint authority. Joint authority permits only
the exact matching FINAL; after FINAL force, the following slot uses new stable
authority. The logical entry identity binds root, authority, predecessor, index and
original entry bytes, not whichever ballot/witness representation later proves it.
No speculative next-slot pipeline; inconsistent same-index authority is corruption.

## Operation lifecycle and readiness

1. Strongly read current configuration and next operation number. Submit exact
   root/number/expected-config/kind/target. A certified RESERVE validates all bounds,
   reserves new identities permanently and advances next number. It creates no
   voting privilege. Exact duplicates return the retained progress; changed payload
   is CONFLICT. Retired numbers never execute again.
2. A certified PREPARE increments internal revision and freezes current application
   and catalog cut. A learner installs the exact verified image/capsule and forces
   its matching receipt. REMOVE has no learner receipt. READY is then certified.
   Concurrent ordinary writes may advance the application; the caller request ID
   remains stable, and a fresh preparation revision catches up again if necessary.
3. SEAL validates the exact prepared application state and forced readiness. Its
   certification is the irreversible boundary; it binds full request, prepared cut
   and learner receipt. Pause DATA after SEAL until FINAL. Controls/activation
   barriers do not alter the sealed application state; the learner must nevertheless
   install their full proven metadata suffix before voting in the joint view.
4. Certify INTENT using old authority. A joining identity becomes eligible for joint
   voting only after its matching image, receipt, complete metadata and INTENT
   are locally forced. It cannot help prove the INTENT that grants its eligibility.
5. Recover/commit matching FINAL using both majorities; apply target configuration
   and terminal result. Activate the new leader with a new current-ballot barrier
   before accepting service. Persist known removal and refuse new captures on the
   removed process. Keep old evidence until ordinary safe floor/retirement permits it.

CANCEL may certify only before SEAL. A competing accepted SEAL must be recovered
even if a later caller requests cancellation against an apparently READY catalog.
Chosen CANCEL prevents delayed SEAL/INTENT. A client disconnect/deadline is not a
certified cancellation; lost responses are queried using the original operation.
Retire only a certified contiguous prefix of terminal detail rows. Keep the
watermark, next number, identity reservations and all required membership descriptors.

## Election, recovery and service rounds

Ballots totally order `(counter, proposer node bytes, durable storage UUID bytes)`;
allocation advances a separately forced local counter beyond every observed bound.
Process/transport session IDs are separate correlation identities, not ballot reuse
permission. No `(epoch-2)%3` rank rule applies to 1.3. Persist root-wide promise and
its exact configuration/cut. A higher observed ballot fences old in-flight work
immediately; force rechecks the fence. Crash recovery retains the durable promise.

Force own grant then immutable own basis before remote PREPARE. Each grant freezes
the proven prefix/capsule plus at most one owned accepted tail. A grant forced
without its basis cannot be resampled at the same ballot: advance to a new ballot.
Duplicate PREPARE returns the original basis even if local progress later advances.

Select one complete eligible quorum containing the proposer, persist the exact
ordered source IDs/basis digests once, and prohibit replacement at this ballot.
Verify compatible proven prefixes; choose the longest proven one and then the
highest-ballot accepted tail at its next index. Conflicting equal-ballot values,
divergent proven parents or missing authority fail closed. A carried INTENT/FINAL
keeps its original identity and governing authority. Install the exact selected
state on every selected voter and force/collect every selected installation ACK
before ACCEPT. A non-selected late basis cannot change the decision.

Within one configuration era, different source prefix lengths are permitted only
after verifying their ancestry: take the longest proven prefix, discard only tails
already covered by that proof, and select the highest accepted tail at its next
index. Never mix promises for different configuration eras. If discovery or a basis
reveals a later proven INTENT/FINAL, verify/install that prefix and adoption fence,
end the old campaign, then allocate a fresh ballot under the newly governing view.
Read-only root-bound STATUS/SOURCE discovery from known historical identities can
carry authority forward; receiving it does not count as an election vote. An old
view rejection must not leave a node permanently retrying a known obsolete view.
The Phase 0 adapters synchronize these cuts explicitly; heterogeneous-cut discovery
and compacted-source composition are required Phase 1 implementation/model gates.

Selected source failure starts a fresh ballot under the same bounded retry/deadline
policy, not same-ballot reselection. Source scheduling rotates after a failed
candidate/source pair, preserving the original campaign deadline; give an eligible
alternative one bounded request opportunity before a previously failing source.
Do not advertise a liveness bound under indefinitely slow storage or scheduling.

For every entry: validate selected decision, local applied parent and root fence;
force ACCEPT on the applicable majority; construct the exact acceptance proof;
force PROOF on the applicable majority; force certified local prefix/materialization;
recheck current authority before successful public callback. Receipts are phased,
root/view/ballot/index/digest/identity-bound and counted once. Publication never
reclassifies an indeterminate mutation as an unsubmitted one.

Recover carried entries before a new stable current-ballot BARRIER may publish
READY. Installing a verified prefix above the retained promise first forces a
certificate-derived adoption floor. Such an adoption floor is not a new PREPARE
grant/basis and cannot authorize old-ballot votes. Prefix and grant writes exclude
each other; no callback bypasses that fence.

After READY, reuse the same ballot and original selected set for sequential stable
DATA/CONTROL/BARRIER entries as specified in
[steady rounds](STEADY_ROUNDS_AND_CATALOG.md). INTENT ends that stable round; joint
FINAL and new-stable activation need fresh ballots. Restart never restores READY
or a previously pending leader callback. Strong reads need the inherited actual
current authority/barrier path, not a heartbeat lease or status observation.

## Recovery, compaction and removal

Validate root and complete capsule/catalog/application inventory before selecting a
generation. Ranges carry new forced checkpoint endorsements; complete membership
certificates and sealed operation descriptors remain explicit. Every required
reference resolves to exact bounded owned bytes. No latest-configuration shortcut,
unverified source hash, genesis fallback or accepted-tail omission is permitted.

Copy a complete new generation, its promise/basis/selection/owned tail and snapshot;
force its selector; obtain exact durable floor copies satisfying the cut's next
authority; force a retirement inventory; only then delete listed obsolete bytes.
Above-floor accepted bytes can retire only with an exact durable active-generation
copy. A crash at any boundary reopens the last forced selector and resumes the exact
retirement inventory. A capsule is evidence of authority, not permission to delete.

On known removal, stop voting, campaigning and new data/read captures. Retain enough
root/configuration metadata to reject stale messages and report REMOVED. An unaware
isolated former voter cannot make a strong quorum, but explicit stale/minimum reads
retain their inherited local guarantees. Already captured read snapshots are not
retroactively revoked. Lost-majority operators must restore the required authentic
copies or create a distinct verified-backup group; editing membership is forbidden.

Maintenance is operator-serialized same-version stop/restart with fresh surviving
majority checks, local drain and rejoin verification before the next stop. Its
observation is not a distributed maintenance lock. Removal/failure does not authorize
deleting local evidence or stopping another host. Mixed-version upgrade is outside
this protocol. API outcomes and bytes are fixed in
[API/format compatibility](API_FORMAT_AND_COMPATIBILITY.md).

## Evidence mapping and composition obligations

Arithmetic, durable ballots, predecessor chains, global promises, learner/operation
integration, floors, capsules and stable rounds each have independent model
observers and counterexamples. They do not form a formal proof of all schedules.
Phase 1–5 must compose same-round operation validation, compacted frozen sources,
actual application bytes, network frames and physical forces in the implementation;
the frozen [acceptance register](acceptance-plan.json) identifies those tests.
