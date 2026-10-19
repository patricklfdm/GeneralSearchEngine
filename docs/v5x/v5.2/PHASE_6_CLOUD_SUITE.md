# V5.2 Phase 6X cloud suite selection

**Status:** the logical suite and source-bound selection validator are implemented
and locally tested. This stage does not execute a workload, admit a cloud request
or qualify a cloud result. Local freeze `a40c510` and hosted run `38875654052`
remain unqualified after the failures documented in
[measurement repairs](PHASE_6_MEASUREMENT_REPAIRS.md). Their original evidence is
retained. The pending cloud suite now derives the corrected M02 selected voting
follower and mandatory M01 read-capture negatives; its canonical digest is
`f8556b7e143e0fc5d85664503bc02a6e583b7227215a3258c9ea8545981cd5b0`.
This update does not rebind any old local freeze, measured history or cloud receipt.
The subsequent [hosted cohort](PHASE_6_HOSTED_ACCEPTANCE.md) passes all 28 formal
histories on its new exact source; cloud selection still grants no execution authority.

## Complete suite, with any starting member

[phase6-cloud-suite.json](phase6-cloud-suite.json) freezes the following grouping.
`cloud_suite.py` checks both its canonical digest and its derivation from the
existing M01–M04 profiles. This is a new cloud grouping; it does not replace the
local machine plan or change any offered business workload.

| Member | Complete histories | Reads including setup | Updates | M01 window seconds |
| --- | ---: | ---: | ---: | ---: |
| experiment | 5 untimed consumer readiness histories | 55 | 15 | 0 |
| failure-drill | 9 M02 + 2 M03 + 2 M04 | 358 | 45 | 0 |
| canonical-1 | 5 M01 modes, repetition 1 | 9,005 | 900 | 900 |
| canonical-2 | 5 M01 modes, repetition 2 | 9,005 | 900 | 900 |
| canonical-3 | 5 M01 modes, repetition 3 | 9,005 | 900 | 900 |
| Total | 33 | 27,428 | 2,760 | 2,700 |

Every canonical mode keeps its 60-second warmup, 120-second measured window,
1,980 offered calls, original target and 125-second response observation allowance.
The nine minimum-progress, two capacity and two recovery profiles retain their
parameters. Experiment uses the existing untimed 11-read/3-update consumer history
per mode; it cannot substitute for a shorter canonical measurement. Formal
histories keep all 439 declared negative cases per location. The remote adapter
must also qualify the experiment's original smoke checks after collection.

Any of the five members may be selected first. One member runs at a time and each
history stays whole on its original session, source and retained lease. Failed
attempts remain separate; a successful fragment cannot fill part of a later run.
No business command or workload is replayed after a lost response. Observation
and immutable evidence download may reconnect under their own qualified protocols.

## Binding and acceptance boundaries

Each immutable selection binds exact source, checkout hash, sequence, suite and
program hashes, shared-build manifest, deployable package and published controls.
It has a unique attempt identity and includes the entire selected member profile.
The complete-set validator rejects missing/extra members, duplicate members or
attempts, altered profiles and mixed source/sequence/build/package/control values.
It accepts all 120 member orderings, but always returns
`COMPLETE_SELECTION_NOT_QUALIFIED` and `qualified=false`.

These functions do not read GitHub/GCP, dispatch processes, mutate resources or
assert that a supplied source/hash was independently admitted. A later cloud
entry must obtain those facts from fresh trusted observations, and a later
aggregate must replay the actual retained bytes. Selection JSON claiming PASS is
not sufficient evidence. V5.1's one-off cross-source continuation exception is
not inherited. No V5.1 fixture, identity, workflow check or historical receipt is
changed.

## Remote implementation still required

1. Admit explicit three-host private topology. Bootstrap each receiver through the
   public API from the same immutable verified source backup; never transfer a
   runnable replica seal to a different filesystem identity.
2. Own a persistent bounded command path or a whole-history guest driver. Preserve
   the original offered clock and all outcomes; do not perform a fresh SSH setup
   for each offered read or treat an uncertain response as permission to resubmit.
3. Retain each guest's original path and process identity. Map collected authority
   bytes explicitly during independent original/relocated replay without rewriting
   seals or subtracting timestamps from different host clocks.
4. Qualify the complete owned lifecycle without GCP, including disconnects,
   partial preparation, original fault schedules, evidence collection and cleanup.
5. Bind a dedicated V5.2 exact-master/full-CI step and fresh provider/IAM/cleanup
   facts. The operator pushes, merges and manually triggers any paid experiment.

Operational lifecycle time and cost budgets remain soft warnings. This does not
remove finite API deadlines, the declared measurement observation rules, lease
ownership/expiry checks or decoder/resource bounds. No current image, quota,
permission, pricing or cloud readiness is inferred from the old V5.1 configuration.

## Local validation

Eight regression tests cover the exact totals and original profiles, all 120
member orders, incomplete/duplicate/mixed sets, altered selection flags, malformed
identities, frozen-plan drift and input isolation. They are integrated into the
existing V5.2 measurement gate without removing any existing checks. They exercise
planning only and do not count as cloud or formal measurement results.

Validation records are retained under `target/v52-cloud-suite/` in the development
worktree. Protected exact-source CI remains pending. No production Java, POM,
workflow topology, provider settings or published controls change in this stage.
