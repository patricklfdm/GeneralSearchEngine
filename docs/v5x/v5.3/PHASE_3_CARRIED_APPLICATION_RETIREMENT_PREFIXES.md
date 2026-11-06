# Phase 3 — carried application retirement file captures

Phase 3 remains **OPEN**. This component extends the same original two-JVM
[application-ACK history](PHASE_3_CARRIED_APPLICATION_PREFIXES.md) with
writer-held file captures while recovery retires the old certified application
end. No runtime code, format, resource limit, timeout or retry policy changes.

## One history across the crash

The first JVM retains its interrupted ACK-force sidecar and all four original
resource owners. The second reopens those same directories, installs a fresh
selection, preserves the old certificate, replays the old input, removes only
the superseded derived application end, completes the inherited transition and
fresh stable barrier, and closes its owners. The new wrapper nests the complete
previous capture/resource/history wrapper; it cannot substitute a different
history's crash or recovery evidence.

The retirement recorder starts only at `CERTIFICATE_ACTIVE_FORCED` when the
original application-end selector differs from the installed selector. It thus
distinguishes retirement from cold recovery of the same selector and from fresh
application writes without a previous end. It captures both in-place certificate
forces, the native retirement authority boundary, typed replay scratch and every
retirement marker/delete callback through `STAGED_RETIREMENT_BEFORE_RETURN`.
Fresh replay outside that transaction does not become retirement evidence.

The separate collection schema binds root, second-lifetime PID, callback digest
and `CLOSED`. Missing starts, unfinished or overlapping owner transactions,
first-lifetime terminals and empty collections reject. This is test observation;
the recorder cannot authorize a runtime write or deletion. It retains original
event indices and original replica bytes, using the existing capture bounds.

## Independent byte projection

The complete original application/process/storage/protocol/export/FLOOR/retention
and resource chain must pass, followed by the interrupted-application byte reader.
The retirement plan then uses the first recovered installed snapshot and the
original second-lifetime event stream. Existing retirement authority validation
checks the retained pending vote, old generation, new selection, certified source
and unchanged command before any expected capture is produced.

The model derives the exact retirement marker, its empty/half/complete candidate,
force and rename sequence. It reuses the original cleanup algorithm with optional
per-callback snapshots; the default return values and event order are unchanged.
The replay claim names the old selector and certificate while the new selector
remains installed. Input files appear only at the typed-replay completion point;
no output backup is invented for these control records. Scratch is removed
children-first. Application files are deleted only after durable authority, with
the plan last, then the marker and finally the end directory. Original vote,
certificate, journal and current selector must survive.

Expected files never come from the captured objects or the final empty directory.
Every original retired-storage callback has exactly one derived capture with its
original global index. Unbound retirement elsewhere in the history rejects.
Captured object hashes, original owner records, file/directory layout and stored
byte/count bounds use the unchanged shared decoder.

All 29 new negatives run only after the unmodified original passes. They include
PID/lifetime/root substitution, omitted callbacks/objects, lost original votes,
reverted selector, early rename/deletion, changed retirement authority, an
incorrect replay selector, invented output and leftover scratch/end/marker.
Every mutation must fail for its exact reason; sidecar mutations preserve the
original history. The preceding interrupted-application reader retains all 24
of its own negatives.

```bash
python3 -B -m unittest scripts.v53.test_native_application_retirement_files scripts.v53.test_native_carried_application_retirement_prefixes
python3 -B -m scripts.v53.native_carried_application_retirement_prefixes ORIGINAL_WRAPPER --qualify
```

Short tests use synthetic inputs where original authority is explicitly mocked;
they do not qualify native history. The two previously qualified resource
originals each yield 54 expected retirement callbacks without changing their
bytes. That projection alone is not captured-file evidence. A new native
INTENT/halt original and its portable replay are retained separately under
`target/v53-carried-application-retirement` with frozen source, compiled classes,
toolchain, original inventories and unretried JUnit records.

## Observed development result

The frozen development snapshot is baseline `7db0c346` plus six modified and six
new capture/model/test files. It is not an exact-commit or final-source cohort.
The selected Java execution passed all 13 tests without skips or reruns in
729.087 seconds; its INTENT/halt native method took 681.231 seconds. The two
original children exited 73 at the declared ACK boundary and 0 after recovery.

Portable qualification passed in 96.468 seconds. The same history supplies 32
first-lifetime application prefixes and 54 second-lifetime old-end retirement
prefixes, with eight owner lifetimes. All 29 retirement and 24 interrupted-write
mutations were rejected for their exact reasons after their original prerequisite
chains passed. All 5,190 files (46,887,506 bytes), compiled classes and frozen
source files remained unchanged through the copy and both replays.

Short validation passed 25 model/staging tests, 11 reader tests, 24 checks with
Python assertions disabled, 261 related carried-history tests and 34 planning
tests. These suites overlap and are not a count of independent native histories.
The documentation contract passes and all 393 preceding evidence indexes remain
unchanged. The other three declared native methods compiled but were not run.

The [development index](phase3-evidence/carried-application-retirement-development.json)
binds the source, toolchain, class inventory, JUnit records, original inventory,
portable results, test logs and collection scripts. No full reactor suite or
hosted/paid-cloud execution was performed for this batch.

## Remaining obligations

The new family covers the original application's retirement and its own replay
scratch only. Complete application-ACK capture composition still needs campaign,
vote, FLOOR, ledger, normal application/publication and other retirement/replay
families across both lifetimes, followed by physical resource-charge binding and
source-bound cohort admission. It does not claim crashes inside this retirement
transaction, physical power-loss behavior or the full simultaneous resource
envelope. The four declared new native axes are not an executed whole cohort.
The twelve existing hosted catalogue counts and all closure flags are unchanged.

Rollback removes the dedicated capture mode/worker flag, native methods, model,
reader and plan references together. The optional cleanup observer can be removed
without changing default simulation behavior. Preserve original evidence; no
persisted runtime migration is involved.
