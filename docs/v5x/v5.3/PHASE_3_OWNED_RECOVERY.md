# Phase 3B — owner-bound storage recovery and continuation

Status: component locally qualified. This batch connects the internal bootstrap-admitted
storage entry to actual original history. It does not enable the public membership
runtime or close autonomous recovery, adoption/elections, learners or Phase 3.

## Original ownership

The internal `MembershipGrantJournal.openBootstrapped` overload requires no
caller-held historical observation set. It acquires the actual exclusive owner,
replays the original journal and opens the selected generation under that owner.
Original BASIS sources, complete governing-floor copies, the inactive generation
and a complete retained retirement original each have separately minted private
copy capabilities. Their original path, file identities, inventories, root,
journal references and exact bytes remain checked. Partial copies cannot provide
historical proof. Capability expiry prevents reuse outside its validating read.

This retains the existing authentic-storage/crash-fault assumption, not Byzantine
or signature protection. Complete historical statements do not become new remote
ACCEPT/PROOF observations. New grants, source receipts, votes, application ACKs and
floor decisions continue through their existing owning/forcing APIs.

Two generations can have the same proven cut while retaining different original
selection coverage or supplemental ancestry. Original-generation validation must
therefore resolve the exact stored generation before attempting prefix reuse.
After inactive deletion starts, recovery uses only the complete original bound to
the retained deletion authority, with exact borrowed-image resolution where needed.
No timeout authorizes deletion and no missing proof is replaced by a hash claim.

Plans for a new materialization preserve the typed verified capsule which created
them. Rechecking permits only the same proven prefix and exact image inventory,
plus separately verified bounded installation ancestry. Full original selection,
first/latest certificate coverage and local identity checks still apply.

## Qualification boundary

The normal gate uses actual public offline bootstrap at all six size/source
profiles, real phased BARRIER/DATA publication, a second campaign in fresh JVMs,
selected installation, floor/source retirement and another publication. Each fresh
worker receives local paths and, for PREPARE, the requested fresh ballot; it receives
no fixture observations or serialized historical grant lists. Every tested owner
uses the new internal entry, including intermediate pending-vote/application opens.

Independent replay reconstructs the original admitted histories, vote phases,
application images and exact storage before validating worker responses. Different
current/source cuts remain distinct after continuation. Corrupt original sources,
inactive files and floor copies must refuse before deleting anything. A separate
process history repeatedly interrupts original retirement with halt/SIGKILL,
including after inactive file deletion, then completes under fresh owners.

The final Java build passes **69 tests across nine suites**. Its new recovery gate
covers six size/source profiles, 72 node publications and 54 fresh JVMs. Four
successive retirement deaths plus completion use five additional JVMs. Independent
original-first replay rejects 12 normal-history and six crash-history mutations.
The Python suite passes 590 tests in normal and optimized modes; the final
negative-fixture-only adjustment additionally passes all five focused reader tests
in both modes and the complete original-evidence qualification. Final-source
inputs, artifacts, original failed attempts and replay results are indexed in the
[qualification receipt](phase3-evidence/owned-recovery.json).

An intermediate actual lifecycle test exposed missing supplemental ancestry when
two original generations shared a proven cut. It remains retained separately from
the corrected qualification. Two subsequent negative-driver attempts failed for
unrelated malformed fixture bytes; they were corrected, not counted as successful
semantic rejections. No workload or production acceptance rule was weakened.

These finite tests do not establish power-loss durability or full distributed
availability. Pending-context turnover across configurations, automatic incoming
adoption, autonomous election ownership, learner/joint transitions and complete
Phase 3 fault/evidence coverage remain separate required work. The frozen formats,
resource ceilings, network deadlines, public factories and V5.2 runtime/workflows
are unchanged.
