# V5.2 Phase 6N portable M01 set admission

**Status:** implementation and local fixture validation passed. No full-size M01
history or complete measured set has executed. Complete machine admission and
M02–M04 schedules remain pending.

## Admit exactly fifteen fresh histories

The set contains exactly five modes × three repetitions. Every expected member
binds the unchanged offered program and its mode/repetition. Before replay starts,
all members must agree on source SHA, checkout fingerprint, JVM identity, workflow
run and attempt. Published V4.4/V5.1 artifacts must match the frozen control hashes.
Candidate modes share the exact candidate JARs and compiled consumer/observer set;
the published mode has its separately compiled baseline set.

Each member has a distinct original evidence path, group ID, history ID and
manifest hash. A copied successful run cannot supply another repetition. Missing,
extra, relabelled, partial or different-attempt members reject. Physical replay
still independently checks the actual domain and source/build binding inside
each stopped history.

## Replay retained bytes instead of trusting a receipt

The set wrapper calls the full member replay itself. Each stopped history is packed
with the large closed-package profile, replayed at its original location, unpacked
to a fresh location and independently replayed again. Actual query answers and
all exact negative case/status/reason results must be identical. A previously
existing inventory must already validate and have the canonical package encoding;
it cannot be silently replaced to bless changed input. Both inventories are checked
again after replay. Archive and inventory hashes are retained.

The wrapper never opens a retained voter with product code. The separate real
V4.4 query process uses its own replay directory. Any failure retains the archive,
relocated bytes, failed receipt and prior completed member receipts. It stops the
set without retrying a business operation or rerunning the failed member.

The final M01 report accounts for 29,700 offered calls: 27,000 reads and 2,700
updates, plus 15 separately labelled setup reads. It reports 2,700 **nominal offered
seconds**, not measured wall-clock duration or runner cost. Outcomes remain grouped
by member. The five modes have different consistency semantics; this admission does
not infer a speedup claim.

Set PASS is still M01-only. `qualifiedMeasurement` remains false until the complete
machine execution freeze and M02–M04 admission are implemented and passed. There is
no newly enabled workload/paid execution CLI or workflow in this stage.

## Validation

Eight deterministic tests exercise all fifteen member identities, complete counts,
mixed source/build/JVM/run/attempts, changed published/candidate artifacts, repeated
domains and incomplete members. Real package round trips with an injected checker
verify that divergent or missing negative results fail while preserving the archive.
A failed third member retains the first two receipts and is called only once.
These fixtures test orchestration and do not establish physical authority.

The unchanged five-mode retained integration bindings are also compared to verify
that independently compiled candidate modes actually share the expected class/JAR
set. All 165 V5.2 Python tests passed, along with CI inventory, documentation
contract, changed local links, shell syntax and whitespace checks. No fresh reactor,
workload or hosted result is claimed. Logs and summaries are retained at
`target/v52-m01-set`.

Continue with M02–M04 and machine admission under the
[local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md) before formal execution.
