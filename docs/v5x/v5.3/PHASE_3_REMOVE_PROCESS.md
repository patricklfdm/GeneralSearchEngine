# Phase 3 — interrupted REMOVE retirement recovery

Status: one retained SIGKILL member has independent physical/process replay;
the complete process matrix and complete network/profile qualification remain OPEN.

## Reproduced failure and correction

The native proposer was killed at `RETIREMENT_BORROW_PREFIX_WRITTEN` while
performing maintenance before INTENT in an original `4-REMOVE` operation. The
fresh JVM reopened the original store, but its first campaign failed with
`native maintenance requires recovered storage`: the automatic entry had left
the interrupted generation retirement pending. Earlier component tests resumed
that transaction explicitly, so they did not exercise the missing connection.

Retaining initial-voter and retaining joined-voter entries now complete an
already-started generation retirement before returning the owner. The required
retention originals are admitted first. Recovery uses the existing exact
original/floor/selector checks, resource accounting and deletion transaction.
It neither establishes a new floor nor releases its governing copies, retires an
unrequested inactive generation, or changes persistent formats. Component opens
continue to expose pending maintenance for explicit diagnosis. A failed recovery
closes its owner and leaves the original transaction available for exact recovery.

The next complete-process diagnostic passed that recovery but exposed a second
gap: before-grant maintenance tried to receive another quorum of copies while
the original complete floor still owned its source reservations. This exceeded
the unchanged six-SOURCE limit. Maintenance now reuses the complete retained
copies only when their original local generation exactly matches the current
generation and they satisfy both governing majorities and any joining-copy
obligation. It re-forces the same proposal, then performs the ordinary retention,
source retirement and floor release steps. It does not replace or extend an
existing proposal, trust a hint, or raise the seven-image/six-source limits.

The first diagnostic stopped earlier at a stale test assertion: the live-child
lock was correctly refused with `membership file already owned`, while the test
expected the older offline-authority message. The assertion now checks the current
exact message and `STORAGE_FAILURE`. That failed execution is retained separately
from the second execution which reproduced the actual recovery defect.

## Process execution and collection

The shared native process harness now accepts four- or five-voter REMOVE. The
parent retains the other voters' actual TCP endpoints. A child owns the original
proposer storage and executes the round; the parent observes the exact requested
cut, verifies no readiness was returned, and either observes halt or sends SIGKILL.
SIGKILL additionally requires a refused concurrent storage open. A distinct fresh
JVM reopens the same directories and must complete the same operation through
the new-stable BARRIER at index 7. Cold-open snapshots occur before endpoint and
round construction; later snapshots retain the original intermediate stores.

The declared 52 members combine `4-REMOVE` and `5-REMOVE`, halt and SIGKILL, and:

- Generation borrowing prefix, proposal force, authority force, original file
  deletion, original directory deletion, borrowed-binding cleanup and authority
  cleanup.
- Source decision write/force, journal rotation write/rename, source file deletion
  and source decision cleanup.

Each selected member is a complete new bootstrap/death/reopen/continuation
history. Members may be dispatched independently; stages inside a member cannot
be stitched together. The existing 600-second native round lifetime and
30-second request timeout remain unchanged. The 52-member catalogue is a test
execution inventory, not a claim that the frozen acceptance matrix is complete.

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
python3 -B -u -m scripts.v53.remove_process_run NEW_OUTPUT \
  --case 4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill \
  --maven /opt/maven/bin/mvn
```

The runner freezes source, build and toolchain inputs, reports progress each
minute, retains failures and refuses output reuse. It requires exactly one
passing JUnit method without skipped, failed, flaky or rerun results. Collection
checks distinct original processes, the selected interruption, cold-open
snapshots and completion observations. Its result is only `PARTIAL` with
`processDeathQualified=false` and `physicalHistoryQualified=false`: these checks
cannot replace an independent reduction of the original bytes and network trace.

## Targeted validation

The [batch receipt](phase3-evidence/remove-process-recovery.json) retains four
diagnostic executions of the same declared case on their recorded sources: the
obsolete lock assertion, the missing recovery call, the duplicate receiving
capacity failure, and the final successful continuation. These are development
executions after changes, not four distinct matrix members or automatic retries.
The final execution passes in 374.548 seconds, observes child exit 137 and a
distinct resumed child exit 0, and retains the original successful lock refusal.

All six tests in the first recovery-regression version fail on the original
runtime. After the first correction, 32 targeted Java tests pass, including seven
recovery tests and the existing retirement/borrowing/lock suites. The final source
passes ten targeted tests: eight recovery/retained-floor tests and two catalogue
tests. Its compiled build and source manifest exactly match the successful native
process producer. All 1,617 V5.3 Python tests pass, including twelve collection
tests; eighteen focused collection/process-reader tests pass.

The 146,295,137-byte archive binds all seven preserved producer/test workspaces,
their source/build manifests, original process histories, diagnostics and test
reports. Every archived producer file is checked against its input digest.
The relocated successful history also returns exactly the same collection under
`python3 -O`, with both original and extracted inventories unchanged.
This is retained execution evidence; neither the archive nor collection status
claims the still-pending independent physical/process qualification.

## Independent replay of the retained original

`scripts.v53.remove_process_evidence` now derives the initial bootstrap, four
preparation slots, original child selection, governing floor, retention state,
first matching retirement prefix and cold-open recovery. It compares every
captured owner's complete files, including inactive voters. It then derives the
three resumed selections and the INTENT, FINAL and new-stable BARRIER through
the final closed snapshot. Fresh source UUIDs and application images remain
observations checked by the existing independent models; claimed digests and
JUnit success are not expected-state authorities.

The interrupted process must stop at the first specified callback, expose no
readiness, and have its recorded halt/SIGKILL exit and distinct resumed PID.
The reader checks the interrupted transaction's exact callback prefix and the
complete cold-open recovery sequence before constructing the new endpoint.
It reuses the existing original publication-ACK checks for all three resumed
slots: retention before send, original certificates, local and remote force
order, exact request/reply bytes, and readiness only after the final BARRIER.
The seven-image/six-source limits remain unchanged, counting equal image bytes
in different physical locations separately.

```bash
python3 -B -m scripts.v53.remove_process_evidence ORIGINAL_PROCESS_ROOT \
  --qualify --workers 2
```

The [replay receipt](phase3-evidence/remove-process-replay.json) binds the reader
and the previously retained successful
`4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill` history. This batch runs no new
native JVM history. All 27 mutations must reject for their exact declared reason,
after the unmodified history passes first. They include altered governing or
recovered files, repeated process identity, wrong exit/lock, wrong command,
omitted retirement/recovery/publication forces, premature floor release,
missing reactivation/ACKs and early readiness. An unrelated parser or original
failure cannot count as a successful rejection.

The receipt records the full Python suite, the prior eight original publication
process cases replayed with the shared validator, and equal original/relocated
results under optimized Python. The archive contains original files, reader
inputs and producer source/build bindings; it does not replace the prior archive
containing the complete native producer workspace and its failed diagnostics.

This is scoped same-proposer retirement recovery and publication qualification.
Complete attempted transport, activation ACKs, export lifetimes and continuous
maintenance/retention callback composition for this process history remain OPEN.
In particular, its 15 observed FUTURE_RETENTION_INTENT rejection diagnostics from
non-selected voters are retained and hashed, not silently discarded or counted
as successful network qualification. The earlier healthy REMOVE network reader
does not automatically qualify this restarted process history.

The reader declares both REMOVE profiles and all 13 cuts in the 52-member
catalogue. Only the one retained native member above has been replayed here;
unit tests of both borrowing/copying branches and all six source-retirement cuts
do not substitute for the remaining native members. Complete each member as one
indivisible bootstrap/death/reopen/continuation history, with separately recorded
source/build and qualification. The large matrix can run on independent hosted
workers after integration is ready; do not splice its stages or retry failed
measurements. The complete seven-profile cohort and frozen acceptance mapping
remain required before Phase 3 closes.

Rollback removes the automatic-entry recovery calls and the new process mode,
restoring explicit component recovery. It restores the reproduced automatic
restart failure as well; no stored-format migration or cloud action is involved.
