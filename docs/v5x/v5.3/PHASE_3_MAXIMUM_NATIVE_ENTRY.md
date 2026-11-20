# Maximum-image native required-four entry

The explicit `maximum-application-required-four-backup-segmented` profile now
connects a calibrated maximum verified backup to the complete native five-voter
replacement history. This is an execution and independent replay entry, **not a
record of a completed maximum native run**. Capture and independent replay run on the dedicated native Linux host after
capacity admission. A failed capture retains its diagnostics.

## Execution and evidence boundary

`V53MaximumNativeQualification` is excluded from ordinary `*Test` discovery. It
uses the existing maximum application generator and the unchanged complete
required-four joining history, with all twelve resource observations enabled.
The normalized source image is 67,108,832 bytes (64 MiB minus the core backup
writer's 32-byte request administration), with 1,024 typed documents and
application sequence 41. It uses explicit segmented-backup wire evidence and
the frozen 16 GiB staging default.

The maximum-native capture fixes the transport request timeout at 300,000 ms.
The resource result applies at that setting. Ordinary and small-backup histories
use 30,000 ms. The producer binds the maximum setting to the Maven command and
the test JVM checks it before bootstrap. Independent replay checks the command,
the Surefire XML property, and the receipt. The transport still uses the
earlier of the individual request deadline and the remaining owner lifetime.
The maximum-native required-four run has one 72,000-second (20-hour) JUnit deadline including seed
preparation and final binding. Its active joining history passes the remaining window
to subsequent round, learner and maintenance work. The transport caps each request at
300 seconds. Capture and replay bind both time settings and check the duration of the
individual JUnit test. Ordinary required-four histories keep their 40-minute round
and the existing child budgets; the original retry counts and storage limits apply.

In run 44203209993, both remote voters prepared valid installation replies.
From the first SELECTED request to the first reply ready for writing took
140.012 s on node 2 and 137.570 s on node 3. By then, all three attempts using
the 30 s request timeout had expired. The caller observed zero replies for
either request digest. The run failed initial activation before it could
qualify the replacement history. [Failed run and original artifacts](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/44203209993)

With the 300-second RPC setting and the earlier 40-minute round, both SELECTED replies
arrived about 195 s after the first PREPARE. The initial BARRIER completed. During
maintenance before the first RESERVE, the caller still received a CHUNK reply at
2,389 s. The stack then reported an ended activation scope. The retained exception
did not record which caller first closed it; its timing is consistent with the
2,400-second owner expiry. Subsequent runs retain that guard and first-end reason
when available. [Failed run 44487786088](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/44487786088)

Run 44531213031 completed SEAL and fetched its original record. On the following
INTENT, node 2 read the first remote ACCEPT 0.132 s after node 1 sent it and was
still fetching records when the caller's 180 s fixture wait expired. The handler
recorded endpoint closure at 179.683 s from the send. The JUnit test had run for
8 h 15 min. An earlier ACCEPT in the same run succeeded after an identical
retry at 300.8 s, with the reply received 497.9 s after its first send.
Direct slot delivery, vote observation and future publication now
use the time left until the original round deadline, including retries. The
fixture logs the remaining window when each of these operations starts.
[Failed run 44531213031](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/44531213031)

Run 44624736872 passed INTENT and placed the new voter. Its minute samples first
showed PREPARE at minute 205, SEAL at minute 457 and the original JOINT source
at minute 622. The previous 12-hour JUnit deadline interrupted the check before
the third of 46 predecessor deletions. The first two files were absent from the
retained workspace and the third still matched the original digest. The current
20-hour bound leaves three hours in the execution job for setup and artifact
collection. The minute heartbeat includes the latest stage or retirement event
and the elapsed time it was reached. [Failed run 44624736872](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/44624736872)

Placement, retirement and joined-owner checks compare freshly read file bytes
and identities with the bound inventory. Each verification now hashes each file once.
Initial custody capture still takes two readings. Checks on both sides of callbacks,
ordered deletion, directory forces and cold recovery use the same evidence as before.
A local probe reproduced the 46 deletion steps using the failed run's file names
and sizes, synthetic contents, and the seven inventory checks per step. With image
sizes capped at 1 MiB it measured 1.61 GiB read before the change and 0.86 GiB
after. With the original near-64 MiB images it measured 91.31 GiB and 45.71 GiB.
These are per-thread read counts, including page-cache hits, for the inventory
checks. The full-history duration is measured by the native run.

For this path, a local whole-image borrow formerly read the selected file in 4 MiB
pieces and hashed the entire file before and after each piece. The reader now checks
the live export, reads its exact selected inode and size once, verifies the bytes
and path identity, and rechecks the export before returning. Network chunk readers
continue to validate each transfer. A Linux regression compares per-thread read
bytes with the cost of the two live-owner checks.

Private Java bootstrap and replica files now live beneath the copied module's
`target/v53-maximum-native-work/`, on the capacity-admitted workspace volume.
JUnit removes only that invocation's private directory after success and retains
it on failure. The independent original observations are outside this temporary
directory. After the whole native history succeeds, the new calibrated seed
observation directory is atomically attached as `maximum-native-seed/` inside
the same original. A failure before that point leaves its seed observation in
`target/v53-maximum-native-seed/` beside the failed native observations; those
fragments cannot qualify as a completed original.

The producer preserves immutable source, reader, compiled classes, toolchain,
exact command, single unretried JUnit result, and before/after inventories. Its
capacity record is hash-bound to its receipt. Collection returns only PARTIAL.
It requires every seed member but does not claim semantic acceptance from file
presence or producer receipts.

Independent replay first checks the real calibration, source backup, typed
maximum image and the new bootstrap history in `original-plan.gsbp`. Bootstrap
allocates a fresh history; the imported and bootstrapped images therefore have
different hashes, while their document bytes, indexes, sequence and exact maximum
length remain equal. The v2 seed binding records both histories and both hashes.
The reader derives the new identity from the original plan, independently checks
the complete typed image under that identity, and matches the plan's source
inventory to every retained imported-backup member. A producer-declared new
history alone cannot authorize different content or a different source. The seed bytes
are included in the same 128 GiB whole-original inventory. Replay then requires
the complete [default-staging resource gate](PHASE_3_NATIVE_STAGING.md), including
all 150 exact negative outcomes, followed by the mandatory
[same-callback image/storage projection](PHASE_3_NATIVE_IMAGE_STORAGE.md).
The v2 wrapper requires seven distinct physical copies of the calibrated
bootstrapped image, each covered by its own original APPLICATION lease, and
rechecks the seed and original inventories. Old v1 receipts lack this requirement.
Its successful scope is one maximum-image native history's observed ownership;
combined maximum pressure, whole-reader memory and final-source qualification
remain explicitly false.

## Future execution

Run only on a qualifying native Linux host, after the remaining reader-memory
and physical-composition work. The existing environment admission requires at
least 272 GiB free disk and 8 GiB available memory for capture, and 144 GiB free
disk plus 8 GiB available memory for verification. It rejects WSL before copying
source or starting Maven. Insufficient disk or memory cannot select a smaller
history. Each output directory must be new; failed evidence must be retained.

```bash
python3 -m scripts.v53.required_four_resource_run capture \
  /qualified-volume/max-native-producer \
  --profile maximum-application-required-four-backup-segmented --maven /opt/maven/bin/mvn

python3 -m scripts.v53.required_four_resource_run verify \
  /qualified-volume/max-native-verification \
  --profile maximum-application-required-four-backup-segmented \
  --producer /qualified-volume/max-native-producer \
  --pins /qualified-volume/max-native-producer/pins.json
```

Use the final immutable source and populated offline Maven dependencies. The
existing child-process runner prints minute progress and retains Maven and
collection logs. Independent replay reports stage progress. These commands do
not dispatch Actions or provision a machine. The [dedicated maximum-native
hosted transport](PHASE_3_MAXIMUM_NATIVE_HOSTED.md) now has separate archive and
download/extraction capacity checks. Independent verification still requires a successful capture.
The existing small-backup workflow's archive budget is unchanged. Neither the EMPTY supplemental slot,
the small-backup profile nor the synchronous maximum-storage component is
replaced by this development entry.

## Development validation and remaining work

The [seed-rebinding correction](phase3-evidence/maximum-seed-rebinding-development.json)
retains a concrete failure of the earlier byte-equality assumption. The already
retained maximum-storage original has two 67,108,832-byte images with different
histories/hashes and identical documents at sequence 41. The old reader rejects
this legitimate pair; the corrected seed reader accepts it with its original
plan/source binding. The historical producer files remain unchanged. A real
small-bootstrap Java regression also checks fresh-history allocation and rejects
wrong source history, documents, sequence and original-plan/image association.
These results qualify the binding correction only. They do not execute the full
maximum native replacement or provide final-source cohort credit.

The [development receipt](phase3-evidence/maximum-native-entry-development.json)
distinguishes configuration/orchestration tests from physical qualification.
Tests reject missing observations, source faults, capacity failures before work,
receipt relabeling, incomplete seed collection, changed producer capacity,
missing negative families and late original mutation. They also check JUnit's
workspace-local private storage. Synthetic producer fixtures are not maximum
native histories.

A separate reader check uses the retained real 67,108,832-byte maximum source,
including calibration and original backup files. It passes independent source
decoding and rejects image/binding mutations without changing the retained
original. Its native-image copy and binding are synthetic: this is a source
reader component check, not a replay of a completed maximum joining history.

Complete native maximum execution, whole-reader memory measurement, simultaneous
same-owner metadata/image/queue pressure with refusal and recovery, hosted
execution, and final-source cohort evidence remain pending. All five
Phase 3 closure gaps remain open. Rollback removes this explicit entry and its
new wrapper; existing profile commands and frozen cohorts remain unchanged.
