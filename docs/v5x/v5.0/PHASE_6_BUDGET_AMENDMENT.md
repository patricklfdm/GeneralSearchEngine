# V5.0 Phase 6 budget ceiling amendment

## Approval and scope

On 2026-09-17 the user explicitly approved raising the cumulative budget ceiling
from USD **40** to USD **100** to leave room for failed attempts. This is approval
for the budget change. Each paid run still requires its exact reviewed request,
cost allocation and manual workflow trigger after protected merge and exact-source CI.

The same append-only GCS budget ledger remains authoritative. All previous
reservations, request identities and failed sequences remain recorded. Cleanup
releases resource leases without refunding budget. The limit is a reservation
guard, not an actual billing report or a provider-enforced spending cap.

This amendment updates Foundation, 6A, runner and full-workload plans, Foundation
and Runner summaries, admission boundaries and the independent five-topology
validator. The VM/disk sizes, timing, measurement rates, fault matrix, cleanup,
retention and ownership requirements retain their reviewed values.

## Current allocation

The last read-only ledger review on source
`e11380647da96e99e42b211bbd9743f93a9788b0` found no active lease and cumulative
reservations of USD 22.08 (GCS generation `1789659640227446`). Exact-source CI
[35275378501](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35275378501)
and manual cleanup
[35277851755](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35277851755)
passed for that source; neither receipt admits the amended source.

| Allocation | USD |
| --- | ---: |
| Approved cumulative ceiling | 100.00 |
| Existing reservations retained | 22.08 |
| Remaining before new runs | 77.92 |
| Five proposed runs at 4.48 each | 22.40 |
| Cumulative reservations after those five | 44.48 |
| Remaining after those five | 55.52 |

The five runs remain experiment, failure-drill and canonical repetitions 1–3.
Additional failures may invalidate a sequence and require new attempts. Available
headroom is not automatic approval to retry, and future allocations must use the
then-current ledger balance.

## Reviewed cost basis

The 2026-09-17 price review reconfirmed the regional rates used in the previous
allocation. Its five-topology estimate is USD **22.213499**, rounded up to USD 22.40
of reservations. No free tier or discount is assumed.

| Item | Calculation | USD |
| --- | --- | ---: |
| Compute | 3 VMs × 5 × 1.5 h × 0.437496 | 9.843660 |
| Boot/data disks and cleanup overhang | 450 GiB × 5 × 1.8 h × 0.000150685 | 0.610274 |
| Evidence storage | 20 GiB × 37 days × 24 h × 0.000031507 | 0.559564 |
| Evidence transfer allowance | 2 copies × 20 GiB × 0.23 | 9.200000 |
| Operations/control allowance | Reserved | 2.000000 |

Sources: [N2 pricing](https://cloud.google.com/products/compute/pricing/general-purpose),
[disk pricing](https://cloud.google.com/compute/disks-image-pricing),
[Cloud Storage pricing](https://cloud.google.com/storage/pricing), and
[network pricing](https://cloud.google.com/vpc/network-pricing).
The transfer rate is a conservative destination allowance; it does not identify
the GitHub runner's location. Evidence assumptions are 4 GiB per topology, 30 review
days plus seven days of soft delete, VM collection and complete GCS read-back.
Review uses the existing GitHub artifacts within their 14-day retention; additional
full GCS downloads or extended retention require a new cost review. No bucket
deletion policy is changed. Operations alone allow 10,000 Class A and 20,000 Class B
requests (USD 0.058); the USD 2 allowance also covers control data and overhead.

## Plan binding and next admission

The digests below record the budget-only amendment. The subsequent
[remote recovery window amendment](PHASE_6_CLOUD_WORKLOAD_PLAN.md#remote-recovery-window-amendment-2026-09-17)
replaces the full-workload digest and records the next failed-attempt reservation.

- 6A plan SHA-256: `c4f14925ab54302249193da2284d0bdebaa538a7dbcd56a005a7437807158cc1`.
- Full-workload plan SHA-256: `64732d1b192351dbe91f81b05314555c7c734eb06a5d6c7b87f1d2208a3a83d5`.
- The runner binds the amended 6A digest; preset/request and bundle digests bind the
  amended runner and full-workload plans. Previous prepared bundles and paid
  confirmations cannot admit a new run.
- The independent set validator obtains its ceiling from the checksum-pinned
  workload plan, rather than a limit supplied by the evidence being validated.

After merge: verify exact-master CI, obtain a matching recent scheduled/manual
cleanup receipt, and prepare a fresh sequence. Review its workflow-service-account
preflight, current ledger, costs and exact request digest before the user manually
triggers the paid run.

## Local validation

- Python discovery: 245 tests passed, including exact-ceiling admission, rejection
  above USD 100, preserved historical reservations and independent set validation.
- `scripts/verify-v50-phase1-foundation.sh --skip-build`: passed, including plan
  binding, fake-cloud evidence and summary validation.
- `scripts/verify-v50-phase6-remote-workload.sh --skip-build`: passed, including
  20 Python tests, 14 local JVM workload cells and 15 provenance negative checks.

These checks used the existing built Java runtime. No paid cloud workflow was
triggered and the live ledger was not modified.
