# Native soft budgets and packed retention

**Status:** accepted through PR #316, source `f46f9a4ea624df2b42902efd0b633c30933ae2f2`.
Native canonical-1 `38280933954` and canonical-2 `38300809738` passed workload,
replay, packed retention, cleanup and ledger finalization. The remaining members
are covered by the explicitly authorized [one-batch continuation](PHASE_6_IMAGE_CONTINUATION.md)
after fixing DEPRECATED image admission. The operator authorized soft **time and money** budgets.
This supersedes the v3 native stage/cost ceilings for new v4 requests. Historical
requests, failed evidence and the separate offline CI qualification keep their
original semantics. This change does not reset the ledger or dispatch cloud work.

## Failure and evidence

PR #315's master `be16ce4af3837a13558b73efbce7c4feade68e44` passed
[CI 38193537774](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38193537774).
[Canonical-1 38206276543](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38206276543)
executed all fifteen cells and passed the original independent physical/history
and backup replay, including all 1080 rich-workload calls. It subsequently failed
the 2400-second validation-retention ceiling:

| Work | Observed seconds |
| --- | ---: |
| Collection and service shutdown | 1103.692 |
| Independent replay | approximately 716.041 |
| Upload and immutable read-back before interruption | approximately 580.267 |

Only 694 small evidence objects (3,441,869 bytes) had been retained; workload parts
had not yet been uploaded. Serial per-file uploads spent minutes on a few MiB.
Cleanup confirmed all thirteen exact resources absent. Retention stayed INCOMPLETE,
completion was blocked, and the ledger reservation remained PENDING with the
original lease retained. The observed cumulative accounting amount was USD 100.
Manual reconciliation must finish that attempt using its original expiry/grace;
this patch does not relabel it PASS or renew its lease.

Original Actions ZIP SHA-256:
`596f8e3a317a6e1475226f6325170b7cc77a3bd1f492cb1054cea2e6651b3bfe`.
Local diagnosis: `target/v51-canonical-failure-38206276543/diagnosis.json`.

## New source-bound policy

[native-soft-budget-policy.json](native-soft-budget-policy.json) is bound to
`gse-v51-native-request-v4` and the immutable five-member sequence identity.
The prepare workflow now emits v4; changing only a legacy request's schema or
profile does not validate. v1/v2/v3 remain readable for cleanup and historical replay.
The historical `native_preset_review` CLI remains the v3 review tool; use the
current Runner's **prepare** output to review and authorize v4 execution.

| Item | v4 behavior |
| --- | --- |
| Preparation, each cell, control overhead, validation/retention, cleanup | Original threshold retained as a warning; exceeding it does not fail the run |
| Ordinary healthy RUNNING command | Observe the same command beyond its warning threshold; never resubmit it |
| USD 200 accumulated amount | Warning threshold; crossing it does not block new v4 admission |
| Price estimate above entered per-attempt amount | Visible warning; exact reviewed plan still required |
| Failed attempts | Their recorded amounts remain in the ledger |
| Identity, permissions, malformed evidence, semantic oracle failure | Terminal failure |
| Repeated transport failure or uncertain receipt | Existing three-failure/three-uncertain fast exit |

Time is still charged once against a controller monotonic clock. Heartbeats run
every 30 seconds; overdue stages emit WARNING, and the summary shows thresholds,
elapsed time and warning categories. Retention logs each verified package and its
cumulative bytes. A stage cannot be restarted to erase its observation interval.

The ledger records conservative input amounts, **not actual provider billing**.
The wire field `maximumCostMicrousd` remains for compatibility but is advisory for
v4. Explicit plan approval, source/build identity, current prices, pending-attempt
exclusion, sequence membership and failed-canonical invalidation remain required.
Integer and evidence-size bounds remain structural checks, not spending caps.

## Platform lifetime and cleanup authority

GitHub-hosted jobs have an unavoidable
[six-hour execution limit](https://docs.github.com/en/actions/reference/limits).
Prepare/run no longer have an earlier shell `timeout`; their jobs use the platform
maximum. This does **not** promise unlimited execution on GitHub hosted runners.

All v4 runtime stages borrow the original 21600-second ownership lifetime instead
of receiving individual kill deadlines. Preparation helpers and guest sessions
use that same source-bound policy. There is no lease renewal; the original
1800-second operation grace still controls independent cleanup. Manual cleanup
cannot delete an active experiment, including one past a soft stage threshold.
At platform expiry, cancellation or process loss, exact-ID cleanup remains the
recovery path. The platform may prevent final Actions artifact upload at six hours.

Quotes conservatively cover 45000 seconds (21600 preparation + 21600 VM lifetime
+ 1800 grace). Approval and preflight freshness remain 900 seconds: these gate
the first allocation, rather than impose a running experiment's time budget.
Per-exchange transport timeouts and frozen fault/watchdog durations retain their
original roles. Measurement call counts, rates, windows, drain rules, fault cases,
physical/history oracles and backup checks are unchanged.

## Retention layout

v4 uses `gse-v51-native-owned-evidence-v2`. Startup, connection, selected preparation
and session metadata are packed as `metadata/part-NNNN.bin` with `metadata/parts.json`.
The compressed archive contains every original logical path and a per-file
size/SHA-256 inventory. The existing bounded binary collector verifies the archive
by unpacking it before upload. Workload evidence retains its separate `parts/`
layout. All uploads still use create-only writes, exact generation read-back and
digest comparison; manifest sealing and successful finalization require every
listed object to be verified. Corruption or incomplete retention cannot count as
acceptance or release the lease. Legacy evidence layouts remain supported.

An offline replay packed 975 original service/connection/preparation/session files
from the authenticated failed-run archive: 7,352,097 bytes became **two upload
objects totaling 332,494 bytes**, with exact path/byte verification in 0.384 seconds
locally. This replay includes all service files, a superset of the startup selector;
it demonstrates packaging and object-count reduction, not measured GCP throughput.
Receipt: `target/v51-soft-budgets-retention/original-metadata-replay.json`.

## Validation and next execution

The dedicated soft-budget tests cover all five members and all stage categories,
slow healthy command observation, preserved fault durations, crossing USD 200,
exact approval and price coverage, immutable archive replay/corruption, full
fifteen-cell modeled lifecycle, late preparation/retention, retained charges,
failed evidence, lost upload and cleanup without an unverified lease release.
The new suite runs in the required cloud-preflight admission lane. These tests use
synthetic transport; they do not manufacture native acceptance.

After protected merge: complete the old manual reconciliation, collect fresh
exact-source CI/preflight, create a **new sequence and v4 prepare**, review the
new price coverage/soft warnings, then manually dispatch any of the five members.
All five passing members must share source, package and policy; earlier-source
successes and the failed canonical run cannot be combined into the final set.
