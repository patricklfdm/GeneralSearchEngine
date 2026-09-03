# GeneralSearchEngine 4.0.0 release checklist

This state-aware record separates the accepted durable evidence, final local candidate,
protected-master acceptance, signed tagging, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.0.0` |
| Release state | locally validated final candidate; protected merge pending |
| Phase 7 entry | `adbe96d9bf73bf03d3082f2ceb58a66ca75dd325` (PR #88) |
| Registered cloud baseline | `v4.0.0-durable-cloud` |
| Canonical source / run | `fe2060b9a872e66ff0067be6e8b7c900f0099708` / `33682157985` |
| Candidate branch | `release/v4.0.0` |
| Final protected-master commit | pending protected Phase 7 merge |
| Signed tag | not created |
| Maven Central | not published |
| GitHub Release | not created |

No unchecked publication item may be described as complete. `3.4.0` remains the
current published release until remote Central, deployment, and GitHub Release proof
all pass.

## Frozen release contents

- unchanged default in-memory and complete published V1–V3.4 behavior;
- additive, explicit single-node local durable mode with format family `gse-durable`
  and version `(1,0)`;
- deterministic codec and storage identities, exclusive ownership, framed WAL,
  contiguous logical sequences, force-before-publication, checkpoints, bounded
  retention, deterministic recovery, and fail-closed corruption;
- local process-crash, repeated-crash, fault-injection, lifecycle, capacity, JMH,
  operational, paid cloud, and replacement-VM evidence;
- immutable V4 format fixtures, independent byte inspection, and an independent
  public-API durable consumer; and
- no replication, multi-writer support, physical-disk-loss guarantee, persisted
  derived indexes, online upgrade, or repair tool.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — final `4.0.0` across all eight active coordinates |
| Reactor and V4 phase gates | PASS — 424 core, 5 processor, Phases 1–6 complete |
| API and published compatibility | PASS — source/reflection and isolated Japicmp through 3.4.0 |
| Independent consumers | PASS — V1/V2/V3/V4 plus travel example |
| Format `1.0` fixtures | PASS — production reader and independent inspector |
| Strict release artifacts | PASS — strict Javadocs and six-JAR service isolation |
| Reproducible build | PASS — two clean final-version builds byte-identical |
| JMH and cloud-local tooling | PASS — full bounded smoke and 102 Python tests; no paid run |
| Durable cloud baseline | PASS — immutable `v4.0.0-durable-cloud` registration |
| Diff hygiene | PASS — no production or format-semantic change; local evidence excluded |

## Reproducible final artifact hashes

Populate this table only from the final two-clean-build validation. These local hashes
are evidence for reproducibility; Phase 8 separately records downloaded Central
artifacts.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.0.0.jar` | `77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4` |
| `general-search-engine-4.0.0-sources.jar` | `3ebfa4b3ca810a52442e7b3997a6b42638356e88425be294819ca6d4b6533b4c` |
| `general-search-engine-4.0.0-javadoc.jar` | `9ffd48a3afdf546e02e12d7cd45a163dfcb8137c35860c280662d2f7805a365b` |
| `general-search-engine-processor-4.0.0.jar` | `1f61e404f4d783d943b73e7b5e108a98a41e5f8e51240d4b735fbcf99bbf3b1b` |
| `general-search-engine-processor-4.0.0-sources.jar` | `4cb2cfbeccb73e16a4c50b15ab14591984f9dcbe56faa8dcb53f5fb0c0c8321c` |
| `general-search-engine-processor-4.0.0-javadoc.jar` | `b5824f84aef6955f75ddd1bb7dad051cb06e45cde22ade3b003e4d18edca113f` |

## Protected candidate acceptance

- [ ] Merge Phase 7 through protected review and record the exact merge commit.
- [ ] Require exact-master CI success for that commit before tagging.
- [ ] Verify local and remote absence of `v4.0.0`.
- [ ] Verify the production environment permits tag pattern `v*.*.*`.
- [ ] Run Central immutability preflight for core and processor.

## Signed tag verification

- [ ] Create annotated signed `v4.0.0` on the exact final protected-master commit.
- [ ] `git cat-file -t v4.0.0` reports `tag`.
- [ ] `git tag -v v4.0.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [ ] `scripts/verify-release-tag.sh v4.0.0` passes.
- [ ] `git rev-parse v4.0.0^{commit}` equals the recorded protected-master commit.
- [ ] Push only the verified tag.

## Protected publication

- [ ] Tag-triggered release validation checks out the exact tag and passes every gate.
- [ ] The repository owner approves `production-release` only after validation.
- [ ] Core and processor POM/main/sources/Javadoc artifacts and signatures publish.
- [ ] `scripts/verify-published-release.sh 4.0.0` passes against Maven Central.
- [ ] Clean V3 and V4 consumers pass without a reactor install.
- [ ] The V4 consumer opens every immutable positive format fixture and rejects the
  corruption fixture using the downloaded artifact.
- [ ] The production deployment reports success for the exact tag commit.
- [ ] GitHub Release `GeneralSearchEngine 4.0.0` is created from the verified tag,
  marked latest, and is neither draft nor prerelease.

## Post-publication evidence

- [ ] Record release workflow run, attempt, event, exact tag SHA, start/end, and result.
- [ ] Record deployment ID/ref/SHA/status and independently query its final status.
- [ ] Record Maven Central URLs and SHA-256 for all six JARs.
- [ ] Record GitHub Release ID, URL, publish timestamp, target, draft, and prerelease.
- [ ] Reconfirm registered durable baseline name, source, set digest, and run.
- [ ] Update README, changelog, roadmap, phase checklist, and this record only from
  observed remote facts on a separate post-publication branch.

Published `4.0.0` and signed `v4.0.0` will be immutable. Any later code or format fix
must use a new version and retain the `(1,0)` compatibility promise.
