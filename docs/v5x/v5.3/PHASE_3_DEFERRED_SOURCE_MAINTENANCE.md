# Deferred same-cut source reclamation

Phase 3 remains **OPEN**. The [active-write heartbeat history](PHASE_3_ACTIVE_WRITE_HEARTBEAT.md)
completed its sole DATA, but a different original voter failed before a fresh
campaign. Its STATUS observations eventually reported cut 1 on both peers while
its own published cut was still 0. Same-view recovery correctly leaves prefix
selection to a fresh quorum; it must not invent a membership adoption fence from
an ordinary BARRIER or DATA certificate.

## Reclamation and grant admission

The pre-grant maintenance predicate includes two distinct physical situations:

- An inactive generation or retained floor needs the existing complete-copy,
  governing-quorum and retirement transaction before further installation.
- A newer promise has made an earlier same-cut source eligible for eventual
  reclamation, while there is no inactive generation or retained floor.

The latter is an opportunity to free space. Failure to obtain a complete old-cut
quorum does not require deleting originals, nor does it prove that a normally
reserved next grant is unsafe. Peers can already have advanced beyond that cut.

The published-maintenance path can now finish without reclamation after an
unavailable-copy pass **only** when no inactive generation/floor exists and no
joining-copy obligation applies. It rechecks its exact original published
permit, fence and deadline before returning. All source bytes, their owners and
resource charges remain. Normal grant/source/generation admission must reserve
its actual bounded capacity; this path grants no capacity exception or new retry.

After a subsequent selected-prefix installation advances the proposer, ordinary
maintenance acquires and forces the new governing floor and retires the inactive
generation. If there is no pending vote/application, it then uses the existing
published-maintenance permit and source-retirement planner to reclaim superseded
sources covered by that actual floor. Current-generation and floor-referenced
sources remain protected. Image charges release only through their normal original
retirement. Selection or its ACK alone never frees them.

Every other case retains its original behavior: an occupied generation/floor or
joining obligation still needs the required copies; malformed input, integrity
errors, changed promises, higher fences, close, deadline and failed cleanup cannot
use this deferral. Available old-cut quorums still follow ordinary floor creation
and exact retirement. The implementation does not adopt same-view hints, skip
selected installation or create a new service/read lease.

## Qualification

The original implementation fails the new retained-source regression with
`native generation maintenance quorum unavailable`. The initial nine component checks passed. The first native extension then reached
new-prefix installation but failed its BARRIER admission at the original image
resource bound: deferred sources had not yet been swept under the new floor.
That original failure is retained. The subsequent implementation adds the proved
post-installation source sweep above. All nine final component checks pass, and
the native lagging-voter producer completes the new BARRIER at cut 2. Its original
trace records both old source retirements after the new governing floor and before
the new ACCEPT. The complete default-bound three-owner competition still fails:
READY was observed, then higher-ballot competition exhausted node 1's finite
campaign retries. Cleanup also reported `live scratch children remain` from the
endpoint owner. This history is retained as FAIL; no DATA replay or increased
retry budget turns it into success. Competing-campaign timing/ownership and
endpoint scratch drain remain open integration work. Neither a source count nor
a STATUS hint is independent original-history evidence; Phase 3 remains open
until its full competition, process and membership-profile requirements pass.
The [source-bound receipt](phase3-evidence/deferred-source-maintenance.json) retains
all seven executions, including the intermediate fixture compilation failure,
initial capacity failure and current competition failure. The final nine-test,
native lagging-voter and competition runs have identical 901 source/resource/POM
inputs. This is scoped evidence, not a complete reactor or process matrix.

The explicit native case builds two original same-cut sources on a lagging voter,
lets a separate actual majority publish a BARRIER, then asks that lagging voter
to run normal discovery, fresh source selection and a new BARRIER. Its producer
receipt can report only PARTIAL until independent physical/network replay.

Rollback removes the source-only deferral and its regressions. No persistent
format, public API, resource bound, time budget, POM or workflow changes.
