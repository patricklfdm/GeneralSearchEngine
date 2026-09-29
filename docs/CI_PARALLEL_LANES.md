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


### Phase 6C2 full-size runtime qualification

PR #228's component boundary passed exact-master CI `36072038218`. PR #229's
[successful CI 36078101942](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36078101942)
measured the combined reclamation job at 27m42s, including 17m46s for the public
512-slot runtime. The [measured split](CI_V51_LANES.md#reclamation-and-full-size-runtime-split)
keeps public reclamation and the component gate in `v51-reclamation`, while the
new required `v51-full-size-runtime` job owns the unchanged
`verify-v51-phase6-full-size-runtime.sh --skip-build` command and always-retained
`v51-full-size-runtime-${{ github.sha }}` evidence.

Both consumers restore the verified shared build and run independently. There is
no additional Maven build. Full CI now has 23 required job IDs (27 executed jobs
with Change scope, Required and matrix expansion); docs-only behavior is preserved.
The public gate retains its 1200-second local backstop, including portable
positive/negative replay. Revised-source protected CI and hosted split timings
remain pending. See the [runtime boundary](v5x/v5.1/PHASE_6_FULL_SIZE_RUNTIME.md).


### Phase 6C3A cloud control qualification

PR #229's split and corrected full-size runtime passed exact-master CI
`36094121631` (all 27 jobs). The additional
`verify-v51-phase6-cloud-control.sh` gate runs in the existing `cloud-runner-tests`
job and always retains `v51-cloud-control-${{ github.sha }}` for fourteen days.
It uses only Python/local diagnostic command receipts and in-memory adapters;
no Java build, GCP credentials, environment or OIDC permission is added. Its
120-second backstop remains inside the existing five-minute cloud job ceiling.
The 23 Required identities, docs-only skips and shared verification build are
unchanged. See the [scope and remaining provider work](v5x/v5.1/PHASE_6_CLOUD_CONTROL.md).


### Phase 6C3C3 owned startup qualification

The existing `verify-v51-phase6-cloud-provider.sh` gate additionally runs guest
access/startup regressions and nine retained HTTP/block-model startup cases under
a separate 120-second backstop. Its existing `v51-cloud-provider` artifact always
retains these receipts alongside provider evidence. The Cloud runner (no GCP)
job, Required identities, docs-only behavior and five-minute job ceiling remain
unchanged. This adds Python and local SSH key generation only; it performs no SSH
connection, block-device write, Java build or cloud access. See the
[startup scope](v5x/v5.1/PHASE_6_GUEST_STARTUP.md).

### Phase 6C3C4 loopback SSH delivery qualification

The existing provider gate now includes authenticated helper installation and
receipt tests plus a real loopback OpenSSH qualification with its own 120-second
backstop. CI installs the server dependency only when missing and prepares the
standard runtime directory. This job has a ten-minute ceiling (previously five)
to include dependency setup and all three bounded qualifications; measured workload
limits are unchanged. The daemon runs as the job user, with ephemeral keys
outside the retained provider artifact. The existing provider artifact retains all
eight positive/negative SSH scenarios and failed installations. The guest package
gate includes the closed helper payload and dependencies in its existing exact-build
inventory. Job dependencies, Required coverage, measurement thresholds and paid
cloud permissions are unchanged. See
[the delivery contract](v5x/v5.1/PHASE_6_GUEST_DELIVERY.md).

### Phase 6C3C6 isolated root admission

Accepted through PR #237 / exact-master CI `36281785824` attempt 1, all 27 jobs.

The provider gate now accepts `--allow-sudo-namespace`, passed explicitly by CI.
It first tries an unprivileged user/mount namespace; the explicit flag permits a
noninteractive sudo namespace fallback on hosted runners that disallow user
namespaces. All system binds are recursively read-only inside the private
namespace. Only the qualification's private chroot is writable. No host account,
SSH configuration, host mount table or block device is changed.

The same gate retains six modeled root-admission lifecycle cases and an additional
120-second isolated-root qualification (eleven receiver cases and three owned
controller cases). It tests real root file ownership with fixture NSS/metadata;
it does not claim IAP or actual cloud sudo execution. The existing provider
artifact, ten-minute Cloud runner ceiling, Required identities and docs-only skips
are preserved. See [the root-admission contract](v5x/v5.1/PHASE_6_ROOT_ADMISSION.md).

Provider evidence is now packaged under `always()` as
`target/v51-cloud-provider.tar.gz` before upload. The artifact name and retention
remain unchanged. The packer preserves fixture symlinks without following them and
publishes only a complete archive. This prevents the uploader from traversing the
root negative case's `/var` link into host files, the artifact-only failure observed
in PR #237 CI `36274635097`. Downloaded artifacts contain the tarball with the full
original provider tree, including case receipts, partial installations and link
metadata; no failed cases are filtered out.

### Phase 6C3C7 complete package and SSH service integration

The foundation lane adds `guest_package_qualification` with a 900-second outer
limit, three modes, seven distinct service installations, thirty warmup calls,
lost command reply, collection checks and process shutdown. Seven complete packages
travel over actual loopback SSH in bounded 1 MiB parts; each transfer loses one
part response and the installation response, then queries without repeating writes.
All service control and binary collection also use SSH from verified installations
on a shared local filesystem. Independent mount-view bootstrap remains a separate
unchanged gate; its namespace UID mapping is not mixed with SSH-user admission.

The lane prepares OpenSSH using the same conditional install and `/run/sshd`
directory setup as the existing provider job. Private test keys are ephemeral and
excluded from artifacts. The new `v51-guest-delivery` artifact contains delivery
claims/parts/receipts, SSH diagnostics, and service evidence under `services/`, with
seven-day retention and compression level 1. The original bootstrap artifact,
plain guest-service gate, same-run build identity,
Required jobs, docs-only decisions, workflow permissions and paid-cloud behavior
remain unchanged. See [the integration contract](v5x/v5.1/PHASE_6_PACKAGE_DELIVERY.md).

### Phase 6C3C8 owned startup and idle service admission

The foundation lane reuses its exact-source complete guest package for
`guest_owned_qualification`, with a 720-second outer guard. It couples modeled
provider/block state to real loopback SSH, three delivered packages and three
idle services, then verifies stop, retention, cleanup and charged completion.
No workload JVM or paid cloud operation runs in this additional gate. The
existing three-mode SSH/JVM and isolated bootstrap gates remain unchanged.
`v51-owned-services-${sha}` retains complete diagnostics for seven days at
compression level 1. No job or Required-result dependency changes.

### Phase 6C3C9 independent guest evidence

Accepted through PR #240 / master CI `36378226619` attempt 1 (all 27 jobs).

The existing packaged guest, complete-package SSH and isolated-mount gates now
independently replay their seven downloaded member collections against retained
controller transcripts and package-manifest bytes. Each three-mode gate still
executes only its original thirty warmup calls. Replay checks logical answers,
the frozen arrival/JVM request/result chain, process identity and resource bounds;
it does not claim complete cells or physical history. The existing artifacts also
retain `package-manifest.json`, `controller-node-N.json` and `validation-node-N.json`.
The foundation test discovery includes the new portable adversarial replay tests.
No additional Java build, job, workload retry or timing allowance is introduced.
The owned idle gate remains unchanged. See the
[accepted contract](v5x/v5.1/PHASE_6_GUEST_EVIDENCE.md).

### Phase 6C3C10 owned bootstrap (accepted PR #241)

The foundation lane adds a second owned qualification with `--bootstrap` and
the same exact-source package. Its 720-second outer guard contains the original
600-second preparation budget, public bootstrap and idle-service lifecycle. Source
preparation and three local public bootstrap JVMs execute; no timed workload JVM
or measured cell executes. Three receivers use independent mount views and real
loopback SSH install/seal/query controls. Source parts use explicitly shared local
paths, so this does not qualify binary cloud source transport.

CI explicitly supplies `--allow-sudo-namespace` to preserve native UIDs for the
authenticated package receiver's ancestor checks. The helper makes mounts private
and drops back to the original user. No host mount or block device is changed.
Completed install/seal replies are discarded once; the gate requires original
receipt queries with no repeated mutations. Group manifest/genesis/source checks
precede all service launches. Preparation failures retain claims and still enter
the owned cleanup/accounting path.

`v51-owned-bootstrap-${sha}` retains producer and receiver backings, package
provenance, local seals, SSH diagnostics and controller records for seven days at
compression level 1. Private keys are excluded. The original idle gate, job graph,
Required dependencies, measured windows and paid workflows remain unchanged. See
the [accepted contract](v5x/v5.1/PHASE_6_OWNED_BOOTSTRAP.md).

### Phase 6C3C11 bounded source transfer (accepted PR #242)

The existing owned-bootstrap step adds `--source-transfer`. The same 720-second
outer guard and 600-second original preparation deadline now cover binary source
chunks over authenticated loopback SSH. Each receiver is checked for an unused
source destination; lost begin, first-chunk and finish replies require three
queries with no mutation replay. All three transfers complete, then the producer
export paths are removed before the first import. Existing independent mount,
public bootstrap, idle-service, cleanup and accounting checks remain required.

The existing `v51-owned-bootstrap-${sha}` artifact also retains source descriptors,
chunk/finish claims and bytes, intent/query records and six extra fresh-check
files. Its retention/compression settings are unchanged. No new job, build,
workflow permission, workload window or paid-cloud execution is introduced.
The standalone one-receiver SSH gate is available for unprivileged local
qualification; it does not substitute for the owned three-receiver CI gate.
See [the source transfer contract](v5x/v5.1/PHASE_6_SOURCE_TRANSFER.md).

### Phase 6C3C12 authenticated source producer candidate

The existing owned-bootstrap command adds `--producer-source`. Preparation and
export download now enter node-1's installed package over the same pinned SSH
endpoint; the controller reads only its verified download cache. The gate loses
one completed prepare response and interrupts one chunk per member. It requires
one preparation, two queries, three manifests and three extra immutable chunk
reads, then hides producer exports before receiver transfer. All prior receiver,
bootstrap, independent-mount, service and cleanup checks remain required.

The same owned-bootstrap artifact additionally retains producer claims, cached
exports, interrupted download prefixes and bounded read diagnostics. No job,
Required dependency, timed window, timeout, build, upload policy or paid workflow
changes. The unprivileged single-receiver source gate accepts the same option for
local qualification. See [the producer contract](v5x/v5.1/PHASE_6_SOURCE_PRODUCER.md).

### Phase 6C3C13 owned automatic healthy workload

PR #243's producer/bootstrap is accepted at master
`eb56fa6d2565770bd8aac7f76e484834f563a0f3`, exact-master CI `36407418156`
attempt 1 (all 27 jobs). The same required owned-bootstrap step now adds
`--workload`: one automatic experiment healthy tape (90 calls), five discarded
submit replies with original-ID query recovery, stopped collection, independent
logical replay and owned cleanup/retention. All three native-UID mount views,
source/package negatives, the 720-second outer bound, artifact name and Required
job graph remain. Provider/block observations are still modeled; physical history
and full remote qualification remain false. See the
[owned workload scope](v5x/v5.1/PHASE_6_OWNED_WORKLOAD.md). PR #244 accepted this
bounded slice at master `71ca5d9e52139815a5bd4dfddf330c4d0d9fe800`, exact-master CI
`36462747697` attempt 1 (27 jobs). It does not accept a complete experiment or
enable paid runs; the original collection failure remains recorded.


### Phase 6C3C14 owned physical evidence

PR #244 is accepted at master `71ca5d9e52139815a5bd4dfddf330c4d0d9fe800`,
exact-master CI `36462747697` attempt 1 (27 jobs). The existing owned-bootstrap
step adds `--physical` to `--workload`: collect only each stopped voter's authority,
independently replay the three sealed authorities and original causal/read traces,
and require ten exact negative results. Original archive parts remain portable.
The 720-second outer bound, 300-second healthy mode ceiling, frozen windows,
27-job Required graph and artifact retention remain unchanged. This qualifies one
automatic healthy cell; full remote and paid flags stay false. See
[physical evidence scope](v5x/v5.1/PHASE_6_OWNED_PHYSICAL_EVIDENCE.md).

PR #245 accepted this slice at master `d07fe8a5ca27e28ebf1b20c157337ed0f078ea5e`,
exact-master CI `36486236193` attempt 1 (27 successful jobs).

### Phase 6C3C15 owned backup/restore

The same owned-bootstrap step adds `--backup`: issue one post-tape backup,
observe the final durable cut, stop all voters and restore once through the
package's published V4.4 entry. Independently decode exported bytes, verify
restored state and bind the original backup response to its physical read barrier.
Discarded submission replies for both new commands must only trigger receipt
queries. The existing 90 calls, deadlines, Required graph and retention remain
unchanged. Synthetic local tests are not protected Linux acceptance; see the
[backup/restore scope](v5x/v5.1/PHASE_6_OWNED_BACKUP.md).

PR #246 accepted this slice at master `2846bbc2758f2336e0ed73dbc45001dfe83d8f6a`,
exact-master CI `36498232963` attempt 1 (27 successful jobs), including the Linux
owned backup/restore gate.

### Phase 6C3C16 owned configured healthy control

The foundation/runtime lane adds a separate 720-second invocation with
`--mode published-v5.0-configured --workload` and the same authenticated
producer/transfer/bootstrap options. It activates node-1 once, runs all 90 frozen
calls, collects stopped evidence and independently validates logical semantics.
Activation and all five window submission replies are discarded; only queries
of the original IDs recover them. The automatic physical/backup gate remains
unchanged. Always retain the new `v51-owned-configured-${{ github.sha }}` artifact;
the Required graph, mode deadlines and paid restrictions are unchanged. See the
[configured control scope](v5x/v5.1/PHASE_6_OWNED_CONFIGURED.md) for qualification
limits and remaining physical/full-preset work.

PR #247 accepted this slice at master `dfae45670330ffe2a3974982bcc020c534861309`,
exact-master CI `36505526404` attempt 1 (27 successful jobs), including the Linux
owned configured workload gate.

### Phase 6C3C17 owned V4.4 healthy candidate

The foundation/runtime lane adds a separate 720-second invocation with
`--mode published-v4.4-local --workload` and authenticated producer, transfer and
bootstrap options. Within the unchanged three-resource topology, only node-1 gets
an owned package, source import, service and V4.4 JVM. One source export and all
90 frozen calls are validated; five lost window submission replies use original-ID
queries. No election, activation or backup command is submitted. Source identity
has no replication authority fields. Always retain `v51-owned-v44-${{ github.sha }}`;
the automatic/configured gates, Required graph, deadlines and cost reservation
remain unchanged. See the [V4.4 control scope](v5x/v5.1/PHASE_6_OWNED_V44.md).


### Phase 6C3C18 configured physical/backup candidate

PR #248 accepted the preceding V4.4 slice at master
`b6c055df306e9e8dbb155924fa4a834fe751e786`, exact-master CI `36514227052`
attempt 2 (27 successful jobs). Attempt 1's V5.0 prerequisite-build failure
remains recorded without inferring a cause from retry success.

The existing owned configured step adds `--physical --backup` within its unchanged
720-second limit. It retains stopped 1.1 authority, independently qualifies actual
forces/quorums/publications/original calls, and restores one final backup in a
separate published V4.4 JVM. Ten physical negatives require exact reasons.
Activation, all five windows, backup and restore use original-ID queries after
lost replies. Artifact names, job graph, Required results and paid restrictions
remain unchanged. See the [configured physical scope](v5x/v5.1/PHASE_6_OWNED_CONFIGURED_EVIDENCE.md).
