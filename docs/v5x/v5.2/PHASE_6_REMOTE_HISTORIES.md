# V5.2 Phase 6AC complete receiver histories

**Status:** whole-history receiver execution and five representative local
histories passed independent original/relocated replay. The existing five-mode
smoke bridge and default detached command entry also passed. This stage does not
qualify three cloud hosts, a full measured cohort or a cloud member.

## One controller, separate receiver roots

`remote_history.py` owns preparation, process generations, fault controls, stopped
collection and portable replay for all 33 closed suite histories. The existing
five-mode smoke bridge uses this same owner. M01, M02/M03 and M04 call their
original `observe` functions. No shorter M01 variant, new offered schedule,
business retry or successful-outcome filter is introduced.

Each receiver bootstraps its own sealed authority from the same immutable seed.
The exact read/capacity and fault configuration files are copied before bootstrap
and checked again after the original processes stop. Loaded JARs, compiled helpers,
source fingerprints, original roots and actual topology remain bound to evidence.
The adapter permits `local-no-gcp` only; private addresses alone cannot pass the
host-identity validator or authorize provider work.

M01 keeps all 60-second warmup and 120-second measurement windows. M02 preserves
its selected voting follower and original waits. M03 preserves saturation plus
the reserved writer. M04 owns only the declared leader SIGKILL/generation-2 reopen
or the snapshot follower's partition/heal. The crashed authority is copied before
reopen and independently inspected against that receiver's original sealed path.

Partition files are atomic at each receiver. The complete cut is installed at
all three roots before the shared controller records its fault milestone and
offers fault-dependent business work. Cleanup independently attempts every heal
and every process stop, even if another cleanup action fails. Original execution
errors and cleanup errors remain separate; collection cannot accept a live voter.

## Stable command ownership and unchanged evidence

The [Phase 6AB owner](PHASE_6_REMOTE_OWNED_HISTORY.md) now accepts any one of the
closed selected histories. Its semantic command slot still submits exactly once.
A lost response only causes queries of that original command; duplicate requests
return its original receipt, and a new command ID for the same slot rejects.
The local command selection is still explicitly synthetic and grants no paid
admission. Cancellation does not authorize another execution.

Formal history identity and physical replay resolve each node's loaded paths and
seals using its independently retained receiver map. Original local histories
retain their original single-root handling. Missing/partial remote bindings,
changed topology or incomplete cleanup reject before replay. The same existing
M01–M04 validators run on both original and relocated bytes, including every
existing exact negative reason. Read/write outcome counts include failures.

Process IDs and timing comparisons are still valid only for this local placement.
A future cross-host backend must supply independent boot/process/resource identity
and appropriate clock domains; this stage does not loosen those requirements.

## Local entry and acceptance boundary

The optional operator gate is:

```bash
scripts/verify-v52-phase6-remote-histories.sh --skip-build
```

Use it after a current reactor package. It executes five complete representative
histories: candidate explicit-strong M01 repetition 1, M02 above/1000 ms, M03 P=4,
retained leader restart, and follower snapshot recovery. Every history uses a
fresh detached command executor, loses the first response, queries the original
result, checks a duplicate from another process, and rejects an alternate ID.
Long-running observations print their history, stage, elapsed time, original
command state and submission/query counts approximately once per minute.

A selected history can also run in a fresh output directory:

```bash
python3 -u -m scripts.v52.remote_history_qualification \
  target/v52-remote-histories/operator-run-1 --history m03-p65
```

The entry stops on the first failure and preserves completed and failed evidence;
it does not retry or splice histories. Operational observation allowances warn,
while public/API deadlines, frozen controller gates and bounded repeated-error
failure remain. The five representative probes are not a complete 28-history
cohort or the five-member cloud suite. Even a PASS retains
`qualifiedMeasurement=false`, `fullRemoteQualification=false`,
`syntheticSelection=true` and `paidCloud=false`.

New regression tests run inside the existing measurement CI gate. The optional
full-window probes are not silently added to every normal CI run. Remaining work
is persistent cross-host process/command transport, owned lifecycle qualification,
complete member aggregation and final exact-source protected CI/provider admission.

## Retained local validation

Validation used the working tree based on `1d77ddc65b47f9153c5b6f35da19265f791b7043`,
with checkout fingerprint
`0b1b41474fa047fcf24a0ed88073d908984c6f01e1fafcda82cbf588c2576062`.
All five complete histories passed in
`target/v52-remote-histories/run.lRJcu2/evidence/receipt.json`:

| History | Original reads | Original updates | Negative cases at each location | Elapsed seconds |
| --- | ---: | ---: | ---: | ---: |
| M01 candidate explicit-strong r1 | 1801 | 180 | 18 | 1031.240 |
| M02 above/1000 ms | 31 | 4 | 15 | 30.591 |
| M03 P=4 | 5 | 4 | 16 | 29.650 |
| M04 retained leader restart | 4 | 4 | 16 | 41.628 |
| M04 follower snapshot | 4 | 4 | 14 | 33.591 |

The 158 negative rejections cover both original and relocated evidence. All five
histories submitted once, returned the identical duplicate receipt and rejected
an alternate command ID. Original call counts include non-success outcomes;
this qualification makes no success-rate or performance-threshold claim. M01's
elapsed time includes the full independent evidence replay, not just its frozen
180-second offered window.

The legacy five-mode bridge and default detached minimum smoke passed at
`target/v52-remote-histories/legacy-bridge/receipt.json` and
`target/v52-remote-histories/legacy-owned/receipt.json`. All 305 V5.2 Python tests
and 21 CI tests passed. Existing unchanged Java artifacts were reused, with helper
compilation performed by each fresh history; no new reactor build or full
28-history cohort was run. Documentation results were added after execution;
the receipts retain their actual pre-summary source fingerprint. Receipt hashes,
all original outcome counts and checked-file hashes are retained under
`target/v52-remote-histories/validation-summary.json` and
`target/v52-remote-histories/validated-worktree-files.json`.
