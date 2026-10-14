# CI dependency and consumer contracts

The [suite registry](../scripts/ci_suite_registry.json) describes the current
36 full-CI lane IDs, their dependencies, fixed matrices, artifact handoffs,
retention and full/docs outcomes. Changes and Required are separate meta jobs:
38 static IDs expand to **46 full jobs**, or 38 docs records with 36 explicitly
skipped placeholders. The registry describes the workflow; it does not schedule
commands or introduce a core profile.

## Execution and artifact boundaries

| Dependency | Contract |
| --- | --- |
| Change scope → every lane | The unchanged complete-diff classifier determines full/docs. Unknown inputs require full. |
| V5.1 verification build → consumers | Tested JARs/classes/Surefire reports, exact source/JDK/content inventory, explicit producer artifact ID. Cache is not test evidence. |
| Rich inputs → three shards | One immutable source/seed, build binding and explicit input artifact ID. |
| Three shards + inputs/build → aggregate | All PARTIAL receipts, independent physical/history replay, five whole cells/1080 calls, shared storage/decoded budgets and ten exact negatives. |
| Changes + all 36 lane results → Required | Every ID must be present; full requires success, docs requires skipped. No missing-as-skipped conversion. |

Shared builds, rich sharding, Python/cloud partitions and relocated-negative
replay are already implemented. Rich producer outputs are `published_controls`,
`automatic_healthy` and `automatic_concurrent`; consumers download those IDs.
Neither build nor rich consumers guess artifact names using their own retry
attempt. Independent Reactor, V5.0, V4, soak, compatibility and release build
domains remain intentional. In V4, later `--skip-build` steps consume earlier
JMH outputs, so their order matters.

The registry records all **24 download and 99 upload definitions**, including
paths, IDs, conditions, missing-file policy, compression and retention. Of the
uploads, 90 use 14 days, eight use seven days, and the V5.1 canonical receipt uses
90 days. These static definitions are not counts of expanded uploaded artifacts.
The release workflow's corresponding reproducibility evidence also uses 90 days.

## External readers

| Reader | Interface that must remain visible |
| --- | --- |
| [V5.1 cloud CI](../scripts/v51/cloud_ci.py) | Exact workflow bytes, explicit job names, fixed rich/tape/repetition matrices, exact master/source and accepted attempt; all expanded jobs successful. |
| V5.1 cloud CI owned qualification | `V5.1 owned experiment (no GCP)` and `Qualify V5.1 owned complete experiment history and backup restore without GCP`. |
| [Runner artifact collector](../scripts/v51/cloud_runner_artifacts.py) | `V5.1 verification build` / `Create exact-source V5.1 verification bundle`, and owned job / `Build and relocate the V5.1 guest package without GCP`. |
| [V5.0 preflight](../scripts/v50/cloud_preflight.py) | Reactor tests, Compatibility, Release artifacts, Cloud runner (no GCP), Required; the Phase 6B runner and remote-workload verification step names. |
| [Release fixture](../scripts/v51/test_phase7_release_fixtures.py) | Named validate/sign/publish blocks and literal validation commands, exact source, artifact roles and retention. |

V5.1 admission requires the current accepted attempt. A successful build reused
by a partial rerun may have an earlier **producing attempt** in that same run;
the artifact collector verifies its original execution/runner/step identity,
metadata and time window. This is not permission to use an arbitrary older green
run. Admission rechecks master, run and attempt after preparation. Docs success
and Required's result summary cannot substitute for full cloud qualification.

The three fixed matrices remain three rich shards, five canonical tapes
(tape/mode/cell mapping and order), and three complete canonical repetitions.
The independent cloud parser validates their catalog in addition to the
registry/workflow consistency tests.

## Release boundary introduced by PR #322

Keep nine JARs and three POMs across core/processor/replication, frozen SHA256
inventory, pinned toolchain, and final `validate-evidence ... --source` binding.
Keep both `5.1.0` and `5.1.0-SNAPSHOT` only where the existing role allowlist
permits them. Do not regenerate these files as a consequence of CI refactoring.

CI and release retain the Phase 7 wrapper, canonical build and candidate
validation commands. Signing and Maven deployment retain their existing before/
after validations and protected `production-release` environment. Compatibility
and published verification retain all six consumers (V1 through V5.1, including
the V1 compile-only consumer). `--skip-consumers` on the Phase 7 wrapper does not
authorize removing either consumer set. Release evidence stays at 90 days.

## Continuous history cannot be split into unrelated successes

A complete canonical repetition includes 15 cells, one lease/request/source and
shared backup, prescribed ordering, combined budgets and final replay/cleanup.
The three repetitions already run independently. Component tapes remain useful
early checks but cannot replace a complete repetition. Frozen measurement
windows and calls cannot be subdivided across new independent histories.

Owned experiment, failure drill and 512-slot runtime checks retain their own
restart/authority/resource histories. Existing whole-cell rich shards retain
their common seed and full aggregate. The canonical validator's existing reuse
of joint physical replay is already implemented and is not a new optimization.

## Updating the registry

Edit the explicit workflow and corresponding registry entry together, then run
`python3 -m scripts.ci_suites` and the CI contract tests. Unregistered jobs,
missing Required dependencies, changed matrices, artifact interfaces and
`continue-on-error` fail validation. The parser accepts only the repository's
closed explicit syntax; it is not a general YAML loader. No expression or shell
string in the registry is evaluated. External consumer tests remain independent;
matching edits to YAML and JSON alone do not establish compatibility or authorize
less coverage.
