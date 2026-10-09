# V5.1 native full-preset admission and execution

**Status:** local implementation candidate after PR #310's accepted
[three complete owned canonical repetitions](PHASE_6_OWNED_CANONICAL_AGGREGATE.md#protected-acceptance--pr-310).
This batch completes the request-to-cleanup integration in step 4 of the
[native preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md). Protected CI and
actual native failure-drill/canonical acceptance remain pending. No paid run or
cloud configuration change is performed by this implementation batch.

## Two distinct outputs

`scripts.v51.native_preset_review` produces a deterministic, expiring review from
supplied configuration, artifact identities, guest access, quotes and a retained
native ledger observation. It performs no credential exchange, network request,
ledger write or cloud allocation. Supplied CI/provider observations are explicitly
**unauthenticated**. Its `REVIEW_ONLY` output cannot substitute for a paid plan,
current protected CI, a fresh precheck or exact user confirmation.

The native Runner separately admits `gse-v51-native-request-v3`. It binds the
member, sequence order, guest access, source/build/package and timing-plan digest.
The same plan digest binds all five sequence members; each member selects its
closed profile. Legacy request v1/v2 and their cleanup expiry remain unchanged.
Old and new requests cannot be mixed within one sequence, and failed reservations
remain charged. A failed canonical member blocks that sequence.

## Closed native time allocation

[native-preset-timing-review.json](native-preset-timing-review.json) is separately
digest-bound to its reader and to the unchanged cloud workload contract. It is
a review artifact mirrored by the closed `native_preset_timing` implementation, not an amendment to the frozen measured workload
or to the already accepted offline controller.

| Allocation | Experiment | Failure-drill | Canonical, each repetition |
| --- | ---: | ---: | ---: |
| Preparation | 3600 s | 3600 s | 5400 s |
| Healthy, all three modes | 2700 s | — | 1800 s |
| Read-heavy / sustained | — | — | 600 s / 600 s |
| Each fault except maintenance/no-quorum | 600 s leader-loss | 600 s | 600 s |
| Maintenance / no-quorum | 900 s / 600 s | 900 s / 300 s | 900 s / 300 s |
| Validation and retention | 1800 s | 2400 s | 2400 s |
| Cleanup / control overhead | 900 s / 900 s | 900 s / 900 s | 900 s / 900 s |
| Sum of stage ceilings | 12000 s | 15000 s | 19800 s |
| Original topology lease | 14400 s | 16200 s | 19800 s |
| Operation grace after lease | 1800 s | 1800 s | 1800 s |
| Minimum priced lifetime | 19800 s | 21600 s | 27000 s |
| Outer command / kill grace | 15000 s / 60 s | 16500 s / 60 s | 20100 s / 60 s |
| Job ceiling | 270 min | 330 min | 360 min |
| Job time outside command/kill guard | 1140 s | 3240 s | 1440 s |

The native healthy controller's full canonical mode ceiling is
600 seconds for each of three sequential modes; frozen calls/windows remain
260 seconds per mode. Native experiment keeps its existing 900-second mode
ceiling. Selected fault ceilings include control/observation time and do not
change minimum fault holds, rate, payload size, document limits or engine timeouts.

All stage maxima fit the enclosing lease. Unspent time does not renew another
stage. The runtime clips every ordinary deadline to the original lease
minus cleanup; validation reserves 300 seconds for retention before starting
one bounded independent replay. That retention split applies only to the
new profiles; the current experiment's runtime path is unchanged. Cleanup gets
its existing separate chance after failure, without turning an overrun into PASS.

The provider lifetime calculation deliberately covers **preparation + lease +
operation grace**: allocation may occur late during preparation and an instance's
maximum runtime starts at creation. An under-covered quote fails even when the
hourly rate and requested reservation appear affordable. For a real admission,
the VM scheduling maximum, lease, guest deadline, shutdown/cleanup clocks,
workflow command guard and independently replayed evidence must all use the same
selected profile. The standalone review tool itself never changes live clocks.

GitHub-hosted jobs have a [six-hour execution limit](https://docs.github.com/en/actions/reference/limits).
Canonical leaves 24 minutes for job work outside the command and kill guard.
This is bounded first-run headroom, not a promise that all future provider delays
fit. Terminal failures and existing bounded observation retry thresholds must
still fail promptly; larger stage ceilings do not authorize mutation replay.

### Evidence informing the proposal

The three accepted offline repetitions took 2878–2906 controller seconds,
including 241–247 seconds preparation and 900–914 seconds validation/retention.
They used loopback SSH and modeled provider/disk facts. The earlier accepted
[native experiment](PHASE_6_NATIVE_EXPERIMENT_ACCEPTANCE.md) used 1432.606 seconds
preparation and 1278.858 seconds validation/retention for only four cells.
Native SSH/provider overhead therefore cannot be inferred from the offline total.
The selected 90-minute canonical preparation and 40-minute validation ceilings
allow additional overhead; actual first full-native results must inform revisions.
The review preserves the three original failed observations and their reruns.

## Price, sequence and ledger checks

Input fields are exactly:

| Field | Meaning |
| --- | --- |
| `configuration`, `artifacts`, `guestAccess` | Same configuration/artifact-proof/guest-access shapes as the existing Runner plan; this tool validates shape/binding, not live authenticity |
| `baseline` | `null` or `[generation, nativeLedger]`, read-only supplied observation |
| `sequence`, `member`, `order` | Original sequence identity, one exact member and one of the existing two fixed orders |
| `prices` | Existing Runner quote schema, indexed by **every remaining member**, including the selected member |
| `maximumCostsMicrousd` | Explicit per-member reservation ceilings with exactly the same keys as `prices` |

`canonical-1/2/3` bind repetitions and configured control hosts 1/2/3. Automatic
leadership remains observed, never forced to a proposed control host. Starting
from an empty ledger is valid for experiment-first/experiment or
canonical-first/canonical-1. A later member requires the original successful
prefix; a duplicate attempt, pending attempt, changed source/bundle/configuration,
changed order or failed canonical sequence is rejected by the existing native
ledger implementation. Only an in-memory reservation is simulated and discarded;
no simulated PASS result or ledger is emitted.

The price calculator is shared with the unchanged experiment entry. Each quote
must cover its member's reviewed lifetime, 3 VMs and 450 GiB of disks, retention,
requests, network, Actions and failure overhang. Rates/costs use bounded integers
and whole-microUSD ceiling arithmetic. Each estimate must fit its explicit maximum.
Previous failed-attempt reservations remain charged. The previous total plus
**all remaining maxima**, not only the next estimate, must fit USD 200. No reset,
refund, cloud price discovery or price approval occurs here.

The entire input observation and computed output are hashed together. Validation
recomputes timing, coverage, sequence rules and totals, rejects changed fields,
and expires at the earliest quote expiry or 15 minutes. Future members will still
need fresh quotes/admission after earlier members run; this review is not a
five-run authorization or an assertion of current free budget.

```bash
python3 -m scripts.v51.native_preset_review prepare \
  --inputs target/native-preset-inputs.json \
  --output target/native-preset-review
python3 -m scripts.v51.native_preset_review validate \
  target/native-preset-review/review.json
```

Inputs should be assembled from the selected source's verified Runner artifacts and
fresh read-only observations. The
test fixtures contain synthetic prices and cannot be used to approve spending.
`REVIEW.md` exposes selection, lifetime coverage, per-member estimates/reservations
and cumulative headroom; `review.json` retains every supplied input.

## Native execution binding

- Resource preparation derives the VM maximum lifetime and original preparation
  deadline from the admitted request. An extended caller timeout cannot renew it.
- Native volume request v2 carries the complete original request and its digest.
  The trusted receiver checks source/package/workload/access binding. Package and
  service sessions inherit that original request and monotonic clock.
- Failure-drill reuses all twelve owned fault algorithms. Canonical reuses the
  five rich tapes and twelve faults, one immutable source backup and seventeen
  fresh groups. V4.4/V5.0 control placement rotates through nodes 1/2/3; automatic
  leadership remains observed. Every original cell executes at most once.
- Native fault control uses the existing 180-second activation/rejoin/isolation
  ceilings and 300-second progress ceiling. Network hold remains at least 15
  seconds; bounded controller acknowledgement/draining may take up to 120 seconds,
  and the guest emergency release is 180 seconds. Emergency release still fails
  validation. The 1500-ms slow force, cut points, document sizes, workload arrivals,
  runtime resource limits and measured windows are unchanged. Offline qualification
  retains its original 17/60-second controls.
- Complete-preset replay runs in a separate read-only process with an explicit
  native authority selection. It checks exact request/repetition/configuration,
  complete cells, original physical/history/backup evidence, negatives and combined
  trace/storage limits. The child is killed and reaped at the original validation
  deadline minus a 300-second retention reserve; it is not retried.
- Runtime identity reads and IAP connections cover only the admitted cells.
  Retention read-back, exact-ID cleanup, conservative charged completion and
  lease release use the existing owner policy. A drill cannot claim healthy
  backup validation; canonical requires all rich backup checks. A single PASS
  still reports `fullRemoteQualification=false`.

## Operator sequence after merge and protected CI

The existing **V5.1 Preflight and Experiment Runner** adds two choices:
`runner_member` (`experiment`, `failure-drill`, `canonical-1`, `canonical-2`,
`canonical-3`) and `runner_order` (`experiment-first`, `canonical-first`).
Diagnostic-only remains the default. No new IAM role, identity or cleanup workflow
is introduced; recent successful manual cleanup remains sufficient.

1. Confirm corrected-source protected CI, fresh read-only observations, and no
   active/pending attempt. Review current quotes covering the lifetimes above
   and the remaining sequence against the USD 200 cumulative ceiling.
2. Start a **new sequence** on the final source/package. Select the first member
   of its fixed order, `runner_experiment=prepare`, and the usual quote JSON
   (`prices`, `maximumCostMicrousd`, `sequence`). Preparation allocates nothing.
3. Inspect the Action summary and retained plan: exact member/order/repetition,
   control node, cell set, stage limits, price estimate and charged reservation.
4. Use a **new dispatch**, `runner_experiment=run`, the same member/order,
   `runner_prepared_run` and the exact plan SHA-256 in
   `runner_experiment_confirmation`. Changed selections fail before allocation.
5. Inspect execution, independent replay, retained evidence, cleanup and ledger
   completion before preparing the next member with fresh prices/admission.
   Failed workload calls are never replayed by an Action rerun.

The first historical native experiment remains a milestone, not a member of the
new source-bound v3 set. Collect experiment + failure-drill + canonical 1/2/3 on
one final source, then independently review/register that complete set. Protected
CI and offline fixtures cannot substitute for those paid results or close Phase 6.

## Validation boundary

The admission CI lane includes `test_native_presets`: both ledger orders, immutable
budgets and old-request compatibility, exact guest sessions, rotated control
placement, changed-selection rejection, trusted receiver imports, every member's
thirteen-resource synthetic preparation and fresh-process expired cleanup.
The native owner controller is also exercised with all fifteen canonical stages
and an injected original-cell failure through synthetic HTTP/IAP and a deterministic
probe. These tests validate wiring, retention and cleanup, not real engine history
or paid-cloud performance. Existing real owned workload gates remain required.
