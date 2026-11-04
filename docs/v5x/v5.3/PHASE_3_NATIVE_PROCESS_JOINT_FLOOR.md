# Phase 3 native joint-floor process entry

The [native partial writer entry](PHASE_3_NATIVE_PARTIAL_JOINT_FLOOR.md) now has
a separate process-death producer. Four copy ordinals, four callbacks and two
death modes form **32 complete 5-REPLACE histories**. These entries are not yet
part of the existing 512-history hosted plan and do not close Phase 3.

## Original ownership and execution

The parent executes the existing bootstrap, learner, old-majority, INTENT and
joining-installation history. At seed maintenance it closes only node-2's
endpoint, transport and owner, verifies drained parent leases, and hands the
same original replica/application paths to a fresh JVM. The other original
voters and the admitted joining owner remain alive.

The child opens those roots and performs actual TCP discovery, prefix and
generation acquisition through `MembershipGenerationMaintenance.beforeGrant`.
It does not deserialize authority tokens, reopen forensic copies, edit a source
or substitute a new quorum. A temporary endpoint exposes the original joining
owner, just as in the existing recovery fixture. Remote floor copies are forced
in generation-digest order; the local copy is last.

At the selected `FLOOR_COPY_CREATED`, `FLOOR_MANIFEST_FORCED`,
`FLOOR_IMAGE_FORCED` or `FLOOR_MEMBER_FORCED` callback, the child blocks while the
parent verifies the live replica lock and snapshots the partial original. The
parent then acknowledges `halt(73)` or sends SIGKILL and requires exit 137. It
checks that the root lock is released and the disk is byte-identical to the
held cut. There is no clean child-owner close in either death path.

The parent reopens node-2 from the original paths, reacquires the exact pending
floor through TCP, finishes ordinary maintenance and continues the same history
through FINAL, stable BARRIER and cold snapshots. The existing storage/resource
bounds and single original 12-minute maintenance interval are unchanged. This
same-host Linux fixture passes the original monotonic start to the child; it
does not reset that interval at launch or recovery.

## Observation and qualification boundary

Each complete child message is retained before acknowledgement. An EVENT is
inserted into the parent's common event order before the child can issue its
next request; acknowledgements are observation barriers, not storage forces.
The raw stdout, control anchors, PID, exact spec, live/released lock checks,
exit status and before/at-cut/after-death snapshots are retained. Truncated or
noncanonical lines fail collection instead of being ignored. Receiving scratch
is retained separately at the held cut and after death; its bytes must agree.
`joint-floor-process`
and `joint-floor-reopened` remain distinct scopes in the unchanged event array.

The focused inspector checks those boundaries, the exact interrupted writer
prefix and resumed floor bytes, and both original copy-transfer transcripts.
Its result stays **PARTIAL** with `processDeathQualified=false` and
`nativeHistoryQualified=false`. It does not replace the full original-first
physical, export-force, maintenance and continuous-ledger replay. The existing
single-reopen reader deliberately rejects this new producer schema.

Shared scope readers now accept an explicit ordered sequence of old-owner opens
as well as their historical single-open declaration. They check distinct scopes,
strictly increasing original event positions, exact CURRENT boundaries where
applicable, and prohibit durable writes from crossing owners. Future/learner,
allocator, slot, grant and CURRENT checks retain all observations. This supports
the upcoming composed reader; it does not itself supply that composition or
reset any derived ledger at a reopen.

The `process_joint_history` reader now composes both cold owners with the complete
original physical, network, export, maintenance and four-ledger derivations.
It derives the interrupted owner's state from bootstrap and the original learner
confirmations, before comparing the sidecar. Both cold snapshots compare against
the continuous ledgers; neither resets them. The initial floor and reacquisition
use distinct native discovery intervals, and only the completed floor can cause
ledger maintenance. Both intervals retain all original force observations.

Expanded process-negative qualification and the frozen 32-history matrix remain
open. The retained receiving scratch still requires
independent ownership and overlapping-resource replay. The representative late local-copy cut cannot stand
in for earlier remote-copy cuts. Torn writes inside files and the full combined
resource maximum remain separate obligations.

Sixteen targeted composition negatives cover child/current overlap, original
allocator rebinding, missing child requests, temporary export ownership, both
partial floor intervals, and resets of each of the four ledgers at each cold
open. The complete unmodified history must pass first. Each mutation changes
one declared file, protects every other byte and directory, and must fail at
its designated layer for its exact reason. This coverage supplements the twelve
process-observation negatives; it does not replace the broader final-source
negative matrix. The [composition receipt](phase3-evidence/process-joint-composition.json)
keeps execution provenance and these checks separate from full process admission.

## Operator entry

```bash
python3 -B -m scripts.v53.native_process_joint_floor plan
python3 -B -m scripts.v53.native_process_joint_floor capture \
  target/v53-native-process-joint/operator-001 \
  --case 4,FLOOR_MEMBER_FORCED,kill --maven /opt/maven/bin/mvn
```

Every execution uses a fresh immutable source copy, emits progress each minute
and retains failed logs and evidence. It requires one exact passing JUnit test,
with no skipped or retried test, before collection completes. `--source-from`
requires a matching recorded producer; no histories are stitched together.
Capture never launches a workflow or paid experiment.

The collection receipt identifies the original raw directory. Inspect it without
rerunning the workload:

```bash
python3 -B -m scripts.v53.native_process_joint_floor inspect \
  target/v53-native-process-joint/inspection.json \
  --case 4,FLOOR_MEMBER_FORCED,kill --raw <original-raw-directory>
python3 -B -m scripts.v53.native_process_joint_floor qualify \
  target/v53-native-process-joint/process-negatives.json \
  --case 4,FLOOR_MEMBER_FORCED,kill --raw <original-raw-directory>
python3 -B -m scripts.v53.process_joint_history <original-raw-directory> --qualify
```

The latter runs the focused original inspection first, then twelve isolated
process-observation mutations. Each must fail for its exact declared reason;
an unrelated failure cannot count as a rejection. This is focused negative
coverage and still returns PARTIAL, not whole-history process qualification.

The [development receipt](phase3-evidence/native-process-joint.json) distinguishes
actual execution, focused inspection and deferred qualification. A catalogue
entry, a process exit, or a successful Java test alone is not full acceptance.

The representative `4,FLOOR_MEMBER_FORCED,kill` history completed through FINAL
and stable BARRIER. The repaired inspector accepts its unchanged retained bytes
and rejects all twelve process-observation mutations. Its two original transfer
intervals each contain 66 exchanges. The original failed scratch-parent setup
and later collection-CLI failure are retained separately; correcting collection
did not rerun the successful Java history. The previous single-reopen history's
complete replay result also remains exactly unchanged. These observations cover
one late local-copy cut, not all 32 process histories or the complete two-reopen
resource qualification. The composed reader is independently exercised against
these same retained bytes; Java execution is not repeated for reader changes.
