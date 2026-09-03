# V4.0 Phase 7 release-candidate checklist

**Status:** complete through protected PR #90 at `0f2ea5e`; the documentation-only
evidence-workspace boundary merged through PR #91 as final release commit
`73479da344f24f69e15904660d46783459d80dcf`, and exact-master CI run `33705710878`
passed before the verified Phase 8 publication

## Accepted entry boundary

- [x] Phase 6 implementation, fixes, paid experiment, replacement-VM drill, and the
  three-member canonical run are complete.
- [x] `v4.0.0-durable-cloud` resolves to the reviewed source
  `fe2060b9a872e66ff0067be6e8b7c900f0099708` and set digest
  `5e71ae200f94f5713278db7312057c4454fb73e18d159f78e71c31a92c44abbf`.
- [x] The Phase 6 evidence and registration record merged through protected PR #88 as
  `adbe96d9bf73bf03d3082f2ceb58a66ca75dd325`.
- [x] Exact-master CI run `33694586398` passed on that merge.
- [x] Phase 7 starts from that exact commit on `release/v4.0.0`.
- [x] The untracked local `benchmark-results/v4-durable/` mirror remains excluded from
  candidate source and release artifacts.

## Final-coordinate and documentation freeze

- [x] Core, processor, reactor, travel example, and V1–V4 independent consumer
  coordinates convert atomically to final `4.0.0`.
- [x] `project.build.outputTimestamp` is fixed to `2026-09-02T00:00:00Z` in both
  published artifacts.
- [x] The changelog describes the candidate without claiming tag, Central,
  deployment, or GitHub Release completion.
- [x] The root README keeps `3.4.0` as the current published dependency until remote
  verification and documents explicit V4 durable opt-in.
- [x] Migration guidance covers import, codec/identity responsibilities, first reopen,
  operator failure handling, backup, rollback, and explicit export/import changes.
- [x] Storage and API documents point to executable independent compatibility proof.
- [x] Phase 8 remains the only authority for signing, pushing a tag, publishing,
  deployment approval, and post-publication claims.

## Independent consumer and format compatibility

- [x] `compatibility/v4-style-consumer` depends only on the public core artifact and
  JUnit test support; it has no reactor or internal-package dependency.
- [x] A complete fresh/checkpoint/update/reopen scenario proves durable sequence,
  documents, checkpoint-plus-WAL recovery, and clean close.
- [x] Negative consumer cases reject changed schema identity and an unsupported custom
  startup index with `INCOMPATIBLE_STORAGE`.
- [x] Immutable format `1.0` fixtures cover fresh, WAL-only, checkpoint-only,
  checkpoint-plus-WAL, valid incomplete-tail, and corrupt-WAL histories.
- [x] Every persisted fixture member carries a frozen SHA-256 and Base64 payload.
- [x] The production reader opens every positive fixture, truncates only the permitted
  incomplete terminal prefix, and rejects the corruption fixture as `CORRUPT_WAL`.
- [x] The independent Python inspector validates the same bytes and classifications
  without calling production recovery.
- [x] Local consumer aggregation, version alignment, CI, and the release workflow all
  include the V4 consumer; remote verification runs it for published major version 4+
  artifacts.

## Candidate validation gates

- [x] `scripts/verify-v40-phase7-release.sh` passes with all four independent
  consumers in a fresh isolated Maven repository.
- [x] Full reactor tests pass: 424 core and five processor tests, no failure, error,
  or skip; the example compiles.
- [x] Frozen source/reflection API fixtures and fresh-isolated Japicmp through
  published `3.4.0` pass.
- [x] All V1/V2/V3/V4 independent consumers and the travel example pass against final
  coordinates.
- [x] Strict release Javadocs and exactly six publishable JARs pass the processor
  service-boundary inspection.
- [x] Two clean final builds produce byte-identical six-JAR output and their SHA-256
  values are recorded in the release checklist.
- [x] Bounded JMH, Phase 1–6 local durable gates, 102 cloud/control-plane Python
  tests, and
  Python fixture tests pass without a paid cloud run.
- [x] `git diff --check`, status review, and candidate source inventory are clean
  except the intentionally excluded local evidence mirror.

## Protected acceptance and Phase 8 handoff

- [x] Merge the candidate through protected PR #90 as `0f2ea5e` without a direct
  master push.
- [x] Merge the evidence-workspace boundary through PR #91 as final protected-master
  commit `73479da344f24f69e15904660d46783459d80dcf` and record successful exact-master
  CI run `33705710878`.
- [x] Confirm local and remote absence of `v4.0.0` before signing.
- [x] Run Central immutability preflight for both artifacts and observe HTTP `404`.
- [x] Begin Phase 8 only from the exact accepted protected-master commit.

Any production Java or format-fixture change after the accepted canonical source must
be classified explicitly. A correctness fix invalidates affected validation and may
require new durable evidence; documentation and release-infrastructure changes cannot
silently alter format `1.0` or the registered performance baseline. Phase 8 completed
successfully from this handoff; the immutable remote facts are recorded in the
[release checklist](RELEASE_CHECKLIST.md).
