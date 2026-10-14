# ADR: explicit suite contracts before CI policy changes

Status: PR0 audited; PR1 merged with PR/master full CI success.
[PR2](CI_V51_STEP_REUSE.md) and [PR3 shadow observation](CI_SHADOW_PLANNER.md)
merged in PR #325. [Full hosted paths and rollout reports](CI_SHADOW_ACCEPTANCE.md)
are observed, including master's failed first attempt and successful partial
rerun. PR #326 completed docs-only hosted acceptance. The
[PR4 review](CI_CORE_POLICY_REVIEW.md) recommends deferring core activation:
the single candidate path matches none of the last 30 merged PRs.
Core is disabled; no coverage reduction is approved by this ADR update.
PR4/PR5 and [PR6's operational handoff](CI_REFACTOR_HANDOFF.md) merged together
in PR #327. [Final hosted acceptance](CI_REFACTOR_ACCEPTANCE.md) records all 46
jobs successful on both new-source full paths, the first PR attempt's platform
cancellation, measured replay results and completed reconciliation.
Base: `98f2996f896f97a85bf18b0be4b73bb44ad6d2d5`. This is a CI maintenance task
after V5.1 publication, separate from V5.2 development.

## Decision

Retain one workflow with explicit jobs and the existing full/docs classifier.
Add a versioned JSON inventory and a standard-library validator. Required reads
`${{ toJSON(needs) }}` through an environment variable, checks the complete
registry/workflow/needs set, and reports each invalid result. It retains its name,
`always()` condition, 37 dependencies, runner and two-minute timeout.

Required adds a pinned checkout with credentials not persisted to read the
validator. Failure to check out, parse or validate fails the job; there is no
fallback PASS. The Change scope test command adds the two new test modules.
PR1 kept other lane bodies unchanged, including all verification/upload commands.
PR2 subsequently extracts only eleven identical ordinary consumer prerequisite
groups, with expanded contract equality and a separate always-upload action.
PR3 adds a baseline-policy-constrained observer and an attempt-specific report
in Change scope. It cannot output a gate result; actual full/docs selection is
unchanged. The initial core allowlist is empty and nonempty lists are rejected.

The JSON inventory stores dependencies, build domain, matrix, inputs/outputs,
evidence options and full/docs expected results. It contains literal Actions
bindings as data, not executable commands. Closed parsing rejects unreviewed
YAML structure instead of silently omitting jobs. Runtime requires no pip
installation. Invalid/duplicate JSON, extra or missing dependencies, missing
classifier output and unexpected skip/failure/cancellation all fail.

The original shell is retained as an independent
[equivalence fixture](../scripts/fixtures/ci-required-v1.txt). Each of 36 lane
results is tested under full and docs, including missing and unknown states.
Strict schema/configuration validation is additional protection; the legal
full/docs result truth table is unchanged. Matrix children still use GitHub's
aggregate result plus existing qualification/aggregate jobs; PR1 introduces no
new child receipt protocol.

## Alternatives and limits

A generic dynamic command matrix or broad reusable workflow would hide existing
step interfaces and blur independently validated build domains. Rewriting YAML
through a general serializer could also change the closed cloud parser's input.
Those approaches are not used here. JSON duplicates artifact declarations so
reviewed contracts are explicit; tests reject one-sided changes. It does not
make coordinated policy edits trustworthy without review or replace the
independent release/cloud fixtures.

This phase improves maintenance and diagnostics. It does not shorten the
canonical workload, claim a time saving, enable core CI, or relax PR coverage.
See the [measured baseline](CI_BASELINE.md).

## Revised phases

| Phase | Scope and exit condition |
| --- | --- |
| PR0 | Completed read-only baseline/attempt/consumer audit; preserve raw observations and failed attempts. |
| PR1 | Registry and Required equivalence; preserve all lanes, artifacts and external consumers; local negatives plus hosted full/docs acceptance. |
| PR2 | Merged: eleven ordinary V5.1 restore/provenance groups reused, hosted restore/upload success observed. Named steps, producer tracking and failure evidence preserved; specialized/release domains remain inline. Full/docs hosted observations complete. |
| PR3 | Merged with PR2: shadow-only planner; actual execution remains full/docs. Hosted first-rollout full fallback, tested source identities and valid-baseline docs observations verified. Empty core allowlist. |
| PR4 | Policy review complete; activation deferred for separate approval. A single existing travel-example Java file is the only audited candidate, with 0/30 recent merged PRs eligible. File-level implementation, acceptance and rollback are documented. If later approved, omit only three complete canonical repetitions; every other lane stays selected. Master/unknown/manual remain full; core cannot pass cloud admission. |
| PR5 | Accepted after #327: [canonical phase analysis and schema parsing reuse](CI_CANONICAL_REPLAY_PERFORMANCE.md), same-byte local equivalence and successful full live PR/master runs. Cache only catalog contents, reread current bytes and retain complete validation. Six new hosted jobs show shorter replay, with no fixed whole-workflow savings claim. |
| PR6 | Complete: generated inventory checked by existing tests, [suite onboarding](CI_SUITE_ONBOARDING.md), current vs historical documentation, measured results, failure triage and rollback. [Final reconciliation](CI_REFACTOR_ACCEPTANCE.md) records both full paths and original cancellation; no new workflow or core policy. |

The PR0 input's release-in-progress assumption is superseded by successful V5.1
publication. Existing build sharing, Python/cloud partitioning and rich replay
fixes are not pending features. CI measurements must distinguish accepted and
producing attempts and avoid counting cloned jobs twice. Continuous experiments
retain their [atomic histories](CI_DEPENDENCY_CONTRACTS.md).

## Acceptance and rollback

Local checks cover the actual workflow, all original legal full/docs outcomes,
configuration drift, untrusted JSON, complete-diff classification, real cloud
job catalog, artifact provenance and PR #322 release fixtures. Hosted PR full,
master full and safe docs-only changes were operator validation steps, with
source/run/attempt and reruns recorded separately. PR #325's full observations,
PR #326's normal docs paths and PR #327's new-source full paths are recorded.
The revised refactor task is complete. Any future
core execution still requires approval and its own hosted acceptance. No new
workflow is triggered by the local implementation/audit task.

If PR1 needs rollback, revert its actual merged commit(s), restoring the old
Required shell, test bindings and Change scope command together. Keep audit
records. For a merge commit use `git revert -m 1 <commit>`; a squash commit uses
`git revert <commit>`. Validate full/docs outcomes and cloud/release interfaces
again. Do not reset master, move the release tag or disable Required to roll
back. PR1 has no core/full policy switch to toggle.
