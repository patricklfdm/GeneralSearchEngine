# V5.1 Phase 4N: public selection and recovery fencing

**Status:** local qualification passed; protected Batch N and full Phase 4 acceptance
remain open. Batches A–M are accepted through PR #205 at
`39332feb71f877d3cbd976631e8a26a9cf2f607c`, exact-master CI `35753082195`.

## Public execution boundary

`scripts/verify-v51-phase4-public-selection.sh --skip-build` runs six cases against
packaged candidate JARs. The external consumer uses public EMPTY bootstrap,
startup, atomic bulks, strong reads and close. Three JVMs exchange real TCP frames;
each case archives and restarts the original leader from its retained directory.
The controller never assigns a ballot, activates a leader, repairs authority or
replays an uncertain mutation. Unique document tags bind writes to forced entries.

The admitted fixture keeps the existing 1200-ms request and 9600-ms operation
budgets, 4096-byte chunks, and node 3's long election policy. Node 3 continues
ordinary voting and recovery; nodes 1 and 2 campaign naturally. Observer-only
hooks pause selected exchanges and lose one PROMISE reply. A pause releases the
trace monitor so the same JVM can observe and force a higher promise. All pauses
and controller waits remain bounded and failures retain evidence.

## Six schedules

| Case | Boundary and required result |
| --- | --- |
| `duplicate-prepare` | Lose one peer PROMISE response after its promise/basis exists. The automatic transport retries identical PREPARE bytes; the voter returns identical frozen reply bytes, appends no second promise for that epoch, and the actual selection includes that basis. |
| `higher-ballot-accept` | Hold a received ACCEPT_ACK before delivery to the old leader. Isolate that leader and let the surviving majority choose the original unknown entry. Force a higher promise on the old leader before releasing the ACK. Its pending public mutation is INDETERMINATE; the old bytes survive and cannot be published under the retired epoch. |
| `higher-ballot-proof` | Hold a received COMMIT_PROOF_ACK after the peer durably stores proof. The surviving majority recovers the proven prefix. Release the ACK only after the old leader forces a higher promise; require conservative completion and later public service. |
| `hidden-proof` | Hold the old leader before sending COMMIT_PROOF, after its local proof force. The surviving quorum has the chosen entry but no old-epoch proof. Its decoded frozen selection must preserve the exact entry as its next value; the old pending call remains uncertain. |
| `lagging-candidate` | Establish the original leader with node 3, then introduce and catch up node 2. Isolate node 2 while the original quorum acknowledges another bulk. Stop the old leader and heal. Node 2 must adopt node 3's strictly higher proven prefix before serving public reads/writes. |
| `epoch-during-basis` | Hold a continuation DATA reply after a real transferred prefix. Block further old-campaign downloads while restarting the former leader, letting an ordinary higher campaign force a promise at the source. Release the stale reply and require a fresh selection with new basis identities and recovered service. |

In the three held-mutation cases, the remaining two-voter majority must read every chosen unknown bulk
and acknowledge a new, distinct bulk while the former leader remains isolated.
No status flag substitutes for this public read/write evidence. Status only helps
coordinate the bounded schedule; independently decoded bases establish the
lagging candidate's lower prefix and the selected higher prefix.

## Independent checks and counterexamples

The Python oracle decodes observed descriptors and chunk bytes, checks exact
transfer ranges, reconstructs each frozen image, and independently applies the
highest-acceptance selection rule. It binds retained archive hashes/inventories,
process generations, the exact paused request/response, promise force order within
one JVM, uncertain outcomes, immutable entry origin/bytes and subsequent service.
It does not compare clocks between JVMs. In the interrupted download case, data
past the paused prefix must not already have escaped before the higher promise;
a stale successful selection at the source is rejected.

Existing independent history and force/quorum/captured-view oracles also run.
Negative variants remove selection transfers, pauses, releases, higher promises,
forces, retry receipts or restarts, and change the final projection. Helper tests
reject borrowed process identities, changed request/reply correlation and fencing
outside the paused interval. A missing witness fails qualification.

## Existing selection conflict evidence, kept at its actual layer

| Requirement | Existing evidence |
| --- | --- |
| Different acceptance and immutable origin ballots | Public Batch F `minority-selected`; internal `V51AutomaticRecoveryTest.selectsAcceptanceBallotPreservesOriginAndReplacesOnlyAfterSelectionForce` and `highestOriginDoesNotOverrideHigherAcceptanceBallot`. |
| Equal-ballot conflicting values or mixed basis identity | Internal `V51AutomaticRecoveryTest.equalBallotConflictsAndMixedBasisIdentityReject`; independent `recovery_inspector.select` rejects inconsistent equal-ballot values. |
| Changed decision at the same ballot or missing frozen evidence | Internal `V51AutomaticRecoveryTest.selectedDecisionCannotBeChangedAtSameBallotAndItsEvidenceIsMandatory`. |
| Proven prefix over obsolete minority tail | Internal `V51AutomaticRecoveryTest.provenPrefixWinsOverObsoleteMinorityTail`; public Batch F distinguishes included and excluded minority voters. |
| Selected but not yet proven value across another campaign | Internal `V51AutomaticRecoveryTest.higherCampaignRetainsPreviouslySelectedButUnprovenVote`; this batch supplies public chosen-unknown and hidden-proof cases. |

Internal store fixtures are not public malformed-quorum executions. This mapping
records their contribution without claiming a public caller can manufacture an
invalid frozen quorum. Final E01–E12 acceptance still needs explicit review.

## CI and remaining work

The gate runs in `v51-protocol-reclamation` with the always-retained
`v51-public-selection-${{ github.sha }}` artifact under `target/v51-public-selection`.
Existing required lanes and documentation-only routing are preserved. No production
Java, limits, timeouts, formats, dependencies or paid-cloud behavior change.

See the [current evidence map](PHASE_4_EVIDENCE_STATUS.md) for pinned-read/rebuild,
partial-write error, repeated-timeout mailbox accumulation and final method/scenario
mapping. This batch does not close Phase 4 or authorize Phase 5/cloud/publication.

## Local validation

Base: `39332feb71f877d3cbd976631e8a26a9cf2f607c` plus this batch.

- Complete six-case gate: `target/v51-public-selection/run.cBX95I/evidence/receipt.json`.
  All six cases passed across 24 runtime process identities and 58 public calls;
  all 66 history/physical/scenario counterexamples were rejected.
- Existing observer regressions `basis-kill` and `before-reply-kill` passed at
  `target/v51-selection/shared-protocol/receipt.json` and
  `target/v51-selection/shared-promise/receipt.json`.
- All 50 existing `V51AutomaticRecoveryTest`, `V51AutomaticProtocolTest` and
  `V51AutomaticTransportTest` tests passed in `target/v51-selection/java-tests.log`.
  This is targeted local Java validation; protected lanes retain full reactor tests.
- The complete independent foundation gate passed at
  `target/v51-foundation/run.XepbXA/evidence/receipt.json`, including version alignment,
  the unchanged V5.0 contract, 37-document V5.1 contract and all 203 V5.1 Python tests.
  Seven new helper tests cover pause/retry/fencing rejection boundaries.
- All 25 CI/toolchain tests passed. `target/v51-selection/static-review.json` verifies
  YAML, 104 shell blocks, 33 unique artifact names, unchanged existing steps/job
  settings/triggers, local links and the historical 87-step migration table.
  Python compilation, shell syntax and whitespace checks passed.

Candidate JAR bytes match the accepted source:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `2ff8fae57f0ee0ce09f2aefe80cfdba294c6f3599eb45823fd5df4fb327a996e`.

Exploratory receipts remain under `target/v51-selection/probe-*`. The initial
freshness check rejected the older JAR timestamp after checkout; archiving and
repackaging regenerated the same artifact bytes. The first executed matrix caught
an oracle field error: ACCEPT carries an encoded `acceptance`, whose `entry` is
nested. Its failed receipt remains preserved; the final full gate above uses the
correct decoder. Runtime outcomes and deadlines were not relaxed. Execution-time
source inventories precede this final documentation record.
