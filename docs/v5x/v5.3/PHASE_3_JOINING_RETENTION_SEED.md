# Original inputs for joining-owner retention initialization

This note records the earlier read-only component. Its downstream transaction is
now implemented in [durable joining initialization](PHASE_3_JOINING_RETENTION_INIT.md);
the seed itself still grants no mutation authority. Phase 3 remains **OPEN**.

Phase 3 remains **OPEN**. A newly joined native owner must acquire the existing
retention obligations before it can participate in automatic joint selection.
Ordinary ledger initialization still requires unused genesis. This component
prepares and independently replays the initial inputs; it does not yet install
the three ledgers, issue a vote or complete FINAL.

`MembershipJoiningRetentionSeed` retains the exact BASIS, inventory envelope,
peer-retention wrapper and learner-retention wrapper from an ordered, distinct
old majority. Every source must have the same ballot and the exact joining
JOINT cut, root, catalog and application. The joining identity must be the
permanent new member outside the old side. A future reference or accepted tail
is refused: callers must obtain settled sources instead of silently converting
an outstanding publication to an empty future ledger. Supporting an unsettled
carried vote would require its own complete transaction.

Each original ledger must be included in its original BASIS inventory, belong
to its permanent source identity, and preserve ancestry authenticated by the
joining installation. Peer possibilities are conservatively unioned. Learner
possibilities and renewal debt are also unioned; a decoded higher confirmation
cannot discard another source's lower obligation. A union exceeding the existing
two-endpoint bound refuses. No current-cut guess, old selected-generation
snapshot or configured identity substitutes for an original source ledger.

The replay descriptor uses the existing eight-MiB control-frame ceiling, bounded
members and canonical Base64/JSON. It is private calculation/evidence metadata;
no public format, wire message, resource allowance, timing limit or production
workflow changes. Reading the descriptor is not authentication of a remote
process or permission to mutate native state.

`MembershipGrantJournal.joiningRetentionSeed` adds the native preparation guard.
It requires the actual joined owner, absent peer/future/learner active and
candidate ledgers, and the original installed files and inode identities both
before and after calculation. An ordinary bootstrap owner cannot use it. The
joining owner cannot use it after allocating its first counter or changing its
journal/generation. In particular, this is not a recovery route for a used
owner whose ledgers have disappeared. Preparation writes no owner files.

Validation and its exact limits are retained in the
[component receipt](phase3-evidence/joining-retention-seed.json). Conditional
checks cover all five ADD/REPLACE profiles and malformed/incomplete inputs.
The native case retains its whole old-two-of-three, typed learner and original
joining installation, with the third old transport unavailable. It supplies
actual floor copies explicitly and captures the two old journals directly;
automatic remote acquisition of those frozen sources is not claimed. Separate
JVM probes check physical lock exclusion; same-JVM reopen is distinct from
process-death recovery. The Python check compares the descriptor with actual
retained source packets, BASIS bytes and original ledgers, then independently
computes the conservative unions. It does not replace full physical/history
qualification.

The next transaction must force the exact seed and all three new-owner ledgers,
recover interrupted initialization under the same original ownership, and
refuse missing ledgers after completion. Only that transaction may feed the
required automatic joint campaign. FINAL, the fresh stable barrier, alternate
coordinator continuation and whole-history/process/all-profile qualification
remain in the [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Full long-running
acceptance can run as whole-history hosted shards after implementation.

Rollback removes this read-only preparation entry. There are no live owner
files, initialized ledgers or public formats from this component to migrate.
