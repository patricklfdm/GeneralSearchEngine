# GeneralSearchEngine V4.4 Phase 6 evidence baseline

- **Branch:** `docs/v4.4-phase6-canonical-review`
- **Base and canonical source:** `6301d855a92a3b2de8d9c338232a520fb9dd2b36`
- **Version:** `4.4.0-SNAPSHOT`
- **Production behavior:** unchanged
- **Status:** Canonical review accepted; registration candidate

## Entry and correction boundary

Phase 5 merged through protected PR #138 as `e47e604`; exact-master CI
`34649742450` and the checksummed two-workspace canonical build passed. The Phase 5
acceptance record merged through protected PR #139 as `59208f6`.

Run `34811157471` at that source is rejected as evidence. Authentication succeeded,
but dry-run received the historical shared image
`ubuntu-2404-noble-amd64-v20260826` while the V4.4 plan requires
`ubuntu-2404-noble-amd64-v20260906`; it exited with configuration code 2 before
creating a VM or disk. No member from that run is reused.

The correction binds the V4.4 workflow directly to its frozen image, prevents
inheritance from a mutable cross-version variable, and makes project, zone and image
validation failures explicit. It merged through protected PR #140 as
`6301d855a92a3b2de8d9c338232a520fb9dd2b36`; exact-master CI run `34812469059`
passed.

## Accepted cloud evidence

| Evidence | Reviewed value |
|---|---|
| Experiment | `34813346549 / attempt 1 / one member / actions` |
| Failure drill | `34818721022 / attempt 1 / one member / actions` |
| Canonical | `34824651199 / attempt 1 / three serial members / gcs` |
| Exact source | `6301d855a92a3b2de8d9c338232a520fb9dd2b36` |
| Machine / zone | `c3d-standard-30 / us-west4-a` |
| Workload | `100000 documents / 10000 mutations / 4 indexes` |
| Measurement | `3600 seconds per member` |
| Data / target disks | two distinct `pd-balanced` 200-GiB disks |
| Suite / preset | `v4.4-final-durable-suite-v1 / v4.4-final-durable-v1` |
| Median write / reopen ratios | `1.022115 / 1.018469` |
| Maximum write / reopen ratios | `1.025553 / 1.027857` |
| Canonical set SHA-256 | `f1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465` |
| Eventual baseline | `v4.4.0-final-durable-cloud` |

The experiment, failure-drill and canonical member bundles and aggregate sets passed
independent validation. All accepted members report canonical validity, unchanged
canonical bytes, successful independent backup inspection, published-4.3 semantic
agreement, replacement-host continuation, all ten families, and complete cleanup.

The canonical members are comparable and `canonicalEligible=true`. Evidence digests
and backup identities are distinct. Both write and reopen ratios satisfy the
per-member `1.35` and set-median `1.20` bounds. Detailed identities are recorded in
[`PHASE_6_CANONICAL_REVIEW.md`](PHASE_6_CANONICAL_REVIEW.md).

## Registration boundary

The canonical review merged through protected PR #141 as
`1bb85f12722f9bfa66ea7b2792513886fcc77b86`; exact-master CI run `34888837170`
passed. This separate registration candidate appends exactly one
`v4.4.0-final-durable-cloud` entry bound to the canonical source, suite, preset,
three-member count, both median ratios and the set digest above.

The registrar rejects duplicate, renamed, non-canonical, threshold-violating or
malformed input. The tracked registry is validated in CI and raw evidence remains
outside Git. Phase 6 is not complete until this registration PR merges and its
exact-master CI succeeds.
