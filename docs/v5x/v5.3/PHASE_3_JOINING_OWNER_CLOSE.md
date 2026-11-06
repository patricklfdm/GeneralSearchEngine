# Joining journal shutdown across five original lifetimes

The required-four resource entry now requires actual close intervals for the
five joining journal lifetimes, in addition to the five original network
owners. Its corrected-source complete native execution is pending. Phase 3,
the full resource envelope and final-source admission remain OPEN.

## Original observations

The optional `v53.resource.joined.close=true` fixture flag requires resource
transition capture. `V53JoiningOwnerClose` registers an already open, original
journal and records `JOINING_OWNER_OPEN_RETURNED`, `JOINING_OWNER_CLOSE_BEGIN`
and `JOINING_OWNER_CLOSE_RETURNED` through the existing joining event recorder.
The node identity must match the real journal. The successful return marker is
written only after `MembershipGrantJournal.close()` returns.

| Scope | Original lifetime |
| --- | --- |
| `initial-owner` | Installed joining owner and original retention initialization |
| `retaining-owner` | First cold retained-owner reopen and BASIS capture |
| `repeated-basis-owner` | Same original BASIS checked after another reopen |
| `continuation-owner` | Joined endpoint, native FINAL and stable BARRIER |
| `stable-cold-owner` | Final cold reopen of the stable result |

The explicit initial close and automatic scope cleanup share one observation
guard, so they cannot invent two lifetimes. A previously closed journal, a failed
close, a failed observation or a second close cannot produce an additional
successful interval. Conditional null owners produce no observations. Existing
endpoint/transport shutdown remains before journal shutdown. The guard releases
no lease itself; ordinary journal cleanup performs the actual work. This is test
instrumentation, with no production runtime, disk format or resource-limit change.

## Independent replay

[`joining_owner_close.py`](../../../scripts/v53/joining_owner_close.py) requires
all five ordered open/begin/return triples from the same original joining node.
Each marker is bound to its exact event index and resource checkpoint. Reopens
must have distinct resource intervals. Begin must still own live journal and
generation storage, with no queued CONTROL or WAITER reservations. Only RELEASE
changes may occur during close, and every live lease must be gone by return.
The last close return is the terminal resource sequence. Subsequent owner events,
duplicate scopes, omitted markers and balanced allocations during shutdown fail.

Persistent BASIS storage uses these same boundaries. Each original packet and
image must remain charged through the actual close **begin**, then release by
the corresponding return. The earlier fallback that used the last event before
reopen would incorrectly choose a newly observed close-return marker as a
still-live boundary. The reader now selects explicit joining intervals when
present; historical unmarked originals retain their earlier limited scope.
Retirement still uses its original forced deletion/clear boundaries.

The shared physical cold-reopen reader accepts the exact marked sequence only
after all five joining intervals are present. It still accepts the historical
unmarked sequence at its original scope. No marker is filtered out: missing,
duplicate, foreign or misplaced markers and changed force order are rejected.
The original reader's rejection of a complete marked sequence is reproduced by
a focused regression before the correction.

Twelve joining-close mutations check missing/foreign/reordered markers, early
returns, hidden allocations, nonquiescent starts and work after the final return.
The [required-four entry](PHASE_3_REQUIRED_FOUR_ENTRY.md) also makes the existing
twelve network-close negatives mandatory. It now requires **71 exact negatives**:
15 accounting + 19 handoff + 13 file custody + 12 network close + 12 joining close.
Complete original physical/network/resource replay precedes all mutations.

The new entry pins both `v53.resource.owner.close=true` and
`v53.resource.joined.close=true`. An old original without the new markers fails
before expensive replay and cannot be relabelled or repaired by adding markers.
The prior failed originals, historical indexes and their source identities remain
unchanged. This adds no hosted history or changes to the twelve-subset catalogue.

## Validation scope

A short component test opens and closes real bootstrapped journal files five
times, sharing one observation-enabled resource pool. Independent replay of
those actual observations checks five lifetimes and twenty releases, then all
twelve joining-close negatives. This proves the collector and interval reader
against real journal cleanup; it is **not** a native joining or required-four
execution. Focused tests also cover scope/identity rejection, idempotent fixture
cleanup, failed observations and original BASIS bindings.

Logs, original observations, negative results and validation hashes are retained
under `target/v53-joining-close-entry/`. The initial test setup failure (missing
fixture parent directory) remains retained separately from the corrected runs.
The complete corrected-source required-four history remains deferred to hosted
verification. Observed close accounting does not establish the precise OS-lock
release instant, all intermediate file lifetimes or simultaneous physical maxima.

Rollback removes the opt-in guard, markers, reader integration and new mandatory
entry flags together. Preserve the prior originals and original-first physical,
source, handoff and file-custody checks; do not accept a partially marked history.
