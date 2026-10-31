# Native joining bootstrap-to-INTENT physical replay

`scripts.v53.joining_transition_evidence` composes the original public bootstrap,
four elections, maintenance, nonvoting learner obligations and the first nine
native slots into one independently derived old-voter history. It extends the
[publication transition reader](PHASE_3_JOINING_PUBLICATION_REPLAY.md), which
treated each applied snapshot as an original predecessor input. The new reader
reconstructs those predecessor files from the preceding derived state instead.

The [batch receipt](phase3-evidence/joining-transitions.json) binds source,
original producer, checks and retained replay inputs. The `df22c398` workload is
not rerun or combined with another attempt.

## Composed history

The reader compares 69 complete node inventories: the original three-node
bootstrap, four three-node installation snapshots and both applied/published
snapshots for nine slots. Node 3 remains offline and byte-identical throughout.

1. Construct bootstrap peer/learner/future ledgers from the original admitted
   identities and application image. No reported revision supplies the starting
   state.
2. Before a fresh campaign, derive maintenance observations from the preceding
   complete original generation copies. Retain the original confirmation bytes
   for equivalent cuts, preserve renewal debt and use the existing bounded
   deferral rule. Every retained peer and learner endpoint must remain covered.
3. Construct each new PROMISE, immutable frozen source and BASIS from that
   derived state. Only fresh source UUIDs are observations; ballot progression,
   wrapped ledger bytes, packet inventory and selected source set are derived.
   Construct the selector-coupled peer/learner intents and merged ledger bytes.
   Verify the complete installed generation while retaining the previous one.
4. Derive inactive-generation and superseded-source retirement from complete
   governing copies. Keep the current source and exact current grant suffix.
   Refuse maintenance with an unfinished vote/application, pending future
   obligation, or uncovered source cut. The offline owner is never rewritten.
5. Derive the learner's two nonvoting source offers at the original PREPARE and
   SEALED cuts. Their exact possible endpoints remain retained through INTENT;
   publication does not silently remove the earlier learner obligation.
6. Construct each actual pending vote, application image, catalog, checkpoint,
   ancestor statement, owned ACK and plan inventory from original commands and
   required endpoints. Compose the already qualified publication derivation and
   compare every resulting file, including unchanged sources and ledgers.

This covers BARRIER, RESERVE, BARRIER, PREPARE, BARRIER, READY, BARRIER, SEAL and
INTENT on the old owners. The joining node's observed pending INTENT ACK remains
required by the existing semantic majority check; this batch does not substitute
old 2/3 for new 3/4.

Seventeen original-first negatives pass the earlier publication gate and fail
the new history reader for their declared reasons. They include self-consistent
installed-generation changes, altered frozen sources, premature deletion,
wrong allocator/future/peer state, lost learner obligations and offline writes.
For the applied-state cases, the mutation also recomputes a matching published
successor. Thus a mutually consistent applied/published pair cannot conceal an
invented revision, erased renewal debt or skipped source/grant retirement.

```bash
python3 -B -m scripts.v53.joining_transition_evidence <original-raw-directory> --qualify
```

## Remaining whole-history boundary

This closes the predecessor-state gap through the old owners' INTENT publication
in this one original `3-ADD` history. It does not yet derive every joining
custody/placement/native-owner file, the subsequent joint source preparation and
recapture, or the two later installations through FINAL and the new-stable
BARRIER. Those physical transitions are the next integration work.

Physical state derivation also does not establish that every actual maintenance
copy, transfer, deletion and receipt occurred in the required causal order.
Complete force/network replay, the updated producer's missing send/arrival
observations, process cuts, all seven profiles and frozen requirement mappings
remain required. `throughIntentPhysicalQualified` is true only for this boundary;
all full-history/Phase 3 qualification flags remain false.

No runtime Java, POM, persisted format, frozen resource/timing bound or workflow
changes are made by this reader batch.
