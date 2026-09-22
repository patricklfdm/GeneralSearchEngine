# V5.1 Phase 4 current evidence status

**Status:** consolidation after Batch L local qualification. Batches A–K have
protected acceptance; Batch L and full Phase 4 acceptance remain pending.
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
| E02 campaigns | F competing campaigns and asymmetric transport schedules; I/J peer and candidate promise/PREPARE boundaries; Phase 3 model/kernel checks. | Explicit public duplicate-PREPARE and higher-ballot-during-ACCEPT/PROOF schedules still need a final mapping or added cases. |
| E03 fencing | D isolated old leader and promise-versus-read capture; F directed request/response loss; retained public rejoin. | Reconcile delayed heartbeat/proof/reply cases against the accepted row; do not infer every delay from a generic partition. |
| E04 promises/epochs | I twelve peer crash cases; J fourteen candidate crash cases; L real 10,000-row store exhaustion and ranked integer overflow. | L limits are internal fixtures, not 10,000 public elections; retain this boundary in acceptance and assess full-row sufficiency explicitly. |
| E05 mutation stages | C lost response and independent histories; D ACCEPT/PROOF/publication interruption; K delayed exact force and conservative outcomes. | Final correlation of each named force/quorum/publication/response boundary, including uncertain inclusion. |
| E06 selection | F minority tail selected/discarded; internal recovery tests cover conflicting equal-ballot bases and different acceptance/origin ballots; model covers selection rules. | Public lagging-candidate/hidden-proof and ambiguous/conflicting frozen-selection rejection mapping remains open. |
| E07 snapshots/reclamation | F basis/snapshot progress/selector cuts; G two-source floors and retirement interruptions; K retained pressure restart; L snapshot reservation/budget exhaustion. | Explicit pin-during-rebuild and epoch-change-during-download mapping; complete control queue saturation remains separate. |
| E08 disk/restart | B/C/D/F/G retained restarts; E imported recovery and missing/copied authority rejection; I/J archived promises and fresh campaigns; K/L retained pressure restarts. | Reconcile one/two lost disks and new-group verified-cut transition with public admission/cleanup evidence. No same-group disk re-enrollment is enabled. |
| E09 reads | B complete façade; C rich V4.4 query/page/rank/highlight/explain comparison; D capture fencing; E cursor reconstruction; independent per-read NO_OP/view checks. | Final method-to-consumer inventory and callback/rebuild overlap mapping, without broadening follower-read guarantees. |
| E10 lifecycle/outcomes | C/D uncertainty/response cuts; E cancellation/close/pins; H admission rejection; K delayed force/reservation release; L exhausted-voter rejection and quorum service. | Explicit queued-deadline, partial-write error and callback-reentrancy public schedules remain to be mapped or added. |
| E11 resources | H payload/application/admission/no-quorum limits; K outbound/inbound reservations and slow force; L public retained/staging budgets plus internal fixed counters. | Runtime input/completion mailbox saturation is not transport saturation. Fixed-limit fixtures do not establish unbounded public endurance or OS resource-exhaustion behavior. |
| E12 compatibility/admission | A bootstrap/resume/cleanup; H mode/configuration/wire rejection; existing compatibility lanes and published controls. | Final mapping of every 1.0/1.1/1.2 wire/disk mismatch and ambiguous-cleanup case to the correct public/internal gate. |

## Next bounded work

1. Qualify internal runtime mailbox pressure, queued deadlines and callback
   reentrancy through permitted public operations and read-only/fault hooks.
   Preserve conservative results and account for every admitted operation.
2. Complete the remaining selection/recovery schedules or document their exact
   existing evidence mapping. A model/fixture result must keep its own execution
   identity even when it supports a public safety argument.
3. Review the final method/scenario map, run the required gates on the final source,
   and obtain protected Phase 4 acceptance. No individual batch merge closes it.

The accepted charter, V5.0 authority/release evidence, future follower reads,
membership changes and paid-cloud authorization are unaffected.
