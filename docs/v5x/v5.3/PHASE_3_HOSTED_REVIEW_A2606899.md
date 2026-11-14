# Phase 3 hosted review: a2606899

Source: `a260689977679acb8582001bb00a135784ce9531`; all listed runs are attempt 1.
The original failed artifacts remain unchanged. Phase 3 and final-source cohort
admission remain OPEN.

## Hosted outcomes

| Family | Run | Successful jobs | Observed result |
| --- | --- | ---: | --- |
| Joining | [43582470815](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470815) | 242 / 242 | 120 originals and 120 replays passed |
| Carried DATA | [43582470403](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470403) | 26 / 26 | 12 originals and 12 replays passed |
| Joint-floor | [43582470481](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470481) | 66 / 66 | 32 originals and 32 replays passed |
| Carried transition | [43582470562](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470562) | 32 / 34 | All 16 originals passed; final-accept-halt replay and dependent aggregate failed |
| Automatic | [43582470309](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43582470309) | 6 / 8 | All three originals passed; competition replay and dependent aggregate failed |

All 183 original jobs succeeded. The four failed jobs have two replay roots;
they are not four independent native failures. Replaying an unchanged reader
would repeat these refusals on the same retained inputs.

## Carried transition: cancelled unselected source

The final-accept-halt history includes a real unselected grant whose reader
received BASIS and PROMISE, then a capsule offer. The exporter offered the exact
capsule chunk after the winning pair had been selected; the client never recorded
that chunk and never sent COMMIT. The prior reader required all CHUNK responses
to have client delivery and therefore rejected the whole original.

The correction admits only this explicit eight-response prefix. It binds the
campaign and unselected grant, all sequence numbers, permanent endpoints,
record and capsule bytes, offers, actual deliveries and the original source
lifetime. The two completed records stay accounted for separately; the capsule
is an offered observation and never a completed source, installation or vote.
Unexpected extra requests, changed content, source retirement or phase crossing
still reject. Complete physical, network and export replay remain prerequisites.

## Competition: overlapping bootstrap continuation

The losing pair installed on node 2 before node 1 completed a higher grant.
Its INSTALL_ACK was offered but not delivered. The higher ballot then installed
on nodes 1 and 3. A third, unused PREPARE on node 2 finished its floor cleanup
and grant after the winning ROUND_INSTALLED, with another undelivered reply.
The old prefix reader required all five captures to precede any installation.

The new explicit continuation reduces each owner's allocator, grant, selection,
installation, floor, generation/source retirement and capture comparison in
original order. It derives intermediate bytes from the preceding state; copied
captures and final files remain comparison targets. It also reconstructs the
losing node's generation lifetime and the delayed unselected grant. Every wire
response and attempted request remains accounted for, including both lost
replies; neither becomes a successful ACK. Winning publication still replays
the original BARRIER and DATA and compares every final inventory.

Only after the full physical/network/export chain and actual automatic lifecycle
pass does the composer select the new interleaved branch. Its ten copied-claim
negatives, twenty applicable temporal-export negatives and twelve lifecycle
negatives are distinct from native fault executions. Six unavailable partial
SELECTED-transfer negatives remain explicitly inapplicable because this original
has no incomplete SELECTED transfer. Other trajectory shapes keep their existing
readers or fail closed. This does not claim general arbitrary schedule coverage.

## Validation and rerun boundary

The downloaded competition original passes all 42 applicable negatives with the
correction. The unchanged final-accept-halt history passes the complete original
chain and all 210 native capture/ownership negatives. All 4,725 V5.3 Python
tests pass, together with the documentation contract and coverage selector audit. Six additional mutations of the retained cancelled-source observation
are rejected; focused unit tests also cover its bytes, delivery and lifetime
boundaries. Detailed local receipts and unchanged artifact hashes are retained
under `target/v53-action-review-a2606899/`.

Only Python readers, their tests, the derived coverage catalogue hash and this
documentation change. Java runtime, workload parameters, source formats, request
limits, workflows and paid-cloud behavior are unchanged. The frozen acceptance
plan is unchanged.

Only Automatic and Carried transition need new hosted runs for this correction.
The other three green families retain their original source identity. They are
not silently relabelled as evidence for the new reader/source; final-source
cohort admission still requires its declared exact-source inputs.
