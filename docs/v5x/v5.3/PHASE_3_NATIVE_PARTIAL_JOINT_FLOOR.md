# Phase 3 native partial joint-floor recovery entry

The [conditional writer matrix](PHASE_3_PARTIAL_JOINT_FLOOR.md) now has an entry
into the complete [native 5-REPLACE history](PHASE_3_JOINT_FLOOR_RECOVERY.md).
Four copy ordinals at directory creation, manifest force, first image force and
first metadata-member force form **16 complete histories**, not history fragments.

`V53NativePartialJointFloorTest` reuses actual bootstrap, learner, old quorum,
INTENT, joining installation and seed maintenance. Node-2 interrupts the handoff
writer with an I/O exception at the exact declared callback. Remote copies are
written in generation-digest order and the local copy is last. No file is edited
or truncated. The same directories close/reopen, recover the four originals over
native TCP, complete maintenance and continue through FINAL, stable BARRIER and
cold snapshots. Resource bounds and the original 12-minute maintenance deadline
are unchanged.

This covers incomplete copy bodies, not torn writes inside a file or halt/SIGKILL.
The [separate process entry](PHASE_3_NATIVE_PROCESS_JOINT_FLOOR.md) now provides
32 whole-history halt/SIGKILL executions; its complete replay/admission remains open.
The initial writer receives already-held original copies at the seed-maintenance
boundary; subsequent recovery performs real remote acquisition. It does not
qualify initially remote-acquired floor construction or a complete simultaneous
resource maximum.

## Independent replay

The reader derives the exact handoff prefix from independently reconstructed
generations. Only directories and bytes written by that prefix may be present
in the interrupted, closed and reopened snapshots. A copy is charged at directory
creation, before its manifest/image is written; absent later copies cannot be
counted as retained. Resumed authority requires every exact original and force.

Whole-history transport/export/floor replay consumes the interrupted and resumed
transactions. Peer, learner, future and allocator/promise state stays continuous
across the same cold boundary. The older complete-copy schema and non-handoff
order remain exact. The new schema requires ordinal, cut and `handoff=true`;
extra fields and process/phase upgrades are rejected. Three cut-metadata negatives
extend the existing seventeen floor negatives. Full original validation precedes
mutations, and unrelated failures cannot count as expected rejection.

## Capture and validation

Each capture records immutable source, command, toolchain, JUnit, compiled classes
and raw inventories. Source-retirement captures remain **inside** that original
raw directory. Only one non-skipped, non-retried test can complete collection.
Collection stays PARTIAL; it is not physical qualification or cohort admission.
Failures remain retained, and execution emits progress every minute.

```bash
python3 -B -m scripts.v53.native_joint_floor_history plan
python3 -B -m scripts.v53.native_joint_floor_history capture \
  target/v53-native-partial-joint/operator-001 \
  --case 4,FLOOR_MEMBER_FORCED --maven /opt/maven/bin/mvn
```

Use the exact catalogue case and a fresh directory for each execution. A final
cohort must share frozen source/build/toolchain/reader and retain all whole
histories. `--source-from` requires a matching unchanged recorded producer.
No hosted workflow or final-source admission is added by this entry.

The capture receipt names the raw directory. All these checks consume that same
original; none reruns the workload:

```bash
python3 -B -m scripts.v53.native_joint_floor_history validate \
  target/v53-native-partial-joint/operator-validation.json \
  --case 4,FLOOR_MEMBER_FORCED --raw <original-raw-directory>
python3 -B -m scripts.v53.joint_floor_recovery_evidence <original-raw-directory> --qualify
python3 -B -m scripts.v53.joint_floor_maintenance_evidence <original-raw-directory> --qualify
python3 -B -m scripts.v53.joint_history_evidence <original-raw-directory> --qualify
python3 -B -m scripts.v53.joint_ledger_evidence <original-raw-directory> --qualify --workers 4
```

The [development receipt](phase3-evidence/native-partial-joint.json) records actual
checks and deferred execution. The full sixteen histories, process-death/torn-file
axes, complete resource maximum and final-source Phase 3 admission remain open.
An available execution entry is not a passed experiment.
