# Carried INTENT / FINAL original-byte replay

Phase 3 remains **OPEN**. This component extends the existing native
[transition round](PHASE_3_TRANSITION_ROUND.md) with retained, independently
replayed carried INTENT and FINAL histories. It complements the
[carried DATA cohort](PHASE_3_CARRIED_DATA_COHORT.md); it is not yet a new
hosted subset or final-source admission gate.

## Complete original histories

`V53CarriedTransitionDriverTest` reuses the existing four-voter REMOVE producer,
native owners and TCP transport. Each of its two methods executes once. The
public bootstrap plan, RESERVE/PREPARE/READY/SEAL prefix, old accepted entry,
higher-ballot selections and subsequent publications remain in one original.

| Old accepted command | Original index | Higher-ballot rounds | Published indices |
| --- | ---: | --- | --- |
| INTENT | 5 | INTENT, FINAL, fresh BARRIER | 5, 6, 7 |
| FINAL | 6 | FINAL, fresh BARRIER | 6, 7 |

The FINAL case also retains the original joint campaign between INTENT and the
old FINAL vote. Completion must preserve the old ENTRY, origin ballot and
payload bytes. New votes use the active selection; the original command is not
rewritten with a new origin. Later selections carry no entry, and readiness
must bind the fresh stable BARRIER's actual publication acknowledgement.
The new stable membership is nodes 1–3. The typed application image and sequence
remain unchanged at sequence 0 throughout these control-only histories.

The existing 30-second request and 600-second round bounds remain unchanged.
There is no native retry, replacement history, budget extension or Phase 2
authority substitution. These native runs do not inject process death.

## Independent physical and lifecycle checks

[The reader](../../../scripts/v53/carried_transition_evidence.py) derives the
admitted preparation prefix, old ACCEPT bytes and exact stopped-PROOF observation.
The complete `before-network` snapshot is compared after applying that old vote.
It then derives fresh grants, selected authority, installation, certified slots,
typed images and retention ledgers. All four original owners, including the
removed voter's final state, are compared through `after-close`.

For the carried slot, new ACCEPT precedes durable floor maintenance; pending
authority cannot retire its source. Once publication completes, the next
campaign may retire that source before issuing its new grant. The expected
retirement file count comes from independently derived physical before/after
states. Missing, duplicate, uncovered or late retirement events fail. Existing
noncarried readers retain their default slot numbering and retirement rules.

Each complete original must pass before any mutation runs. **30 exact negative
checks per kind** cover original command/vote changes, selected tail and new
ballot votes, certificates, control images, final peer state, missing activation,
early readiness, wrong completion, force ordering, publication acknowledgements,
source retirement and scope/budget claims. A different error does not count as
the expected rejection. Original evidence is never edited.

## Retained development evidence

The [receipt](phase3-evidence/carried-transitions.json) binds the two native
captures, source/build/toolchain identities, reader, raw inventories, replay
results and portable archives. The first native executions passed in 313.396
and 291.336 seconds, including fixture preparation. Reader development failures
remain recorded separately; those originals were replayed without rerunning
the native producers.

Both originals pass physical/lifecycle replay and all 60 negative checks.
Packing, relocating and replaying with Python assertions disabled gives exactly
the same results and leaves the original inventories unchanged. Focused tests
cover the shared default-reader behavior and explicit carried differences.

The producer source was frozen before this reader and its documentation were
finished. These results therefore qualify a development reader against recorded
native originals, not a newly frozen final-source cohort. The original producer
receipts remain `PARTIAL`; no historical source identity is relabeled.

## Remaining boundary

The result explicitly reports `fullNetworkQualified=false`,
`publicReady=false`, `processDeathQualified=false` and `phase3Complete=false`.
Publication boundaries and acknowledgements are checked, but the complete
activation/transfer network and failure classification are still separate work.
Other profiles, process faults and exact-source capture/admission must be added
before this component can contribute to phase-wide acceptance. The existing
nine hosted subsets / 460 planned whole histories are unchanged by this batch.
