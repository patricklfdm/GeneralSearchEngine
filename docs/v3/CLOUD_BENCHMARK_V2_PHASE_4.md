# Cloud Benchmark V2 Phase 4 evidence profile hardening

## Status and authority

This document freezes the Phase 4 implementation contract before profile-hardening
work begins. It specializes the normative
[Phase 0 evidence model](CLOUD_BENCHMARK_V2_PHASE_0.md), audits the profile behavior
already required by [Phase 2 set aggregation](CLOUD_BENCHMARK_V2_PHASE_2.md), and
preserves the [Phase 3 comparison boundary](CLOUD_BENCHMARK_V2_PHASE_3.md). Phase 0 wins
if these documents conflict.

The original roadmap placed evidence profiles after aggregation and comparison. In the
implemented dependency graph, Phase 2 could not construct or validate a run set without
already distinguishing `experiment` from `canonical`. Phase 4 therefore does not add a
second profile implementation. It closes profile-specific test, UX, and documentation
gaps around the one checkpointed set wrapper. Production behavior changes are allowed
only when a frozen profile invariant is proven missing by a focused test.

## Goals and boundaries

Phase 4 must:

- retain exactly two evidence profiles: `experiment` and `canonical`;
- keep profile, benchmark mode, workload preset, and soak diagnostic profile distinct;
- prove the full profile/mode/repeat/provisioning/preset matrix before cloud mutation;
- exercise both profiles through the existing checkpointed set wrapper;
- prove profile choice is immutable across resume, replacement, derivation, aggregation,
  comparison, and registry validation;
- preserve the existing V1 single-run command and exit semantics;
- close profile-specific fake-cloud, Python, CLI, and documentation gates.

Phase 4 must not:

- add a new profile value, profile registry, profile file, or second set wrapper;
- add `--profile` or `--evidence-profile` to `run-cloud-benchmark.sh`;
- reinterpret `GSE_SOAK_PROFILE`, which remains `none` or `jfr` for investigation;
- silently upgrade experiment evidence because it used Standard provisioning, three
  repeats, or a canonical-shaped workload;
- silently downgrade canonical requirements to complete a set;
- relabel, edit, or regenerate a finalized run or set manifest;
- add GCS upload, upload receipts, baseline mutation, GitHub paid workflows, or a hard
  performance gate;
- create a real VM during implementation or CI.

## One public profile route

The shortest one-run experiment remains unchanged:

```bash
./run-cloud-benchmark.sh full
```

The only public multi-run profile route is:

```bash
./run-cloud-benchmark-set.sh \
  --evidence-profile PROFILE \
  --repeats N \
  [--preset ID] \
  [--dry-run | --confirm-paid-run] \
  MODE
```

`PROFILE` and `N` remain explicit for a new set. Phase 4 does not introduce implicit
wrapper defaults. The prompt's one-run experiment default is satisfied by the unchanged
V1 command; an explicit wrapper experiment declares `--evidence-profile experiment
--repeats 1`.

Options for a new set are rejected on `--resume` and `--replace`. Those forms read the
profile, mode, preset, repeat count, source, and frozen controls only from the immutable
`set-plan.json`:

```bash
./run-cloud-benchmark-set.sh \
  --resume benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --confirm-paid-run

./run-cloud-benchmark-set.sh \
  --replace benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --slot N \
  --reason TEXT \
  --confirm-no-score-selection \
  --confirm-paid-run
```

No resume-time environment variable or CLI option may change the stored profile.

## Profile namespace

The canonical schema spelling remains:

```text
evidenceProfile
```

The public V2 wrapper spelling remains:

```text
--evidence-profile
```

If a V2-only shell boundary needs an environment spelling, the only permitted name is:

```text
GSE_BENCHMARK_EVIDENCE_PROFILE
```

Phase 4 does not require an environment alias where an explicit CLI argument already
exists. The variable must never override a conflicting explicit argument, be forwarded
to the VM as workload configuration, or be read by the V1 orchestrator. The following
names retain unrelated meanings or remain forbidden:

```text
GSE_SOAK_PROFILE       # investigation profiler: none or jfr
--profile              # not an evidence-profile option
profile                # not a schema replacement for evidenceProfile
```

## Frozen eligibility matrix

| Evidence profile | Modes | Provisioning | Repeats | Preset | Registry eligible |
|---|---|---|---:|---|---|
| `experiment` | every supported V1 mode | Spot or Standard | 1–10 | optional supported preset | never |
| `canonical` | `full`, `concurrency`, `soak`, `all` | Standard only | 3–10 | exact mode-owned preset | after Phase 5 review/upload only |

Supported experiment modes are:

```text
quick
full
concurrency
soak
investigation
stabilized-investigation
all
```

The canonical preset mapping remains:

| Mode | Required preset |
|---|---|
| `full` | `v3-production-full-v1` |
| `concurrency` | `v3-production-concurrency-v1` |
| `soak` | `v3-production-soak-v1` |
| `all` | `v3-production-all-v1` |

`quick`, `investigation`, and `stabilized-investigation` remain experiment-only even on
Standard provisioning with three or more repeats. A canonical request with Spot,
fewer than three or more than ten repeats, an ineligible mode, a missing preset, or a
different preset fails with exit `2` before a workspace or cloud resource is created.

An experiment preset may be omitted. When supplied, it must be one of the supported
versioned preset IDs and must remain compatible with the selected mode. Phase 4 does
not invent an experiment preset or copy current ad hoc environment overrides into a
new named preset.

## Experiment evidence contract

An experiment set is intended for cheap development or controlled scientific work:

- the wrapper default provisioning remains Spot unless the user explicitly chooses
  Standard;
- one declared slot is the ordinary wrapper experiment;
- multiple slots still represent separate V1 VM lifecycles;
- schema-0, missing strict environment facts, Spot, dirty-source, or retained-VM facts
  remain warnings or ineligibility facts according to the Phase 1 contract;
- selected members have status `VALID_EXPERIMENT`;
- a finalized set has `evidenceProfile=experiment` and
  `status=VALID_EXPERIMENT_SET`;
- it is never directly comparable as canonical evidence and is never registry eligible.

Using Standard, a canonical mode, a known preset, three or more members, or a strict
environment fingerprint does not promote the evidence. Promotion requires a new run
requested as `canonical`; editing the existing profile would break its manifest,
checkpoint, set identity, and checksums.

## Canonical evidence contract

A canonical set is intended for release/version evidence and requires:

- an explicit `canonical` request;
- Standard provisioning before slot 1;
- 3 through 10 predeclared independent slots;
- an eligible canonical mode and its exact frozen preset;
- a clean exact pushed source commit;
- one exact resolved image and frozen project, zone, machine, network/SSH, JVM, disk,
  runtime, and workload controls;
- `VALID_CANONICAL_MEMBER` for every selected member;
- compatible schema-1 suite, environment, configuration, and metric identities;
- ordinary cleanup and independent VM lifecycle proof for every member.

The exact JDK build cannot be known before the first apt-based VM bootstrap. It remains
part of each member's environment fingerprint. A package change between slots makes
the set incompatible; Phase 4 does not normalize Java versions or rerun a valid slot.

A finalized canonical set has `evidenceProfile=canonical` and
`status=VALID_CANONICAL_SET`. That status is necessary but not sufficient for registry
registration: Phase 5 must additionally provide verified durable upload receipts and
human-reviewed immutable naming.

## Checkpoint and identity invariants

`set-plan.json` is the sole profile authority after initialization. It records the
profile before slot 1 and is bound by `planSha256` in every checkpoint. The profile also
participates in:

- expected member status during attempt validation;
- compatible-member checks;
- minimum final member count;
- final set status;
- the content-addressed set identity payload;
- Phase 3 direct/exploratory comparison eligibility;
- baseline registry validation.

Changing only the JSON spelling, checkpoint, member status, final status, or set ID
must be detected as a checksum, plan, compatibility, or identity contradiction. There
is no profile migration operation.

Every declared slot keeps the Phase 2 attempt/replacement semantics. Profiles do not
change which failures are replacement eligible, permit score-based member selection,
or allow a valid slow run to be discarded.

## Dry-run and mutation ordering

For both profiles, a new-set dry run must:

1. validate CLI form, profile, repeats, mode, preset, and provisioning;
2. verify a clean source and exact commit;
3. resolve project, zone, machine, exact image, JVM, disk, network/SSH, runtime, and
   preset controls;
4. validate the immutable set plan with the Python utility;
5. invoke the existing V1 dry-run preflight only;
6. print profile, slot count, preset, exact image, worst-case VM count, and sequential
   cleanup behavior;
7. leave no workspace, VM, disk, upload, registry edit, or tracked file.

Any new-set command that could create a VM requires `--confirm-paid-run`. Missing
confirmation fails before workspace creation. A resume that only finalizes already
valid members may complete without creating a VM; the existing Phase 2 state machine
remains authoritative.

## Compatibility and comparison consequences

Phase 4 does not change Phase 3 comparison arithmetic:

- only two compatible `VALID_CANONICAL_SET` inputs are directly comparable;
- any run or experiment set requires `--allow-exploratory`;
- an experiment/canonical pair can be at most `COMPARABLE_WITH_WARNINGS`;
- the exploratory flag does not waive machine, zone, image, Java/JVM, workload,
  schema, or metric-signature mismatches;
- an experiment can never resolve as a named canonical baseline;
- performance classifications never upgrade evidence quality.

No Phase 4 test may register a placeholder baseline. The tracked baseline registry
remains read-only and empty unless a later reviewed Phase 5 change supplies a valid
upload receipt.

## Exit behavior

Phase 4 introduces no exit code:

| Exit | Profile-specific meaning |
|---:|---|
| `0` | valid dry run, completed set operation, or local validation |
| `2` | invalid profile/mode/repeat/preset/provisioning/CLI combination |
| V1 exit | the exact existing single-run lifecycle failure from a selected slot |
| `80`–`82` | Phase 1 evidence/schema/contradiction failure |
| `83` | incomplete or incompatible set |
| `84` | valid evidence not comparable under the requested Phase 3 mode |
| `85` | registry validation or local binding failure |

An experiment result, Spot warning, or suspected performance regression is not by
itself a failed process. Evidence validity, not desirability of a score, controls exits.

## Implementation rule

Phase 4 begins with tests against the existing implementation. If all frozen behavior
already passes, production scripts and schema versions remain unchanged. A production
change requires a focused failing test that demonstrates one of these contract
invariants is absent. The smallest compatible fix is preferred; no refactor is justified
only to make Phase 4 appear larger.

The expected implementation surface is therefore primarily:

```text
scripts/cloud/test_benchmark_v2.py
scripts/cloud/test-benchmark-set-runner.sh
.github/workflows/ci.yml (only if a new test entry is needed)
docs/v3/CLOUD_PERFORMANCE_TESTING.md
```

The Phase 2 manifest, aggregate, checkpoint, audit, and set identity schema versions
remain `1` unless a real incompatible schema defect is discovered and reviewed before
implementation.

## No-cost test matrix

Required Python plan/profile coverage:

- experiment repeats `1` and `10` accepted; `0` and `11` rejected;
- canonical repeats `3` and `10` accepted; `1`, `2`, and `11` rejected;
- every experiment mode accepted with appropriate controls;
- canonical `full`, `concurrency`, `soak`, and `all` accepted with exact presets;
- canonical `quick`, `investigation`, and `stabilized-investigation` rejected;
- canonical Spot, missing preset, wrong-mode preset, and unknown preset rejected;
- experiment unknown preset rejected without inventing a fallback;
- profile is included in plan/checkpoint hashes and final set identity;
- experiment and canonical expected member/final statuses cannot be interchanged.

Required wrapper/fake-cloud coverage:

- existing canonical dry run remains mutation-free;
- a one-slot Spot `quick` experiment completes through a fresh fake V1 lifecycle;
- the experiment final manifest is `VALID_EXPERIMENT_SET` and retains one member;
- an experiment does not silently receive a canonical preset;
- an unconfirmed experiment creates no workspace or fake VM;
- resume reads the immutable profile and rejects new-set profile arguments;
- `run-cloud-benchmark.sh --evidence-profile ...` remains an unknown V1 option;
- `GSE_SOAK_PROFILE=jfr` remains independent from evidence-profile choice;
- profile errors launch no later slot and preserve underlying V1/Phase 1 exits.

Required cross-phase coverage:

- Phase 1 canonical and experiment run derivation remains byte-stable;
- Phase 2 aggregation and replacement tests remain unchanged;
- Phase 3 direct comparison rejects experiment evidence;
- explicit exploratory comparison preserves its warnings and missing-variation rules;
- registry validation accepts only canonical entries;
- shell syntax, fake-gcloud lifecycle, soak, reactor, compatibility, release, and
  reproducibility gates remain green.

All tests use temporary repositories, fake gcloud, synthetic evidence, and local
filesystem fixtures. They must not authenticate, create a VM, contact GCS, mutate IAM,
or execute an arbitrary command supplied through an untrusted environment variable.

## Phase 4 completion checklist

- [ ] The existing V1 command and CLI remain unchanged.
- [ ] Exactly one checkpointed V2 set wrapper owns evidence-profile selection.
- [ ] Experiment and canonical eligibility matrices are enforced before mutation.
- [ ] Experiment profile is covered end to end through a one-slot fake Spot lifecycle.
- [ ] Canonical mode, repeat, provisioning, preset, and environment rules remain strict.
- [ ] Profile state is immutable and bound through plan, checkpoint, members, set, comparison, and registry.
- [ ] Evidence-profile spelling remains distinct from `GSE_SOAK_PROFILE` and workload mode.
- [ ] Experiment evidence cannot be promoted, directly compared, or registered as canonical.
- [ ] No schema bump or production change exists without a focused failing invariant test.
- [ ] No GCS, receipt, registry mutation, paid workflow, product, or real-cloud work is included.
- [ ] Profile-specific tests and all existing no-cost gates pass.
