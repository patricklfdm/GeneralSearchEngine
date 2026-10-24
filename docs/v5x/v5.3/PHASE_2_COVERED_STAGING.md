# Applied staging behind a published majority

Status: private storage recovery implementation. Phase 2 remains **OPEN**; public
membership execution remains disabled. This extends
[unapplied phased-vote recovery](PHASE_2_COVERED_PHASED_VOTES.md), not the voting or
publication authority of an old ballot.

## Reproduced gap and authority

An admitted lagging voter can actually apply its certificate and retain its
applied end while a disjoint majority publishes the same certified entry. After
all voters capture a newer ballot and select that published prefix, installing it
on the lagging voter previously failed with `settlement conflicts with derived or
protected authority`. The rejection correctly preserved the old applied files,
but there was no explicit path for retiring them under this newer selection.

`retireCoveredApplication` now verifies the complete selected installation plan
before touching derived staging. It requires the current original certificate and
selector, a newer durable PROMISE/BASIS/SELECTED, the exact original local frozen
source (including all phased records), the same stable authority, authenticated
old-parent ancestry and a prefix covering the old slot. Protected contexts and
incomplete authority transactions remain excluded.

Typed replay reconstructs the original result from the original image, payload,
certificate and actual phased observations. Its resulting cut, catalog and image
must be an authenticated endpoint of the selected prefix. The existing bounded
applied-end retirement transaction validates every original staged member and
binds the covering generation/selector in its private authority map before any
applied-end deletion. It does not acknowledge the old application again. The old
vote, selector, journal, sources and generation remain unchanged until the
subsequent ordinary installation and independently authorized retirement paths.

The existing same-parent `retireSupersededApplication` shares the typed cleanup
implementation while retaining its original authority-map bytes. Shared selected
plan construction remains the same for installation and coverage verification.
Selection and installation retain their live voting fences. Pure verification
for this exact cleanup does not lower or persist a higher volatile observation;
cleanup can complete, while installation/acknowledgements remain fenced.

## Local qualification

The retained [evidence index](phase2-evidence/covered-staging.json) records the
original red reproduction, each subsequent producer/source manifest, raw outputs,
Java reports, compiled artifacts and independent Python replay. Failed attempts
are retained; historical observations are not relabelled as final-source runs.

The admitted profile matrix covers 3/4/5 voters, each EMPTY and verified backup:
eight lagging applied owners, 24 initial voters and 40 subsequent node publication
results. Eighteen cleanup boundaries are interrupted twice, including replay
scratch, candidate/active retirement authority, partial deletion and directory
removal. Final recovery preserves all original voting bytes before the selected
prefix is installed. Negative runtime checks cover missing phased observations,
changed images/ACKs and altered retained cleanup authority. Higher-observation
checks cover entry and four in-flight boundaries. Existing phased settlement,
same-parent staging and observation-fencing tests remain regressions.

Independent replay derives the complete admitted/source/publication chain, old
applied files, retirement marker, exact protected originals, force/delete order,
repeated interruption states and post-cleanup installation. Seventeen modified
evidence cases must fail for their exact expected reason. The unmodified chain is
validated before any mutation; normal Python, optimized Python and relocated
replay must agree. Replay scratch is bounded and tied to the exact claim; its
application semantics remain the typed Java producer's responsibility.

No frozen format, resource ceiling, public API, workflow or V5.2 experiment
changes. These small-image profiles and exception interruptions do not establish
fresh-process/power-loss durability, maximum-size lifetime or complete cross-view
qualification. An old applied endpoint hidden inside a still later compacted
range needs separately qualified supplemental ancestry; this batch does not
silently authorize its deletion without that proof. Protected-context covered
recovery and the other [Phase 2 obligations](PHASE_2_CLOSURE_CHECKLIST.md) remain
pending.
