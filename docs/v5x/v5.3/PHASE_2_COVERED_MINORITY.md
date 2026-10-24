# Settling a bare pending vote behind a proven selected prefix

Phase 2 remains **OPEN**. The earlier
[distinct minority qualification](PHASE_2_DISTINCT_MINORITY.md) kept all voters
at one published parent. A separate real three-voter reproducer established that
a minority owner with a bare ACCEPT could not install a later proven prefix:
the implementation rejected `pending ACCEPT requires covered-prefix publication
before advancing generation`. A disjoint majority had already actually published
the different ENTRY, so retrying the same storage operation could not help.

The new path is deliberately bounded to a bare ACCEPT in a stable view. An
original PROOF/certificate, protected context, replay scratch or applied end is
not discarded by this rule. Configuration-changing adoption keeps its separate
guards. No public runtime or transport behavior is enabled.

Before installation, the owner checks the original vote against its exact
selector, generation, original PROMISE/SELECTED and retained journal. The verified
incoming capsule must authenticate that original parent and cover the vote's slot
within the same stable authority. The new installed decision is strictly newer,
and includes the exact local BASIS whose immutable source still contains the
original ENTRY, ACCEPT and payload. That source must equal the original generation
packet composed with the original vote, including its complete inventory.

The existing generation installation forces the entire candidate and selector
before any vote clearing. Under that forced selector, the owner repeats the
complete original/incoming/source checks at every empty-container replacement
boundary. It writes and forces the bounded candidate, forces its parent, atomically
renames it and forces the parent again. Internal `SETTLED_VOTE_*` callbacks identify
these boundaries; they add no frozen wire or record kind. The existing 12-byte
empty-container allowance remains part of the shared JOURNAL completion budget.

Opening an owner defers only this advanced-vote classification until the retained
sources and application authority are available. It then validates and finishes
the same transaction before returning. A partial empty candidate must match the
exact expected prefix; an unrelated replacement cannot authorize clearing. The
original inactive generation and frozen local source remain present. Their later
deletion still requires the ordinary governing-floor and retirement transactions.

A later volatile observation does not revoke permission to complete this exact
cleanup, but it prevents an old installation response from succeeding. It neither
creates an old vote ACK nor lowers a durable promise. Corruption of originals
must fail without deleting or repairing the inconsistent authority.

Local qualification and its exact source/build inventory are recorded in the
[evidence index](phase2-evidence/covered-minority.json). The continuous case uses
real public EMPTY bootstrap, minority ACCEPT2, majority selection/voting/publication
at ballot 3, all-voter installation at ballot 4, later source reclamation and a
ballot-5 BARRIER. Typed inspection requires the chosen document exactly once and
the losing document absent. Additional cases interrupt installation/clearing
twice, reject damaged authority and verify observation fencing.

These are local owner calls and injected IOException boundaries, not fresh-process
halt/SIGKILL or power-loss qualification. Independent complete physical replay,
all size/source profiles, proof-bearing/context-bearing recovery, cross-view
adoption, maximal bytes/headroom and protected acceptance remain separate pending
obligations. Raw snapshots and callback traces are retained for that next audit;
a green Java test alone does not close those obligations.
