# V5.3 checkpoint, floor and retirement research

Historical research note. Current decisions and local closure are recorded in
[PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md) and [the final audit](PHASE_0_CLOSURE_AUDIT.md).
Earlier open items, result counts and limitations below refer to that batch.

**Status:** bounded executable candidate for D06/D09. Phase 0 remains OPEN.
This extends the [transition chain](TRANSITION_CHAIN_RESEARCH.md); it changes no
Java storage, public API, wire format, CI, POM or V5.2 cloud execution.

## Actual predecessor behavior reviewed

The local source at parent `5a890bf` still has the V5.2 implementation of
[`AutomaticRecoveryFiles`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/AutomaticRecoveryFiles.java)
and [`AutomaticStore`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/AutomaticStore.java).

- Recovery generations are selected separately from writing their files. Source
  inventory and hashes bind the selector and complete generation files.
- Floor establishment retains two distinct complete sources at the same cut,
  including the exact current local source. Two is a fixed-membership assumption;
  it is not sufficient for every proposed V5.3 configuration.
- Cleanup requires a durable floor and retains the exact retirement inventory
  before deleting inactive files. Partial deletion is resumable; an unfinished
  retirement prevents treating that directory name as a free generation slot.
- Current `deletable` refuses every old ACCEPT/PROOF above the floor. Root promise
  and authority metadata are separate from disposable generation files. Losing a
  selected generation after initialization cannot silently return to genesis.

The candidate below evaluates these obligations for mutable membership. It is
not a claim that the current implementation already follows the new rules.

## Candidate recovery boundary

Each synthetic source contains an owner, generation identity, a complete certified
snapshot prefix, a certified journal suffix and at most one unresolved owned
acceptance. Snapshot and journal bytes have a hash-bound seal. These are research
JSON bytes and metadata, not GSE application snapshots or GSER records.

The immutable input is a transition execution already accepted by its independent
history oracle. A source must match that owner's observed forced prefix; its tail
must match the owner's observed ACCEPT at the next slot. A configuration counter,
latest FINAL, or an unexplained digest cannot replace the predecessor chain.

Checkpointing is serialized against history advancement in this model:

1. Reserve an inactive generation. Copy the certified journal suffix into the
   snapshot while retaining the **complete** authority chain and exact owned tail.
2. Force snapshot, journal and seal. Stage and separately force the new selector.
   A crash before selector force still opens the previous generation.
3. Derive floor authority from the certified cut: stable old majority before
   INTENT, both majorities after INTENT, new stable majority after FINAL. Copy each
   selected source's complete files and force the floor only after every copy.
   Require the exact selected local packet among these distinct eligible voters.
4. Retain the inactive generation's complete retirement inventory, then force that
   record. Delete its files individually; delete its empty directory; clear the
   retirement record last. Repeat crashes can resume the remaining deletions.

The candidate permits an above-floor unresolved ACCEPT to leave the old generation
only when its exact owned copy is already forced in the active generation. The
root promise remains monotonic, and the retained immutable recovery basis remains
byte-identical. **This is stricter than merely copying a proven prefix, but it is
a proposed extension of current cleanup, which refuses above-floor ACCEPTs.** It
requires later Java storage integration and physical qualification before use.
The preserved basis here is one opaque prior frozen basis; this model does not
generate or select a new election quorum after checkpointing.

No copy from another owner can impersonate the local unresolved acceptance. No
checkpoint lowers the promise to its tail's ballot. No removed voter counts in a
new-stable floor. Removing a voter is not permission to erase its disk.

## Explicit retention limits, without a new trust anchor

| Research limit | Behavior |
| --- | --- |
| 16 certified entries per packet | Refuse an additional packet; never drop the oldest certificate |
| Four INTENT entries per chain | Refuse the fifth membership operation's retained history |
| 128 KiB encoded packet | Refuse before starting its generation |
| 2 MiB counted retained bytes | Refuse allocation/force that exceeds the bound |
| Two generation slots, six identities | A retirement record keeps its slot owned even after directory removal |

Counted bytes are generation files, copied floor source files, the retained basis
and the complete retirement packet. Small selector/floor descriptors, Python
objects, input histories and checker traces are not a production disk accounting
model. Tests exercise both actual entry/change ceilings and synthetic byte pressure.
These are finite research bounds, not frozen production resource limits.

This is journal compaction with retained authorization, **not authority-chain
elision**. In particular, 16 counts DATA entries too. It deliberately stops once
that bound is reached; it is not a usable unlimited-history storage design. D06
must still choose a separately verifiable bounded authority representation or an
explicit operational lifetime before production freeze. Replacing the chain with
an unauthenticated "latest configuration" is not an acceptable shortcut.

## Independent checks and declared scope

Implementation: [storage model](../../../scripts/v53/recovery_model.py),
[replay observer](../../../scripts/v53/recovery_oracle.py),
[matrix driver](../../../scripts/v53/recovery_research.py),
[regressions](../../../scripts/v53/test_recovery_model.py).

The observer first replays the original transition execution. It derives forced
prefixes, promises and acceptances from that journal, then reconstructs generation
files, durable selection, floor copies and retirement from recovery events. It
does not consult live `Store`/`World` state or call their validation/deletion
methods. Majority families are constructed separately. Encoding and immutable
record types are shared; this is not an independently implemented byte parser.

Five deliberately unsafe implementations must fail specific checks: dropping a
tail; switching before selector force; deleting without a floor; resetting the
root promise; reusing a slot still owned by retirement. Original histories pass
before missing-force evidence, a foreign root or a changed basis is rejected.
Replay binds claimed view/tail coverage to the observed certified prefix and tail;
relabelled duplicate histories cannot fill a missing case. A subprocess confirms
floor refusal still executes under Python `-O`.

The matrix uses seven add/remove/replace size profiles, three cuts (old, joint,
new) and tail absent/present: 42 input histories. In tail-present histories,
ACCEPT reaches all current voters but PROOF/publication has not happened. For
each history, use its first inclusion-minimal floor quorum and crash/reopen at
every named boundary in one checkpoint/retirement sequence. This does **not**
enumerate all quorum subsets or arbitrary asynchronous interleavings. Post-crash
continuation is separately tested for staged retirement and partial deletion;
the matrix itself observes each cut, rather than running every possible suffix.

All final histories are retained as compressed portable JSON, replayed after
serialization, with a digest over every observed cut. The source receipt binds the
parent HEAD and exact dirty source/test hashes. An interrupted traversal is
INCOMPLETE; an execution/check failure retains its trace. Output directories must
be new. See [development status](DEVELOPMENT_STATUS.md) and
[the receipt](recovery-research.json) for measured counts and local paths.

Assumptions: authentic source packets, trusted immutable genesis, atomic complete
file/selector force, frozen history during checkpoint, a separate monotonic root
promise, one unresolved slot, no malicious voter. Exclusions: application-state
integrity, torn writes/fsync behavior, new-learner transfer, concurrent campaigns,
root-promise allocation/activation integration, indefinite generation recycling,
endpoint/incarnation fencing, reads, operation APIs, liveness and performance.
One additional generation reservation checks slot reuse after retirement; it does
not qualify an unlimited sequence of checkpoints.

## Next decision batch

Map certified chains, retained bases and joint authority into the actual global
promise, recovery-source selection and activation protocol. Resolve unavailable
sources and the lifetime/representation of retained authority before declaring
D02/D03/D06 closed. Then specify learner fencing, operation IDs/query/cancel,
removed-node reads, and API/byte/resource contracts D04–D10. This local research
result cannot authorize a production runtime or cloud experiment.
