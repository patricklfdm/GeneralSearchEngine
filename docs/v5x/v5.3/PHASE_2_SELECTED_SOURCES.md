# Original selected sources and bounded ancestry pruning

Status: local private Phase 2 integration; Phase 2 remains **OPEN**.

## Preserve the whole selected set

`SELECTED` retains only each voter's identity, BASIS identity and BASIS digest.
Those references alone do not reveal all original cut indices. Pruning using only
the local BASIS can therefore leave different voters renewing different endpoint
sets, preventing a real quorum from endorsing a required bridge.

A newly installed selected generation now retains `selected-sources.gsr`: the
ordered concatenation of the exact original BASIS frames in the selected set.
It is private generation metadata, bounded to six frames / 96 KiB and included in
the existing generation manifest, force order and shared metadata accounting.
No new wire/record kind or replacement vote is introduced. Installation, reopen,
publication and governing-floor copy validation bind every frame to the unchanged
SELECTED references, root, view, ballot, quorum and longest original cut. Each
original endpoint must remain directly represented or authenticated by retained
ancestry. These bytes are not new force/ownership receipts.

## Prune only the next materialization

Admission and certified application compute their required endpoint set from:

- Every original selected BASIS, including remote voters' cuts.
- All locally retained original BASIS/source endpoints.
- The governing floor and the actual current parent.

The next capsule retains exactly the bridges needed for endpoints absent from its
direct anchors. Older endpoints hidden by an enlarged RANGE receive new exact
endorsements at the actually forced end. Unneeded groups are omitted from the next
generation; the old generation, old source packets, original decision and existing
proofs remain byte-for-byte intact. Old generation/source deletion still requires
its separate floor and retirement authority. Publication rejects missing or
extraneous groups rather than silently substituting or filtering submitted proof.

During retained replay or an applied-end transaction, source retirement and floor
establishment/release are refused before mutation. The exact transaction can still
resume and publish; observing a higher ballot and read-only inspection remain
available. This prevents maintenance from changing the endpoint set between an
interrupted application and its recovery. Inactive-generation retirement keeps
its existing independent authority checks.

Legacy private generations without this original-frame member continue to retain
all existing groups conservatively. A missing manifest-listed member is corruption,
not permission to downgrade to that legacy behavior. The existing six-group,
five-additional-endpoint, 4 KiB coverage, seven-image and 32 MiB metadata bounds
remain unchanged. Pre-ACCEPT capacity rejection still occurs before a new vote.

## Reserve publication completion before new votes

Application completion now reserves the eventual candidate image as well as the
applied end and the two replay images. If the inactive slot already owns an image,
its existing reservation is enlarged to the 64 MiB image ceiling in place; it is
not counted as a second physical image. An empty slot uses a dedicated future
reservation. Installation transfers that reservation to the exact candidate.
Reopen counts the physically present candidate image, or reserves the missing
future image when interruption occurred before its write. Authorized inactive
retirement restores a future reservation when a pending vote still needs it.

This prevents a new ACCEPT from consuming all seven image slots while leaving
no room to publish its certified result. Staging bytes are also reserved, not
just the image count; failed growth leaves accounting unchanged. A pre-ACCEPT
capacity refusal preserves the original bytes. Safe maintenance before an
application transaction may free space and permit a new explicit admission.
The seven-image and shared staging limits are unchanged. This is local completion
headroom, not permission to delete an existing generation or discard a vote.

## Qualification and limits

See the [source/build/evidence index](phase2-evidence/selected-sources.json).
The focused tests exercise all seven membership profiles at stable/joint/new cuts,
exact source-set binding, three actual voters with distinct original cuts 1/2/4,
and a six-old-group fixture that publishes only the required 8→9 bridge. They
also test exact member write/force interruption, changed/missing/linked members,
floor validation even with a matching manifest hash, conservative legacy capacity
rejection, pre-vote image headroom and atomic reservation growth. Historical bootstrap and earlier bridge authority are explicit
conditional fixtures; new votes, application, force and publication use local owners.

Independent replay derives installation members from the original source frames,
not the candidate output. Publication replay uses the original selector-bound
manifest, then compares the whole projected output. Historical receipts retain
legacy handling; new installation/vote/retirement drivers explicitly record the
original-frame profile. Missing or altered original evidence fails before mutation
qualification. Fresh-process publication and ancestor-renewal evidence exercises
halt/SIGKILL, interruption during recovery and covered cleanup; the current
image-headroom revision reruns actual journal publication and its image-write
recovery boundary; portable replay
and original-first negatives remain required.

This does not establish long-lived bounded progress, same-round continuation,
public runtime or network behavior, power-loss durability, or the full frozen
storage/fault inventory. The [dedicated six-to-one pruning process qualification](PHASE_2_ANCESTRY_PRUNING.md)
now passes separately. Coordinated source/floor retirement remains follow-up work under the
[Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).

## Focused local commands

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53SelectedSourcesTest,V53ResourceTransferTest,V53JournalApplicationTest#completionSpaceIsReservedBeforeNewAcceptAndIncludedInJournalCeiling,V53JournalPublicationTest#actualJournalProcessCrashesAndRepeatedRecoveryRetainExactPublicationAuthority+actualDataJointAndFinalPublishThenRetireOnlyCoveredStateAndAllowFreshCapture' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_selected_sources_evidence
```

Use the exact newly printed evidence directory for independent replay, never the
lexicographically last old run. The retained local sample collector and raw index
are referenced by the evidence index; its 30 driver samples are a scoped change
check, not reruns of all historical full qualification matrices.
