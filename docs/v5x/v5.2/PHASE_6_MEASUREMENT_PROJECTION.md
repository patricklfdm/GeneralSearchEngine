# V5.2 Phase 6G chosen-update projection and streaming negatives

**Status:** compact projection, selected-update query replay and streaming negative
views are locally verified. Complete measured-history admission and M01–M04
execution remain pending; no formal or paid measurement ran in this stage.

## Attempts, chosen effects and visible application sequence

A concurrent workload can reject an update before submission and later submit a
different update. Application sequence therefore counts chosen updates that have
been published, not all attempted updates or the numeric offered ordinal. An
indeterminate response does not prove rollback: its chosen effect must remain in
the application replay if the physical quorum evidence contains it.

`measurement_projection.Projection` consumes the independently verified chosen
entries and original offered updates. It requires a contiguous unique chosen
prefix, only the declared updates and NO_OPs, unique offered identities, and the
original mutation order. Successful updates require a chosen entry; an update
reported NOT_SUBMITTED must not have a chosen effect. An INDETERMINATE or PENDING
operation may have an effect, but this projection helper does **not** make an
incomplete measurement pass. The outer history/measurement admission must still
require its declared completion and fault rules.

The projector retains at most 8,192 chosen entry identities and 181 application
states of the fixed 64-document corpus. It does not retain every publication's
snapshot/ancestry. Every publication is independently checked against the whole
chosen ancestry, actual application bytes, application sequence and terminal proof.
A successful update response must follow a publication containing its own chosen
entry. Existing force/quorum/basis/proof/storage checks still execute first.

## Explicit selected-update query format

The original `gse-v52-measurement-query-input-v1` remains strict: its update list
must be the original complete prefix. The new v2 schema adds `offeredOrdinals`, a
strictly increasing subset of the declared 180 update ordinals. Both the Python
admission and Java query consumer check that each supplied document exactly
matches that ordinal. Duplicate, reversed, foreign or silently relabelled updates
reject. Query keys still distinguish exact application sequence and descriptor.

V2 is a query-replay format, not proof that an update was chosen. Its caller must
supply actual quorum-selected entries and original invocation identities through
the physical projector. A selected but unpublished tail cannot supply a readable
cut; the actual core advances only through the highest requested application cut.

The foundation executes all 138 descriptors at six application states for offered
ordinals `[0, 2, 65, 130, 179]`: 828 actual queries in each of published V4.4 and
candidate core, with independently reconstructed state hashes and identical query
results. Existing full-prefix/direct and advancing 690-query checks remain intact.
This is untimed query qualification and says nothing about replication throughput.

## Streaming negative replay

Negatives now wrap a repeatable decoded trace and copy only the one targeted row.
The identity includes node, PID, process generation and local order, so a repeated
order after restart cannot mutate another process. Every pass reopens the original
bounded trace and applies the same change. Missing or duplicate targets reject;
no original bytes are rewritten. The bounded controller history can still be
copied separately. The original must pass before a negative result counts.

The existing short gate preserves every negative name, expected reason and result.
Its separate 64 MiB decoded smoke limit remains; this refactor is not permission
to call the short validator a full M01 verifier. The future measured admission must
bind the full trace/package/runtime limits and complete offered window.

## Local evidence

- `target/v52-measurement-projection/core-1`: published and candidate direct/full
  prefix query checks plus 828 selected-update queries per core pass.
- `target/v52-measurement-projection/replay-1`: all ten unchanged original/relocated
  inputs from `run.oupfL5` pass. Complete results, including 124 exact negative
  rejections, equal the previously retained results. Replay took 79.603 seconds;
  no workload was rerun and original source bindings remain unchanged.
- All 103 V5.2 Python tests pass, including selected/rejected/uncertain effects,
  missing/reordered entries, wrong publication bytes, premature responses and
  lazy/repeatable generation-specific negative views.
- Existing CI inventory, documentation contract, changed links, shell syntax and
  whitespace checks pass. No new Maven reactor or protected hosted result is claimed.

Continue with complete measured-history outcome/ownership validation and the
fault schedules, then commit the complete execution freeze before any measured
window under the [local sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
