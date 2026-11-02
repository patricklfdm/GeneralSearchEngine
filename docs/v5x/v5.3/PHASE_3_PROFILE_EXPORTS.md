# Phase 3 — profile-bound temporal export authority

The [complete profile network reader](PHASE_3_JOINING_PROFILE_NETWORK.md)
already binds the five ADD/REPLACE topologies and original durable replies.
The subsequent export reader still assumed the joining identity was `node-4`
and considered only the original three-node fixture's active owners. That is
insufficient for `4-ADD`, `4-REPLACE` and `5-REPLACE`, whose joiners are `node-5`
or `node-6`. This batch extends temporal content authority to the actual profile.
It does not assert that all five native profiles have executed.

## Original ownership and recovery

`scripts.v53.joining_profile_export_evidence` first executes the complete
profile physical continuation and attempted-network reader. It then derives:

- Every original voter's generation lifetime, including voters unused by the
  selected cohort, and the actual joiner's initialized generation.
- Subsequent installations and publications from original SELECTED sources and
  CERTIFICATE proof voters. Repeated SELECTED bytes do not invent another install.
- A final newer-prefix adoption only when those original records leave the joiner
  behind the final cut. Its original snapshot becomes exportable after the actual
  adoption return; the selector replacement interval cannot serve either copy.
- Original journal, pending vote, checkpoint, payload and frozen-source windows,
  with the existing exact alias, bytes, view, ballot, force and retirement checks.
- The actual joiner's pending INTENT ACK and its original force/parent/return
  interval. An observation from `node-4` cannot stand in for `node-5` or `node-6`.
- Joining exports under their original initial/continuation owner lifetime.

The existing export authorization functions are shared. Legacy three-node and
same-view recovery callers keep their existing window sets and result shapes.
The profile caller explicitly includes every original voter and uses its distinct
final-adoption boundary; it cannot silently interpret a same-view installation as
ordinary adoption.

All committed transfer sessions are accounted for. The result separately counts
authorized content and remaining control/retention sessions. It remains `PARTIAL`:
complete control exports, maintenance/ledger composition, process death, the
full membership cohort and Phase 3 are not qualified by this entry point.

## Qualification and execution

```bash
python3 -B -m scripts.v53.joining_profile_export_evidence /path/to/original \
  --profile 4-ADD --qualify
```

The original must pass before any mutation. Twelve export negatives are defined.
The pending-ACK lifetime mutation applies only if the independently authorized
original actually contains that export; otherwise it is explicitly reported as
`NOT_APPLICABLE`, never counted as a rejection. All other cases remain required.
An unexpectedly missing mutation target fails the qualification with its case name.
Each applicable negative uses a disposable copy, preserves every non-observation file/directory, and first
passes the complete attempted-network reader. Only the exact declared authority
rejection counts. Accepted mutations, unrelated errors and broken transcripts fail
the qualification. Progress is emitted after each completed negative.

The [receipt](phase3-evidence/profile-exports.json) records measured results and
separates historical native inputs from the current reader. Conditional tests
cover all five topologies, unused voters, adoption ordering, larger joiner ACKs,
owner lifetimes, complete session accounting and rejection isolation. Three
profile-boundary regressions fail against the previous export implementation.

The first REPLACE qualification completed eleven rejections and then failed while
trying to find an unobserved pending-ACK export. Its original, reader, log and failed
attempt remain retained. The corrected applicability rule is derived from the
complete original authorization result; it does not remove an observed failing
case or count this setup error as a successful rejection.

Measured validation: all 1,801 V5.3 Python tests pass, including fifteen new
conditional boundary tests. The complete retained 3-REPLACE original passes eleven
applicable exact negatives and records its unobserved pending-ACK case separately.
Historical 3-ADD passes all twelve. The existing full same-view composition also
passes. These are three retained native histories, not fresh executions of five
profiles. All three replay from the 40,862,402-byte archive with
Python assertions disabled and exactly match their prior results; original and
extracted inventories remain unchanged. The archive retains 21,428
files, including the unsuccessful first qualification and its reader.

## Remaining work and rollback

Generalize control/retention export authorization and the maintenance/ledger
composition to the larger profiles before claiming their complete authority gate.
The final-source seven-profile cohort, whole-history fault/process matrices,
combined resource bounds and frozen S/N mapping remain open. Long native histories
remain indivisible and can be run on independent hosted workers after development.
No native experiment or workflow is triggered by this batch.

Rollback removes the profile adapter and reverts the shared helper extensions,
preserving the retained original evidence and the larger-profile regression
diagnostics. Runtime Java, persisted formats, frozen limits, POMs and workflows
are unchanged.
