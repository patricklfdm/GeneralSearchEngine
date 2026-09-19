# V5.0 Phase 6 checklist

- **Status:** Complete — registration in PR #179 and local telemetry correction in PR #180 accepted; exact-master CI `35421934224` passed.
- **Measured source:** `340df06148bc7d5a25a29a55c3ee928c9472dd09`.
- **Candidate baseline:** `v5.0.0-replicated-cloud`.

## Entry and execution

- [x] Public runtime and Phases 1–5 accepted before cloud measurement.
- [x] Exact-source full CI `35384694759` passed all six jobs and executed the local/remote workload gates.
- [x] Every paid member has exact source, bundle, request, plan, fresh preflight and explicit paid approval.
- [x] Sequence `893a44dee3a84a6eb2ac5d263a75f8db` follows canonical 1/2/3, experiment, failure-drill.
- [x] All five members have three concurrent private voters with separate VM/PID/disk identities.
- [x] Published V4.4 control and candidate artifacts match across all five members.
- [x] All three canonical repetitions pass 11 cells; experiment and failure-drill each pass eight.
- [x] Correctness, proof/success boundaries, recovery, replacement, fencing and bounded rejection validate independently.
- [x] Every owned resource is absent after cleanup; all leases were released.
- [x] Raw evidence retained in Actions/GCS, completion hashes match the sequence ledger, GCS manifests remain retrievable.

## Review and accounting

- [x] Existing independent five-topology validator returns `gcp-cloud-workload-set / PASS`.
- [x] Per-window operation counts, document counts, p50/p95/p99 and scheduler delays preserved in machine-readable review.
- [x] Uninstrumented healthy quantiles recomputed from raw samples with an explicit aggregation rule.
- [x] Instrumentation ratios, sustained offered/completed rates, force timings, resource peaks and recovery action durations reviewed.
- [x] Fixed offered rates and sampled resource peaks are not presented as maximum capacity or an SLA.
- [x] The user-authorized IAP rollback is disclosed with failed-run identity and retained audit hashes.
- [x] Final live reservations USD 84.80 and gross allocations USD 89.28 both remain below USD 100.
- [x] Failed evidence is preserved; the administrative rollback is not described as a billing refund.

## Accepted registration

- [x] [Canonical review](PHASE_6_CANONICAL_REVIEW.md), [baseline](PHASE_6_BASELINE.md) and [machine-readable report](phase6-cloud-review.json) prepared.
- [x] Append-only registrar requires all five raw bundles and regenerates the reviewed metrics before writing.
- [x] [Registry](cloud-benchmark-baselines.json) contains exactly one candidate entry bound to measured source and review digest.
- [x] Registration counterexamples and tracked-registry integrity run in existing CI Python discovery.
- [x] Separate protected 6D review/registration PR #179 merged at `8f31d8589528e872db30de68df689cd458b107a9`, including the disclosed administrative exception.
- [x] Exact-master CI `35421934224` passed all six jobs on `3e5da79c0fae47d4d1e8e50022c928fb3d0b1d60`, after PR #180 corrected the local telemetry window race.

Master CI `35420066938` failed the local 6A telemetry window check; its
[correction](PHASE_6_LOCAL_PERFORMANCE.md#window-attribution-correction--2026-09-19-utc)
was accepted through PR #180 and [exact-master CI](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35421934224).
This closes Phase 6 and permits [Phase 7](PHASE_7_CHECKLIST.md). The measured source
and retained cloud baseline identities remain unchanged.
