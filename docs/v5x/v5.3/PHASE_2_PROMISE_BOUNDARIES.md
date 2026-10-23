# Unmarked and torn PROMISE boundaries

Status: local safety qualification. Production Java is unchanged; Phase 2 and the
public runtime remain open/disabled. This resolves the failure-handling audit for
the existing PROMISE writer, not a new automatic repair mechanism.

## Required behavior

| Retained state | Reopen and subsequent request |
| --- | --- |
| Crash before the new PROMISE write | Preserve the previous promise and allow a new grant |
| Complete new PROMISE, no capture intent or BASIS | Seal/retain the full ballot fence; refuse a same-ballot replacement BASIS; allow a strictly newer fresh ballot |
| Partial PROMISE header or body, no original recovery authority | Refuse open and preserve every byte; repeated reopen must also refuse |

A source capture intent is written after PROMISE. The exact original intent/source
can authorize [torn BASIS completion](PHASE_2_CAPTURE_JOURNAL_RECOVERY.md); it cannot
recover a preceding PROMISE for which those inputs never became available. An
absent marker is not permission to truncate the journal, lower the promise, invent
a BASIS or fall back to the selected generation's earlier promise. A damaged
store cannot join a campaign until a separately verified offline recovery or
replacement procedure supplies authority. Such a procedure is not implemented by
this batch.

## Qualification

The process gate has 26 cases and 100 fresh child JVMs:

- 18 halt/SIGKILL cases after PROMISE force: 3/4/5 initial voters and old, joint,
  new configurations, retaining an accepted DATA/FINAL tail as applicable.
- Four more halt/SIGKILL cases before the write and after a complete write before
  force. Inspection preserves the fence, then a fresh request creates one exact
  original BASIS; duplicate reopen preserves all bytes.
- Four explicit header/body damage cases. The test truncates the just-written
  whole PROMISE before halt/SIGKILL, then two fresh JVMs independently refuse open.
  This is test-only storage damage injection, not observation of an OS torn write
  or a power-loss durability claim.

A separate component test visits every nonempty proper prefix of the original
343-byte PROMISE: 342 header/body lengths, each refused twice, with unchanged
files, no resource leaks and a released owner lock. The restored complete frame
opens with its original fence and no invented BASIS. The test restoration is not
a production repair path.

The independent Python validator first validates the original generation and
journal. It reconstructs exact crash bytes from the retained original PROMISE,
checks all actual exit codes and event order, verifies the fresh ballot and
original source/image/tail bindings, and compares all files after inspection,
completion and duplicate reopen. Twelve negative mutations run only after the
original passes; relocation and Python `-O` use the same checks.

[Source/build/raw index](phase2-evidence/promise-boundaries.json).
The first execution completed its process cases but failed while serializing a
test receipt whose key used a disallowed hyphen. The key was corrected and the
entire gate rerun; that development failure remains retained.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53PromiseBoundaryTest,V53CaptureRecoveryTest,V53CaptureJournalTest,V53GrantJournalTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.promise_boundary_evidence <new-retained-run-directory>
```

## Remaining limits

Historical prefix ownership and current-generation provisioning are conditional
fixtures. This gate makes no distributed grant, bootstrap, public service or
power-loss claim. Full-size capacity/lifetime, carried-first-entry integration,
cross-view storage progression, complete offline provisioning and the Phase 2
S/N acceptance mapping remain required by the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
