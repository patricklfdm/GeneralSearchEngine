# GeneralSearchEngine V4.4 Phase 6 canonical review

## Decision

Workflow run `34824651199`, attempt 1, produced an acceptable three-member V4.4
final-durable canonical set. All members ran serially from exact protected-master
source `6301d855a92a3b2de8d9c338232a520fb9dd2b36`, passed member and aggregate
validation, retained canonical evidence in GCS, and reported complete resource
cleanup. No member from a rejected run was reused.

The set is accepted as the candidate input for a separate append-only registration
named `v4.4.0-final-durable-cloud`. It proves the frozen V4.4 workload and paired
published-4.3 bounds on the pinned topology; it is not an SLA.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `34824651199 / 1` |
| Source commit | `6301d855a92a3b2de8d9c338232a520fb9dd2b36` |
| Exact-master CI | `34812469059 / success` |
| Request | `canonical / 3 serial / standard / c3d-standard-30 / 3600s / gcs` |
| Suite / preset | `v4.4-final-durable-suite-v1 / v4.4-final-durable-v1` |
| Zone / image | `us-west4-a / ubuntu-2404-noble-amd64-v20260906` |
| Data / target storage | distinct `pd-balanced` 200-GiB disks |
| Peak quota boundary | `30 vCPU / 400 GiB data + 100 GiB boot` |
| Published control | checksum-pinned GeneralSearchEngine `4.3.0` |
| Set status | `PASS / canonicalEligible=true / members=3` |
| Median write / reopen | `1.022115 / 1.018469` |
| Maximum write / reopen | `1.025553 / 1.027857` |
| Frozen thresholds | `both medians <= 1.20 / every member ratio <= 1.35` |
| Set SHA-256 | `f1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465` |
| Registry name | `v4.4.0-final-durable-cloud` (pending separate registration) |

The complete set is retained under:

```text
v4.4-final-durable/6301d855a92a3b2de8d9c338232a520fb9dd2b36/34824651199-1/canonical/
```

Downloaded member mirrors, checksum inventories, aggregate set and cleanup receipts
passed independent local validation. Raw evidence and remote logs are not committed.

## Independent members

| Slot | Evidence SHA-256 | Backup identity | Write ratio | Reopen ratio | Cleanup |
|---:|---|---|---:|---:|---|
| 1 | `85b04d71e76ffcd4ae2bfc9cc1883e9d2e2385af91d80f7f267a7d9e9ca7644e` | `gse-backup-v3-4b2576c2048e83f3a20b9febb524b5c6047a6a316b25cb750239491a38884376` | 1.025553 | 1.027857 | PASS |
| 2 | `84a07aa3acef428cd71852b3efa1a4a8c8167db7780d2ba81d2635228ef99b9f` | `gse-backup-v3-6895171fe5f83ff8ee2f6416a2d810205a5480b85dcc298003ce9a27cd200169` | 0.985501 | 1.002019 | PASS |
| 3 | `d6b44df06f499e1af96238795eb307e12eeed7245c04d0e507e496b322940d91` | `gse-backup-v3-e1e44ea0da85d521338de89f9e1130904d6a003d94a62a8434bee92a036a3b50` | 1.022115 | 1.018469 | PASS |

## Paired measurement review

| Metric | Slot 1 | Slot 2 | Slot 3 |
|---|---:|---:|---:|
| Published-4.3 write | 0.742 s | 0.755 s | 0.749 s |
| Current write | 0.761 s | 0.744 s | 0.766 s |
| Published-4.3 reopen median | 0.224 s | 0.231 s | 0.228 s |
| Current reopen median | 0.231 s | 0.232 s | 0.232 s |
| Write ratio | 1.025553 | 0.985501 | 1.022115 |
| Reopen ratio | 1.027857 | 1.002019 | 1.018469 |
| Measurement reads | 92.394 billion | 97.999 billion | 90.178 billion |

Every member measured exactly 3,600 seconds with 100,000 documents, 10,000
mutations and four indexes. Canonical bytes were `14,893,819`, source derived bytes
were `23,209,229`, replacement derived bytes were `23,209,250`, and source temporary
peak was `52,997,013` bytes for every member. The common oracle, continued-state and
published-control digests match across the set.

## Experiment and failure-drill controls

| Profile | Run | Set SHA-256 | Write ratio | Reopen ratio | Cleanup |
|---|---:|---|---:|---:|---|
| Experiment | `34813346549` | `f1692cf9745fdd39dfb16b4812a172d7fca77f9929a57c4836ac952c5a8e9e50` | 0.990807 | 1.035882 | PASS |
| Failure drill | `34818721022` | `a30de00f5561310c664de308013cbd23385bf3d113639cf29eda8fa415e56f4c` | 0.996326 | 1.019988 | PASS |

Both use the same exact source and passed member/set validation. The rejected dry-run
`34811157471` is configuration history only and contributes no evidence.

## Registration boundary

This canonical review must merge and pass exact-master CI before registration. The
later registration PR must validate this exact set, reject non-canonical or duplicate
input, and append one immutable entry without changing the reviewed evidence.
