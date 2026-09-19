# V5.0 Phase 6 cloud evidence baseline

- **Status:** Five cloud members and independent set validation PASS; registration merged in PR #179, exact-master CI acceptance pending.
- **Measured source:** `340df06148bc7d5a25a29a55c3ee928c9472dd09` (`5.0.0-SNAPSHOT`).
- **Exact-source CI:** [35384694759](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35384694759), all six jobs passed.
- **Sequence:** `893a44dee3a84a6eb2ac5d263a75f8db`, canonical-first.
- **Candidate registry name:** `v5.0.0-replicated-cloud`.
- **Review date:** 2026-09-19 UTC.

## Evidence and result

| Member | Paid Actions run | Cells | Lifecycle seconds | Cleanup / retention |
| --- | --- | ---: | ---: | --- |
| Canonical 1 | [35394514093](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35394514093) | 11/11 | 3332 | PASS / VERIFIED |
| Canonical 2 | [35402218541](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35402218541) | 11/11 | 3354 | PASS / VERIFIED |
| Canonical 3 | [35407548985](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35407548985) | 11/11 | 3384 | PASS / VERIFIED |
| Experiment | [35414044623](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35414044623) | 8/8 | 1293 | PASS / VERIFIED |
| Failure-drill | [35415871650](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35415871650) | 8/8 | 1898 | PASS / VERIFIED |

Durations use the retained lifecycle's `finishedAt - startedAt`; Actions also
includes setup, approval and artifact upload. All 49 cell executions passed. Each
topology used three concurrent private `n2-standard-8` VMs in `us-west4-a`, fixed
three-voter membership, a configured leader and public runtime 1.1. Published V4.4
ran sequentially on the leader host as the independent single-node control.

The [canonical review](PHASE_6_CANONICAL_REVIEW.md) records latency, resource peaks,
fault/recovery results, exact artifacts, raw-evidence retrieval and the explicitly
authorized pre-candidate IAP failure exception. Its
[machine-readable review](phase6-cloud-review.json) preserves per-window and
per-member measurements. Raw streams and authority bytes remain outside Git.

## Interpretation

The tested workload maintained 10 requests/second in healthy windows and 20
requests/second in the sustained window. Each canonical repetition measured 10,800
calls with 8,340 durable mutation successes; successful reads are counted separately.
These are fixed offered rates, not maximum throughput. No pre-existing V5 throughput
or p99 target was defined. The evidence establishes correctness, recoverability and
bounded operation for this workload, not an SLA or automatic failover capability.

Three-repetition median healthy p50 is approximately 13.335 ms for ADD, 15.419 ms
for UPDATE and 2.501 ms for QUERY. Replicated writes include entry quorum, proof
quorum and publication; the single-node control has a different durability topology.
The review reports those costs without applying historical V4 ratio thresholds.

## Budget and exceptional retry

The final live ledger reserves USD **84.80**, including USD 22.40 for the five
successful members. A user-authorized administrative rollback removed USD 4.48 for
an IAP-disconnected attempt before candidate startup. Including that preserved
failed attempt, gross historical reservations are USD **89.28**, below the approved
USD 100 ceiling. These amounts are allocations, not actual billing or a refund.
The failed run, completion receipt and before/after rollback records remain
retrievable; the [review](PHASE_6_CANONICAL_REVIEW.md#failed-attempt-and-budget-exception)
identifies them explicitly.

## Registration boundary

The append-only [registry](cloud-benchmark-baselines.json) contains one candidate
entry generated from all five raw bundles by
[`cloud_baseline`](../../../scripts/v50/cloud_baseline.py). Registration reruns the
existing independent set validator, regenerates the review from bounded raw
evidence, compares it with the reviewed document and refuses duplicate entries.
CI's existing Python discovery runs the registration counterexamples and verifies
the tracked registry/review binding without cloud access.

The review digest is SHA-256 of the repository's canonical JSON encoding of the
entire review, including member completion/parts digests and all reported metrics:

```text
864552f0fa669738fd059d4739c5d78b2411c448274eb9af5265b3beade6c685
```

The separate 6D registration merged through
[PR #179](https://github.com/patricklfdm/GeneralSearchEngine/pull/179) at
`8f31d8589528e872db30de68df689cd458b107a9`; it is not relabelled as the measured
source. PR CI `35419078286` passed, but master CI `35420066938` found a local 6A
[telemetry window race](PHASE_6_LOCAL_PERFORMANCE.md#window-attribution-correction--2026-09-19-utc).
Successful exact-master CI remains pending. The [checklist](PHASE_6_CHECKLIST.md)
keeps that gate open before Phase 7.

## Local validation for the registration candidate

- Full raw member/set validation and deterministic review regeneration passed for all five bundles.
- All five retained GCS parts manifests match their locally validated SHA-256 identities.
- Python discovery: 279 tests passed, including seven registration tests with malformed, duplicate, changed-review and failed-raw-evidence cases.
- Phase 0 documentation contract, 522 local links/anchors in changed Markdown, code fences and whitespace passed.
- The changed-file classifier selects full CI because this PR adds Python registration tooling and JSON evidence records.

No Maven/Java runtime behavior changed in this candidate. Local validation focuses
on the offline evidence/registration path; the protected PR still runs the full
repository CI before merge.
