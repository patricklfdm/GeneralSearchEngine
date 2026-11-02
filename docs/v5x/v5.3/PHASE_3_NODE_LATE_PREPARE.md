# Phase 3 — unused grant reply across installation completion

The one post-allocation native ACCEPT_RENAMED/halt execution on `a7d35e71`
completed with both original crash/lock observations and a clean second-child
exit. Its second child recovered the carried mutation, published a new BARRIER,
reconciled the next campaign and completed its own DATA publication. The
interrupted client did not report success or resubmit. Original service, call
and parent deadlines remained unchanged, with no JFR or automatic retry.

Initial independent replay rejected `node network request crosses completed
phase`. The original bytes identify a narrower observation-model omission:
node 3 received a ballot-4 PREPARE before `ROUND_INSTALLED`; its source/floor
retirement ended just after that boundary. Its PROMISE response followed at
event 5268, before the first `ROUND_SLOT_BEGIN` at 5277, and was never delivered.
Node 3 was not in that selected pair. This reply supplied no selection, vote,
publication, readiness or contact quorum.

## Exact replay boundary

The current reader classifies only a PREPARE/PROMISE response in the gap between
installation completion and the next slot begin. Every send and actual receipt
must precede installation completion. The original SELECTED must exclude this
peer, the ballot must match, and the physical reader must have independently
derived this peer's post-grant maintenance transition. Request PROMISE and
response BASIS hashes must match the original forced copies. Any delivery
observation rejects this exception.

The response keeps its actual event position. It is counted once with its
originating activation, with the same trace, sequence and bounded duplicate
rules. The existing unused-grant reader forbids a dependent source pull or
selection. Complete floor/source/release replay consumes every maintenance
callback through the actual response; only those checked continuation events
are excluded from the next slot's unrelated-voter prohibition. This is mandatory
full replay, not an ignored error or a fabricated earlier response.

Other kinds, selected voters, requests received after installation, replies at
or after the next slot, changed grant bytes and invented delivery remain
rejected. Legacy readers retain strict phase bounds by default. No runtime,
wire format, retry, selection or deadline changes are part of this reader fix.

## Evidence and scope

The [receipt](phase3-evidence/node-late-prepare.json) retains the successful
native source/build and original inventory, the initial rejected replay, and
the corrected reader results. The history has three campaigns, five published
slots, 768 writes, 755 responses, 13 classified silent attempts and 25 contact
samples. One undelivered late grant is explicitly reported with `authority=false`.

The existing 34 negative cases remain required. Originals exercising this late
path additionally require three exact rejections: fabricated delivery,
substituted BASIS and a missing final floor-release callback. An invalid
original cannot count as successful negative qualification.

The older qualified PROOF/SIGKILL and failed ACCEPT/halt originals retain their
prior results. Native success here is one finite observation after an allocation
reduction; it does not establish a timing root cause or eliminate slower-machine
failures. The new reader postdates the captured runtime source, so this is not a
final-source cohort. The other two rename combinations, joining process
composition and full frozen acceptance mapping remain open; Phase 3 is open.

Rollback removes the explicit late-grant classifier and optional reader plumbing.
That restores the original strict rejection of this retained history; original
files and failed execution/replay records are preserved.
