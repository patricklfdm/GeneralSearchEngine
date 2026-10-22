# Phase 1 original frozen-source selection

Historical batch record. Later completion and remaining runtime gates are recorded
in the [Phase 1 closure audit](PHASE_1_CLOSURE_AUDIT.md); pending statements below
refer to this batch, not the final local Phase 1 state.

Status: local conditional byte calculation and independent fixtures. No membership
runtime, PREPARE grant, durable SELECTED write, installation ACK or READY is enabled.
The full same-round/catalog/recovery model remains a separate Phase 1 obligation.

## Frozen inputs and one decision

`MembershipSelection.Source.verify` accepts a fully walked capsule, an exact framed
BASIS, the previously retained source reference and the authenticated complete
owner identity. It checks the original basis UUID/digest, permanent storage and
endpoint, root, governing view, ballot and owned basis parent. An optional accepted
tail must have its original ENTRY/payload, legal control context, eligible original
and accepting ballot identities, and that source's owned ACCEPT at the same parent.
All these checks are conditional on authentic ownership observations from later
storage/transport integration. A wire sender cannot supply its own trusted `Owned`.

A campaign admits 2–6 ordered distinct sources in the same root/ballot/configuration,
with both required majorities and its exact local proposer basis. The 5→4 joint
case keeps a removed proposer plus the necessary survivors; a smaller majority
that excludes the proposer cannot replace it. A later configuration requires
verified adoption and a fresh campaign, not mixing old and new basis responses.

The calculation first verifies compatible proven cuts and monotonic complete
catalogs, including permanent identities and allocator/retirement watermarks. A conflicting known anchor is rejected even when a supplement carries new ACKs. It
selects the longest proven prefix, then the highest-ballot accepted entry at the
next slot. Equal-ballot different entries fail closed. Original entry origin and
payload bytes are retained without re-encoding them at the recovery ballot.

A compatible proven prefix settles every covered slot; a minority's different
accepted value at a covered slot does not displace it. Its original source/tail
stays in the decision inputs for inspection. This is not an assertion that the
minority value was chosen, and does not authorize deleting its physical bytes.

The result encodes the unchanged 1.3 SELECTED schema with exact ordered basis
references. An in-memory campaign returns at most one decision and cannot select
again after abandonment. Phase 2/3 must force this decision, install it on every
selected source and collect all exact installation ACKs before using it to vote.
Restart never inherits this object's readiness; this helper has no readiness bit.

## Compacted ancestry without resampling

Verified capsule anchors now retain cut **and** catalog/application digests. A cut
hidden inside a stable range is not inferred from its index or common ROOT.

For such an original frozen source, a supplemental existing-format RANGE
CHECKPOINT must connect its exact cut/catalog/application to a verified anchor in
the longer capsule, within the same stable view. Each CHECKPOINT_ACK binds the
complete statement, end cut and durable identity, and has an authenticated owned
observation after that exact end was applied. A statement with different catalog
hashes, old endorsements, missing ownership or an incomplete majority is rejected.

This supplement never replaces the frozen BASIS or changes its original inventory.
It is a separate ancestry proof about those immutable endpoints. Ordinary progress
may continue after the grant; duplicate PREPARE must still return the original basis.
Only required supplements are admitted: at most six, each at most 16 KiB including
all ACK frames, within the existing 2 MiB miscellaneous reservation (at most 96 KiB).
No new storage/wire kind, frozen resource limit or checkpoint trust anchor is added.
Actual allocation, lease ownership and source loss scheduling are later runtime work.

## Local qualification

- Seven focused selection regressions exercise seven profiles, heterogeneous cuts,
  no-proof refusal, highest/covered tails, same-ballot conflict, identity/digest
  substitution, missing owned tails, wrong era/ballot, mandatory proposer,
  either joint majority, missing/changed bridge observations and fixed decisions.
- A fresh Java worker emits 28 selection fixtures / 117 sources, using previously
  independently replayed compacted histories. Four cases per profile cover
  heterogeneous cuts, highest next-slot tail, covered minority tail and joint view.
- The independent Python reader checks original capsule bytes, separate images,
  exact source records and parent/tail/basis fixture force order. It independently
  recomputes the selected prefix/tail and original SELECTED references. Thirteen
  original-first negatives reject; copied evidence replays at another path.
- These are deterministic byte fixtures with real single-JVM file-force calls.
  They are not a causal network/grant history, crash evidence, a liveness proof,
  or evidence that a live cluster accepted these synthetic tail observations.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53SelectionTest,V53CapsuleTest,V53ContextTest,V53ResourceTransferTest,V53SourcePacketTest,V53FormatTest,V53DeclarationsTest,V53PublicApiInventoryTest,V51VersionBoundaryTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest discover -s scripts/v53 -t .
python3 -m unittest scripts.test_build_coordinates scripts.test_ci_v51_bundle
python3 -m scripts.v53.selection_qualification target/v53-selection/run-UNIQUE
```

The driver refuses existing output, checks source/JAR/class freshness and retains
failure receipts. Logs are under `target/v53-phase1-selection/`. The 5.3 build bundle
requires the executed unskipped selection suite and both new fixture classes.
Legacy coordinates, APIs, workflow jobs and the independent V5.2 experiment remain
unchanged. Protected/unified qualification is still deferred.

[Retained summary](phase1-evidence/selection.json): 52 focused Java tests, all
217 V5.3 Python tests and 20 build-contract tests passed. The source binding is
parent `52871ef` plus the tested dirty inventory; final reporting edits follow it.
The initial Java compile caught the DATA codec overload's return type; its failure
log remains alongside the corrected executions. No clean-source CI is claimed.
