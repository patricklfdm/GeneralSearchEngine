# Phase 3 hosted review: b23242fa

Reviewed source: `b23242fae2f55acee96bbdffdf3993bb82a14c2a`; both runs below
are attempt 1. Original failures remain retained. Phase 3 and final-source cohort
admission remain OPEN.

| Family | Run | Result |
| --- | --- | --- |
| Carried transition | [43653110389](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43653110389) | All 34 jobs passed: 16 originals, 16 replays, preparation and aggregate |
| Automatic | [43653110445](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43653110445) | 3/8 jobs passed; competition and higher-ballot-restart originals failed, their two replays and aggregate consequently failed; reply-revocation original/replay passed |

## Durable allocation lost to an observation

Competition received a higher authenticated observation while reserving its own
counter. The counter had completed its force/rename/directory-force sequence,
but the post-force fence check threw a generic exception and poisoned the
journal. Automatic recovery could not treat it as a normal campaign loss.

A completed reservation now reports the existing typed `HigherBallot` cause.
The counter stays consumed and the next reservation must exceed the observation;
no promise, selected value or publication is added by that failed reservation.
Ownership and allocator write/force failures still poison the writer and remain
terminal. The automatic adapter uses its existing bounded fresh-session recovery,
without replaying a client mutation or renewing the original deadline.

Two regression methods cover all seven allocation cut points, equal/higher
observed counters, reopening, and injected I/O failure alongside an observation.
The positive regression fails on the original implementation; both pass after
the fix, together with the existing journal, campaign-fence and owner regressions.

## Restart: transmission budget and an actual reconciliation

The failed original selected nodes 1/2, then nodes 1/3 after the authenticated
fence. Before its sole DATA call, retained peer observations required one native
reconciliation, selecting nodes 1/2 again. It therefore produced three BARRIERs
inside **two automatic-owner sessions**, rather than the fixture's fixed two
BARRIER assumption. The final PUBLISH exhausted three 5-second transport
attempts while the receiver was still fetching checkpoint authority. This is
not evidence that the protocol's original 300-second lifetime was exhausted.

The restart **semantic fixture only** now uses the existing explicit 30-second
control-request profile. Its leadership policy stays at the original defaults:
heartbeat 5 seconds, election 15–25 seconds, operation policy 20 seconds. Simply
deriving that policy from the longer transport timeout would instead wait
90–150 seconds per election; a local diagnostic exposed that configuration
coupling and the final fixture does not use it. The 300-second original lifetime,
three transport attempts and one client DATA call remain unchanged. Production
defaults and competition's default-bounds profile are unchanged. This result
will not establish a default-5-second transport performance guarantee.

The fixture records both profiles and every attempted request with its original
event anchor. The explicit current-profile reader accepts two campaigns, or
exactly one additional pre-DATA reconciliation, while retaining two owner
sessions and one higher-ballot loss. It independently reconstructs every snapshot,
selected source, retirement, ancestry and original wire transfer. A formerly
unused candidate can retire a superseded same-cut source before forcing its new
BASIS; becoming selected does not waive its floor, deletion or transfer checks.
A lagging selected source also needs its actual compacted-ancestry acquisition
and must retain that lower endpoint through later application/publication.

Silent failures are bound to attempted bytes, identities, ballot, source cut,
phase and finite attempt count. Only exact unused retention intents and the
original unused checkpoint lookups are admitted. They supply no ACK, source,
majority or completion. A recorded response needs a preceding distinct send.
Unknown silent requests still reject. Historical default-profile originals keep
their original reader; the new collector requires the declared profile and send
inventory. Original validation precedes all exact-reason negative mutations.

## Validation and follow-up boundary

Local validation records are retained under `target/v53-action-review-b23242fa/`,
including downloaded artifact hashes, original failures, diagnostic failures and
replay receipts. The final restart JUnit execution passed in 124.6 seconds with
its original 300-second lifetime. Its complete physical/network/lifecycle replay
passed with all 77 applicable exact-reason negatives (55 physical/network/profile and
22 lifecycle). One unused-source mutation is explicitly inapplicable to this
original. Source-bound hosted qualification is still required.

The unchanged failed hosted history's completed prefix through the third
BARRIER also replays independently, including changed peers and ancestry. Its
incomplete final DATA is still FAIL: this prefix check does not promote that
original to a successful execution. An earlier successful hosted default-profile
history remains readable unchanged. A separately labelled synthetic reader
fixture exercises the new profile's negative paths; it supplies no native or
hosted evidence credit.

The 4,731-test Python run had one stale coverage-catalogue assertion: it listed
only the historical profile. After adding the explicit control-profile vector,
all 48 related tests pass, including the full coverage suite and new collector
checks. The initial failed log remains retained. Documentation contracts, source
coverage audit and whitespace checks pass.

Only Automatic is selected for the next hosted run. Its three originals and
three independent replays must share the new source/build, so reply-revocation
runs with the two repaired cases; old-source green results cannot be spliced into
that aggregate. Carried transition and other green families retain their exact
prior identities, and are not automatically rerun or relabelled as new-source
qualification. No workflow, frozen acceptance scenario, paid-cloud behavior or
release setting changes.
