# V5.1 Phase 4 current evidence status

**Status:** Batches A–M accepted through PR #204 / #205 at master
`39332feb71f877d3cbd976631e8a26a9cf2f607c`, exact-master CI `35753082195`.
Batch N selection/recovery qualification passed locally; protected Batch N and full
Phase 4 acceptance remain pending.
This is a coverage review, not a replacement for the accepted
[scenario matrix](TESTING_AND_EVIDENCE.md#scenario-matrix) or a Phase 5 entry decision.
The older Batch C coverage table remains its historical gap record.

## Reading the map

A scenario named below has an implementation/gate and its batch-local evidence.
This table does not assert that every possible schedule in an E row has passed.
Public gates execute external consumers against candidate JARs; internal model,
byte-fixture and Java checks supply separate evidence. Batch L deliberately retains
that distinction for impractically large public exhaustion schedules.

| Family | Concrete evidence now available | Remaining qualification/reconciliation |
| --- | --- | --- |
| E01 startup/activation | A public EMPTY/import bootstrap; B public lifecycle/failover; E imported retained recovery; H no-quorum startup. | Reconcile activation NO_OP and successful-prefix coverage across those receipts in final Phase 4 review. |
| E02 campaigns | F competing campaigns and asymmetric transport schedules; I/J peer and candidate promise/PREPARE boundaries; N exact duplicate PREPARE and higher promise crossing delayed ACCEPT/PROOF; Phase 3 model/kernel checks. | N protected acceptance and final named-schedule reconciliation remain required. |
| E03 fencing | D isolated old leader and promise-versus-read capture; F directed request/response loss; N delayed ACKs crossing a forced higher epoch; retained public rejoin. | Reconcile delayed heartbeat coverage against the accepted row; delayed ACCEPT/PROOF evidence does not establish every heartbeat schedule. |
| E04 promises/epochs | I twelve peer crash cases; J fourteen candidate crash cases; L real 10,000-row store exhaustion and ranked integer overflow. | L limits are internal fixtures, not 10,000 public elections; retain this boundary in acceptance and assess full-row sufficiency explicitly. |
| E05 mutation stages | C lost response and independent histories; D ACCEPT/PROOF/publication interruption; K delayed exact force and conservative outcomes. | Final correlation of each named force/quorum/publication/response boundary, including uncertain inclusion. |
| E06 selection | F minority tail selected/discarded; N public lagging candidate, hidden proof and chosen-unknown retention; N also maps exact internal conflicting-selection/acceptance-versus-origin tests. | Conflict/mixed-basis rejection uses internal fixtures, not fabricated public quorum traffic. Review that layer boundary at final acceptance. |
| E07 snapshots/reclamation | F basis/snapshot progress/selector cuts; G two-source floors and retirement interruptions; K retained pressure restart; L snapshot reservation/budget exhaustion; N higher epoch during partial basis download. | Explicit pin-during-rebuild mapping remains; complete control queue saturation remains separate. |
| E08 disk/restart | B/C/D/F/G retained restarts; E imported recovery and missing/copied authority rejection; I/J archived promises and fresh campaigns; K/L retained pressure restarts. | Reconcile one/two lost disks and new-group verified-cut transition with public admission/cleanup evidence. No same-group disk re-enrollment is enabled. |
| E09 reads | B complete façade; C rich V4.4 query/page/rank/highlight/explain comparison; D capture fencing; E cursor reconstruction; independent per-read NO_OP/view checks. | Final method-to-consumer inventory and callback/rebuild overlap mapping, without broadening follower-read guarantees. |
| E10 lifecycle/outcomes | C/D uncertainty/response cuts; E cancellation/close/pins; H admission rejection; K delayed force/reservation release; L exhausted-voter rejection and quorum service; M queued deadlines, query reentrancy and completion callbacks. | Partial-write error and the final lifecycle method/scenario mapping remain to be reconciled. |
| E11 resources | H payload/application/admission/no-quorum limits; K outbound/inbound reservations and slow force; L public retained/staging budgets plus internal fixed counters; M internal 32/16 mailbox boundaries and public completion admission. | M mailbox saturation uses internal private-method calls, not public reachability. Repeated-timeout mailbox accumulation, unbounded endurance and OS resource exhaustion are not established. |
| E12 compatibility/admission | A bootstrap/resume/cleanup; H mode/configuration/wire rejection; existing compatibility lanes and published controls. | Final mapping of every 1.0/1.1/1.2 wire/disk mismatch and ambiguous-cleanup case to the correct public/internal gate. |

## Next bounded work

1. Obtain protected acceptance of [Batch N](PHASE_4_PUBLIC_SELECTION.md). Preserve
   internal/public evidence identities in its selection-conflict mapping.
2. Qualify or map pinned-read/rebuild overlap, partial-write errors and repeated
   timeout/mailbox accumulation. Reconcile the named delayed-heartbeat and remaining
   compatibility/admission cases with their actual gates; do not infer them from a
   generic partition or from queue capacity alone.
3. Review the final method/scenario map, run the required gates on the final source,
   and obtain protected Phase 4 acceptance. No individual batch merge closes it.

The accepted charter, V5.0 authority/release evidence, future follower reads,
membership changes and paid-cloud authorization are unaffected.
