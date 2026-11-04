# Deferred-grant process interruption and required-four follow-up

Status: **conditional process recovery PASS; complete native history OPEN**.
The production correction remains [deferred grant capture](PHASE_3_DEFERRED_GRANT.md).
This batch adds tests/readers and records a later capacity boundary; it does not
change production Java, formats, quorum rules, resource limits or time budgets.

## Fresh-process recovery

`V53DeferredGrantProcessTest` executes fourteen cases: halt and external SIGKILL
at each of these seven original callbacks:

- `PROMISE_FORCED`
- `FLOOR_BEFORE_RETURN`
- `SOURCE_RETIREMENT_JOURNAL_PRUNED`
- `FLOOR_RELEASE_BEFORE_RETURN`
- `CAPTURE_INTENT_FORCED`
- `SOURCE_PACKET_PREFIX_WRITTEN`
- `BASIS_FORCED`

Each case starts from the same conditional four-voter joint-floor fixture with
two retained original sources. Three distinct child JVMs perform interruption,
same-directory recovery and a second cold inspection: **42 child executions**.
The external kill checks the marker and actual owner lock before SIGKILL; process
exit, PID and clean close are retained. These are actual files/process deaths,
but preceding membership authority is supplied by a conditional fixture. They
are not native quorum histories or a power-loss simulation.

Before a capture intent exists, recovery preserves the original forced PROMISE,
finishes ordinary floor/source cleanup, refuses a same-ballot capture without
changing files, and requires a fresh higher ballot. Once the original capture
intent is forced, recovery completes that exact BASIS and its original source;
it cannot replace the UUID or resample another grant. A subsequent fresh grant
and second cold reopen preserve all derived files. Owner reservations remain
within SOURCE=6/APPLICATION=7 and release on close; this is not a qualification
of the full network/installation/publication resource maximum.

`deferred_grant_process_evidence` independently derives every crash, reopened,
maintained, same-ballot, next-grant and cold inventory from the original seed and
forced promise identities. It checks original floor/source retirement, capture
intent/prefix/BASIS bytes, critical force order, process binding and unchanged
peers. Ten copy-only mutations require exact rejection reasons, after the original
history passes. The original directory is bounded and hashed before and after
qualification. The complete unmodified process execution passed in 49.53 seconds;
all fourteen independent cases and ten negative replays passed.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.deferred.process=true \
  '-Dtest=V53DeferredGrantProcessTest' test
python3 -m scripts.v53.deferred_grant_process_evidence "$ORIGINAL" --qualify
```

Keep the printed original path and Maven log. The entry is opt-in and does not
add a hosted subset or an accepted frozen scenario. The existing twelve subsets /
544 planned native histories and final-source admission remain unchanged.

## Complete required-four execution still fails

A new original on runtime `aa7a9820` passed the previously failing old-side retention
preparation, initialized/cold-reopened the joining owner, and installed JOINT cut 9.
It then failed after **1079.384 seconds**, in installed-generation maintenance
before FINAL ACCEPT, while establishing the required four-copy governing floor.
This is a later storage count conflict, not a timeout or a failed transport retry.

The installed snapshots contain two retained source images and two generation
images. Four complete floor copies would require **8 application images**, above
the unchanged bound of 7, even though six SOURCE slots would suffice. The older
source still backs the real predecessor generation. Existing retirement correctly
refuses deleting it before that generation; successful installation alone grants
no deletion authority. Byte sizes are small and increasing a time budget cannot
resolve this count conflict.

A new short `V53RequiredFourCapacityTest` performs two real selected installations
on conditional originals. Its first four-copy floor fits at seven images. After
the next installation it reproduces the eight-image demand, confirms the source
cannot be retired first, and checks that admission refusal leaves original files
and reservations unchanged. All three capacity diagnosis tests pass. This is a
reproducer, not a runtime fix or a passing required-four execution.

The independent required-four reader rejects the failed original at
`joining complete control order`; none of its thirteen negatives is qualified.
Both long failures remain retained. The next implementation must resolve the
selected predecessor/source/floor lifetime together, with original-byte recovery
and no early release, followed by a corrected complete native execution. Phase 3
remains OPEN; final-source cohorts and full physical/resource qualification remain
required.

[Process evidence index](phase3-evidence/deferred-grant-process.json).
[Required-four follow-up index](phase3-evidence/required-four-followup.json).

Rollback removes this optional process entry/reader and its plan references.
The existing native regression and the two failed originals remain separate
requirements; removing a diagnostic does not resolve their capacity conflicts.
