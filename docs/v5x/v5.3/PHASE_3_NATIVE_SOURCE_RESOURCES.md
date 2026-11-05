# Phase 3 native source/control resource binding

The [source component qualification](PHASE_3_SOURCE_CONTROL_RESOURCES.md) now has
a multi-session reader in `scripts/v53/native_source_resources.py`, integrated
into the original native accounting/physical pipeline. Exact input and report
hashes are in the [development index](phase3-evidence/native-source-resources.json).
Phase 3 remains OPEN.

## Native binding

Each copied transport request must be allocated while its original logical
request buffer is still charged, with the same original byte extent. The copy
has its own send/terminal lifetime. Cancellation may release the logical buffer
before that later terminal; it cannot release before the copy's allocation.
Response bytes come from the
validated wire response, not counters. Each response must be allocated after its
first original request read, belong to the original source/reader/root/trace
session, and be live when offered or already transferred to that session's exact
completed cache. A completed cache grows before response/session release; its
extent is exactly `32768 + original reply bytes`. Serial replacement is checked
within each session while unrelated sessions may overlap.

A new allocation nonce can represent a new service lifetime with the same
request/session hash. It cannot reuse an earlier allocation, borrow an unrelated
session, or let one trace reopen an export. The native reader separately tracks
all such allocations rather than collapsing them by request hash.

Joining checkpoint serving uses `joining-checkpoint-trace` with the same original
identity hash and allocation nonce. The marker name fits the frozen 128-character
owner bound. This observation change preserves bytes, retries, deadlines and
capacity. Actual joining-endpoint lost-reply, later-campaign and owner-close
regressions pass; full new-source joining/native resource qualification is still
pending.

## Physical replay and compatibility

The stable physical reader formerly accepted only response rows without socket
metadata. New collections first pass complete original connection replay; only
then are connection fields projected out for the existing response/physical
checks. Event positions are preserved. Partial or forged connection metadata is
rejected before projection. No protocol check or original failure is discarded.

`python3 -m scripts.v53.native_resource_evidence RAW --source-control` requires
complete new source bindings. An all-legacy or missing collection rejects in this
mode. Without this flag, historical UUID-only resource owners report
`sourceControlResources.status = NOT_OBSERVED`; they are not retroactively
qualified. Whole-runtime and final-source flags remain false in either mode.

The short native collector opt-in is `-Dv53.resource.source.control=true`, with
`-Dv53.resource.transitions=true -Dv53.transport.connections=true`. It enables
original request observations and refuses missing prerequisites. Owner-close,
unsent and publication observations retain their existing independent flags.

## Retained development evidence

One new three-owner native activation and two-slot history passes original
storage, network, publication and accounting replay. It binds 444 reservations:
183 request buffers, 183 response buffers, 39 sessions and 39 traces, including
37 completed caches. Each selected owner reaches two simultaneous sessions.
All 17 coherent native mutations reject for their specific obligation. An older
owner-close history still passes its original scope and is explicitly refused by
the new strict source-control option. No original is rewritten or rerun for a
reader correction.

The native execution used the source inventory captured before the subsequent
joining-checkpoint owner-name correction; the development index records that
one-file difference and the separate endpoint test inputs. It does not relabel
the short history as final-source execution. Long required-four and hosted
qualification are deferred until the remaining implementation is ready.

## Remaining boundaries

`allObservedSourceBuffersBound` means these four source categories (plus the
separate joining trace category when observed) match original transport
boundaries. `serviceCloseIntervalsQualified` remains false: nested lease release
and final zero accounting do not prove the exact service close call/return.
Exports, task/control owners, physical post-handoff custody, combined maxima,
completion headroom, further negative matrices and final-source hosted
qualification remain separate obligations. No limits or frozen histories change.
