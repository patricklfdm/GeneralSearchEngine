# V5.3 predecessor-certified transition research

**Status:** executable protocol candidate, not a frozen production contract.
The model builds on [durable ballots](BALLOT_AND_HANDOFF_RESEARCH.md), but now
replicas can hold different local configuration views and recover multiple slots.
Phase 0 and the production integration obligations remain open.

## The proposed chain

Every new slot requires a complete, certified predecessor. A candidate derives the
slot's authority from its own **forced local prefix**. Each receiving voter does
the same independently before staging a request. No global "current membership"
variable grants votes, and seeing a larger generation number is insufficient.

| Entry being decided | PREPARE / ACCEPT / PROOF authority | Authority for the next slot |
| --- | --- | --- |
| Stable DATA or research BARRIER | Stable majority | Same stable configuration |
| INTENT(operation, target) | Old stable majority | Joint old/target configuration |
| FINAL(same operation, same target) | Majority of old **and** target | New stable majority |

A certificate includes both durable ACCEPT and PROOF acknowledgement quorums.
A voter installs the certificate chain with a separate stage/force boundary before
using it for the next slot. A forced promise or ACCEPT by itself cannot admit a
learner or activate a new view. During the joint interval, only its matching FINAL
is admissible; another INTENT, ordinary DATA and a new BARRIER reject.

The model deliberately permits only one unresolved slot beyond a certified prefix.
It does not pipeline future slots, infer a missing parent, roll back a promise on
installation, or clear durable voting history after membership removal. Joining
identities can vote in joint consensus only after installing that prefix.

This is a conservative hypothesis. The final entry still uses both majorities.
That is a design choice being evaluated here, not a transcription of Raft's
configuration activation/finalization algorithm. A research BARRIER represents a
new quorum-backed operation; it does not implement V5.2's read capture, tokens,
minimum/stale policies, leases or existing client response semantics.

## Competing operations and recovery

Competing INTENT payloads share the **same old-authority slot**. The proposed target
is part of the value, not a parameter that creates a separate ballot store. A
higher candidate proposing target B must carry target A when its frozen recovery
quorum requires the already accepted A. A lost operation response does not undo A.

The reused ballot model selects the highest accepted value from immutable bases.
Both stages of reconfiguration are exercised with restart before/after PREPARE,
ACCEPT and PROOF force, plus partial PROOF force and lost replies. Recovery then
certifies the selected entry, installs it and resumes the chain. Duplicate old
requests are delivered after adoption to check that they cannot reopen an earlier
slot or apply old authority to a later one.

Candidate ballot allocation remains a unique, monotonically increasing research
primitive. The underlying model stores promises per logical slot. Mapping this to
GSE's global promise, activation and selected-prefix storage is still D03 work;
this batch does not claim that the current Java algorithm can adopt that layout
without a reviewed storage/wire change.

## Logical identity is independent of proof representation

The model's entry identity hashes its authority, predecessor and canonical value.
It excludes the ballot and the specific receipt sets. The following must give the
same logical entry ID:

- The same entry proven by different sufficient subsets of receipts.
- The same chosen entry re-proven after a higher-ballot recovery.

Otherwise two valid proofs of one entry could create different next-slot contexts
and fragment recovery. Both cases have executable tests. Root, logical index,
configuration/operation context and entry contents remain bound; excluding the
proof representation does not allow a different history or target to pass.

The cross-slot checker compares choices by immutable root and logical index.
Changing a predecessor/configuration field cannot partition away a fork.

## Old configuration and removed nodes

A voter that has forced a newer prefix rejects an earlier-slot request locally.
A lagging old voter may still participate in recovering that old slot, but its
isolated responses cannot manufacture a sufficient old quorum for a different
value. Once it learns the final chain, a removed voter cannot start a new campaign.

The retained tests include an old leader left at genesis while a majority and the
joining node adopt the transition. Its attempted old DATA cannot obtain a prepare
quorum. This checks new model operations, not termination of an already captured
public read or permission to delete a removed node's data directory.

## Independent observations and assumptions

Implementation: [transition model](../../../scripts/v53/transition_model.py),
[finite schedule driver](../../../scripts/v53/transition_research.py),
[regressions](../../../scripts/v53/test_transition_model.py).

The observer replays a chronological journal of local admission, staged writes,
force, crashes, prefix installs and certificates. It reconstructs each replica's
forced prefix and verifies each certificate against previously observed ACKs.
It does not use the live World's prefix/configuration tables and does not call its
chain fold, successor function or quorum predicate. The earlier ballot/history
oracle additionally checks votes, proofs and conflicting choices across views.

Three deliberate implementation faults must produce specific safety failures:
installing a prefix before force, bypassing a receiver's local predecessor, and
counting an old-only majority as a joint quorum. Original histories pass before
corrupted serialized evidence is tested. Missing prefix-force evidence, wrong
roots and incomplete inventories reject; Python `-O` retains explicit checks.

Authentic, non-Byzantine ACKs, atomic force and a trusted immutable genesis are
assumptions. Prefix transfer retains the **complete authority chain** and preserves
local promises/acceptances. It is not an application snapshot, checkpoint
compaction, endpoint authentication, same-identity disk replacement or byte-level
crash model. No fake storage fixture is claimed to be a real disk force.

## Declared matrix

- Seven change profiles: 3→3 replacement, 3→4, 4→3, 4→4 replacement, 4→5,
  5→4 and 5→5 replacement. The last reaches six physical identities.
- Intent and final boundaries, seven crash/force cuts, and forward/reverse ordering
  of the first/last inclusion-minimal quorum pair: **196 cases**.
- Each case has four certified slots: DATA, INTENT, FINAL, DATA. The matrix records
  **73,835 events and 784 publications**. It is not an all-interleavings search;
  it does not enumerate every quorum pair here. The preceding single-slot matrix
  separately enumerated all minimal-quorum pairs for its own declared profiles.
- A separate 3→4→5→4→3 walk completes **13 slots and four operations**, preserving
  the full chain across every membership change.
- Fifteen representative histories (14 boundary/cut combinations plus the walk)
  are retained as deterministic gzip-compressed JSON and independently replayed.
  Every matrix case contributes to a deterministic trace digest.
- The research bound is 32 slots and six named identities, with 3–5 stable voters.
  These are finite exploration limits, not production disk/resource budgets.

Receipt: [transition-research.json](transition-research.json). Actual logs and
compressed examples are listed in [development status](DEVELOPMENT_STATUS.md).
A limited run exits INCOMPLETE, never PASS. Existing output directories are refused;
failed cases retain their original event trace. Receipt source fields distinguish
the parent commit from the exact uncommitted model/test bytes.

## D02/D06 progress and next obligations

D02 now has an executable candidate for slot authority, local adoption and final
quorum, with explicit restrictions and directed counterexamples. D06 has full-chain
transfer/restart and preservation of durable voting state. Neither is closed for
production. Before freezing Phase 0:

1. Specify snapshot/floor authority and bounded retention without losing the
   configuration chain or an unresolved acceptance. Model interruption and rollback
   at those boundaries; full-chain retention here is not a compaction solution.
2. Map the protocol to GSE's selected bases, activation and global promise storage,
   including unavailable recovery sources. Decide whether the conservative pause
   and no-pipelining policy is acceptable under the intended workload.
3. Complete learner data installation, removed-node read policy, operation ID/query
   semantics, endpoint/incarnation fencing and exact API/byte/resource contracts.
4. Freeze deterministic physical/public validation and performance workloads only
   after those decisions. V5.2 fixtures and cloud results remain predecessor evidence.

The consensus background remains [Paxos Made Simple](https://lamport.azurewebsites.net/pubs/paxos-simple.pdf)
and [Raft's membership discussion](https://raft.github.io/raft.pdf). Those sources
motivate preserving accepted values and separating old/new authority; they do not
certify this GSE-specific chain protocol or its future implementation.
