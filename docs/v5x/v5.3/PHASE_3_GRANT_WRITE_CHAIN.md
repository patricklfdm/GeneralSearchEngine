# Phase 3 — complete original grant capture writes

The callback audit found another concrete gap after the
[proposer installation correction](PHASE_3_PROPOSER_INSTALLATION.md). Deleting
node 1's first `BASIS_PREFIX_WRITTEN` from the retained `3-REPLACE` original still
passed the complete prior ballot/learner/future/authority/network/physical chain.
The audit retained the mutated copy and result. Original storage, wire and other
observations were unchanged; no native history was rerun. This is an evidence
reader defect, not evidence that the original runtime omitted its actual write.

## Source-derived transaction

`joining_network_evidence.grants` now checks the complete ordinary capture
transaction against the actual `MembershipGrantJournal`, `MembershipCaptureFiles`
and `MembershipBasisSources` writer order:

1. PROMISE before-write, written and forced.
2. Capture-intent creation, prefix, complete write, file force and parent force.
3. Source directory before-create and creation.
4. Original packet creation, prefix, complete write and force; then the same four
   observations for each original image.
5. Source and source-parent directory forces.
6. BASIS before-write, prefix, complete write and force.
7. Capture-intent deletion and durable clear before grant return.

The original packet/image count comes from the independently checked captured
source bytes. It is not supplied by a receipt or assumed to be one image. All
callbacks must occur between this original owner's capture and return, in its
exact scope with no unrelated fields. The collector already binds that return to
its original writer-held source copy. The network check still requires the
original peer grant to precede its actual PROMISE response.

Every capture-specific callback in the complete event stream must belong to
exactly one such transaction. Unknown capture callbacks, another owner's events,
and writes outside any capture cannot be silently ignored or borrowed. PROMISE
observations within the transaction are checked here; the existing continuous
ballot reader still owns other promises, including the newer-authority adoption
fence. Other event families retain their existing readers.

This order describes complete ordinary captures. It does not pretend that an
interrupted capture should have the same complete sequence: process recovery
requires its own prefix/state derivation and remains part of the separate process
qualification obligations. Duplicate transport replies do not invent a second
capture or authorize rewriting the original source.

## Original-first qualification

Nine focused regressions include absent write boundaries, wrong scope/shape,
duplicate/reordered writes, late/early writes, unbound/unknown callbacks, and
zero/one/multiple image inventories. The fixture lists the native sequence
explicitly rather than building its expected observations from the reader helper.
Before the correction, 26 negative subcases were incorrectly accepted.

The network qualification adds 23 exact negatives: seventeen missing boundaries,
duplicate/reordered prefixes, foreign scope, pre-capture prefix and two unbound
callbacks. The existing transport, installation, slot and terminal-attempt
negatives remain enabled. The full untouched original passes before mutations;
only event/wire metadata is mutable, physical members/directories must stay exact,
and an unrelated error cannot satisfy a negative's expected rejection.

The [batch receipt](phase3-evidence/grant-write-chain.json) records the original
composed replay, current complete network negative matrix, historical ADD check,
Python tests and archive portability. Qualification uses the frozen reader and
preserves original files. Historical evidence remains bound to its old producer;
it is not a new current-source profile/cohort execution.

The complete original chain passed in 52.765 seconds;
all 100 current network negatives passed in 490.591 seconds. All 1,745 V5.3
Python tests pass. The historical ADD physical/network replay also passes.
The 16,909,470-byte archive retains 8,791 files and
1,208 directories. Optimized-Python replay after extraction
matches the full original result exactly, with every source/input inventory
unchanged. These are historical original/replay results, not a new native matrix.

## Remaining Phase 3 scope

The retained REPLACE history has nineteen original captures and 437
capture-specific callbacks; their 57 PROMISE write callbacks are also checked
inside those transactions. This closes the reproduced grant-write omission and
its listed variants. It does not establish exhaustive coverage of every callback
family or close all seven profiles, fault/process matrices, combined resource
limits or the frozen S/N acceptance mapping. Full physical/network/process and
Phase 3 completion flags remain false.

No runtime Java, POM, frozen format/bound, workflow trigger, Required or cloud
behavior changes. Rollback reverts the shared reader correction and its tests;
keep original/audit evidence so the known gap is not erased.
