# GeneralSearchEngine V4.4 Phase 6 performance and evidence contract

- **Status:** Canonical review accepted; append-only registration candidate
- **Canonical source:** `6301d855a92a3b2de8d9c338232a520fb9dd2b36`
- **Production behavior:** unchanged

Phase 6 executes the final V4.x durable evidence plan accepted in Phases 0–5. It may
measure the existing implementation and record evidence, but it may not change public
API, live or backup formats, canonical authority, recovery, migration, reopen,
cleanup, or retrieval semantics.

## Frozen identities

- member schema: `gse-v44-final-durable-evidence-v1`;
- cloud-plan schema: `gse-v44-final-durable-cloud-plan-v1`;
- aggregate schema: `gse-v44-final-durable-evidence-set-v1`;
- suite: `v4.4-final-durable-suite-v1`;
- preset: `v4.4-final-durable-v1`;
- append-only baseline: `v4.4.0-final-durable-cloud`.

## Frozen topology and workload

Every member uses exact protected-master source, Standard `c3d-standard-30`, the
frozen Ubuntu image, one 200-GiB `pd-balanced` data disk, one 200-GiB target disk and
one auto-deleted 100-GiB boot disk. Peak allocation is 30 vCPU and 500 GiB of
provisioned disk. Members execute serially and have a 10,800-second maximum runtime.

The production workload contains 100,000 documents, 10,000 mutations and four
indexes. Each member measures for 3,600 seconds and exercises all ten frozen final-
durable families, including published-4.3/current paired controls, backup inspection,
source-host deletion, replacement-host continuation, recovery/fallback, migration,
checkpoint/WAL and lifecycle behavior.

Experiment and failure-drill profiles contain one member and retain an Actions
mirror. Canonical contains three independent serial members and retains members plus
the aggregate set in GCS. The complete-run cost ceiling is USD 40.

## Acceptance thresholds

Both current/published-4.3 write and reopen ratios are lower-is-better. Every
canonical member must be at most `1.35`; both canonical set medians must be at most
`1.20`. Member and set validators also require identical source and configuration,
distinct evidence and backup identities, all ten families, published control,
replacement-host proof and complete cleanup.

These are pinned-system regression bounds, not an SLA or a portable hardware claim.
OS page-cache treatment remains explicitly reported; no memory-mapping claim is
made.

## Accepted execution sequence

| Profile | Run / attempt | Members | Retention | Result |
|---|---|---:|---|---|
| Experiment | `34813346549 / 1` | 1 | Actions | PASS |
| Failure drill | `34818721022 / 1` | 1 | Actions | PASS |
| Canonical | `34824651199 / 1` | 3 serial | GCS | PASS |

All three runs use source `6301d855a92a3b2de8d9c338232a520fb9dd2b36`, whose
exact-master CI run `34812469059` passed. Downloaded member bundles and aggregate
sets passed independent checksum and semantic validation. Every accepted receipt
proves both VMs, both data disks and staging objects absent.

Canonical review merged through protected PR #141 as
`1bb85f12722f9bfa66ea7b2792513886fcc77b86`; exact-master CI run `34888837170`
passed. Registration remains a later reviewed append-only change and is implemented
as a fail-closed candidate separate from the accepted evidence review.
