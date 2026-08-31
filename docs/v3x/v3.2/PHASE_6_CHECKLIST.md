# V3.2 Phase 6 hardening and release checklist

Status: complete. Snapshot hardening, final `3.2.0` validation, protected-master
acceptance, signed tag, publication, remote verification, and post-publication
evidence all resolve to release commit
`c96a15e41719cac8d7c1ee8f3c064338ef20ac61`.

## Entry and frozen boundary

- [x] Phase 5 merged to protected `master` as `fbbce30` through PR #55.
- [x] `feat/v3.2-phase6-release-hardening` starts from that exact accepted merge.
- [x] The snapshot-hardening identity remained `3.2.0-SNAPSHOT`; published
  compatibility identities remain immutable.
- [x] The ordered evidence states and blocker-fix boundary are frozen in
  [the hardening and release contract](HARDENING_AND_RELEASE.md).
- [x] Phase 6 introduces no search feature, public API, stored offset payload, HTML,
  analyzer composition, cloud family, broad refactor, or speculative optimization.
- [x] Snapshot-hardening PR #56 merged to protected `master` as
  `fdd6882c7e052e85883277bbcca5e96d2cbf8ceb`; the release branch starts from that
  exact accepted merge after required CI confirmation.

## Public API freeze

- [x] Review the complete Japicmp additions against `1.0.0`, `2.0.0`, `2.1.0`,
  pinned `3.0.0`, and pinned `3.1.0`.
- [x] Confirm the supported additions are exactly `OffsetAnalyzer`,
  `OffsetAnalyzedToken`, the highlighted request/result family, and the additive
  `SearchEngine.search(HighlightedSearchRequest)` default method.
- [x] Review constructors, generic descriptors, overload/null behavior, defaults,
  validation timing, immutability, and strict Javadocs.
- [x] Confirm `Analyzer` remains a SAM and `AnalyzedToken` retains its published shape.
- [x] Confirm the concrete engine override and Javadoc-hidden execution bridge are
  implementation consequences, not application SPIs.
- [x] Confirm no evidence, offset mapping, witness, fragment assembler, plan, posting,
  snapshot, or internal document-ID type becomes supported API.
- [x] Update [API compatibility](API_COMPATIBILITY.md) with the final accepted diff.

## Correctness and storage hardening

- [x] Audit offset equivalence, Unicode mapping, validation, result construction,
  TEXT/PHRASE/FUZZY/BOOL/BOOST evidence, and fragment coverage.
- [x] Preserve focused, randomized, differential, mutation, lifecycle, and concurrency
  suites from Phases 1–5.
- [x] Confirm highlighted hits retain canonical document, score bits, order, limit,
  filter, and failure semantics.
- [x] Confirm Search/Explain and ordinary V1/V2/V3 behavior remain unchanged.
- [x] Confirm no offset analysis occurs during indexing, ordinary search, Explain, or
  dynamic-index build.
- [x] Confirm no offset, evidence, highlight, or sidecar payload is retained in a text
  snapshot.
- [x] The final-candidate PR exposed shared-runner noise in the shortened stabilization
  E2E gate; the minimal regression-tested fix separates explicit `reduced-test`
  pipeline readiness from formal cross-window performance readiness without changing
  any production mode.

## Compatibility, consumers, and example

- [x] Frozen V1 source/reflection fixture remains present.
- [x] V3.2 descriptor/source fixture freezes the complete supported addition.
- [x] Fresh-isolated five-baseline Japicmp passes.
- [x] V1- and V2-style consumers remain source-unchanged.
- [x] V3-style consumer executes highlighted search and validates exact fragment/span
  output through supported APIs.
- [x] Travel example executes snapshot-bound highlighting through the built-in simple
  analyzer and owns presentation output.

## Phase 5 evidence inheritance

- [x] Audit the diff from the reviewed Phase 5 evidence source to Phase 6 entry.
- [x] Confirm no production, JMH workload, preset, JVM/toolchain, ordinary index shape,
  or evidence-identity change invalidates the local evidence.
- [x] Retain the Phase 5 stop boundary: no measured result justifies a production
  optimization or a universal latency claim.
- [x] Documentation, consumer, and release-metadata work does not require a paid cloud
  run.
- [x] Any affecting blocker fix must rerun the applicable local evidence before final
  release preparation.

## Documentation

- [x] Prepublication documentation kept published `3.1.0` stable and identified V3.2
  as unreleased; post-publication documentation now promotes verified `3.2.0`.
- [x] The 3.1-to-3.2 migration guide covers opt-in highlighting, exact offsets, legacy
  analyzer behavior, markup ownership, compatibility, and operational cost.
- [x] Architecture, offset, highlighting, API, validation, performance, hardening, and
  release documents agree with the implementation.
- [x] Documentation maps link every V3.2 Phase 6 document.
- [x] Both roadmaps and the changelog describe the actual candidate state without
  claiming publication.
- [x] Historical V3.0 and V3.1 release records remain unchanged.

## CI, artifacts, and reproducibility

- [x] `CI / Required` still depends on reactor, compatibility, release-artifact, and
  cloud-runner jobs.
- [x] Java 21 and Python 3.11 workflow assumptions remain explicit.
- [x] Strict release Javadocs pass for core and processor.
- [x] Only core and processor produce publishable artifacts.
- [x] Core has no processor service entry; processor has exactly the expected entry.
- [x] Main, sources, and Javadoc JARs exist for both artifacts.
- [x] Two clean builds produce byte-identical six-JAR output.
- [x] Central immutability preflight, protected approval, exact signed-tag validation,
  and clean remote verification remain mandatory.

## Snapshot validation — `3.2.0-SNAPSHOT`

- [x] `git diff --check` passes.
- [x] Version alignment passes for `3.2.0-SNAPSHOT`.
- [x] Core clean verify passes with 343 tests and no failures/errors/skips.
- [x] Reactor verification passes with 343 core and 5 processor tests; the example
  compiles successfully.
- [x] Frozen API fixture and fresh-isolated five-baseline Japicmp pass in the final
  working tree.
- [x] All independent consumers pass from a fresh repository.
- [x] Travel example passes and prints structured highlight fragments.
- [x] Unsigned strict release packaging and artifact inspection pass.
- [x] Reproducible-build verification passes; six snapshot hashes are recorded in the
  [release checklist](RELEASE_CHECKLIST.md).
- [x] JMH package, expanded forked smoke, and production-soak instrumentation pass.
- [x] Python 3.11 Cloud Benchmark 61-test unit suite, shell syntax, fake-gcloud,
  synthetic analysis, and lifecycle gates pass.
- [x] Protected snapshot PR/master acceptance is complete before final conversion.

## Final version conversion — `3.2.0`

- [x] Start only after the snapshot-hardening PR and exact protected-master CI pass.
- [x] Create an independent `release/v3.2.0` branch from accepted merge commit
  `fdd6882c7e052e85883277bbcca5e96d2cbf8ceb`.
- [x] Convert core, processor, reactor, example, and all current consumer coordinates
  atomically to `3.2.0`.
- [x] Preserve every published compatibility and cloud baseline identity.
- [x] Freeze `project.build.outputTimestamp` at `2026-08-30T00:00:00Z` and the
  changelog heading at `3.2.0 — 2026-08-30`.
- [x] Remove release-facing snapshot references while preserving historical evidence.
- [x] Repeat every snapshot validation family against `3.2.0`.
- [x] Record final artifact hashes and local pre-tag evidence in the
  [release checklist](RELEASE_CHECKLIST.md).
- [x] Release-preparation PR #57 merged as
  `c96a15e41719cac8d7c1ee8f3c064338ef20ac61`; exact-commit master
  [CI run 33351541204](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33351541204)
  passed.

## Signed tag and publication — complete

- [x] Create annotated signed `v3.2.0` on the exact approved protected-master commit.
- [x] Verify tag type, signature fingerprint, version/changelog alignment, commit
  identity, and `origin/master` reachability locally.
- [x] Push only the verified tag and let the protected Release workflow run.
- [x] Release validation and Central immutability preflight pass.
- [x] Approve `production-release` after validation.
- [x] Core and processor publish successfully with all required signed artifacts.
- [x] Clean remote verification and the published V3 consumer pass without a local
  reactor install.
- [x] GitHub Release is created from the exact tag and marked latest.

## Post-publication record — complete

- [x] Record exact tag/master commit, fingerprint, workflow/deployment, Central,
  remote verification, and GitHub Release evidence.
- [x] Update root and V3.x documentation to identify `3.2.0` as current stable.
- [x] Add published `3.2.0` as a mandatory future compatibility baseline without
  removing any earlier baseline.
- [x] Treat Maven Central coordinates and signed tag as immutable.
- [x] This post-publication evidence change is the final Phase 6 deliverable; its
  protected-master merge completes Phase 6 and V3.2.

Publication and all remote evidence are real and accepted. The documentation-only
protected merge of this record closes Phase 6 and the V3.2 development cycle.
