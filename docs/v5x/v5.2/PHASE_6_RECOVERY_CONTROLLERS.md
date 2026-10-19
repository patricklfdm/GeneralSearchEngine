# V5.2 Phase 6R recovery controllers

**Status:** two fresh local development histories execute and pass the general
physical validator. M04-specific process-generation, token/query, resource and
portable negative admission remains open. These are not formal measurements.

## Closed fault schedules

Both cases use the unchanged default minimum-read configuration, three confirmed
setup updates, and an initial strong read at application sequence 4. Every voter
must publish that cut and report a corresponding recovery floor before the fault.
Controller probes are observations; independent replay must verify their physical
events and retained bytes before accepting a measurement.

- `leader-sigkill-retained-restart`: SIGKILL the initial leader, retain its full
  pre-reopen directory inventory, observe a surviving leader, and issue one update,
  one strong read and one read with the original token. Reopen the killed voter on
  its existing directory as generation 2, observe sequence 5, and read with the same
  carried token. Keep the abrupt exit and the three final clean exits separately.
- `follower-snapshot-carried-token`: identify the voter outside the leader's actual
  selected pair, isolate its four directed links, and advance the healthy pair by
  one update and one strong read. Observe the healthy pair's recovery floor while
  the isolated voter remains behind. Heal, require a real snapshot-install hint and
  publication at sequence 5, then issue reads with the old and later tokens on that
  follower. Incremental-only progress or a target that becomes leader is rejected.

Each case has four original updates and four original reads. There are no business
retries, cancelled replacement requests or silent target changes. The bounded
40-second activation and 80-second recovery observation loops preserve failures;
100-ms polling stays below the consumer command bound. Controller clocks describe
observed milestones, not exact process failure time or a failover SLA.

## Fault ownership and cleanup

`measurement-fault.json` accepts only these two cases in candidate-minimum mode.
The Java observer rejects missing declarations, wrong modes, extra fields,
symlinks, oversized inputs and arbitrary/asymmetric link rules. The only nonempty
network rule set is one complete bidirectional single-voter cut. Configuration
and actual dropped frames enter the retained trace. M01–M03 reject fault metadata
or files before process launch and again at evidence admission.

Only owned JVMs are killed. The controller waits for SIGKILL exit before copying
the pre-reopen directory and resumes that same voter once. The network is healed
and every remaining process is stopped even when an execution or cleanup fails.
Cleanup errors are retained separately and cannot hide the original failure.

The observer exposes selected-pair/epoch and snapshot-install hints only after
writing their source event. They do not replace independent selected-basis,
recovery-floor, installed-generation or read-capture validation. Production Java,
wire/storage formats, workload parameters and workflow topology are unchanged.

## Local validation

Eight deterministic controller tests cover exact targets/tokens, both schedules,
stale selection, missing floors, incremental/leader substitution, original-call
failures, complete partition rules, mixed-profile rejection and cleanup failures.
A compiled Java fault probe covers 57 accepted observations and 15 rejected inputs.

Fresh retained development histories under `target/v52-recovery-controller/development-1`
contain seven JVM generations across the two cases. Both pass general physical
quorum/force/publication validation; the killed leader's pre-reopen inventory and
authority also pass independent inspection. This partial result does not yet
establish M04-specific public lifetime, token/query, resource or portable acceptance.

All 196 V5.2 Python tests pass. The unchanged five-mode short gate at
`target/v52-measurement-runtime/run.7yqA9T/evidence` passes 55 reads, 15 updates,
original/relocated physical and V4.4 query replay, 200 evidence-negative rejections,
and the large-package qualification. CI inventory, documentation contract, 628
changed local link targets, shell syntax and whitespace checks pass. No reactor
rebuild or hosted acceptance is claimed for this observer-only stage.

Continue with that independent admission, the complete machine execution freeze
and fresh formal M01–M04 histories under the
[local sequence](LOCAL_DEVELOPMENT_SEQUENCE.md). No paid cloud execution or push.
