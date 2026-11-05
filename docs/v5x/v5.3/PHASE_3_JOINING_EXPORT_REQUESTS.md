# Phase 3 joining export request bindings

This follows [session export ownership](PHASE_3_SESSION_EXPORT_OWNERSHIP.md)
and [direct local export ownership](PHASE_3_DIRECT_EXPORT_OWNERSHIP.md).
The [development index](phase3-evidence/joining-export-requests.json) records
conditional component checks and a historical stable replay. Phase 3 remains
OPEN. No full joining or required-four history is newly qualified by this batch.

## Original requests and handles

Five CONTROL metadata owners now include the digest of their exact first
framed request, followed by the existing fresh allocation UUID:

- `joining-retention-export`
- `joining-intent`
- `joining-preparation-export`
- `joining-completion-export`
- `joining-checkpoint-export`

The digest is taken from the validated original `Decoded` request. In particular,
the checkpoint exporter receives that request rather than only its ballot.
Repeated allocations of the same request retain different UUIDs. Every name
fits the existing 128-character owner bound; no resource limit is increased.
Wire/disk formats, reservation extents, admission, retry policy, deadline and
close order are unchanged. These local names confer no protocol authority.

After complete original network/resource replay, `native_source_resources`
can return each session's actual first request bytes and the received/offered
resource boundaries. Outputs are published only after successful original
replay. They are not inferred from matching allocation sizes or nearby events.
The native close reader then supplies those originals to
`joining_export_request_evidence` together with the previously validated exact
session/export handles.

The new reader checks the complete initial-request inventory, first CHUNK
sequence/action, full root/reader/source/trace session binding, request digest,
and construction between the original receive and session allocation. Attachment
must precede the original offer. Early revocation remains observable; it cannot
substitute another handle or repair an unsuccessful close. Any unclaimed probe
or rollback allocation remains visible and keeps overall inventory PARTIAL.

The opt-in native gate is `native_resource_evidence --profile
5-REPLACE-required-four --source-control --control-closes --export-ownership
--joining-requests`. It still requires the original physical/network/maintenance
prerequisites. It has not yet been executed on a new complete required-four
capture. The existing fixture also contains deliberate direct probes and rejected
constructors whose ownership must be qualified separately.

UUID-only historical joining names remain readable in the earlier handle-only
scope, whose receipt explicitly leaves request qualification false. The new
request gate rejects them. The request digest is not a served-content digest:
metadata extents, content authorization, family authority and full physical
custody remain separate obligations.

## Retained validation

- Two new real-handler regressions fail on the original implementation at the
  missing request binding; no unrelated error is counted as that regression.
- The corrected Java run passes 44 tests with no skips or errors. This includes
  the new three-test class and existing retention, preparation, completion,
  checkpoint, session-ownership and direct-ownership suites.
- Two original conditional handler captures cover retention metadata plus its
  nested prefix, and preparation metadata excluding shared publication. Their
  independent replay and 20 exact negative checks pass. Outer receipts stay
  PARTIAL, with native membership and all-family qualification false.
- All 153 focused Python tests pass, including twenty new tests covering all
  five typed names, route/trace and initial
  request mismatches, ordering, legacy captures, missing inputs, strict component
  inventory, preserved partial results and original-before-negative behavior.
- The retained stable native original from the prior batch still passes complete
  physical/publication/network/owner/source/session/direct replay with 45 exports.
  Its 39 first requests also bind to exact original sessions. This historical
  replay is not execution of the new Java source or joining qualification.

Evidence and logs are retained under `target/v53-joining-export-requests/` and
the replication module's same-named target directory. The first auxiliary replay
invocation lacked the repository Python import path and failed before reading
any evidence; it passed with `PYTHONPATH=.`. Both logs are retained. An initial documentation check used a nonexistent
module name; the actual `scripts.v53.contract_check` passes all 2,658 links.
The plan inspector remains source-inventory-only (12 requirements / 544 planned
histories). No workload was rerun to hide a measurement failure.

Complete joining/required-four composition, constructor and abnormal-cleanup
ownership, original content/extent and physical peak/custody checks, frozen cohort
admission and final-source hosted execution remain OPEN. No workflow, POM, frozen
format, paid execution or Phase 4/5 scope changes are included.
