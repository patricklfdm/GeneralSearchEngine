# Immutable selection with retained original context

Phase 2 remains **OPEN**. This extends [protected capture](PHASE_2_CONTEXT_CAPTURE.md)
with local persistence of one actual selected quorum per ballot. It does not yet
enable installation into a reused generation slot.

## Admission and persistence

The owner must retain a complete original context, its exact source and vote,
and the governing floor. The old generation must already be retired. The latest
forced local BASIS must equal the context backing and differ from the installed
generation's BASIS. A higher PROMISE without a completed protected capture cannot
reuse the previous quorum, and an already installed backing gives no permission
to select again.

The existing selection verifier consumes actual original sources from the three
local owners. The new decision must preserve the original parent and carried
ENTRY. The owner checks journal capacity before writing; this path does not
implicitly rotate a journal or reclaim a source. An identical explicit request
returns the original SELECTED; changing the chosen set requires a fresh ballot.
Higher observations still fence every persistence/return boundary.

## Local evidence

The [source/build-bound index](phase2-evidence/context-selection.json) retains:

- Three actual owners selecting 22 and then 23, with installed selection 21 and
  original certificate 20 unchanged. Exact intermediate-source retirement removes
  the whole obsolete grant group, including its SELECTED frame.
- Four selection cuts, each followed by another interruption during context-source
  re-sealing and then an explicit original request. Reopen produces no selection
  response. Identical retries add no second SELECTED record.
- Higher-observation fencing, rejection of changed selected sets, an unmarked
  higher PROMISE and an already installed backing, with unchanged refused state.
- Eighteen Java methods across selection, capture and backing retirement; independent
  original-first byte replay, exact force/return traces, negative mutations and
  relocated replay in normal and optimized Python modes.

The retirement oracle previously had no selected intermediate grant in its input.
This gate adds that case: compaction removes all frames for the retired ballot,
rather than filtering only top-level `basisId` fields. Production compaction
already removes the complete group; the correction is in the independent oracle.
The initial oracle failure remains retained alongside the unchanged raw workload.

These are local exception interruptions with small actual payloads and conditional
historical bootstrap fixtures. Seven peak/six steady image reservations remain
unchanged. Fresh-process selection recovery, later installation and slot reuse,
complete old/joint/new lifetime, maximal storage qualification and public runtime
remain separate obligations.
