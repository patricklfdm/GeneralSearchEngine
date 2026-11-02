# Phase 3 — profile continuous peer ledgers

This follows [profile maintenance authority](PHASE_3_PROFILE_MAINTENANCE.md).
The new adapter binds the existing continuous peer-ledger derivation to every
declared ADD/REPLACE profile's actual old voters and joining identity. It still
requires the full original physical/network/export/control/maintenance chain.

All original voters, including those unused by later selections, have their own
bootstrap reseal. The actual joining node has five separately scoped opens:
initial, retaining, repeated-basis, continuation and stable-cold. Both peer-file
and parent forces must follow CURRENT/learner recovery and precede future recovery
in that owner. Missing, duplicate, reordered and unbound reseals fail. Opening a
file preserves its continuously derived bytes; it does not create a revision.

The shared reader no longer treats `node-4` as the universal joining node. In
larger profiles, an old `node-4` voter has an ordinary unscoped write, while the
actual `node-5`/`node-6` joiner requires its continuation-owner scope. Conditional
regressions reproduce the previous reader's rejection of both valid cases.
Initialization, original seed/source checks and cold-file selection use the
actual joining identity as well.

Each semantic change starts from the preceding derived ledger. Its revision
advances by exactly one, its previous hash names that complete predecessor, and
its root and permanent owner remain unchanged. Every change consumes exactly
one original write/force/rename/parent-force transaction within the corresponding
maintenance, selected-installation or publication interval. No-op derivations
cannot consume a write. All original writes and selected-completion callbacks
must be used exactly once.

Profile maintenance inputs are recorded once, preserving original acquisition
order and the actual direct-copy cohort. The shared covering-copy derivation
handles view reconciliation and retained identities. A future covering copy can
protect an older cut without becoming a same-cut peer observation; unresolved
renewal debt remains intact. Recorded fixture totals are not general limits.

Bootstrap, original grants, joining initialization, selected generations,
applied/published observations, all reseals and cold-close files must match the
continuous chain. Newer-authority adoption now also compares its original ledger
at the adoption return instead of waiting for a later capture or cold snapshot.
It never replaces the derived predecessor with the observed file.

```bash
python3 -B -m scripts.v53.joining_profile_peer_evidence /path/to/original \
  --profile 5-REPLACE --qualify
```

Twenty negatives mutate only disposable event traces. Physical files, wire bytes
and directories remain unchanged. Network/export/control/maintenance must pass
before each exact peer rejection counts. Missing targets, unrelated errors,
accepted mutations and invalid originals fail the qualification driver.

The [receipt](phase3-evidence/profile-peers.json) binds the frozen reader,
historical original provenance, conditional regressions, exact negative results
and independent extracted-archive replay. Larger-profile native results are not
inferred from conditional checks or from the retained three-node histories.

Measured validation: all 1,854 V5.3 Python tests pass, including sixteen new
conditional tests. The retained 3-REPLACE and historical 3-ADD each reject all
twenty exact peer mutations after their preceding gates pass. REPLACE derives
78 writes (46 maintenance, 10 selected, 22 publication), 90 ledger comparisons,
17 captured ledgers and eight reseals. ADD derives 90 writes (54 maintenance,
12 selected, 24 publication), 97 comparisons, 19 captured ledgers and eight
reseals. Both original chain hashes and final revisions remain unchanged.

The existing full same-view replay also passes. Relative to the preceding
receipt, its only changed result is the peer comparison count, from 93 to 94,
for the explicit original adoption comparison. Every other result is identical.
All three current results match after extraction and replay with Python assertions
disabled. The 40,432,914-byte archive retains 21,441
files, original producer metadata, frozen readers and development diagnostics.
Original and extracted inventories remain unchanged. No new larger-profile native
execution is implied by these retained histories or conditional checks.

## Remaining closure and rollback

Profile-wide continuous learner/future ledgers and ballot composition remain
OPEN, as do final-source seven-profile and process/fault cohorts, combined bounds
and the frozen S/N mapping. Phase 3 remains OPEN. This change does not modify Java,
POMs, workflows, frozen formats, workloads or timing/resource limits, and triggers
no native rerun or paid-cloud execution.

Rollback removes this adapter and restores the shared reader helpers while
preserving original evidence, regression logs and source manifests.
