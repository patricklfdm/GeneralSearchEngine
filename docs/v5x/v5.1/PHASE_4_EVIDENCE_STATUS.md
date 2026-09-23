# V5.1 Phase 4 current evidence status

**Status:** Batches A–O accepted through PR #207 at master
`1a043615ec4a8de5b7f110d999c5f7268e5e165c`, exact-master CI `35794875603`.
[Batch P](PHASE_4_FINAL_COVERAGE.md) adds final public witnesses and the complete
method/scenario/compatibility reconciliation; protected Phase 4 acceptance is pending.
This is a coverage review, not a replacement for the accepted
[scenario matrix](TESTING_AND_EVIDENCE.md#scenario-matrix) or a Phase 5 entry decision.
The older Batch C coverage table remains its historical gap record.

## Reading the map

A scenario named below has an implementation/gate and its batch-local evidence.
This table does not assert that every possible schedule in an E row has passed.
Public gates execute external consumers against candidate JARs; internal model,
byte-fixture and Java checks supply separate evidence. Batch L deliberately retains
that distinction for impractically large public exhaustion schedules.

| Family | Concrete evidence now available | Final reconciliation / layer boundary |
| --- | --- | --- |
| E01 startup/activation | A public EMPTY/import bootstrap; B public lifecycle/failover; E imported retained recovery; H no-quorum startup. | Mapped to activation NO_OP and full-prefix physical checks in [final coverage](PHASE_4_FINAL_COVERAGE.md#e01e12-disposition). |
| E02 campaigns | F competing campaigns and asymmetric transport schedules; I/J peer and candidate promise/PREPARE boundaries; N exact duplicate PREPARE and higher promise crossing delayed ACCEPT/PROOF; Phase 3 model/kernel checks. | Named schedules and kernel counterparts reconciled in the final table; progress assumes the declared healed/stable period. |
| E03 fencing | D isolated old leader and promise-versus-read capture; F directed request/response loss; N delayed ACKs crossing a forced higher epoch; retained public rejoin. | P adds real delayed HEARTBEAT request and ACK across higher durable promises, old-handle refusal and retained rejoin. |
| E04 promises/epochs | I twelve peer crash cases; J fourteen candidate crash cases; L real 10,000-row store exhaustion and ranked integer overflow. | L limits remain internal fixtures, not 10,000 public elections; explicit final-layer boundary retained. |
| E05 mutation stages | C lost response and independent histories; D ACCEPT/PROOF/publication interruption; K delayed exact force and conservative outcomes. | Force/quorum/publication/response correlation and uncertain inclusion mapped in the final table. |
| E06 selection | F minority tail selected/discarded; N public lagging candidate, hidden proof and chosen-unknown retention; N also maps exact internal conflicting-selection/acceptance-versus-origin tests. | Conflict/mixed-basis rejection remains internal; public selection cases and exact test names mapped in the final table. |
| E07 snapshots/reclamation | F basis/snapshot progress/selector cuts; G two-source floors and retirement interruptions; K retained pressure restart; L snapshot reservation/budget exhaustion; N higher epoch during partial basis download; O held public query overlapping new snapshot install and queued reconstruction. | O proves serialized view release before actual reconstruction; accepted-tail preservation mapped to the named internal test. |
| E08 disk/restart | B/C/D/F/G retained restarts; E imported recovery and missing/copied authority rejection; I/J archived promises and fresh campaigns; K/L retained pressure restarts. | P adds one/two unavailable authority directories, repeated rejected opens, surviving-majority/minority behavior and verified-cut import into a new group. |
| E09 reads | B complete façade; C rich V4.4 query/page/rank/highlight/explain comparison; D capture fencing; E cursor reconstruction; O old pinned-view completion followed by recovered new-prefix reads; independent per-read NO_OP/view checks. | [Complete method/overload inventory](PHASE_4_FINAL_COVERAGE.md#complete-runtime-method-inventory), including metadata and diagnostics; no follower-read guarantee added. |
| E10 lifecycle/outcomes | C/D uncertainty/response cuts; E cancellation/close/pins; H admission rejection; K delayed force/reservation release; L exhausted-voter rejection and quorum service; M queued deadlines, query reentrancy and completion callbacks; O actual partial ACCEPT/PROOF I/O failure, quarantine, rejected unchanged restarts and majority recovery. | Lifecycle methods, public outcomes and kernel regressions reconciled in the final table. |
| E11 resources | H payload/application/admission/no-quorum limits; K outbound/inbound reservations and slow force; L public retained/staging budgets plus internal fixed counters; M internal 32/16 mailbox boundaries and public completion admission; O three queued-timeout waves and three real network-timeout rounds with bounded samples and balanced reservations. | Mailbox saturation remains internal; O samples are finite, not arbitrary stalled-control accumulation, endurance or OS exhaustion. |
| E12 compatibility/admission | A bootstrap/resume/cleanup; H mode/configuration/wire rejection; existing compatibility lanes and published controls. | [Bidirectional compatibility map](PHASE_4_FINAL_COVERAGE.md#compatibility-directions); P explicit decoder checks supplement H public rejection. Ambiguous cleanup remains an internal public-API fixture. |

## Acceptance remaining

1. Run Batch P and the affected shared-oracle/semantic regressions on the final source.
2. Obtain protected full CI and record the merge SHA / exact-master run.
3. Review the final E01–E12 layer boundaries and make the explicit Phase 4
   acceptance decision before planning Phase 5. A batch merge alone is not that decision.

The accepted charter, V5.0 authority/release evidence, future follower reads,
membership changes and paid-cloud authorization are unaffected.
