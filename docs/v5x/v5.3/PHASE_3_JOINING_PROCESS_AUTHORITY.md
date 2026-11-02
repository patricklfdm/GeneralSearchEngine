# Joining process export and continuous-ledger authority

`scripts.v53.joining_process_authority` extends the
[physical/transport composition](PHASE_3_JOINING_PROCESS_COMPOSITION.md) with
temporal exports, control messages, maintenance floors, continuous peer/future/
learner ledgers and the ballot allocator/promise chain. The complete original
must pass the preceding physical, child-lifecycle and durable-ACK readers first.
The development result remains `PARTIAL`; final-source whole-process admission,
the complete negative catalogue and Phase 3 closure are still **OPEN**.

The subsequent [process matrix](PHASE_3_JOINING_PROCESS_MATRIX.md) now binds
these readers to all 360 exact-source producer histories, requiring the complete
authority, physical and transaction negative catalogues. Hosted execution and
final-source native acceptance remain pending.

## Original lifetimes and recovery boundaries

The temporary observation view includes the five actual child control messages
(`STARTED`, `CUT`, `STARTED`, `READY`, `CLOSED`) as diagnostic anchors. Their
original values and combined order must exactly match the retained interprocess
trace. Removing those anchors leaves exactly the previous event projection.
They are not storage callbacks, successful votes or new authority. Event indices
are recomputed within each view, so an inserted/removed observation cannot make
a stale numeric offset authorize an export.

Child transport callbacks must follow the original `FIXTURE_OPEN_RETURNED`
and precede the original CUT/CLOSED control. Child exports must also fall inside
their actual process lifetime and owner scope.
A successful completion export additionally requires the resumed child's READY,
completed original initialization, recovered ledger forces and an unfenced
generation. The original parent endpoint and interrupted child cannot export
completion. The later continuation endpoint still needs its own completed
retaining-owner recovery.

A partial seed must reacquire its original old-majority preparation and sources
after reopening with native operations refused. A complete original seed
finishes recovery before native owner open returns. If DONE was already renamed,
the recovery path reseals the original decision and DONE instead of emitting
another `JOINING_RETENTION_BEFORE_RETURN`. The reader derives the correct
completion boundary from the explicit cut, with exact callbacks independently
checked by the physical process reader.

The original parent and interrupted child have no active native ledger reseal.
The resumed child, completed-owner observation and four subsequent retaining/
continuation/cold lifetimes must each reseal all three original ledgers. No
snapshot starts a fresh chain: original preparation derives the joining seed,
and existing semantic transitions derive every later revision, debt obligation,
selected completion and retained promise through FINAL/BARRIER and cold reopen.
The ordinary readers retain their original single-process lifetimes and exact
BEFORE_RETURN requirement. New methods expose those existing checks for an
explicit process subclass; no ordinary gate silently enables process recovery.

## Qualification and mutation scope

The driver declares 130 negative cases: all existing export, control,
maintenance, peer, future, learner and ballot families, plus five process-specific
cases. Only three explicitly evidenced absences can mark a case NOT_APPLICABLE:
no original pending checkpoint export, no joining-owner learner write, or an
already complete seed that has no incomplete-native-use refusal path.

Full original validation precedes all mutations. Each mutation uses a disposable
same-history view, and all original physical files remain unchanged. The
future/learner/ballot negatives follow the existing profile-gate convention:
only their designated callbacks may change; wire bytes, diagnostic anchors and
all other callbacks remain identical. Their target chain then must reject for
the exact declared reason. This avoids mistaking an earlier ACK precondition's
rejection for the intended continuous-ledger check. Export/control/maintenance/
peer cases retain their preceding transport and authority checks.

Failures and unrelated rejection reasons are retained as FAIL. A selected
subset cannot set `completeNegativeCatalogue`; even a full successful catalogue
does not certify a final-source native cohort or close Phase 3. At most three
local reader processes may run concurrently. Native histories and measurements
are never retried by this driver.

```bash
# Replay the entire original and the complete declared negative catalogue.
python3 -B -u -m scripts.v53.joining_process_authority /path/to/original/raw \
  --case 3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt \
  --qualify --workers 3

# Explicit development subset; remains PARTIAL.
python3 -B -u -m scripts.v53.joining_process_authority /path/to/original/raw \
  --case 3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt --qualify \
  --negative process/completion-before-ready
```

## Development evidence and remaining work

The [development receipt](phase3-evidence/joining-process-authority.json) records
reader/source hashes, actual tests, selected negative results and portable replay.
The same retained successful SEED_PREFIX_WRITTEN/halt development history now
derives 90 peer-ledger writes, 54 future-ledger writes, nine learner-ledger writes,
19 forced promises and ten ballot reservations. Each ledger has nine original
open/reseal lifetimes across the three old voters and six initialized joining
owners. The control layer accounts for all 689 committed transfers, including
both preparation acquisitions required by the interrupted partial seed.

This batch changes Python readers/tests and documentation only. It performs no
new Java/native workload, hosted dispatch or paid cloud experiment. The producer
still predates the final read-only discovery-scan correction and these readers;
successful replay cannot upgrade its source identity.

The 21-case development subset exercises each authority layer and all five new
process-specific cases. The complete 130-case negative catalogue and all 360
declared native process combinations remain deferred to the source-bound
acceptance campaign. The next implementation step is whole-case collection,
portable replay and cohort/hosted wiring with exact source/build/toolchain/reader
bindings. Death, recovery and continuation remain one indivisible history.
