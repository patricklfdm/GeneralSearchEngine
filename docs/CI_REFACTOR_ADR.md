# ADR: explicit suite contracts before CI policy changes

Status: PR0 audited; PR1 implemented for review; hosted PR1 acceptance pending.
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
Other lane bodies remain unchanged, including all verification/upload commands.

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
| PR2 | Small mechanical reuse of identical ordinary V5.1 restore/provenance steps. Keep externally observed named steps, original producer tracking and failure evidence visible. Exclude release literal blocks and specialized builds. |
| PR3 | Shadow planner only; actual execution remains full/docs. Unknown, policy, registry, toolchain, frozen artifact and qualifier changes remain full. PR edits cannot downgrade themselves. |
| PR4 | Separately approved reduction in PR coverage. Initial candidate omits only three complete canonical repetitions, retaining their component checks and every other lane. Master/unknown/manual remain full; core cannot pass cloud admission. |
| PR5 | Measure one hotspot's internal phases before optimizing. Preserve immutable-byte/source-bound replay, all negatives and combined budgets. Shared builds/sharding/replay corrections are already done. |
| PR6 | Reconcile current vs historical documentation and establish V5.2 suite registration rules with measured results and explicit remaining gaps. |

The PR0 input's release-in-progress assumption is superseded by successful V5.1
publication. Existing build sharing, Python/cloud partitioning and rich replay
fixes are not pending features. CI measurements must distinguish accepted and
producing attempts and avoid counting cloned jobs twice. Continuous experiments
retain their [atomic histories](CI_DEPENDENCY_CONTRACTS.md).

## Acceptance and rollback

Local checks cover the actual workflow, all original legal full/docs outcomes,
configuration drift, untrusted JSON, complete-diff classification, real cloud
job catalog, artifact provenance and PR #322 release fixtures. Hosted PR full,
master full and a safe docs-only change remain operator validation steps, with
source/run/attempt and any reruns recorded separately. No new workflow is
triggered by the local implementation task.

If PR1 needs rollback, revert its actual merged commit(s), restoring the old
Required shell, test bindings and Change scope command together. Keep audit
records. For a merge commit use `git revert -m 1 <commit>`; a squash commit uses
`git revert <commit>`. Validate full/docs outcomes and cloud/release interfaces
again. Do not reset master, move the release tag or disable Required to roll
back. PR1 has no core/full policy switch to toggle.
