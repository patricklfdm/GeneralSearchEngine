# V5.1 Phase 5 evidence ledger

**Status:** offline replay PASS; accepted through PR #214 with the [Phase 5C review](PHASE_5_ACCEPTANCE.md).
The source/artifact identities below remain those of the original fully tested runtime.
This is a static review index of existing CI evidence, not runtime authority or a new test run.

## Common identity

- Source: `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`.
- CI: [35826641489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35826641489), all 19 jobs and 23 V5.1 verification steps succeeded.
- Tracked source inventory SHA-256: `e172f2b89bb5236ef93fb3c595fb775a441a322182107369a84bb9213be2a36a`.
- All eight suites bind this same source inventory and the candidate JAR hashes below.
- Offline replay: 23 public cases and 8 internal cases passed; 349 evidence-negative variants rejected.
- Relocated authority: 6 ordinary-inspector copied-path rejections; forensic replay uses the existing archive API with immutable inventories.
- Downloaded raw evidence was unchanged by review. All suites record paid cloud disabled.

| Candidate artifact | SHA-256 |
| --- | --- |
| `general-search-engine-5.1.0-SNAPSHOT.jar` | `4faf3c4e65fae50df515c003a40f76d2261e6fe502a0c36679856b61abeb0d9d` |
| `general-search-engine-replication-5.1.0-SNAPSHOT.jar` | `d3982f888e2628fdf49b08e32ab3eeca02391f9c05164f0a794533afef149e10` |

## Original CI artifacts

Every artifact name below has the suffix `-fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`.
GitHub digests identify compressed archives. Expanded-inventory SHA-256 hashes identify
canonical file maps produced by the existing storage inspector; they are not ZIP digests.
Artifact IDs are bound to the CI run above; download requires GitHub access and unexpired retention.

| Artifact prefix | GitHub artifact ID | Compressed bytes | Expanded files |
| --- | ---: | ---: | ---: |
| `v51-backpressure` | 10735298620 | 2564610 | 634 |
| `v51-combined-lifecycle` | 10735646774 | 4694727 | 760 |
| `v51-hardening` | 10736095855 | 11563205 | 680 |
| `v51-lifecycle-hardening` | 10734949707 | 8086607 | 955 |
| `v51-public-pressure` | 10735303357 | 5245437 | 920 |
| `v51-resources` | 10735612715 | 4632286 | 642 |

| Artifact prefix | GitHub digest | Expanded-inventory SHA-256 |
| --- | --- | --- |
| `v51-backpressure` | `sha256:8324dad8e9d5b823357bd481cb766e2e0089ed67c1c2002f5ab0ecc10e954000` | `9a80ee7e69b0078345105e564d928fd1a87e71b74347dd537308bfdda5555ae4` |
| `v51-combined-lifecycle` | `sha256:4feaea4c78d2ea9625abc08054627a1b5c38af8a262845509175ea871bc6ea4a` | `a1ab94eef8f867b3eb3ae61ec479fa4e3ce6e584ccc67144a84a59029e06c176` |
| `v51-hardening` | `sha256:5acdc4f0ba986c24d760878ed4aca142764561ebe11968e220a7305cb0741bd0` | `910487134d2e5fcb0a216422c0f6309147d79ac590e3fdcc78fc9c3ecffdccf1` |
| `v51-lifecycle-hardening` | `sha256:eefc5d59684c61bf264f1e9fc2867e6c0f88db1338f30eb2076cecedb0fc9c14` | `f3ac098a3037101757893a7ed97cff4f7aaea172de3bcde7f47e61a5c91abd4b` |
| `v51-public-pressure` | `sha256:8921c62bd43cad5da1eb5feed1ca94d98236501f139e894476f1f5c59d382503` | `ae1dc4f201e9e107ca965bfd8fed047e207de95666d020557bcb9d02e2b99f42` |
| `v51-resources` | `sha256:e6ae222c57c7ae2a40c29447bea73958e7d5f2a22ccde16f3f1ec873c7b46e77` | `6fd96cf22145e548b806542a8212d0ffb2c745b97be2e92f7b55e07ebf2304eb` |

## Replayed suite receipts

Paths are relative to the named artifact prefix above. The receipt hash binds the
original summary; the review separately reran its existing independent checks.

| Execution | Artifact prefix / receipt | Receipt SHA-256 | Cases / negatives |
| --- | --- | --- | ---: |
| `internal-runtime-mailbox` | `v51-backpressure` / `run.KEM5hk/internal/receipt.json` | `773ac45d7f71d1a83a4f7587fdc1564b3c6fdad8b581876bd7231abb2c223432` | 2 / 12 |
| `public-runtime-backpressure` | `v51-backpressure` / `run.KEM5hk/public/receipt.json` | `9a5dee079b1512ba5addaa3c04b673b8404c2d763b4b3279a3930076a01985b6` | 4 / 61 |
| `public-combined-lifecycle` | `v51-combined-lifecycle` / `run.lQ3VBL/evidence/receipt.json` | `3844ce3314f1d123f54ca8813ffa38440a1501d1246c3145a5373bfffefb478f` | 4 / 60 |
| `public-combined-hardening` | `v51-hardening` / `run.3l85cq/evidence/receipt.json` | `cc76f7a5d81f40522e80e38e628d5dd1be94a70c19668fdff827ea9511022484` | 3 / 49 |
| `public-lifecycle-hardening` | `v51-lifecycle-hardening` / `run.8glMx9/evidence/receipt.json` | `9d28ea8ba6535a84cf55e6b2230661b1b019e5e383a5c61cf7fd3ce1f55e216b` | 5 / 54 |
| `public-transport-pressure` | `v51-public-pressure` / `run.LQNQca/evidence/receipt.json` | `9246791271422a45339fc485a1883f70c5ebcdd3af493996dba440dcb5c84cf9` | 5 / 65 |
| `internal-resource-boundary` | `v51-resources` / `run.Fj6EEb/internal/receipt.json` | `4717b22d8e50a74876ed05aa0a1d4aa34525a7d816a771ee6ac9c9f605ed5f36` | 6 / 18 |
| `public-resource-exhaustion` | `v51-resources` / `run.Fj6EEb/public/receipt.json` | `99706cddabe2d01f945def2f863549bfcf3eb06f22430dceed97098f68a10265` | 2 / 30 |

## Per-case replay

All rows passed. Public application histories include every attempted read/write.
Total public calls additionally include recorded lifecycle calls. JVM counts exclude
failed startup probes; internal fixtures are not assigned public-call/JVM claims.

| Suite | Case | Application calls | Total public calls | Runtime JVMs | Rejected variants |
| --- | --- | ---: | ---: | ---: | ---: |
| `internal-runtime-mailbox` | `inputs` | — | — | — | 6 |
| `internal-runtime-mailbox` | `completions` | — | — | — | 6 |
| `public-runtime-backpressure` | `queued-deadline` | 12 | 12 | 4 | 17 |
| `public-runtime-backpressure` | `query-reentrancy` | 8 | 8 | 4 | 15 |
| `public-runtime-backpressure` | `completion-chain` | 10 | 10 | 4 | 14 |
| `public-runtime-backpressure` | `completion-capacity` | 13 | 13 | 4 | 15 |
| `public-combined-lifecycle` | `torn-accept-pressure` | 14 | 14 | 4 | 15 |
| `public-combined-lifecycle` | `torn-proof-pressure` | 14 | 14 | 4 | 15 |
| `public-combined-lifecycle` | `cancel-chosen-recovery` | 11 | 12 | 4 | 15 |
| `public-combined-lifecycle` | `close-pinned-recovery` | 14 | 18 | 4 | 15 |
| `public-combined-hardening` | `partition-accept-kill` | 28 | 28 | 6 | 17 |
| `public-combined-hardening` | `partition-proof-kill` | 29 | 29 | 6 | 17 |
| `public-combined-hardening` | `whole-group-restart` | 22 | 22 | 12 | 15 |
| `public-lifecycle-hardening` | `pinned-rebuild` | 13 | 13 | 4 | 14 |
| `public-lifecycle-hardening` | `partial-leader-accept` | 12 | 12 | 4 | 10 |
| `public-lifecycle-hardening` | `partial-follower-proof` | 12 | 12 | 4 | 10 |
| `public-lifecycle-hardening` | `queued-timeouts` | 18 | 18 | 4 | 10 |
| `public-lifecycle-hardening` | `exchange-timeouts` | 14 | 14 | 4 | 10 |
| `public-transport-pressure` | `outbound-saturation` | 10 | 10 | 4 | 11 |
| `public-transport-pressure` | `inbound-saturation` | 10 | 10 | 4 | 12 |
| `public-transport-pressure` | `slow-follower-accept` | 10 | 10 | 4 | 14 |
| `public-transport-pressure` | `slow-follower-proof` | 10 | 10 | 4 | 14 |
| `public-transport-pressure` | `slow-leader-accept` | 12 | 12 | 4 | 14 |
| `internal-resource-boundary` | `promise-count` | — | — | — | 3 |
| `internal-resource-boundary` | `retained-bytes` | — | — | — | 3 |
| `internal-resource-boundary` | `transfer-staging` | — | — | — | 3 |
| `internal-resource-boundary` | `entry-count` | — | — | — | 3 |
| `internal-resource-boundary` | `ancestry-count` | — | — | — | 3 |
| `internal-resource-boundary` | `epoch-overflow` | — | — | — | 3 |
| `public-resource-exhaustion` | `snapshot-staging` | 11 | 11 | 5 | 15 |
| `public-resource-exhaustion` | `retained-bytes` | 12 | 12 | 5 | 15 |

## Combined-schedule accounting

All process/archive/overlap checks passed. A/B transport ceilings are eight inbound,
four total outbound and 4194304 reserved bytes. Peaks below are maxima across the
voter observations, not sums of simultaneous use. Normal closes balance every reservation.
Only explicitly recorded SIGKILL deaths may destroy live reservations, bound by PID.

| Case | Repeated rounds | Pre-reopen/quarantine archives | Rejected startup probes | Peak inbound / outbound / bytes | Reservations destroyed with recorded SIGKILL PIDs |
| --- | ---: | ---: | ---: | --- | --- |
| `torn-accept-pressure` | one fixed schedule | 2 | 2 | 2 / 4 / 8552 | none |
| `torn-proof-pressure` | one fixed schedule | 2 | 2 | 3 / 4 / 7260 | none |
| `cancel-chosen-recovery` | one fixed schedule | 1 | 0 | 2 / 3 / 8293 | none |
| `close-pinned-recovery` | one fixed schedule | 1 | 0 | 3 / 3 / 7117 | none |
| `partition-accept-kill` | 3 | 3 | 0 | 3 / 4 / 13918 | node-1:9540=2, node-2:9574=1, node-2:9919=1 |
| `partition-proof-kill` | 3 | 3 | 0 | 2 / 4 / 8561 | node-1:10163=1, node-2:10547=1, node-2:10197=1 |
| `whole-group-restart` | 3 | 9 | 0 | 2 / 4 / 8560 | none |

Public minority staging refused a **39668-byte** image against the **32768-byte**
per-transfer allowance of its sealed 131072-byte staging limit. Retained-byte pressure
refused **146760 bytes** against the entire **131072-byte** retained limit. Both cases
kept the healthy majority available; neither claims the exhausted voter regained service.

## Executed V5.1 gates

Every listed step concluded `success`; none was skipped. Supporting non-V5.1 jobs
also succeeded, as recorded in the main review.

| Job | Executed verification step |
| --- | --- |
| V5.1 protocol and selection | Verify V5.1 public campaigns, minority selection and interrupted recovery |
| V5.1 protocol and selection | Verify V5.1 public selection and recovery across higher epochs |
| V5.1 public recovery and pressure | Verify V5.1 imported failover, rejected authority and public lifecycle boundaries |
| V5.1 public recovery and pressure | Verify V5.1 public transport pressure and slow-force boundaries |
| V5.1 public recovery and pressure | Verify V5.1 runtime backpressure and callback ownership |
| V5.1 public recovery and pressure | Verify V5.1 final heartbeat and disk-loss qualification |
| V5.1 admission and resources | Verify V5.1 public capacity, admission and wire rejection |
| V5.1 admission and resources | Verify V5.1 public bootstrap, V4.4 import and offline crash recovery |
| V5.1 admission and resources | Verify V5.1 resource exhaustion and public budget isolation |
| V5.1 admission and resources | Verify V5.1 quarantine pressure and recovery lifecycle combinations |
| V5.1 public hardening | Verify V5.1 pinned recovery, partial writes and repeated timeouts |
| V5.1 public hardening | Verify V5.1 combined faults and repeated retained recovery |
| V5.1 candidate crashes | Verify V5.1 public candidate crashes and fresh elections |
| V5.1 public reads and faults | Verify V5.1 public lifecycle, strong reads and retained failover |
| V5.1 public reads and faults | Verify V5.1 concurrent public histories, read crash cuts and rich V4.4 semantics |
| V5.1 public reads and faults | Verify V5.1 public partitions, read fencing and mutation crash cuts |
| V5.1 foundation and runtime | Verify V5.1 declarations and independent leadership foundation |
| V5.1 foundation and runtime | Verify V5.1 ledgers, frozen recovery and real JVM interruption cuts |
| V5.1 foundation and runtime | Verify V5.1 election and activation transition evidence |
| V5.1 foundation and runtime | Verify V5.1 real TCP runtime and application recovery |
| V5.1 foundation and runtime | Verify V5.1 retained-voter rejoin and two-source reclamation |
| V5.1 reclamation | Verify V5.1 public two-source floors and interrupted reclamation |
| V5.1 promise crashes | Verify V5.1 public promise force and reply crash boundaries |

## Local review outputs

`target/v51-phase5-acceptance/revalidation.json` retains full replay details, including
history witnesses and per-node reservation summaries. `revalidate.py` is the one-off
forensic review driver described in the main review; original checkers remain under
`scripts/v51`. The first review-driver report attempt encountered an output-field
mismatch (`accounting` versus `transport`); its log remains separate. Correcting that
reporting field preceded the complete replay recorded here; no checker or raw evidence
was changed to obtain this result.
