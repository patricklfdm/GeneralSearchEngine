# Phase 3 — independent continuous learner replay

The reader `scripts.v53.learner_cycles_evidence` consumes one complete original
`V53LearnerAlternationNetworkTest` history. It never combines different executions
or opens a filesystem path recorded inside a plan. Copied bytes are checked against
recorded original identities; the archive's own inodes confer no authority.

## Independent checks

The reader reduces BARRIER, RESERVE, PREPARE 1–6 and CANCEL from the original
bootstrap. Each original applied/published voter tree must exactly match the
derived state. Six LEARNER receipts and six complete source generations are
derived from those states, independently of the learner snapshots and Java result.

Six acquisitions must each contain four distinct complete ROOT/status/prefix/
generation sessions. All received exchanges must match the original server
history, and every returned byte must match the derived native generation.
Per-cycle exchange intervals are checked against this partition rather than used
as authority to choose convenient slices.

Twenty-five snapshots cover admission, immutable seed selection and retirement,
B1 selection, A2/B3/A4 installation/selection/retirement and cold reopen. Their
seven fixed roots must contain the exact derived source, typed backup and receipt,
plan, installed marker, head and vacancy bytes. Rolling plans bind the preceding
head/vacancy and the covered inactive plan. Cold reopen preserves bytes and
original identities; absent old roots cannot reappear. Observed generation and
application reservations must match the corresponding stage, within the existing
resource parser's bounds.

The producer records event and exchange offsets when each snapshot is taken.
The force reader checks each entire interval, including candidate/active forces,
replacement marker deletion, both source-move parents, covered member deletion,
vacancy forces and release. Missing, duplicate, extra or reordered events fail.
Expected deletion counts come from independently matched member inventories,
not a claimed pass count or the number of observed delete events.

The negative driver first validates the unmodified original. It then requires
twelve mutations to fail for their exact declared reason. An unrelated original
or mutated failure cannot count as successful negative qualification.

## Evidence serialization correction

The first execution found a fixture error before the first learner snapshot:
the protocol JSON encoder deliberately rejects keys such as `initial-typed`,
`.` and `backup/file`. Filesystem inventories and stage labels need those keys.
The helper now uses the existing test-only independent JSON writer for those
two evidence records, retaining explicit byte bounds. Production protocol field
restrictions and persisted records are unchanged. Two focused Java regressions
cover canonical ordering, path keys, escaping, exact capacity and continued
production-codec rejection. A third regression covers partial observation output
without a synthetic PASS record. Failure paths now retain events, received
exchanges and completed snapshot offsets; a retention error is suppressed onto
the original history failure rather than hiding it.

## Execution and scope

Local execution is **PARTIAL**, recorded in
[the development receipt](phase3-evidence/learner-cycle-replay.json). After the
serializer correction, all six learner revisions completed, but final CANCEL
was refused at the original 900-second round deadline. No retry with a larger
budget was used. A separate diagnostic independently reduced the eight completed
native publications and matched all 25 learner snapshots plus auxiliary copies;
it does not replace the missing ninth publication or the whole-history gate.

The failed producer wrote its event buffers only after successful CANCEL. Those
missing observations cannot be reconstructed from expected events and called
evidence. The final helper corrects that failure-retention gap, with three focused
Java tests and complete test-source compilation. The native history was not rerun
after that final test-helper change. All 74 learner Python tests pass, including
14 focused synthetic cycle-reader tests; the complete original-first wire/force
replay and twelve real-evidence negatives remain unexecuted and required in the
deferred hosted gate. Neither a byte diagnostic nor synthetic tests establish
complete native acceptance.

After one successful whole native history, use its printed evidence directory:

```bash
python3 -B -m scripts.v53.learner_cycles_evidence RAW_DIRECTORY
python3 -B -m scripts.v53.learner_cycles_evidence RAW_DIRECTORY --qualify
```

The command's PASS covers only this focused native learner history and observed
force order. It does not qualify process death, the complete voter-network fault
matrix, all five joining profiles, maximum combined resources, cancellation
recovery, matching local INTENT or autonomous integration. Phase 3 remains OPEN.
The [hosted acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md) preserves those gates;
revisions, transfer/installation and crash/restart parts of a history may not be
distributed across independent runners.
