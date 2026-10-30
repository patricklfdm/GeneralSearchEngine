# Observing completed joining initialization

Phase 3 remains **OPEN**. The original old preparation now exposes
`probeInitialized()`: one read-only request/transfer to the actual joining
identity, while keeping its preparation publication and original ballot alive.
This supplies the remote observation needed before handing coordination to a
fresh normal activation. It does not itself schedule preparation, poll, close
the preparation, allocate a new ballot or run FINAL.

Starting that next activation before the new owner finishes reading preparation
would invalidate the published BASIS/ballot. Conversely, learning a current cut
from STATUS cannot distinguish the read-only joining stage from completed native
retention initialization. The separate completion lookup addresses this gap
without changing STATUS or claiming public readiness.

## Serving and interpretation

`MembershipJoiningCompletion` uses an exact root/cut/joining lookup alias over
the existing CHUNK/SOURCE_OFFER/TRANSFER_COMMIT channel. Its at-most-16-KiB
canonical `gse-v53-joining-completion/1.3` metadata contains only schema, root,
current JOINT cut and joining identity. This is an ephemeral observation, not a
new frozen wire frame, durable record, majority proof or installation receipt.
Only known old identities may request it.

The read-only joining endpoint responds to a valid initial request with a
correlated `NOT_READY`, without observing the request ballot or creating a
transfer. After the managed handoff, the normal activation endpoint serves
completion metadata only if `joiningEndpointReady` validates the actual native
joined owner, original forced completion and all three live retention ledgers.
Conditional owners cannot export positive completion. Each live export rechecks
that eligibility, the original local fence, same cut, close and its own original
deadline. The request ballot is correlation only. A live export reserves 32 KiB
of existing CONTROL capacity; ordinary transfer/session/cached-reply accounting
remains in force.

The old probe is bound to its exact local BASIS, preparation hint, cut and ballot,
with no selection allowed. It validates every transfer correlation and the exact
canonical completion bytes. A valid initial `NOT_READY` returns false. A
mid-transfer refusal, other rejection, malformed payload, higher local fence,
expired/revoked preparation or unavailable transport fails instead. Transport
IO/deadline retries retain the existing identical-request limit; the method does
not silently turn an exhausted failure into an absent initializer.

The result cannot authorize a vote, installation, publication, read or deletion.
After success, coordination still has to use the ordinary fresh activation,
both governing majorities, exact source validation, FINAL and fresh BARRIER.
Read-only exact completed reply caches cannot renew those authorities. A joining
process may fail after observation; subsequent activation must handle that loss
through its own existing protocol.

Each probe holds 64 KiB of CONTROL capacity through its worker's exit. The old
preparation owns at most one active probe. Close cancels and drains it before
abandoning the old campaign or releasing preparation scratch. A failed drain
retains that child for cleanup retry. All work uses the original preparation
start/budget; no remote monotonic clock is imported and no retry renews a lifetime.

## Validation boundary and remaining work

The initial focused run passed 25 tests in 42.999 seconds. The final-source run
passed **74 tests in 267.928 seconds**, with zero failures or skips; all main/test
sources compiled. Both runs and the affected endpoint/transfer regressions are indexed in
[`phase3-evidence/joining-completion.json`](phase3-evidence/joining-completion.json).
Tests exercise the real read-only handler, original conditional grants, exact
transfer parsing/retries, malformed requests/metadata, non-initial refusal,
deadline/fence revocation, cancellation, resource return and absence of new
grants/publication. Positive client replies are explicitly synthetic routing
observations; they do **not** qualify the native producer or durable initialization.

The existing whole native TCP entry now checks the original old proposer's
probe before initialization (false), then after real force completion and
endpoint handoff (true), before continuing through FINAL/BARRIER and cold reopen.
It is compiled and **deferred**, not executed in this component batch. The
[hosted queue](PHASE_3_DEFERRED_ACCEPTANCE.md) retains this indivisible history.
Automatic coordination/wait scheduling, independent original-first physical
replay, all joining profiles, process death and maximum combined resources remain
required. No POM, workflow, frozen bound, public API or V5.2 experiment changes.
