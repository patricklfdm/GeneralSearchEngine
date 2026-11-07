# Complete verified-backup joining execution

This is the development integration entry for the full required-four history
from a nonempty verified durable backup with segmented observations. It is
separate from the frozen EMPTY supplemental cohort and from the simultaneous
resource-maximum qualification.

## Exact history and collection

The explicit profile is `5-REPLACE-required-four-backup-segmented` in
`scripts.v53.required_four_resource_run`. It selects only
`V53BackupJoiningQualification#verifiedBackupCompletesReplacementFinalAndStableBarrier`.
The class name excludes it from ordinary `*Test` discovery. The lightweight
`V53BackupJoiningQualificationTest` checks admission of its observation switches;
it does not execute the history.

The native entry uses the existing three-document seed at application sequence
731 and the existing five-voter required-four REPLACE history. It invokes
`requiredFourFromVerifiedBackup` with `SEGMENTED_BACKUP`, including early learner
startup, native initialization, replacement FINAL, stable BARRIER, cold recovery
and original ownership/custody observations. The external backup's original
files must remain unchanged. All twelve existing observation switches must be
explicitly enabled before the seed is created. Source-fault injection is rejected.
No workload shortening, measurement retry, runtime budget increase or history
stitching is introduced. The dedicated command sets a 4 GiB Java heap ceiling;
the existing history's 40-minute lifetime remains unchanged.

Capture runs one exact test in a fresh source copy, records source/build/reader/
toolchain hashes and runs collection from that same immutable copy. A once-per-
minute progress line includes the process ID, elapsed time and latest log line.
Capture and collection return only `PARTIAL`. They retain failures and reject
existing output paths. The backup collector validates the segmented registry
and all of its original segments, alongside the required physical/resource
sidecars. The 128 GiB whole-original bound and unchanged per-owner/member limits
are described in [segmented evidence](PHASE_3_SEGMENTED_EVIDENCE.md).

## Independent admission

Verification rechecks exact source, compiled bytes, portable toolchain, reader,
command, single unretried JUnit method, process exits and original collection.
It then runs `required_four_resources.qualify_backup(...,
wire_layout='SEGMENTED_BACKUP')`, including all independent semantic, physical,
network, export, ledger and resource preconditions before the negatives.
All 149 exact negative results are required: the existing 147 resource cases,
the declared-EMPTY rejection and the declared-JSON rejection. Producer and
verifier receipts bind both `bootstrapSource` and `wireLayout`; neither marker
can select the caller's policy. Original/source pins are checked again after
replay. Missing or unrelated negative errors cannot qualify.

The result scope is `required-four-backup-observed-ownership`. It does not claim
the simultaneous byte maximum, final-source cohort or Phase 3 completion.
The existing `5-REPLACE-required-four` command, 147 negatives, receipt shape,
512 MiB raw bound, hosted workflow and supplemental cohort remain EMPTY. A
backup receipt cannot replace that cohort member.

## Commands for a complete run

These commands are provided for the later long acceptance batch; adding this
entry does not mean it has been executed. Run from the intended frozen checkout
with its pinned tools and offline Maven dependencies available:

```bash
qualification_dir="target/v53-backup-execution/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -B -m scripts.v53.required_four_resource_run capture "$qualification_dir/producer" \
  --profile 5-REPLACE-required-four-backup-segmented --maven /opt/maven/bin/mvn &&
python3 -B -m scripts.v53.required_four_resource_run verify "$qualification_dir/verification" \
  --profile 5-REPLACE-required-four-backup-segmented \
  --producer "$qualification_dir/producer" --pins "$qualification_dir/producer/pins.json"
```

Keep the complete producer, raw evidence, logs and verification directory,
including any failure. Each attempt needs a new output directory; resuming by
combining pieces of different histories is not supported. The existing EMPTY
hosted adapter is not a backup transport entry. The separate
[small-backup hosted entry](PHASE_3_BACKUP_HOSTED.md) now binds this profile to
three exact-attempt jobs and documents its distinct artifact-capacity admission.
It has not been dispatched or credited as a native execution.

## Current evidence and remaining work

The [execution-entry development index](phase3-evidence/backup-execution-development.json)
records lightweight Java and Python checks only. Synthetic producer tests cover
the exact native command, single original, source/build bindings, source/layout
markers, mandatory 149-negative contract, retained failure and rejection of a
backup as the ordinary EMPTY supplement. They do not supply native evidence.

Full positive backup execution and independent admission remain pending, followed
by whole-reader maximum-input memory and the real simultaneous-resource history.
Final-source cohort and frozen-coverage obligations remain open.
