# Bounded automatic fresh campaigns

Phase 3 remains **OPEN**. The private automatic owner can now abandon a lost
round, drain its work and start a fresh election/discovery/activation round. It
does not replay the client operation that encountered the loss.

## Implementation boundary

`MembershipCampaignLost` distinguishes an authenticated higher ballot, an actual
view change and exhausted majority contact. Journal polling supplies only a
cancellation hint; every subsequent work boundary retains full original storage
validation. Incoming wire validation keeps its existing errors. Message text,
nested exceptions, storage corruption, malformed replies and closed transports
cannot authorize a new campaign.

The automatic owner rejects the old queue, closes the exact old session and
requires successful drain before opening the next session. A suppressed cleanup
failure is terminal. A concurrent close also owns any late factory result and
prevents it from starting. An admitted write fails to its caller and is never
resubmitted by this loop; its durable outcome still requires normal recovery.

The native adapter permits at most `min(3, maxRetryAttempts)` total service
rounds. Existing activation campaign and identical-exchange retry bounds are
unchanged. All rounds receive the same original start and lifetime budget;
waiting, cleanup and factory work consume it. This finite private qualification
owner is not an indefinitely running public service. A journal that has already
failed during a write remains failed; safe cold reopen is still separate work.

## Retained validation

The [source-bound receipt](phase3-evidence/automatic-campaigns.json) separates two
source snapshots rather than presenting all tests as one final-source execution:

- The first snapshot passed 64 Java tests: ten fresh-session orchestration,
  fourteen owner, three real-journal fence, fifteen heartbeat and twenty-two
  activation checks, in 256.004 seconds. Its native WAITING-close history passes
  independent original replay and six negatives.
- The final Java snapshot also preserves the typed error from a correlated
  higher activation REJECT. Five affected activation regressions, a native READY
  fence, the existing automatic service and the new automatic reactivation history
  passed: eight tests in 313.562 seconds. The new history itself took 161.4 seconds.
- The unchanged service history passes complete discovery/barrier/heartbeat/DATA
  replay and seventeen negatives. The READY-fence failure component is retained
  separately; it is not claimed to be a successful service history.
- Twenty-three focused Python tests passed. The new physical reader passes
  eighteen exact evidence negatives. Across the three replayed histories there
  are 41 evidence negatives; no unrelated original error counts as a rejection.

The new native history uses three real TCP members. After barrier 1, node 2
durably reserves counter 3 and sends an authenticated higher-ballot heartbeat.
The same owner drains its old round, elects at counter 4, publishes barrier 2,
accepts one new DATA call at index 3, then closes. Default heartbeat/RPC/election
policy is unchanged. This new two-campaign fixture declares a single 300-second
whole-history budget before opening its endpoints; it never renews that budget.

Independent physical replay derives all fourteen snapshot groups, including
bootstrap, both frozen selections, each original vote/proof/certificate, the
application image, retention ledgers, hidden ancestry and final close. It also
checks the forced peer allocator and delivered higher-ballot ACK between the
two READY boundaries. An unused node-3 PREPARE source is reconstructed from its
preceding original files and fresh source UUID, without adding it to the chosen
pair. The first reader attempt omitted pre-campaign maintenance and that unused
capture and failed; its diagnostic is retained. The raw Java history was not
modified or rerun to fix the reader.

`automatic_restart_evidence` deliberately retains its **PARTIAL** result: that
entry checks physical state and the fence/READY boundaries. The complete network
continuation below adds its own acceptance rather than widening the older entry.

## Complete original network replay

`automatic_restart_network` now replays this same unchanged native history in
full. The [network receipt](phase3-evidence/automatic-campaign-network.json)
binds the original Java execution/source and the new Python reader separately.
No native workload was rerun and no original evidence was edited.

| Continuous phase | Original exchanges | Source traces |
| --- | ---: | ---: |
| First discovery and activation | 28 | 4 |
| Barrier 1 | 79 | 16 |
| Higher fence, discovery and second activation | 85 | 10 |
| Barrier 2 | 87 | 18 |
| DATA 3 | 109 | 21 |
| Total | 388 | 69 |

Of the 69 traces, 68 complete their original transfers. The remaining trace
belongs to the unused node-3 source: its BASIS and PROMISE complete, then its
CAPSULE offer arrives without the body or commit. The reader checks that exact
offer against node 3's independently reconstructed capture, without accepting it
as a usable source. Only the complete selected pair can justify installation.

The replay requires original discovery before allocation, complete maintenance
copies before floor/retirement, forced grants and delivered replies before
dependent selection, exact ACCEPT/PROOF receipts, all application endorsements
(including parent and hidden-ancestor ACKs), and durable future recording on both
voters before every publication send. It accounts for every wire response and
delivery, permits only finite identical retries and rejects cross-phase trace
reuse. The three unselected rejection groups are bound to the exact requests
derived from their corresponding recording rounds; diagnostics do not vote.

Twenty-nine network negatives plus the eighteen physical/fence negatives reject
for their declared reasons. Twenty-three focused Python tests pass. This remains
one controlled three-node history, not native process restart, SIGKILL recovery,
all membership profiles, public readiness or Phase 3 closure.

## Reproduction and next gate

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53AutomaticCampaignTest,V53CampaignFenceTest,V53AutomaticRestartTest test
python3 -B -m scripts.v53.automatic_restart_network RAW_DIRECTORY --qualify
```

The native test prints `v53NativeDispatchEvidence=...`. Keep its entire bootstrap,
first activation, fence, new election, second activation, DATA and close together
in one workspace. Hosted parallelism may distribute independent whole histories,
not stages of this history. Next extend automatic ownership to admitted progress
and safe process recovery.
The seven membership profiles and complete process/negative matrix remain open.

No POM, workflow, frozen format/resource limits or paid-cloud behavior changes.
