# V3 Phase 8 hardening and release checklist

## Preparation and frozen boundary

- [x] Phase 7 is merged to `master` with its required gates passing.
- [x] Work starts from `feat/v3-phase8-hardening-release` at the merged Phase 7 state.
- [x] Phase 0–7 contracts, current CI/release workflows, scripts, consumers, travel
  example, JMH suite, and V2.1 release precedent are audited.
- [x] The Phase 8 boundary is frozen in
  [HARDENING_AND_RELEASE.md](HARDENING_AND_RELEASE.md).
- [x] The root Phase 8 Codex prompt remains an untracked implementation input.
- [x] No Phase 8 change introduces a V3.1/V4 feature or speculative public knob.

## Public API freeze

- [x] Review every supported V3 addition for naming, generics, null behavior,
  immutability, defaults, exceptions, thread safety, and strict Javadocs.
- [x] Review the full Japicmp additions against 1.0.0, 2.0.0, and 2.1.0.
- [x] Confirm no accidental implementation type is supported public API.
- [x] Confirm the exact unsupported boundaries of `SearchExecutionAccess`,
  `PhrasePositionAccess`, and `FuzzyVocabularyAccess` remain unchanged.
- [x] Confirm query nodes, plans, postings, vocabulary, positions, candidates, score
  state, snapshots, and internal IDs remain unexposed.
- [x] Document every accepted additive descriptor in `docs/v3/API_COMPATIBILITY.md`.

## Correctness hardening

- [x] Audit structured filters, TEXT, BOOL, BOOST, cross-field BM25, PHRASE, FUZZY,
  Explain, mutation, snapshot, lifecycle, bulk, and legacy-equivalence coverage.
- [x] Preserve all Phase 3–7 focused and deterministic randomized/differential tests.
- [x] Add only tests that close a named release-critical gap.
- [x] Keep any large bool, phrase, fuzzy, mutation, reader, or build/replay stress test
  bounded and suitable for CI.
- [x] For each discovered blocker, land a failing regression test and minimal fix in a
  narrow commit before rerunning full gates.
- [x] Confirm normal search and Explain retain identical match/score semantics.
- [x] Confirm V2-compatible requests retain documents, scores, order, missing-index,
  empty-analysis, limit, filter, and BM25 behavior.

## Compatibility and independent consumers

- [x] Frozen v1 source/reflection fixture passes.
- [x] Japicmp passes against published 1.0.0.
- [x] Japicmp passes against published 2.0.0.
- [x] Japicmp passes against published 2.1.0.
- [x] Normal and fresh-isolated artifact compatibility runs both pass.
- [x] v1-style consumer passes without using V3 internals.
- [x] v2-style consumer passes without source changes required by V3.
- [x] v3-style consumer covers text, filter, BOOL/BOOST, cross-field, phrase, fuzzy,
  and Explain through supported APIs.

## Performance and memory evidence

- [x] Freeze a named, bounded JMH matrix rather than a Cartesian product.
- [x] Compile all JMH sources with the project profile.
- [x] Record environment, JDK/JVM, forks, warmup, measurements, dataset, and command.
- [x] Measure V2-equivalent text, text plus filter, and direct V3 text.
- [x] Measure MUST, SHOULD-only, nested BOOL, BOOST, and cross-field cases.
- [x] Measure selective/common/repeated/gapped phrase cases.
- [x] Measure fuzzy exact/edit/transposition/no-match/high-expansion cases.
- [x] Measure 10k and 100k fuzzy vocabulary scaling.
- [x] Run one valid 1M fuzzy capacity row or record the exact resource limitation.
- [x] Compare normal search with matching and non-matching Explain.
- [x] Review positional single/bulk mutation costs and token-order-only updates.
- [x] Quantify representative term-occurrence, position, posting, length, and bitmap
  memory impact with a reproducible method and limitations.
- [x] Record the V2-equivalent regression review without universal speedup claims.
- [x] Record whether bounded vocabulary scan is accepted for 3.0.0.
- [x] Record whether raw primitive positions are accepted for 3.0.0.
- [x] Keep raw benchmark outputs untracked under `target/`.
- [x] Complete `docs/v3/PERFORMANCE_BASELINE.md` with summarized measured evidence.

## Documentation and example

- [x] Root README has a concise supported-public-API V3 newcomer flow.
- [x] Snapshot docs still identify 2.1.0 as the currently published stable release.
- [x] `docs/v3/MIGRATION_GUIDE.md` explains optional migration from 2.1.0.
- [x] Existing `search(Query)` and `searchTopK` support is stated clearly.
- [x] Ranked, positional, fuzzy, and Explain documentation matches implementation.
- [x] `docs/v3/API_COMPATIBILITY.md` is the future V3.x compatibility contract.
- [x] Travel demonstrates structured search, ranked text, cross-field BOOL/BOOST,
  phrase, fuzzy, filter, Explain, and dynamic-index lifecycle without internal APIs.
- [x] `docs/README.md` and `docs/v3/README.md` link all V3 final documents.
- [x] `DEVELOPMENT_ROADMAP.md` and `CHANGELOG.md` reflect actual—not anticipated—state.
- [x] `docs/v3/RELEASE_CHECKLIST.md` exists with pre-tag and post-publication sections.

## CI and release workflow

- [x] Reactor, travel, compatibility, consumers, packaging, artifact inspection, and
  reproducibility all feed `CI / Required` directly or through required jobs.
- [x] JMH sources compile in an appropriate gate without putting full benchmarks on
  every pull request.
- [x] Release tag validation still requires a signed tag reachable from `origin/master`.
- [x] Central immutability preflight remains mandatory.
- [x] `production-release` approval and all four existing secrets remain required.
- [x] Release packaging signs core and processor POM/main/sources/Javadoc artifacts.
- [x] Only core and processor are staged or deployed.
- [x] Core has no processor service entry; processor has exactly the expected entry.
- [x] Central publication remains automatic only after protected approval.
- [x] Post-publication resolution uses a fresh Maven repository.
- [x] Published POM/main/sources/Javadocs/signatures/checksums are remotely verified.
- [x] A clean V3 consumer compiles/runs without reactor installation.
- [x] GitHub Release is created from the exact verified signed tag.

## Snapshot validation — `3.0.0-SNAPSHOT`

- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes (246 core + 5 processor tests).
- [x] `scripts/run-travel-example.sh` passes.
- [x] `./mvnw clean -Papi-compat test` passes (3 frozen fixture tests).
- [x] Normal artifact compatibility passes.
- [x] Fresh-isolated artifact compatibility passes.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] Strict core and processor Javadocs pass through the release profile.
- [x] Unsigned release packaging passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] `./mvnw clean -Pjmh -DskipTests package` and the forked smoke pass.
- [x] API, correctness, performance, memory, docs, CI, and release audits are accepted
  before final version conversion.

## Final version conversion — `3.0.0`

- [x] Convert core, processor, reactor, example, and current-version consumer properties
  together; leave historical published baselines unchanged.
- [x] Freeze `project.build.outputTimestamp` consistently in both publishable POMs.
- [x] Convert the changelog to `3.0.0 — <actual release date>`.
- [x] Update release-facing coordinates and links without claiming publication success.
- [x] No release-facing `3.0.0-SNAPSHOT` occurrence remains.
- [x] Version alignment passes for `3.0.0`.
- [x] Rerun every snapshot correctness and compatibility gate against final version.
- [x] Final release-profile packaging and artifact inspection pass.
- [x] Reproducible build passes and final six-JAR SHA-256 hashes are recorded.
- [x] Working tree contains no generated output, credentials, signatures, prompt, or
  temporary evidence.
- [ ] Final release-preparation PR passes `CI / Required` and is approved.
- [ ] Approved final state is merged to protected `master`.
- [ ] Required `master` CI passes on the exact intended tag commit.

## Signed tag and protected publication

- [ ] Create annotated signed `v3.0.0` on the exact approved `master` commit.
- [ ] Verify the tag locally against the expected OpenPGP fingerprint.
- [ ] Push only the verified tag.
- [ ] Release workflow validates the exact tag and commit.
- [ ] Protected workflow builds and verifies all eight detached signatures.
- [ ] Maven Central immutability preflight passes.
- [ ] Owner approves the `production-release` environment deployment.
- [ ] Both 3.0.0 artifacts publish successfully to Maven Central.
- [ ] Workflow waits for Central publication and does not redeploy.
- [ ] GitHub Release is created from the exact signed tag.

## Post-publication verification and record

- [ ] Both coordinates resolve from a fresh isolated Maven repository.
- [ ] Remote POM/main/sources/Javadoc artifacts match the validated release evidence.
- [ ] Published detached signatures and checksums verify.
- [ ] Clean published-3.0.0 V3 consumer compilation/execution passes without local
  reactor installation.
- [ ] Central artifact pages and GitHub tag/release links are verified.
- [ ] Release record contains actual release date and exact tag/master commit.
- [ ] Release record contains actual fingerprint, workflow/deployment result, test
  counts, compatibility reports, consumer/example results, and six JAR hashes.
- [ ] Release record contains actual Central resolution and GitHub Release facts.
- [ ] A post-publication documentation commit identifies 3.0.0 as current stable.
- [ ] Future compatibility planning retains 1.0.0, 2.0.0, and 2.1.0 and adds 3.0.0
  only after its publication can be resolved.
- [ ] Published 3.0.0 artifacts are treated as immutable; later fixes use a new version.
- [ ] Phase 8 is marked complete only after every applicable post-publication item is
  supported by real evidence.

Phase 8 being release-ready is not the same as Phase 8 being released. The checklist
is complete only after clean published-artifact and consumer verification succeeds and
the post-publication record is committed.
