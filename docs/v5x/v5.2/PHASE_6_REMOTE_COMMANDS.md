# V5.2 Phase 6AA durable command ownership

**Status:** local command-store and subprocess qualification passed. This is a
control foundation. It does not execute a cloud workload, establish provider
ownership or qualify a complete remote member.

## One immutable command claim

The V5.2 owner retains the complete closed suite selection, one selected history,
node, Linux boot identity and session. All 33 selectable histories fit the bounded
owner format. Requests bind that owner and a command ID, with a closed operation
set: receiver preparation, voter start, whole-history execution, declared fault,
voter stop and collection. Individual measured reads/updates are not commands in
this store. A trusted adapter must validate payload semantics and lifecycle order;
no request supplies executable shell text or argv.

An exclusive directory claim is forced before the request and RUNNING receipt,
and both precede handler entry. Existing IDs return the original state; a changed
request under the same ID rejects. Partial claims, torn publications or a missing
terminal receipt cannot authorize reexecution. Forced receipts publish atomically
without replacement. Query and cooperative cancellation remain available while
one executor holds the store lock. A cancellation racing with handler completion
retains the original result under CANCELLED.

Requests and owner records are bounded at 64 KiB, responses at 4 MiB and consumed
claims at 64 per history/node/session. Special files, symlinks, duplicate JSON keys,
nonfinite numbers and malformed receipt fields reject. Generic forced-file helpers
are reused from V5.1; its command schemas, executor and paid workflow are unchanged.

## Connection loss and budgets

The controller submits once and subsequently only queries that request. Each
exchange has a finite deadline. Three consecutive transient exchange failures or
three uncertain replies fail promptly by default; permanent errors and malformed
responses fail immediately. The threshold is explicit and bounded. Late submit
responses are resolved by querying the original command, never by resubmission.

A valid RUNNING process may exceed the operational time allowance; that emits one
warning and continues observation. No total wall-clock limit is added to a healthy
command. The stored boot identity, PID and process start ticks are checked against
the local process table. A missing executor, zombie, different boot or reused PID
returns UNCERTAIN. A terminal receipt remains readable after its process exits.
This layer does not change finite public read deadlines or measured schedules.

## Local validation

- 21 unit cases cover immutable claims, every suite history, owner drift, partial
  publication, lost terminal writes, concurrent queries, cancellation, process
  identity, byte/count limits, strict JSON and observation failure thresholds.
- Four real subprocess cases prove one handler entry after a lost initial reply,
  no reentry from a separate duplicate process, retained uncertainty after SIGKILL,
  and cooperative cancellation. All five owned child processes were reaped.
- The subprocess probe writes a forced marker; it explicitly reports
  `engineWorkloadExecuted=false` and `syntheticSelection=true`. Its zero build and
  package hashes are test fixtures, never evidence of a physical cloud artifact.
- The combined V5.2 Python regression passes 264 cases. Raw receipts, source
  bindings and earlier development runs remain in `target/v52-next-command/`.

## Remaining adapter requirements

Command-ID deduplication does not by itself forbid a caller from inventing another
ID. [Phase 6AB](PHASE_6_REMOTE_OWNED_HISTORY.md) now derives stable semantic slots
and connects one real detached untimed receiver history. Full remote orchestration
must preserve these slots, immutable roots and one execution per selected session.
It must connect actual persistent guest pipes, process/fault ownership, complete
M01–M04 evidence and cross-host identities. Private addresses and a command-store
PASS alone confer no cloud authority. Final exact-source full CI and fresh provider
admission remain required before any operator-triggered paid execution.
