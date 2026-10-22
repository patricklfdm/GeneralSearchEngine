# Phase 1 context, transfer and resource foundation

Status: **locally qualified foundation, Phase 1 still open**. New internal helpers
are not connected to a live runtime. The existing 1.1/1.2 paths and public API
fixtures are unchanged.

## Context boundaries

`MembershipContext` consumes an **already verified applied cut**, immutable ROOT
and CATALOG records, and separately verified application images. It checks full
permanent identities, view shape, operation number/retirement/detail consistency,
prepared receipts and sealed bindings. Certificate checks require the immutable
ENTRY, exact ACCEPT and PROOF bytes, both governing majorities, phased receipts,
durable storage identity and the exact owned applied parent. Control proposals
are checked against the applied operation phase before they can be admitted.

Wire context checks bind authenticated endpoints, root/view/ballot and exact
correlation. Neither sender nor recipient may use a learner for voting/reads;
source offers are size bounded and readiness requires the actual bound receipt.
These checks do not fetch or force records, establish a campaign, or produce ACKs.
The caller must prove the applied cut and ownership; a supplied `Owned` tuple is
not proof of remote force. Phase 2/3 must integrate those obligations.

The 32 MiB metadata inventory is separate from application materializations
(at most 64 MiB each). The context retains verified image identities, not duplicate
image arrays. A compacted cut does not require retaining the old genesis application
image; the current image and original genesis record remain checked. The seven
staging-image slots correspond to six frozen sources plus one learner; generation
application storage remains part of the inherited application storage accounting.

## Transfer and accounting

- `MembershipTransfer` binds one content-addressed transfer to the exact root,
  session, transfer ID, full source identity, original basis ID/digest and cut.
  Reserve the declared total before any sink write. Chunks are bounded, contiguous
  and hash checked. An exact immediately previous chunk can be acknowledged again
  without writing it twice. Completion needs all bytes, full hash and semantic
  validation. Sink/hash/semantic failure cannot become VERIFIED.
- A duplicate verified commit is idempotent. VERIFIED means received and validated,
  **not** installed or forced. Closing only releases the explicit reservation;
  the future storage owner must dispose/transfer ownership of its staging files
  before releasing the lease. No file deletion or selector change is implemented.
- `MembershipExchange` permits at most three identical exchange attempts under
  the original monotonic deadline; late completion is refused. It never retries
  a client mutation. These are hard library bounds, independent of soft cloud
  experiment budgets.
- `MembershipResources` accounts for both generations, six frozen sources, learner,
  journal/catalog/miscellaneous space, shared application/metadata staging, global
  queued bytes and waiters. Full metadata copies total 324 MiB within 384 MiB.
  Ordinary allocations preserve 36 MiB completion space. Failure is checked before
  counters change; leases release exactly once. Exhausted membership lifetime
  blocks a new change, not an ordinary stable operation reservation.

## Independent physical fixture replay

One fresh Java fixture worker writes actual 1.3 framed files for all seven size /
change profiles, nine certificates each, plus separate per-voter parent/phase
copies. It records each successful `FileChannel.force(true)` on those fixture
files: 514 owned phased records and 1,028 file-force calls. This is a single-process
byte fixture, not distributed consensus, crash durability, directory-force evidence,
or a public runtime execution.

The Python reader imports no Java production decoder. It bounds inventory/file
sizes before reading payloads, refuses links/unknown files/duplicate paths, decodes
original bytes and independently derives each resulting catalog from the original
control payload. It checks exact phased records, identity, both majorities, owned
parent copies and fixture force ordering. Explicit retirement must retain permanent
identities and the original transition descriptor.

An unmodified original must pass before any negative can count. Eighteen variants
cover missing/corrupt files, links, inventory bounds, missing profiles, relabelled
runtime claims, missing owned proof, force order, foreign storage, wrong parent,
forged catalog/entry/certificate, profile relabelling and lost descriptors. A
relocated copy must produce the same independent result.

## Repeat local checks

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53ResourceTransferTest,V53ContextTest,V53FormatTest,V53DeclarationsTest,V53PublicApiInventoryTest,V51VersionBoundaryTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_context_evidence \
  scripts.test_ci_v51_bundle scripts.test_build_coordinates
python3 -m scripts.v53.context_qualification target/v53-context/run-UNIQUE
```

The qualification refuses existing output, retains failures, records exact checkout
inventory, local JARs' identities and fixture class hashes. It does not claim a
clean-source protected build. Use a fresh output path. Current 5.3 build bundles
also require executed, unskipped `V53ContextTest` and `V53ResourceTransferTest`;
the earlier suites and all older-coordinate requirements remain required.

[Retained qualification receipt](phase1-evidence/context.json): 37 focused Java
checks, 205 V5.3 Python checks, 20 build-contract checks and five optimized-Python
checks passed. All seven physical profiles / 63 certificates, 18 negatives and
relocated replay passed on the corrected Java/Python source. The source binding
precedes this receipt and the final reporting edits, as recorded in the receipt.
Local logs and raw files: `target/v53-phase1-context/`. The initial worker attempt
failed because long file paths were used as restricted JSON object keys; the
manifest now carries a bounded array of explicit path/hash/size rows. The initial
bundle fixture also exposed the newly required suites and was updated. Those failed attempts remain retained. A later origin-identity test initially
used a syntactically forbidden zero ballot counter; correcting its test setup
then exercised the intended retired-voter rejection. Qualification was repeated
on the corrected source.

## Remaining Phase 1 obligations

Complete packed capsule/inventory validation and original frozen-basis selection
are still pending; mere presence of referenced hashes is insufficient. Their
future API must accept verified complete sources, with no resampling during one
campaign. Same-round/catalog/compacted-source composition, full S/N case coverage
and the final closure audit also remain open. This batch does not relabel separate
Phase 0 models or physical fixture files as those results.
