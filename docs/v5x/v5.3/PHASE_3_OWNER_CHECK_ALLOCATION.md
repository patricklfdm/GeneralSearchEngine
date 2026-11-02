# Phase 3 — measured owner-check allocation

The single diagnostic ACCEPT_RENAMED/halt capture on `14c6fe4d` failed. Its
captured guard was `DEADLINE`, with `firstEnd=NONE` and elapsed
180,001,470,549 ns against the original 180,000,000,000 ns limit. The service
start bracket independently places failure between 180.015680188 and
180.016123135 seconds after start. It occurred while obtaining a generation
copy for maintenance, not after a completed final client response.

This identifies the rejecting condition in this execution. It does not prove
that the earlier combined-guard failures had the same condition or that a
particular allocation caused the deadline. The failed original remains FAIL;
the diagnostic reader for a **completed** post-publication history correctly
rejects this incomplete history. No extra close, ACK or successful call is added.

## Profile and correction

One 160-second JFR recording was attached to the existing second child after
checking its command line and exact original path. The recording may affect
timing and does not cover early startup. It contains 30,157 allocation samples
with about 63.2 GB of sampled allocation weight. About 33.7 GB has
`MembershipBasisSources.inspect` as its first project frame. These are estimated
cumulative allocations, not retained heap or disk consumption; inclusive stack
totals overlap and must not be added together. Execution sampling omits much
virtual-thread work and cannot establish wall-time percentages.

That checker previously allocated 64 KiB on every invocation, even for empty or
tiny records. It now allocates `max(1, min(65536, expected size))` bytes. The
positive empty-file buffer still probes for EOF or growth. Every invocation
continues to read and hash the complete file and enforce the original path,
regular-file, link, length and inode checks. There is no cached content,
skipped owner guard, new retry, changed authority or extended deadline.

## Validation

All 27 targeted source/current-generation/export tests passed: 26 completed in
the sandbox; the one real TCP test was rejected by the sandbox's socket policy
and then passed outside it. The original sandbox log is retained. The new
integrity regression covers empty, one-byte, small, chunk-boundary and
multi-chunk files, repeated reads, truncation, append and last-byte corruption.
Existing linked/replaced-file and original-owner checks remain exercised.

A separate per-thread allocation probe ran one before/after JVM pair using the
same six file sizes, 200 warmups and 500 measured inspections per size. Allocation
fell 63–72% for the four sizes below 64 KiB; the two larger sizes were unchanged.
The targeted tests were also active, so those wall times are not a throughput
comparison. This verifies the allocation reduction, not native latency closure.

The [receipt](phase3-evidence/owner-check-allocation.json) retains exact source,
original inventory, profile, logs and probe hashes. Full native qualification
remains OPEN. The [single post-change native execution](PHASE_3_NODE_LATE_PREPARE.md)
completed under unchanged limits and exposed an unused-grant reply classification
gap in independent replay. Its separate receipt retains that failed replay and
the correction. Final-source cohorts remain separate hosted acceptance work.

Rollback restores the fixed buffer allocation. Original failures and all
validation requirements remain retained.
