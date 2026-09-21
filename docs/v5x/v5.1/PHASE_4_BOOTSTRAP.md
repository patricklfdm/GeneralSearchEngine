# Phase 4A: public automatic bootstrap and cleanup

**Status:** accepted through PR #192 at
`fce35d955e0b6b973014959e23fc38eb95dd2745` (CI `35547603482`).
Batch A retained the runtime factory guard; [Batch B](PHASE_4_PUBLIC_RUNTIME.md)
subsequently enables it. Public method descriptors and configured 1.1 behavior stay unchanged.

## Complete request binding

The original 1.2 PLAN binds replication bounds and policy but omits materialization
settings and stable parent identity. It cannot by itself meet the accepted complete
request revalidation requirement. This batch adds two independent record kinds;
the original format catalog, fixtures and checksums remain byte-for-byte unchanged.
The additive schema is [bootstrap-catalog.json](../../../general-search-engine-replication/src/test/resources/replication/v51/bootstrap-catalog.json).

| Kind | Purpose and binding |
| --- | --- |
| 28 BOOTSTRAP_BINDING | Canonical JSON with one base64 `descriptor` containing canonical JSON. Exact fields: operation, source, application, replicas, sourceInventory. Local descriptors reuse the full storage format/codec/budget and parent filesystem identity representation. |
| 29 BOOTSTRAP_CLEANUP | Nested PLAN, BOOTSTRAP_BINDING and kind-22 CLEANUP. Retains exact original deletion authority while coordinator files are removed. |

Both kinds use GSER 1.2 framing and a 65,536-byte total record limit. They add no
wire messages. `bootstrap-binding.gsr` is the ninth initial authority file and a
coordinator file. Its exact size/hash is in each PLAN target inventory; preparations,
receipt and seals transitively bind it. Existing eight-file internal fixtures remain
readable; new public bootstrap always emits the complete nine-file projection.

Descriptor `application` and each replica's `materialization`/`replicationBounds`
use the existing deterministic configuration projection, with no configured leader
authority. Source inventory rows contain path, kind, size and sha256; GENESIS's
sourceDigest is the SHA-256 of the canonical inventory. Parent bindings include
real path, file-store name/type and parent file key. Apply/resume reject altered
configuration, summaries, source bytes, aliases and pre-existing materializations.

All nested PLAN/RECEIPT/SEAL/CLEANUP metadata limits remain enforced. A source that
cannot fit these bounds fails during read-only projection, before creating output;
maxSourceBytes is an upper bound, not a promise that every backup of that size fits.

## Ordering and interruption

1. Pure plan captures and validates all callbacks/configuration and absent/disjoint
   target paths; verified source reads preserve the source.
2. Apply recomputes the full projection before creating the owned coordinator.
3. Force PLAN, binding and PREPARING. Exclusively own each target and force all
   initial files and preparations; then force PREPARED.
4. Revalidate the request/source before forcing COMMITTING. Publish the receipt
   with atomic rename and directory force, then force COMMITTED.
5. Publish each local seal. The caller receives success only after all three seals.

DECISION rows are sequence 1–4 in the above order; the first previousDigest is
64 zeroes, later rows bind the preceding frame digest. Resume may complete only
an exact deterministic partial row after complete request verification. Codec-free
result reads and cleanup reject incomplete or ambiguous decision tails.

Once COMMITTING is durable, resume validates the retained configuration and
decodes/re-encodes the retained application with current callbacks; source backup
contents need not remain available. It never changes the decision. Result reading
holds coordinator ownership and validates the complete receipt and COMMITTED row.
Node admission needs only its own seal and local binding, not a live coordinator.

## Cleanup

Cleanup requires an intact PREPARING or PREPARED journal and no decision receipt.
All existing targets must be exclusively ownable, with only exact planned file
prefixes. Unknown members, changed contents, copied paths, missing authority or a
live owner reject. No source or materialization path is a deletion target.

Kind 22 uses virtual roots `operation` and `target-0` through `target-2`, resolved
only through the nested original plan. A root directory has size zero and SHA-256
of empty bytes; file rows retain exact size/hash. `operationDigest` and `planDigest`
both identify the original PLAN, and decisionTail is the exact pre-commit row digest.
The public cleanup summary's planDigest identifies the complete kind-29 intent.

The forced cleanup intent blocks bootstrap continuation. Targets are removed before
coordinator authority; locks remain held through deletion. Interrupted cleanup can
resume only a prefix of its exact deletion order, with the intent remaining lockable
after operation.lock is unlinked. Missing/corrupt retained intent fails closed;
an empty directory left after the final intent unlink is not guessed as safe to delete.

## Qualification

`scripts/verify-v51-phase4-bootstrap.sh --skip-build` retains:

- Current JAR/source hashes and executed Java regression report.
- External public-consumer compilation and execution; fault worker code injects
  interruptions only and delegates all authority effects to that consumer.
- Five bootstrap boundaries with both Runtime.halt and controller SIGKILL,
  plus interrupted cleanup with both exit mechanisms.
- Exact archived pre-reopen bytes and an independent decision/preparation/seal oracle.
- Three source formats produced by the hash-pinned published V4.4 JAR; source
  inventory, sequence, active index count and canonical document order comparisons.
- Corrupted decision/binding/seal/genesis negatives and always-retained failure logs.

The full reactor and foundation gate preserve configured-mode compatibility and the
public factory guard.

## Local validation

Base `263c488fa3d1b0f78ff8a4a4454d7b3b7ff0bfab` plus this batch, 2026-09-20:

- Full reactor package passed: core 549 tests (four existing skips), replication
  270 tests and processor five tests. The final review added four bootstrap
  negatives/schema checks; all ten bootstrap tests passed after that review,
  alongside the automatic-record/store regression checks.
- Final public-bootstrap gate passed at
  `target/v51-bootstrap/run.64UoR3/evidence/receipt.json`: 16 cases, ten executed
  Java tests and five rejected independent-oracle negatives. The final replication
  JAR SHA-256 is `ce4f49b7f5514350e8addf75f3d502bc2a72be7025b8e43b82f1668e30e1c854`.
- Final foundation gate passed at
  `target/v51-foundation/run.Ny0iv7/evidence/receipt.json`, including 47 Python
  tests, published binary compatibility and the guarded runtime factory.
- Original 25 storage fixtures and 19 wire fixtures, shell/Python syntax,
  documentation links and whitespace checks passed. Earlier local runs and the
  corrected test-fixture JSON parser failure remain retained; none is used as a
  substitute for the final passing receipts.

These local results were followed by protected acceptance of Batch A, including
kinds 28/29, through PR #192 at `fce35d955e0b6b973014959e23fc38eb95dd2745`
(exact-master CI `35547603482`). See the [Phase 4 checklist](PHASE_4_CHECKLIST.md).
