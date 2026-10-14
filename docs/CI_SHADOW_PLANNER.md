# CI shadow planner (PR3)

Status: merged together with [PR2 step reuse](CI_V51_STEP_REUSE.md) in PR #325;
[hosted first-rollout reports verified](CI_SHADOW_ACCEPTANCE.md), valid-baseline
docs-only observation verified by PR #326. No core execution
policy is enabled. The existing classifier, all 36 required suites and all
three complete canonical repetitions continue to run under the original
full/docs conditions.

## What is observed

[The planner](../scripts/ci_shadow_plan.py) runs after Change scope's existing
classifier. It reads that classifier's result as data in `ACTUAL_RUN_FULL_CI`;
it never writes `GITHUB_OUTPUT`, job outputs, environment commands or a matrix.
Required still reads only `changes.outputs.run_full_ci`.

The summary displays **actual execution profile** and **shadow recommendation**
separately. `target/ci-shadow-plan/plan.json` retains the complete changed-path
list, non-documentation paths, reason codes, event, repository, run/attempt,
tested SHA, head/base/merge-base, workflow identity/hash, planner hash and both
baseline/tested policy hashes. `summary.md` is the same human-readable report
appended to the job summary. Neither file is runtime qualification evidence.

One additional pinned upload step retains this observation for 14 days as
`ci-shadow-plan-${{ github.run_id }}-${{ github.run_attempt }}` with `always()`.
An attempt-specific name avoids collisions when Change scope itself is rerun.
Partial reruns that reuse a successful Change scope reuse that attempt's report;
they do not manufacture a new observation. No downstream job downloads this
artifact. Existing 99 suite evidence uploads and all 24 downloads are unchanged;
this adds one **meta-job observation upload**, for 100 effective upload
declarations in the complete workflow after composite expansion.

## Source and trusted-policy boundaries

[The initial policy](../scripts/ci_shadow_policy.json) is a closed JSON schema:
shadow mode, profiles `docs/core/full`, the frozen documentation rule, and an
empty `corePaths` list. Data never becomes shell, Python code or a dynamic path
pattern. Nonempty core lists, changed documentation rules, duplicate keys,
unknown fields and unsupported schema versions recommend full.

| Context | Comparison and policy source | Conservative checks |
| --- | --- | --- |
| PR to master | Full `base...head` diff; policy from the event's base commit | Checked-out HEAD must equal tested SHA, whose two parents must equal the event base/head; fork heads are allowed, but base repository must match. |
| master push | Full `before..after` diff; policy from `before` | Event/ref must target master and `after` must equal tested SHA. |
| Manual/unknown | No reduced recommendation | Full, even when the actual result is unavailable or disagrees. |

The workflow ref must identify this repository's `ci.yml` at the event ref;
workflow SHA must equal tested SHA. Recorded workflow and planner bytes come
from that commit and must match checkout. A PR head SHA is **not** substituted
for its test merge SHA. These checks follow GitHub's documented
[event-specific SHA/ref semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request)
and [workflow/run variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).
Unsupported event shapes or identity mismatches recommend full.

The baseline policy is obtained with `git show <validated-base-sha>:<fixed-path>`.
The tested policy must be byte-identical to it. A PR cannot edit its policy file
to classify its own runtime change as core. **The rollout baseline `62b104e...`
has no policy**, so its PR and merge-push observations both reported
`POLICY_UNAVAILABLE` / full, as expected, leaving actual full CI unchanged.
PR #326 subsequently exercised the valid-baseline docs recommendation in both
its PR and master push; see the hosted acceptance record.

`git diff --name-only --no-renames -z` preserves both sides of a rename, unusual
filenames and the complete path set without GitHub file-API pagination limits.
Empty/malformed diffs, missing history, invalid context and unavailable policy
recommend full with a retained reason. There is no last-commit shortcut or
fixed file-count cutoff. The existing documentation allowlist is not broadened
to all of `docs/`; JSON plans, frozen hashes, runtime/test resources and scripts
continue to require full. All files under local CI actions require full as
introduced by PR2.

This is an observation safeguard within the reviewed workflow, not an external
security boundary against someone rewriting the planner and workflow together.
Enabling any execution reduction requires PR4's separate review and explicit
authorization. Ordinary I/O/programming/upload failures still fail the step;
the implementation does not add `continue-on-error` to hide them. Known
observation gaps instead produce a valid full recommendation, not a false PASS.

## Candidate allowlist and expected savings

**Approved core paths: none.** No audited path in this change establishes that
three complete canonical repetitions can safely be omitted. The initial policy
rejects nonempty lists rather than supplying a dormant execution switch.

| Paths / domain | Recommendation and evidence |
| --- | --- |
| Existing documentation allowlist | Docs only when every path passes the original conservative rule; actual docs checks remain authoritative. |
| Runtime, consensus, WAL/storage, recovery, migration, fencing and protocol | Full: shared source and public/internal qualification dependencies. |
| Fixtures, oracles, qualifiers, build bundle, permissions, leases and cleanup | Full: scripts and source/test resources affect acceptance and retained evidence. |
| CI/actions/policy/registry, POMs and toolchain | Full: execution and artifact identity inputs. |
| Release verifiers/fixtures, candidate hashes and artifact roles | Full: exact-source replay, nine JARs/three POMs, six consumers and release evidence contracts. |
| Any other non-documentation path | Full: no audited core allowlist exists. |

Under this policy **0% of PRs are eligible for a new core saving**, by construction;
this is not an empirical traffic estimate. Existing docs-only savings are not new.
The three historical path fixtures below include two full changes and one docs
change, but are selected boundary examples, not a representative sample. The two
hosted rollout reports add full-fallback observations, not measured PR2/PR3 speedup.
V5.2+ core development
is likely to remain full; a useful future allowlist requires dependency evidence
and representative path observations first.

## Validation, acceptance and rollback

[Tests](../scripts/test_ci_shadow_plan.py) use real temporary Git histories to
exercise fork PRs, divergent base/head, earlier code followed by docs, source-to-doc
renames, over 3,500 paths, literal shell-like filenames, master pushes, manual
events, wrong identities, first rollout and edited/unapproved baseline policies.
The real CLI retains reports without changing a pre-existing `GITHUB_OUTPUT`.
Malformed events remain observable; summary rendering escapes untrusted text.

[Historical fixtures](../scripts/fixtures/ci-shadow-history-v1.json) retain exact
merge/base/head identities and complete local diffs for PRs #322 (43 paths),
#323 (12) and #324 (15). These test path classification. They are reconstructed
from actual immutable Git history, not captured webhook payloads or newly
executed qualifications; those old commits predate the policy.

The suite validator also rejects rewiring gate outputs to the shadow plan,
changed observation command/input, a missing upload or loss of attempt identity.
Required's full/docs truth table, unchanged external cloud/release consumers and
expanded PR2 artifact contracts remain independently tested. Combined local
results and commands are in [the progress record](CI_REFACTOR_PROGRESS.md).

The full PR/master accepted views retain the unchanged suite set and observation
reports; master includes a partial rerun after its first workload failure, which
remains recorded. PR #326 completed docs-only PR and master acceptance, retaining
the original expected skips and displaying both docs profiles. Check the
actual tested SHA and attempt in the artifact, not only the API's PR `head_sha`.
No new workflow is dispatched by this implementation task.

To roll back this combined PR, revert its merged commit(s) with the matching
validator/tests and documentation. For a merge commit use
`git revert -m 1 <merge-commit>`; for a squash use `git revert <squash-commit>`.
Keep evidence and the release tag. To retain PR2 while removing only shadow
observation, remove both new Change scope steps, its test-module binding and
matching shadow validator/tests/policy together in a reviewed change. There is
no enabled core execution switch to disable. The [PR4 policy review](CI_CORE_POLICY_REVIEW.md)
recommends deferring activation; its implementation proposal is not an active policy.
