# GeneralSearchEngine V4.4 Phase 6 checklist

- **Status:** Canonical review accepted; registration candidate
- **Scope:** paid exact-source evidence, independent review and append-only registration

## Entry and source

- [x] Phase 5 acceptance merged through protected PR #139 as `59208f6`.
- [x] Frozen-image correction merged through protected PR #140 as
  `6301d855a92a3b2de8d9c338232a520fb9dd2b36`.
- [x] Exact-master CI run `34812469059` passed for that source.
- [x] V4.4 remains a zero-production-change release candidate.
- [x] Rejected run `34811157471` stopped during dry-run before paid resources and is
  excluded from accepted evidence.

## Cloud safety and topology

- [x] The workflow is manual, exact-master, short-lived-OIDC and serial.
- [x] The V4.4 workflow binds its frozen Ubuntu image without inheriting another
  release lane's mutable image variable.
- [x] Experiment/failure-drill use one member and Actions retention.
- [x] Canonical uses three independent serial members and GCS retention.
- [x] Peak allocation is one 30-vCPU VM, two 200-GiB data disks and one auto-deleted
  100-GiB boot disk.
- [x] Every source VM is deleted before replacement-host continuation.
- [x] Every accepted receipt proves both VMs, both disks and staging objects absent.
- [x] GCS transport and evidence remain confined to `v4.4-final-durable/`.

## Accepted paid evidence

- [x] Experiment run `34813346549`, attempt 1, passes independently from exact source
  `6301d855a92a3b2de8d9c338232a520fb9dd2b36`.
- [x] Failure-drill run `34818721022`, attempt 1, passes independently from the same
  source.
- [x] Canonical run `34824651199`, attempt 1, contains three serial passing members.
- [x] Every member exercises all ten families and reports published-4.3 agreement,
  canonical validity, independent backup inspection and replacement-host proof.
- [x] Member evidence and backup identities are distinct.
- [x] Canonical write ratios `1.025553`, `0.985501`, `1.022115` satisfy `1.35`; median
  `1.022115` satisfies `1.20`.
- [x] Canonical reopen ratios `1.027857`, `1.002019`, `1.018469` satisfy `1.35`;
  median `1.018469` satisfies `1.20`.
- [x] Canonical set digest is
  `f1435bdf528138363986542ecafac563dbee0cf9dbed60f781ada27ff53c6465`.
- [x] Raw evidence remains untracked and canonical evidence remains in GCS.

## Review and registration

- [x] Curated evidence and independent-member identities are documented in
  [`PHASE_6_CANONICAL_REVIEW.md`](PHASE_6_CANONICAL_REVIEW.md).
- [x] Canonical review merged through protected PR #141 as `1bb85f1`; exact-master
  CI run `34888837170` passed.
- [x] A separate append-only registrar validates the accepted canonical set and
  rejects duplicate, renamed, non-canonical or malformed input.
- [x] `v4.4.0-final-durable-cloud` is present exactly once in the candidate registry.
- [ ] Registration PR merges and its exact-master CI passes.

Phase 7 must begin only from the accepted registration commit.
