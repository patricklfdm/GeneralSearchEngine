# V5.2 Phase 1: disabled read declarations and independent foundation

**Status:** implemented locally; protected full PR/master acceptance pending.
**Base:** Phase 0 PR #335, master `9e1aeb282135802ff8886c4585351ce42a7908b0`.
Master CI `38710485375`, attempt 1, passed **docs scope**: Change scope and Required
succeeded, 36 suite placeholders skipped. This accepts the documents, not runtime.
The operator then switched to `feat/v52-phase1-foundation` to authorize this batch.
Published V5.1 remains `5.1.0`; current development coordinates are `5.2.0-SNAPSHOT`.

## Delivered boundaries

- Six new public types and one additive default method match the
  [accepted API](API_FORMAT_AND_COMPATIBILITY.md). Exact declarations have separate
  V5.2 fixtures; historic V5.0/V5.1 inventories remain intact.
- Every explicit `read(options, callback)` fails with an already failed
  UnsupportedOperationException Future. Null arguments fail synchronously. GSE
  inherits that default; there is no runtime override, follower access, waiter or
  view implementation in this batch. Existing API methods keep their behavior.
- Three independent [112-byte token samples](fixtures/read-tokens-v1.json) cover
  zero, ordinary and maximum signed-long indices. Their [digest](fixtures/read-tokens-v1.sha256)
  is checked in Python and Java. Byte flips, length, rechecksummed version/reserved
  and negative-index mutations reject. GSER/GSRP/catalog and frozen release pins
  are unchanged. Tokens allocate fixed-size buffers and never access storage.
- The seventh external consumer compiles all seven view methods, exercises all
  policies/default failures and invalid options. A concrete third-party class is
  generated and compiled **only against hash-pinned published V5.1**, then loaded
  with candidate JARs without recompilation. All old abstract methods throw if
  called; the new default must reject without reaching them. A stopped GSE handle
  also retains an empty directory and untouched instrumented codec. Paging and
  mutation on ReplicaReadView fail separate compilation.

## Independent model and evidence

`python3 -m scripts.v52.foundation OUTPUT` records source HEAD, full checkout byte
inventory digest (including dirty/untracked source), actual JDK, candidate/control
JAR hashes, executed Java test reports, run and attempt. A dirty local result is
never presented as acceptance of the base commit. The normal wrapper is
`scripts/verify-v52-phase1-foundation.sh [--skip-build]`.

The finite model explores all enabled schedules from two declared roots to depth
12: positions 0–3, sequence 0–2, epochs 1–3, two identities, three requests and one
active callback. It observes one replica; the other two voters are symmetric quorum
witnesses. It assumes inherited consensus/proof validity, and does **not** re-prove
three-node election or storage durability. The two roots cover strong/minimum/stale
and foreign/zero/future minimums. It records every explored transition, phase and
bound. A two-million-state safety cap produces INCOMPLETE. Captured cancellation
retains the view until a separate release; close/fencing cannot reclaim that view.
Explicit fair-publication tests are separate from nondeterministic safety exploration.

The synthetic evidence schema checks source/build/run/attempt/process identity,
complete raw inventory and original-location mapping before read semantics. The
checker independently decodes tokens, distinguishes accepted/proven/published
positions, compares result projections with the selected synthetic cut, checks a
strong barrier at capture, minimum, cancellation/deadline, write ordering, view use
and permit/timer/pin accounting. All N01–N16 families must reject for their exact
category, after the original passes. ZIP packaging/relocation repeats the negatives.

These fixtures say `synthetic-foundation-only`. Their process identities and
result projections are **synthetic**, not observed JVMs or V4.4 oracle results.
Actual physical decoding, V4.4 result replay and three-process histories remain
mandatory in later phases. The [schedule map](PHASE_1_SCHEDULE_MAP.md) lists those
remaining obligations; none is silently counted as completed runtime evidence.

## CI integration and version migration

| Review field | Choice |
| --- | --- |
| Owner / identity | V5.2 Phase 1; `v52-foundation` / `V5.2 read foundation` |
| Toolchain/resources | Existing ubuntu-latest / pinned Temurin 21; Python >=3.10 standard library; finite model roughly 1 million states, reserve 2 GiB RAM; no mounts/cloud/listening servers |
| Inputs | Existing exact-source `v51-verification-build` artifact ID and original producing attempt; same schema/hash/path/JDK checks; no cache substitution |
| Test prerequisites | At 5.2 coordinates also require executed V52ReadTokenTest, V52PublicApiInventoryTest and legacy V51PublicApiInventoryTest; missing/skipped/failed reports reject |
| Output | `v52-foundation-${sha}` plus `v52-foundation-build-inputs-${sha}`, failure uploads, 14 days; source/control/model/negative/compiler receipts |
| Dependencies | Change scope supplies policy; shared producer supplies tested JARs/reports; Required aggregates the suite result |
| Policy | Full and integration require success; docs skips. Unknown V5.2 paths select full. No new integration allowlist |
| Initial ceiling | 15-minute job ceiling, expected foundation work under 3 minutes plus setup/download; local measurements are not hosted timing evidence |
| Failure | Keep FAIL receipt and command logs; no measurement/test/integrity retry or silent fallback |
| State boundary | One independent foundation execution; no split lease/history, no changes to existing continuous rich/canonical suites |

The registry now has 37 suites, 39 static job IDs and 47 expanded full jobs;
integration runs 44 and docs runs 2. Twelve ordinary suites share restore/retain
composites. Existing suite names, fixed matrices, steps, accepted/producing attempt
semantics and release retention remain unchanged. New tests are explicitly
executed by the V5.2 wrapper, outside the V5.1 Python partition.

`scripts.build_coordinates` owns the reviewed current build coordinates. Inherited
regression gates may test the current 5.2 pair only with an exact current-POM source
binding. `scripts.v51.artifact_version` keeps its original historical allowlist;
historical replay stays valid. The paid V5.1 entry rejects new coordinates before
collecting cloud admission inputs. Offline nine-JAR preparation tests current
artifacts but does not freeze or publish them; V5.1 frozen hashes, six-consumer
release contract, exact-source validation and 90-day evidence stay intact.

## Acceptance and rollback

Local reports are retained under `target/v52-foundation-work/`; final counts and
paths are recorded in its validation summary and PR body. Run the reactor, seven
external consumers, new foundation, version alignment, inherited foundation and
CI/cloud/release interface tests. Local Ubuntu OpenJDK 21 results do not replace
pinned Temurin hosted results. The operator's subsequent
[local batching instruction](LOCAL_DEVELOPMENT_SEQUENCE.md) permits Phase 2 after
local verification and defers protected PR/exact-master qualification until the
combined pre-cloud handoff. Local completion is not hosted acceptance.

Rollback the reviewed API/coordinate/consumer/suite/registry/Required/build-reader
change together. Revalidate the previous inventory and old coordinates; preserve
receipts and published artifacts. Do not delete Required, weaken checks or move tags.
