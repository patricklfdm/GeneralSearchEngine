# CI parallel lanes: dependency audit and migration map

This audit and migration map record the architecture **before** V5.1 build
sharing: nineteen independent full-CI jobs after `changes`. The current
[V5.1 verification build domain](CI_V51_BUILD_DOMAIN.md) replaces eleven repeated
prerequisite builds with one producer and exact-source restores, adding a twentieth
required gate. The graph and prerequisite table below are historical; the original
verification/upload migration map remains useful for checking preserved coverage.
See [V5.1 lane ownership](CI_V51_LANES.md) and [CI/CD operations](CI_CD.md) for
current ownership, triggers and branch protection.

```text
changes
  ├── reactor-core (display name: Reactor tests)
  ├── v51-foundation
  ├── v51-remote-rich
  ├── v51-remote-faults
  ├── v51-admission-resources
  ├── v51-promise-crashes
  ├── v51-public-reads-faults
  ├── v51-public-recovery-pressure
  ├── v51-public-hardening
  ├── v51-protocol-selection
  ├── v51-candidate-crashes
  ├── v51-reclamation
  ├── v50-authority
  ├── v50-recovery-workload
  ├── v4-regression
  ├── soak-examples
  ├── compatibility
  ├── release-artifacts
  └── cloud-runner-tests
            ↓ all nineteen results + changes
         Required
```

## Build prerequisites and isolation

Ordinary builds below now run through the [bounded Maven infrastructure helper](CI_MAVEN_INFRA_RETRY.md).
It preserves the underlying command and permits one retry only for classified remote
transfer failures before test execution. Phase gates and specialized builds keep their
original single-attempt behavior; all attempt logs are uploaded independently.

| Job | Local prerequisites | Timeout |
| --- | --- | --- |
| `reactor-core` | Existing `./mvnw -f reactor/pom.xml clean package`, with all reactor tests | 30 minutes |
| `v51-foundation` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-remote-rich` | Same reactor package/tests; full 1080-second frozen JVM tapes and binary replay | 60 minutes |
| `v51-remote-faults` | Same reactor package/tests; twelve frozen fault cells, independent evidence and relocated replay | 60 minutes |
| `v51-admission-resources` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-promise-crashes` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-public-reads-faults` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-public-recovery-pressure` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-public-hardening` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-protocol-selection` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-candidate-crashes` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v51-reclamation` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v50-authority` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v50-recovery-workload` | `./mvnw -f reactor/pom.xml package`, including tests | 60 minutes |
| `v4-regression` | `./mvnw -DskipTests package` compiles core test harnesses; original specialized builds stay in place | 60 minutes |
| `soak-examples` | Its first Maven JMH test compiles its inputs; the soak script packages JMH and travel script compiles the example reactor | 30 minutes |
| `compatibility` | Unchanged independent build | 20 minutes |
| `release-artifacts` | Unchanged independent build | 30 minutes |
| `cloud-runner-tests` | Unchanged shell/Python checks | 5 minutes |

The regression timeouts retain headroom from the old 60-minute job. They are
limits, not expected durations. Workload sizes, Maven test selection and Surefire
concurrency are preserved. The
[test-only catch-up budget correction](CI_V51_LANES.md#build-failure-and-fix) separates
whole-operation completion from prompt admission; production RPC bounds are unchanged.

### Dependencies found during the audit

- **V5.0 and V5.1 need executed tests, not just compiled classes.** V5.0
  `admission_evidence.py`, `offline_harness.py` and `runtime_harness.py` read
  Surefire XML reports, check that tests executed successfully and check freshness.
  V5.1 storage/protocol/runtime/recovery/bootstrap/public runtime gates also read
  local test reports. Their lane builds therefore execute tests. Existing
  `--skip-build` gates keep their meaning, with fresh JARs, test classes and reports
  produced on the same runner. The full reactor build in `reactor-core` remains
  independently required; duplicate Maven tests here are intentional.
- **V4 has an ordered JMH artifact dependency.** V4.0 Phase 6 creates
  `target/benchmarks.jar`, which V4.1 Phase 6 consumes with `--skip-build`.
  V4.2/V4.3 Phase 6 intentionally perform their own clean JMH packages. V4.3
  resolves its published V4.2 control locally. V4.4 conditional gates and the
  final clean non-JMH package stay in their original relative order. The initial
  core package compiles `target/test-classes`; it does not need another full test
  execution because `reactor-core` retains that required coverage.
- **Soak/example commands already establish their own inputs.** The JMH test uses
  the core POM; the stabilization script performs `clean -Pjmh -DskipTests package`
  and uses a private temporary directory with its existing cleanup trap. The
  travel script compiles with `-pl :travel-search-example -am`. No extra full
  reactor package is added to this lane.
- **Evidence paths are local to each runner.** V5 gates use fresh `run.XXXXXX`
  directories under their existing `target/v50-*` and `target/v51-*` roots.
  Published controls are resolved by each lane's scripts. V4 and soak retain
  their existing temporary-directory and cleanup behavior. V5 harnesses allocate
  loopback ports and close/kill their owned processes; jobs run on separate
  hosted runners and cannot collide on ports or `target/`. No within-lane gate
  reordering or concurrent process-harness execution is introduced.
- **V5.0 cloud preflight consumes CI identifiers.** The internal job ID becomes
  `reactor-core`, but its display name remains `Reactor tests`. The Phase 6B
  step name remains unchanged in `v50-recovery-workload`; preflight already searches
  all jobs for that step. `Required` covers all seventeen lanes. No cloud
  preflight, environment, WIF, paid workflow or release behavior changes.

Action pins, Java setup and Maven dependency caching are copied from the original
job. Maven's dependency cache is not a substitute for build outputs. No artifacts
are downloaded between jobs; evidence uploads keep their exact existing names,
paths, `always()` conditions, missing-file behavior and 14-day retention. Nine new
per-lane Java report artifacts retain reactor failures. All 45 artifact names are
unique; the [V5.1 map](CI_V51_LANES.md) records their ownership.

## Required and documentation-only behavior

`Required` retains `always()` and its stable display name. Successful change
classification is mandatory. For `run_full_ci=true`, every one of the seventeen lanes
must return `success`; for `false`, every lane must return `skipped`. Failure,
cancellation, an unexpected skip/success or an invalid classification fails the
gate. Change classification itself is unchanged. Docs-only CI runs no Maven.

`scripts.test_ci_changes` executes the actual Required shell across each lane's
success/failure/cancellation/skip cases, checks that every result is wired into
Required, and verifies that all full lanes start independently and skip for docs.

## Original step mapping with current destinations

This table uses the 87-step worktree immediately before the split, including the
V5.1 Phase 4H public-bounds gate added in the same batch. Original substantive
steps and upload configurations move unchanged and in order within each lane.
Steps 1–2 belong to `reactor-core`. The current build matrix above and the separate
[V5.1 migration map](CI_V51_LANES.md) include later gates and independent builds.

| Old # | Original step | New job |
| --- | --- | --- |
| 1 | Check out source | `reactor-core` |
| 2 | Set up Java 21 | `reactor-core` |
| 3 | Verify aligned development versions | `reactor-core` |
| 4 | Verify the V5.0 Phase 0 contract candidate | `reactor-core` |
| 5 | Test the reactor | `reactor-core` |
| 6 | Verify V5.1 declarations and independent leadership foundation | `v51-foundation` |
| 7 | Verify V5.1 ledgers, frozen recovery and real JVM interruption cuts | `v51-foundation` |
| 8 | Verify V5.1 election and activation transition evidence | `v51-foundation` |
| 9 | Verify V5.1 real TCP runtime and application recovery | `v51-foundation` |
| 10 | Verify V5.1 retained-voter rejoin and two-source reclamation | `v51-foundation` |
| 11 | Verify V5.1 public lifecycle, strong reads and retained failover | `v51-public-reads-faults` |
| 12 | Retain V5.1 public runtime and read barrier evidence | `v51-public-reads-faults` |
| 13 | Verify V5.1 concurrent public histories, read crash cuts and rich V4.4 semantics | `v51-public-reads-faults` |
| 14 | Retain V5.1 public qualification including failed histories and pre-reopen bytes | `v51-public-reads-faults` |
| 15 | Verify V5.1 public partitions, read fencing and mutation crash cuts | `v51-public-reads-faults` |
| 16 | Retain V5.1 public fault matrix including failed cases and pre-reopen bytes | `v51-public-reads-faults` |
| 17 | Verify V5.1 imported failover, rejected authority and public lifecycle boundaries | `v51-public-recovery-pressure` |
| 18 | Retain V5.1 public recovery and lifecycle evidence including failed cases | `v51-public-recovery-pressure` |
| 19 | Verify V5.1 public campaigns, minority selection and interrupted recovery | `v51-protocol-selection` |
| 20 | Retain V5.1 public protocol and recovery evidence including failed cases | `v51-protocol-selection` |
| 21 | Verify V5.1 public two-source floors and interrupted reclamation | `v51-reclamation` |
| 22 | Retain V5.1 public reclamation evidence including failed cases | `v51-reclamation` |
| 23 | Verify V5.1 public capacity, admission and wire rejection | `v51-admission-resources` |
| 24 | Retain V5.1 public bounds and rejection evidence including failed cases | `v51-admission-resources` |
| 25 | Verify V5.1 public bootstrap, V4.4 import and offline crash recovery | `v51-admission-resources` |
| 26 | Retain V5.1 public bootstrap and pre-reopen evidence | `v51-admission-resources` |
| 27 | Retain V5.1 rejoin sources and process evidence | `v51-foundation` |
| 28 | Retain V5.1 runtime wire, force and JVM recovery evidence | `v51-foundation` |
| 29 | Retain V5.1 protocol transitions and independent causal evidence | `v51-foundation` |
| 30 | Retain V5.1 authority bytes and process crash evidence | `v51-foundation` |
| 31 | Retain V5.1 model traces, process cuts and public consumer evidence | `v51-foundation` |
| 32 | Verify V5.0 public-admission declarations and independent 1.1 bytes | `v50-authority` |
| 33 | Retain V5.0 public-admission foundation evidence | `v50-authority` |
| 34 | Verify V5.0 public offline authority and published V4.4 round trips | `v50-authority` |
| 35 | Retain V5.0 offline authority evidence including killed processes and pre-reopen bytes | `v50-authority` |
| 36 | Verify V5.0 public runtime with three owned JVMs and pinned V4.4 | `v50-authority` |
| 37 | Retain V5.0 public runtime evidence including SIGKILL cuts and wire bytes | `v50-authority` |
| 38 | Verify V5.0 Phase 6A public performance probe and independent evidence | `v50-recovery-workload` |
| 39 | Retain V5.0 performance evidence including failed probes | `v50-recovery-workload` |
| 40 | Verify V5.0 Phase 6B runner failures and offline volume-layout probe | `v50-recovery-workload` |
| 41 | Retain V5.0 Phase 6B no-GCP evidence | `v50-recovery-workload` |
| 42 | Verify V5.0 full cloud workload and independent local evidence | `v50-recovery-workload` |
| 43 | Retain V5.0 cloud workload qualification including failed probes | `v50-recovery-workload` |
| 44 | Verify V5.0 remote workload adapter and bounded evidence | `v50-recovery-workload` |
| 45 | Retain V5.0 remote adapter qualification including failed probes | `v50-recovery-workload` |
| 46 | Exercise the V5.0 replication foundation | `v50-authority` |
| 47 | Exercise V5.0 production storage and independent crash inspection | `v50-authority` |
| 48 | Exercise V5.0 leader quorum and publication over three concurrent JVMs | `v50-authority` |
| 49 | Exercise V5.0 recovery, snapshot installation and safe compaction | `v50-recovery-workload` |
| 50 | Exercise V5.0 deterministic faults, pressure, close and repeated recovery | `v50-recovery-workload` |
| 51 | Retain V5.0 hardening evidence including failed cases and wire attempts | `v50-recovery-workload` |
| 52 | Retain V5.0 recovery evidence including failed cases and V4.4 comparison | `v50-recovery-workload` |
| 53 | Retain V5.0 leader-path evidence including failed cases | `v50-authority` |
| 54 | Retain V5.0 storage evidence including pre-reopen bytes and failed cases | `v50-authority` |
| 55 | Retain V5.0 foundation evidence including failed process workspaces | `v50-authority` |
| 56 | Exercise the V4 crash-harness and fake-cloud foundation | `v4-regression` |
| 57 | Exercise the V4 production WAL crash-barrier matrix | `v4-regression` |
| 58 | Exercise the V4 production recovery crash matrix | `v4-regression` |
| 59 | Exercise the V4 checkpoint crash matrix | `v4-regression` |
| 60 | Exercise the V4 lifecycle and repeated-crash hardening matrix | `v4-regression` |
| 61 | Exercise the V4 durable performance and operational evidence matrix | `v4-regression` |
| 62 | Exercise the V4.1 operational-safety foundation | `v4-regression` |
| 63 | Exercise V4.1 codec-free structural verification | `v4-regression` |
| 64 | Exercise V4.1 live backup and crash matrix | `v4-regression` |
| 65 | Exercise V4.1 semantic restore and crash matrix | `v4-regression` |
| 66 | Exercise V4.1 plan-bound safe cleanup matrix | `v4-regression` |
| 67 | Exercise V4.1 source-loss operational evidence | `v4-regression` |
| 68 | Exercise V4.2 exact format and codec-free inspection | `v4-regression` |
| 69 | Exercise V4.2 production V1.1 and format-only migration | `v4-regression` |
| 70 | Exercise V4.2 typed transform and target-index rebuild | `v4-regression` |
| 71 | Exercise V4.2 lifecycle, authority and cleanup hardening | `v4-regression` |
| 72 | Exercise V4.2 performance and replacement-host evidence | `v4-regression` |
| 73 | Exercise the V4.3 fast-reopen foundation | `v4-regression` |
| 74 | Exercise V4.3 exact derived format and inspection | `v4-regression` |
| 75 | Exercise V4.3 structured images and direct migration | `v4-regression` |
| 76 | Exercise V4.3 text images and complete selective fallback | `v4-regression` |
| 77 | Exercise V4.3 lifecycle and derived cleanup hardening | `v4-regression` |
| 78 | Exercise V4.3 fast-reopen performance and evidence lane | `v4-regression` |
| 79 | Exercise the V4.4 final-hardening foundation | `v4-regression` |
| 80 | Exercise the V4.4 complete local final-durable matrix | `v4-regression` |
| 81 | Exercise the V4.4 zero-production-change admission | `v4-regression` |
| 82 | Exercise the V4.4 bounded local hardening probe | `v4-regression` |
| 83 | Restore the closed-surface non-JMH artifact | `v4-regression` |
| 84 | Exercise V4.4 stabilization and no-GCP readiness | `v4-regression` |
| 85 | Test benchmark-only instrumentation contracts | `soak-examples` |
| 86 | Exercise reduced stabilization and measurement-only JFR | `soak-examples` |
| 87 | Run the travel example | `soak-examples` |

## Historical PR #199 partitioning

The following describes the earlier five-lane V5 split. Its V5.1 job IDs and
estimates were superseded by the [current nine-lane V5.1 map](CI_V51_LANES.md).

The first [PR #199 CI run](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35685132725)
completed V5.0 in **17m19s** and V5.1 in **32m40s**. Their reactor builds took
289s and 305s respectively. The follow-up split uses those successful step timings:

| Lane | Verification and upload seconds | Build/setup seconds | Estimated lane total |
| --- | --- | --- | --- |
| `v51-foundation-admission` | 471 | 315 | 13m06s |
| `v51-public-lifecycle` | 570 | 315 | 14m45s |
| `v51-protocol-reclamation` | 601 | 315 | 15m16s |
| `v50-authority` | 360 | 302 | 11m02s |
| `v50-recovery-workload` | 374 | 302 | 11m16s |

These totals sum this one run's existing steps and repeat its build/setup cost for
each new lane. They are estimates, not new measurements or timing guarantees.
With comparable runner capacity, V5.0 should finish in roughly 11–12 minutes and
V5.1 in 15–16 minutes. The complete CI still waits for compatibility and release
artifacts. Three additional reactor builds increase total runner minutes by
roughly 15 minutes at these observed build durations. Queueing, cache hits and
runner variation can change the outcome.

The five V5 lanes are partitioned as follows:

- `v50-authority`: public admission, offline authority, public runtime, Phase 1–3.
- `v50-recovery-workload`: Phase 4–6, including hardening and local cloud workloads.
- `v51-foundation-admission`: Phase 1–3, public admission/bounds, promise crashes and bootstrap.
- `v51-public-lifecycle`: public runtime, concurrent qualification, faults, recovery/lifecycle and transport pressure.
- `v51-protocol-reclamation`: public protocol faults, candidate election crashes and interrupted reclamation.

Each gate constructs its own process/evidence workspace. Sharing Python helpers
between public harnesses does not mean sharing generated evidence: each harness
compiles its own consumer/observer and bootstraps its own processes. Gates needing
published V4.4 controls resolve them locally. No split lane consumes an earlier
lane's receipt, archive, port file or process state. Original within-lane order
and every upload remain intact.

The V4.4 toolchain fixture test now checks each Java job's distribution and version
selector, including the existing broad Java 21 compatibility selector and the
conditional release selectors. It no longer counts occurrences of the pinned
version string; adding lanes cannot invalidate the fixture solely by changing
that count. Negative tests still reject missing setup, missing versions and drift.

Maven `-T` is deliberately deferred. The project has reactor dependencies and
JMH generated-source/shaded-artifact steps, and this change does not establish
plugin/test safety under threaded Maven execution. Job-level isolation delivers
the scheduling improvement without introducing that additional variable.

Local syntax, migration comparison and Required decision tests cannot reproduce
GitHub scheduling, cache races, upload execution or hosted-runner load. The next
full PR CI run must confirm those behaviors and the actual duration. A docs-only
run can pass Required, but remains documentation evidence rather than proof that
the full regression lanes executed.

## Historical follow-up additions

The sections below retain job names and lane counts at introduction. Current gate
owners and requirements are listed above and in [the V5.1 split map](CI_V51_LANES.md).

## Additions after the migration

Phase 4I adds the twelve-case public promise crash gate and an always-retained
`v51-public-promises-${{ github.sha }}` artifact to `v51-foundation-admission`.
The 87-row map above remains the original migration record; the new gate is
additive. The eleven required lanes, build isolation, cloud-preflight identifiers
and docs-only behavior are unchanged. Historical timing estimates above exclude
this new qualification; later CI runs measure its added runtime.

Phase 4J adds fourteen candidate-side election crash cases and an always-retained
`v51-public-candidates-${{ github.sha }}` artifact to `v51-protocol-reclamation`.
It shares only compilation and read-only evidence helpers with the peer-promise
suite, not generated artifacts or process state. The eleven required lanes and
historical migration map remain intact; earlier timing estimates exclude this gate.

Phase 4K adds five public transport pressure/slow-force cases and an always-retained
`v51-public-pressure-${{ github.sha }}` artifact to `v51-public-lifecycle`.
The lane builds its own candidate JARs and runs three transport reservation Java
regressions as part of its existing reactor build. No required lane, existing gate
or evidence upload is removed. The historical 87-step map and timing estimates
remain unchanged; hosted CI must measure the additive qualification duration.

Phase 4L adds six internal resource-boundary cases and two public budget-isolation
cases to `v51-foundation-admission`, with the always-retained
`v51-resources-${{ github.sha }}` artifact. Internal fixtures and public executions
have separate receipts and source inventories. The original migration map, eleven
required lanes and existing gates/uploads remain unchanged. Historical timing
estimates exclude this additive gate.

Phase 4M adds two internal mailbox fixtures and four public queued-deadline/callback
cases to `v51-public-lifecycle`, with the always-retained
`v51-backpressure-${{ github.sha }}` artifact. The gate builds no shared state across
lanes. The original migration map, eleven required lanes and existing gates/uploads
remain unchanged; earlier timing estimates exclude this addition.

### V5.1 Phase 4N selection qualification

`v51-protocol-reclamation` additionally runs
`scripts/verify-v51-phase4-public-selection.sh --skip-build`: six public JVM/TCP
selection/recovery cases plus independent evidence checks. It always uploads
`target/v51-public-selection` as `v51-public-selection-${{ github.sha }}` for
fourteen days. This uses the lane's existing reactor build; the eleven required
lanes, prior gates/uploads, documentation routing and cloud workflows are unchanged.
See [the scope and evidence record](v5x/v5.1/PHASE_4_PUBLIC_SELECTION.md).

### V5.1 Phase 4O lifecycle hardening

`v51-public-lifecycle` additionally runs
`scripts/verify-v51-phase4-lifecycle-hardening.sh --skip-build`: five public JVM/TCP
scenarios for pinned reconstruction, partial writes and repeated timeouts, with
independent history/physical checks and negative variants. It always uploads
`target/v51-lifecycle-hardening` as `v51-lifecycle-hardening-${{ github.sha }}` for
fourteen days. The existing eleven required lanes, all prior gates/uploads and
documentation-only routing are preserved. See [the evidence record](v5x/v5.1/PHASE_4_LIFECYCLE_HARDENING.md).

## Phase 4P addition

`v51-public-lifecycle` adds `verify-v51-phase4-final-coverage.sh --skip-build`
after the Phase 4O gate, with always-retained `v51-public-final-coverage` evidence.
The migration table above remains the historical original-step audit. This new
gate uses the lane's existing reactor artifacts; the eleven-lane Required result
and dependency graph are unchanged. See [the final map](v5x/v5.1/PHASE_4_FINAL_COVERAGE.md).

## Phase 5A addition

`v51-public-lifecycle` adds `verify-v51-phase5-hardening.sh --skip-build` after
Phase 4 final coverage, with always-retained `v51-hardening` evidence. Its three
cases execute nine consecutive recovery rounds in total. The lane's reactor build
runs the five snapshot-rebuild regressions required by this gate. This extends the
lane without changing dependencies, its 60-minute timeout or Required aggregation.

## V5.1 Phase 6A follow-up

The existing `v51-foundation` job additionally executes
`scripts/verify-v51-phase6-performance.sh --skip-build` and always uploads
`target/v51-performance` as `v51-performance-${{ github.sha }}` for fourteen days.
This is a bounded local three-mode/SIGKILL qualification, with no provider access.
The seventeen required job identities, docs-only decision and other verification
commands are unchanged; the original migration table above remains historical.
See [current V5.1 gate ownership](CI_V51_LANES.md).

## V5.1 Phase 6C1 follow-up

`cloud-runner-tests` now executes `scripts/verify-v51-phase6-remote-foundation.sh`
and always retains `target/v51-remote-foundation` as
`v51-remote-foundation-${{ github.sha }}` for fourteen days. It uses Python only,
with a 120-second subprocess backstop and no GCP credentials. The local gate checks
command receipts, scheduler accounting and binary collection; it does not qualify
GSE rich concurrency or enable a paid runner. The foundation discovery also runs
its unit regressions. Required identities, docs-only behavior and the job's existing
five-minute ceiling remain unchanged. The original migration map is historical.

## V5.1 Phase 6C2A follow-up

The additional `v51-remote-rich` lane owns
`scripts/verify-v51-phase6-remote-rich.sh --skip-build`, an independent reactor
package/test and always-uploaded Java reports plus `target/v51-remote-rich`.
Both artifacts use unique job names and fourteen-day retention. Its original
frozen windows require at least nineteen minutes; adding a separate lane avoids
serializing those windows behind the existing foundation gates. It has no GCP
permission or environment. `Required` now checks nineteen full lanes, including
this lane's intentional skip for documentation-only changes. Existing commands
and historical migration rows are preserved.
