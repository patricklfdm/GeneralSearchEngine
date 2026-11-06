# Phase 3 — interrupted application file captures

Phase 3 remains **OPEN**. This component captures the original writer-held
application files through `APPLY_ACK_DIRECTORY_FORCED` in the carried INTENT or
FINAL process history. It builds on the
[application resource chain](PHASE_3_CARRIED_APPLICATION_RESOURCES.md).
Runtime code, frozen limits, child deadlines and protocol formats are unchanged.

## Explicit interrupted boundary

The dedicated process methods retain the complete four-owner resource history,
kill or halt its first JVM at the declared ACK-force callback, and recover on the
same original directories in a second JVM. The new sidecar records only the
first lifetime's application callbacks. Its separate
`gse-v53-carried-application-cut-capture-v1` envelope binds the original root,
PID, lifetime, callback bytes, final event index and `node-1` owner. The terminal
is `CUT_PREFIX`; it cannot claim normal completion or publication.

The recorder requires exactly one unfinished application transaction and the
declared ACK-force callback as the last original event. A wrong owner, another
unfinished transaction, earlier boundary, later event, second lifetime, normal
return or repeated seal rejects. The existing normal completion collector still
refuses unfinished application writes, including generic `CUT_PREFIX` calls.
The new worker flag is confined to an application-ACK first lifetime with the
original resource observer; it cannot enable a different crash case implicitly.

## Independent replay

The new reader first validates the complete original application storage,
process, callback, TCP, export, FLOOR, retention and resource chain. Only then
does it derive the application write plan from the independently checked
`at-cut` replica state. It removes the new application end to reconstruct the
starting inventory, models each original create/prefix/write/force callback,
and preserves the callback's original global index.

Every captured file and directory must equal that derived state. Captured
objects never supply the expected image, ACK, certificate or selector. Complete
callback coverage, original owner records, object digests, byte/count bounds
and the exact sidecar inventory remain mandatory. The original resource trace
and child transcript bind the event stream and PID; the envelope alone confers
no authority.

All 24 negative variants run after the unmodified original passes. They cover
altered objects, missing/duplicate callbacks, ownership, PID/lifetime/root,
ordinary-completion schema substitution, a changed interrupted boundary,
boolean numeric fields, nonempty creation, an early complete image, an early
ACK and unrelated replica changes. Each must reject for its specified reason.
Mutations touch copied sidecars only; the original history and immutable write
plan are checked again. Accepted mutations or unrelated prerequisite failures
earn no credit.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_prefixes
python3 -B -m scripts.v53.native_carried_application_prefixes ORIGINAL_WRAPPER --qualify
```

The short decoder tests use synthetic files and explicitly mocked original
authority where needed. They do not constitute native process qualification.
Development execution and portable replay are retained separately under
`target/v53-carried-application-prefixes`, with source/build/toolchain
inventories, unretried JUnit results and original/copy hash inventories.

## Development validation

The [development receipt](phase3-evidence/carried-application-prefix-development.json)
records an unretried FINAL/SIGKILL execution in 568.165 seconds; the selected
reactor tests and build took 621.220 seconds. All 13 selected Java tests pass,
including default completion's refusal of unfinished ends. The four native
methods compile; only FINAL/SIGKILL was executed in this batch.

Its complete copied original passes the application/resource prerequisite and
all 32 file-prefix comparisons, followed by 24 exact negatives. Both original
PIDs and all eight owner lifetimes remain bound; child exits are 137 and 0.
The 5,764 original files (44,067,858 bytes), compiled classes and frozen source
remain unchanged. Native portable qualification took 38.674 seconds.

The existing normal completion reader also accepts all three independently
copied conditional components (DATA, INTENT and FINAL): 90 captures and 13
physical negatives each, with unchanged originals. Including these checks,
portable replay took 46.104 seconds. This confirms normal completion format and
validation behavior; those conditional components do not become native protocol
histories.

The frozen development source contains baseline `297e2294` plus four modified
and four new capture/test/reader files. It is not an exact-commit or final-source
hosted cohort. Ubuntu OpenJDK 21.0.12.1 and Maven 3.9.11 identities are retained.
The 250 related Python tests, 51 planning/model tests and 11 optimized new-reader
tests pass; these suites overlap. Documentation/whitespace checks pass and all
392 earlier evidence indexes remain unchanged. No full reactor suite, repeated
native trial, hosted dispatch or paid-cloud execution is claimed.

## Remaining scope

This is the interrupted application's file family only. Recovery's original
certificate reseal, staged/superseded end retirement, replay, campaign, votes,
FLOOR, ledgers and publication still need complete transient capture composition
for application-ACK histories. Physical resource-charge binding and the full
simultaneous envelope remain open. The four declared native axes are not an
executed complete cohort. The twelve existing hosted catalogue counts and all
Phase 3 acceptance flags are unchanged.

Rollback removes the dedicated sidecar/worker flag, process methods, reader and
planning references together; preserve original evidence. No persisted runtime
state migration or production recovery behavior change is involved.
