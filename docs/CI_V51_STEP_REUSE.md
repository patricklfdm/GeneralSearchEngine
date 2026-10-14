# V5.1 restore and provenance step reuse (PR2)

Base: `62b104e914e690be860a8c7a770d4de39ef797ec`, after PR #324.
Status: merged in PR #325. [Hosted full-path observations](CI_SHADOW_ACCEPTANCE.md)
confirm restore/provenance success; PR #326 also completed docs-only hosted acceptance.

## Exact migration scope

Eleven ordinary V5.1 consumers have the same ordered prerequisites: checkout,
pinned Java, download by the verification producer's artifact ID, validate and
restore the tested bundle, and retain the restore receipt/manifest. Only their
provenance artifact names differ.

| Consumers | Shared prerequisite |
| --- | --- |
| `v51-foundation`, `v51-remote-faults` | Exact-source tested build |
| `v51-admission-resources`, `v51-promise-crashes` | Same |
| `v51-public-reads-faults`, `v51-public-recovery-pressure`, `v51-public-hardening` | Same |
| `v51-protocol-selection`, `v51-candidate-crashes` | Same |
| `v51-reclamation`, `v51-full-size-runtime` | Same |

Two repository-local composite actions replace the repeated definitions:

- [Restore build](../.github/actions/v51-restore-build/action.yml) downloads the
  supplied producer ID and runs the original `scripts.ci_v51_bundle restore`
  command. Its only input is the artifact ID; source comes from `GITHUB_SHA`,
  and bundle/receipt paths remain fixed. Checkout and Java setup stay visible
  in each caller before restoration. The single command explicitly uses Bash
  and propagates a nonzero exit without retry or suppression.
- [Retain provenance](../.github/actions/v51-retain-build/action.yml) uploads the
  original receipt and manifest, under the caller's existing name, with the
  same 14-day retention and missing-file warning policy. It remains a separate
  step immediately after restore and before qualification. **Both caller and
  child use `always()`**, so a download/restore failure still attempts diagnostic
  retention. It does not depend on entering the restore action successfully.

Actions are loaded from the checked-out source, not a moving remote action ref.
The nested upload/download actions keep their existing pinned revisions. This
uses GitHub's documented [local composite action mechanism](https://docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action)
and [step conditions](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax#runsstepsif).
The restore action keeps an internal missing-ID sentinel because `required: true`
alone does not enforce presence at runtime. Missing IDs cannot become an
unfiltered download. Inputs are action data; none is interpolated into shell
source or accepted as an arbitrary command.

## Contract checks

The [registry](../scripts/ci_suite_registry.json) remains byte-identical to PR1.
Its 24 download and 99 upload contracts describe effective per-job operations.
The suite jobs now contain 13 direct download and 88 direct upload declarations,
plus eleven calls to each action. After expanding those calls the original counts, names,
paths, IDs, conditions and retention match exactly.
The accompanying [PR3 observer](CI_SHADOW_PLANNER.md) adds one separate Change
scope upload; it is not part of the suite qualification evidence inventory.

[The validator](../scripts/ci_suites.py) recognizes only these two local actions
in the eleven reviewed callers. It reads their actual metadata, checks required
input bindings, fixed command/shell, action order and checkout/Java prerequisites,
then compares the expanded artifact contracts with the unchanged registry.
Unknown/nested helpers, extra inputs, skipped restore, missing either `always()`,
changed command, wrong producer ID, altered path or retention fail validation.
It does not execute Actions expressions or become a general YAML loader.

All files below `.github/actions/`, including Markdown, now require full CI;
the new executable domain cannot inherit the ordinary Markdown short circuit.
Existing documentation paths retain their classification. Required's result
policy, job conditions, matrices, names and dependencies are unchanged.

## Deliberately separate domains

Owned experiment's externally observed qualification/package steps stay inline.
Guest services and owned network/drill/canonical jobs retain their existing
package setup and provenance spelling. Rich inputs/shards/aggregate retain their
extra artifact-ID dependencies, producer outputs and attempt-aware handoffs.
These are not identical to the selected ordinary consumer group.

The tested-build producer, independent Reactor, V5.0/V4/JMH, compatibility and
release lanes retain their current builds and ordering. Release's literal
validation commands, nine JARs/three POMs, six consumers and 90-day evidence
remain intact. No guest-package producer, new job dependency, build sharing
domain, workload split, core profile or paid-cloud behavior is introduced.

The existing bundle validator still checks exact source/JDK, content/mode hashes,
executed Surefire reports, allowlisted members, sizes, paths, links and output
freshness. A rerun consumes the ID of its actual producer, including an earlier
producing attempt in the same accepted run. The existing independent cloud
collector's expiry/source/attempt checks remain authoritative.

## Validation and operational limits

- **202 tests passed** under Python 3.11: new action contract/negative tests,
  full/docs Required parity, existing classifier, bundle restore, cloud
  preflight/artifact/admission, toolchain and release fixtures.
- An independent retained inline fixture checks the three original steps in
  every migrated caller. The real restore command was exercised with a stub
  executable to check argv, spaces, literal untrusted data and exit propagation;
  this is not a hosted Actions execution. Existing bundle tests cover the real
  restore validation and failure receipt using small fixture artifacts.
- Base-to-working-tree comparison found identical effective step data/order
  for all 38 jobs, allowing only the added Change scope test module and the
  explicit single-command composite Bash shell. All 26 other job bodies are
  byte-identical. All 169 effective shell blocks parse, and the independent
  cloud parser still expects exactly 46 full jobs.
- Workflow/action YAML, artifact inventory, protected release/runtime inputs,
  changed local links and whitespace were checked. Evidence and read-only
  comparison tooling are in `target/ci-v51-step-reuse/` during review.

No full Maven build, hosted workflow, cloud experiment or release was started
by the implementation agent. The operator's subsequent PR/master CI showed all
eleven composite restore/provenance pairs succeeding. Master's first workload
failure occurred after restore, and its runtime evidence was uploaded; a hosted
failure inside the composite was not injected. PR #326 completed docs-only
hosted validation with all suites skipped and Required successful. If checkout fails before local action metadata exists, its retention
action cannot run; the original source-bound restore receipt cannot exist at
that point either. Runner termination cannot guarantee artifact upload.

This is a maintenance refactor. The dependency graph and workload are unchanged;
there is no measured PR2 time saving. PR1's master run is a baseline, not a
post-PR2 performance observation. Revert this PR's commit(s) together to restore
inline steps and the matching validator/tests; leave registry, qualifiers,
branch protection and release tag intact. This PR2 record describes its own
validation before the user's additional PR3 authorization; the
[combined progress record](CI_REFACTOR_PROGRESS.md) covers the final batch.
