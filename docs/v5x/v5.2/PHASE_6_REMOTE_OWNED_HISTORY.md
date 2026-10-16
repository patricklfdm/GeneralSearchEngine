# V5.2 Phase 6AB stable slots and an owned receiver history

**Status:** the complete integrated local gate passed on 2026-10-16. This stage
connects the command store to one real untimed `candidate-minimum` history.
It does not qualify a full remote member or a paid cloud run.
[Phase 6AC](PHASE_6_REMOTE_HISTORIES.md) extends the same local command owner to
all closed histories and adds complete M01–M04 receiver qualification probes.
The record below describes this original untimed stage.

## Stable semantic slots

`remote_slots.py` derives the command ID from the immutable owner binding and a
closed semantic slot. A different ID for the same selected history/node/session
rejects before handler entry. Payloads cannot contain arbitrary shell commands.
Start/stop permit generations 1 and 2 only; generation 2 belongs exclusively to
the declared retained-leader restart history. Fault slots permit only that
history's SIGKILL or the snapshot history's partition/heal actions.

The existing command store still owns atomic claims, original RUNNING/terminal
receipts, cancellation, process identity and bounded reconnect observation.
Deduplication does not replace provider ownership, lease expiry or lifecycle
admission. The current local history entry accepts only the declared untimed
experiment profile on its coordinator node.

## Real detached execution and replay

`remote_owned_history.py` launches a detached command executor which owns three
receiver-local public JVM/TCP voters. It invokes the existing shared program:
11 reads and three updates. Original and relocated authority, public calls,
queries, ownership and resources pass through the existing independent validator.

The test deliberately loses the first submit response. Observation queries the
original claim; it never submits another workload. A second process sends the
identical request and must receive the identical terminal receipt without
changing the history, topology or claim count. A fresh alternate command ID
rejects. All original JVMs and command processes must be reaped successfully.

The qualification owner uses explicit synthetic build/package selection fields;
actual loaded JAR/class identities are independently retained in the history.
Receipts therefore report `syntheticSelection=true`, `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`. This is a real local engine
history under a test control identity, not proof of cloud artifact admission.

## Validation and remaining work

The existing `verify-v52-phase6-measurement-runtime.sh` gate retains its default
five-mode consumer/load and packaging checks, then runs receiver bootstrap, all
five receiver modes, command-store subprocess cases and this owned-history probe.
Stable-slot and owner/source/profile rejection tests run in the same gate.
Fresh receipts and their source/build identities are retained under
`target/v52-measurement-runtime/run.*/`. Integration results are summarized in
`target/v52-integration/validation-summary.json` after execution.

Persistent cross-host pipes, complete M01–M04 history/fault orchestration, guest
boot/resource identity, original-path collection and full no-GCP ownership
qualification remain required. Healthy-command operational time budgets warn;
finite API/exchange deadlines and repeated observation-error fast failure remain.
No business retry, shortened measurement window or cloud dispatch is introduced.

## Integrated qualification record

The fresh gate `target/v52-measurement-runtime/run.MUcwmR/` passed all five default
modes and the 4,392-file large-package replay, six bootstrap receivers and 40
Java/Python topology parity cases, all five receiver modes (55 reads/15 updates;
100 exact negatives at each location), and four real command subprocess cases.

The owned real history passed with one submission, 55 original-command queries,
11 reads, three updates and three normally stopped JVMs. A separate duplicate
process returned the identical receipt; an alternate command ID was rejected.
Both original and relocated physical replay passed. This is still one untimed
local history under a synthetic control selection, not cloud qualification.

All 292 V5.2 Python tests and 21 CI suite contract tests passed. Fresh reactor
packaging succeeded with Maven tests skipped for that packaging command; this
does not claim a new complete reactor-test run. Shutdown probes passed 14 checks
against each API family. The executed gate itself also passed its 228-test subset.

The receipt base HEAD is `a40c5108aa9463a4f526bd3547b09518a2d49d83` with the
integrated, uncommitted implementation checkout fingerprint
`1d7ed28b045a886b2694e8bcc07aa830dbfeed2e73879e97c0c92af37c8a5bff`. That receipt
describes the actual execution before this documentation-only result update; it
does not claim the old HEAD alone contained the integrated files. Receipt hashes
and actual JAR/class identities remain in the validation summary and raw evidence.
