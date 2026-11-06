# Required-four export bindings in the complete resource entry

Status: **implementation ready; complete corrected-source execution pending**.
This strengthens the existing [required-four resource entry](PHASE_3_REQUIRED_FOUR_ENTRY.md).
It collects one complete original, including the five joining journal lifetimes,
and never combines session, direct-operation or probe evidence across histories.
Phase 3 and the combined byte/resource envelope remain OPEN.

## Collection and original-first admission

The producer additionally enables `v53.resource.source.control`,
`v53.resource.control.close` and `v53.resource.export.ownership`. These existing
fixture options apply to the original network owners and the joining pool.
Collection requires `control-close-captures/index.json` alongside the resource
and storage-transfer indexes. Presence is collection only; it gives no acceptance.

The independent verifier invokes the existing native resource composition with
`complete_exports=True`, `joined_files=True` and `joined_closes=True`. Physical,
network, continuous ledger, generation, handoff, file and close checks still run.
The strict export option additionally derives original source responses, cleanup
children, every session's content extents, direct-operation borrows and the
published-prefix probe. Their exact allocation inventory must agree with the
resource journal and cleanup observations. No allocation may remain unclaimed.

An optional in-process output map receives bindings only after all original
readers and the final original-inventory comparison pass. It must be an empty
plain dictionary with complete exports enabled; it cannot supply input proofs.
The entry replays those derived bindings against the same original journals and
requires the entire coverage result to match before running any mutation.
Bindings are rederived on download and are not loaded from a receipt or new file.
This avoids replaying the expensive physical history solely to recover the map.

All three scopes (`session`, `direct`, `probe`) must be nonempty. Allocation
counts must match their sum. Complete observed exports do not establish all
CONTROL/WAITER work, failed constructors, every export failure path, physical
maxima or whole-runtime shutdown. Those claims stay false.

## Exact negative replay

[`export_allocation_negatives.py`](../../../scripts/v53/export_allocation_negatives.py)
validates the unmodified inventory and all three scopes first. Eighteen
in-memory mutations then remove scopes/proofs, substitute owners or nodes,
miskey bindings, change scope/role/content/extent/lifetime, introduce invalid
types or fields, and duplicate a proof under another key. Each must fail for
its exact expected reason; an unrelated failure or accepted mutation fails the
entry. The original bindings, journals, cleanup observations and files stay intact.

The complete entry now requires **89 exact negatives**: the preceding 71
accounting/handoff/file/network-close/joining-close cases plus these 18 export
binding cases. Other component negative catalogues retain their own obligations.
The source, compiled classes, toolchain, readers, workflow/run/attempt and raw
inventory remain pinned. The twelve-subset catalogue and its 566 histories,
260 execution groups, 500 archives and 544 selected jobs are unchanged.

## Validation and remaining execution

Focused tests exercise all eighteen mutations for each of the ten session
families, including nested exports, plus original-first rejection and unchanged
inputs. Entry tests reject missing cleanup/coverage, absent or altered binding
output, mismatched coverage summaries, missing scopes and broader claims.
Hosted orchestration still requires a complete original and all exact negatives.

A short native stable TCP history and independent replay pass with the combined
source/control/export flags: 96 cleanup intervals, 39 sessions, six direct exports
and four publications with 44 physical boundaries. Its 708 files (4,343,087 bytes)
remain unchanged. It is not a required-four history, lacks the joining/probe
scope and cannot qualify these 89 required-four negatives.
The earlier stable smoke also executed successfully, but replay refused an extra
storage-transfer sidecar outside that reader's exact directory contract. That
configuration failure remains retained. The corrected stable run omits only this
required-four-specific observation; no reader rule or required-four flag is relaxed.
All 237 related Python tests and 52 optimized-mode tests pass.
Detailed logs and hashes are retained under `target/v53-required-four-export-entry/`.
The complete corrected-source required-four run remains deferred to the hosted
batch. No long original, source identity or historical evidence is relabelled.

Rollback removes this entry's three additional capture flags, required cleanup
sidecar, strict export call/output and eighteen-case family together. Keep the
original physical checks and preceding 71-case resource gate. No production Java,
POM, frozen capacity, retry/deadline, Required job or paid-cloud change is made.
