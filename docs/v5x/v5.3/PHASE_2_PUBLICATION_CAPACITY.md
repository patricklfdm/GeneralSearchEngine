# Complete publication metadata admission

Status: locally qualified private storage admission. Frozen byte and logical limits
remain unchanged. This storage admission work does not enable a public runtime.

## Reproduced failure

A preconstructed, independently encoded replacement-history prefix was accepted
by the native capsule verifier. On the following SEALED operation, three real
storage owners forced ACCEPT, PROOF and certificate, and applied INTENT. Publishing
its complete capsule then failed at `complete packet envelope capacity`. The
preceding stable RESERVE had also completed in a separate retained owner probe.
The original failing packets, source maps and owner logs are retained in
`target/v53-capsule-boundary/`.

The prefix is conditional test data, including its historical owned observations.
Only subsequent grants, selection, maintenance, votes and application use actual
local owners. This is not evidence of 233 public changes or learner admission.

## Admission correction

The existing pre-vote ancestry/coverage check is extended to reserve the complete
capsule envelope, referenced metadata and generation files. Immutable historical
edges and their original proofs remain retained. A mutable final stable RANGE may
be replaced as the existing checkpoint builder specifies. A new or pending change
also reserves its remaining INTENT/FINAL edges and following stable RANGE, original
first-slot proof, control completion, selected bases and six ancestry groups.

The estimate uses frozen complete-record bounds and maximal future counter/view
widths. Hash placeholders only measure serialized size; they are never persisted,
used as receipts, or decoded as protocol authority. Shared hashes can reduce the
real size. No frozen hash, resource ceiling, codec or deletion rule changes.

The current implementation already enforces the aggregate 48 KiB membership-item
limit. Reservation additionally charges the conservative 88 KiB sum of independent
record maxima, including ENTRY, ACCEPT, PROOF and payload. A size regression checks
maximum field widths against the unchanged aggregate bound. The logical lifetime
limit is a ceiling; byte limits may refuse a change earlier.

Capacity refusal must happen before a new ACCEPT write and before an application
reservation grows. Existing accepted originals remain readable and duplicate
semantics remain intact. A legacy already-forced vote cannot be relabelled as
NOT_SUBMITTED or erased. Valid pre-SEAL cancellation has stable publication sizing;
post-SEAL cancellation remains forbidden by existing context validation.

## Local qualification

The owner regression checks new RESERVE and legacy SEALED/INTENT refusal, exact
unchanged files, no write events, unchanged reservations and repeated refusal on
reopen. A stable BARRIER, actual typed DATA and valid pre-SEAL CANCEL still publish. The
DATA case increments the original application sequence and reopens its exact new
document after maintenance, without admitting another membership change. A separately
assembled native history packet checks the conservative future size. Both owner-refusal regressions fail on the original admission path and pass after
the correction. Eight new Java regressions and 46 related same-round, ancestry,
source, resource and application tests pass. The initial fixture directory error
is retained separately from those two valid original implementation failures.

Normal and optimized Python compare complete before/after owner inventories and
reject targeted mutations only after the original evidence passes. The reader
claims unchanged physical files and classified outcomes, not proof that the
conditional historical peers ran. The [evidence index](phase2-evidence/publication-capacity.json) binds both source
versions, original failures, JUnit reports, all 709 production classes and the two
JARs. Six unchanged-owner samples and six original-first mutations pass in normal
and optimized Python; all 36 focused Python tests pass in both modes. The context,
same-round and carried-publication regression evidence also passes independent
normal/optimized and portable replay. Maximum-image execution and Phase 2 closure remain
separate obligations.
