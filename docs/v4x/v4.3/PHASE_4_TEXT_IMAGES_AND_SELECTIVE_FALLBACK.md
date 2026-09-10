# GeneralSearchEngine V4.3 Phase 4 text images and selective fallback

- **Phase:** 4 — SimpleAnalyzer images and complete four-kind fallback
- **Status:** Candidate for protected acceptance
- **Entry:** Phase 3 protected-master commit
  `98527a2475d69673513addb15e5693bc197ddf2c`
- **Scope:** Exact `(1,2)` SimpleAnalyzer images and mixed generations

## Delivered boundary

Phase 4 completes the production image kinds frozen by Phase 2. Exact `(1,2)` stores
now publish and load equality, range, prefix and SimpleAnalyzer text components in one
checkpoint-bound generation. Canonical checkpoint documents, descriptors and WAL are
still mandatory and authoritative. Existing/default `(1,0)` and published `(1,1)`
bytes and behavior remain unchanged.

No new third-party index or analyzer SPI is introduced. The only supported text image
identity remains `gse-simple-v1`; any other analyzer remains incompatible with durable
mode under the inherited contract.

## Text logical image

The production writer emits the exact Phase 2 encoding:

- positive field lengths keyed by strictly increasing live document ID;
- exact document count and overflow-safe total field length;
- strict UTF-8 terms in canonical unsigned-byte order;
- document frequency equal to the non-empty posting count;
- strictly increasing live posting document IDs; and
- non-empty, strictly increasing positions bounded by the document field length.

Source text and highlight payload are not duplicated. The production loader validates
all framing, integrity, authority, descriptor and text relations before constructing
an immutable `TextIndexSnapshot`. Its postings, positions, document lengths and fuzzy
dictionary are materialized directly from validated bytes without analyzer execution.
The codec remains separate from the independent codec-free inspector and Python
physical-format parser.

## Complete reopen and fallback matrix

A valid four-component generation reports `COMPLETE_WARM` with four loaded and zero
rebuilt components. A rejected text component preserves all three structured siblings;
a rejected structured component preserves the text sibling and other valid structured
components. Both report `PARTIAL_FALLBACK`, rebuild only the rejected ordinal from
canonical documents, and make one bounded best-effort refresh. Catalog absence or
rejection reports `FULL_FALLBACK`, rebuilds all four and attempts a complete refresh.

Term, any/all term, phrase, fuzzy vocabulary, BM25 score bits, explanation score,
structured filters and deterministic order are differential-tested against a forced
in-memory rebuild. Post-checkpoint text mutations and dynamic text drop/create are
replayed over the complete checkpoint snapshot. Rebuild failure keeps
`INDEX_REBUILD_FAILURE` as the primary failure.

## Publication, migration and authority

Text bytes use the same forced staging, atomic rename, parent-force, catalog replace
and published-generation reinspection protocol as structured components. Refresh is
downstream of canonical checkpoint success; capacity or derived I/O failure cannot
fail a successful canonical checkpoint or reopen. Backup-triggered checkpoint cuts
remain canonical-only.

Direct older-to-`(1,2)` and meaningful `(1,2)` migration continue to publish cold
targets. The first ordinary target open rebuilds all configured components, including
text, then attempts one complete generation refresh. The second open can be fully
warm. Source and target canonical authority never depend on derived members.

## Local crash evidence

The production separate-JVM harness adds text-component pre-rename and post-parent-
force barriers and reuses the pre/post catalog publication barriers. Internal halt and
external kill bypass graceful close. A separate inspector JVM validates canonical and
derived classification before production open; a replacement JVM proves the complete
structured/text query oracle, canonical byte identity and a final valid generation.
Evidence remains checksummed under the frozen `gse-v43-fast-reopen-evidence-v1`
schema. No paid cloud execution belongs to this phase.

## Deferred work

Phase 5 owns exhaustive repeated checkpoint/reopen, stale-generation cleanup,
temporary amplification, corruption/fault/capacity/concurrency, backup/restore,
migration and cross-version lifecycle hardening. Phase 6 alone may execute paid cloud
evidence or mutate the append-only baseline registry.
