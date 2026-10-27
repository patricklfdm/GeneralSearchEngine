# Phase 3 — native whole-slot coordination

`MembershipSlotDriver` owns one complete outgoing slot under the actual installed
selection. Its caller owns the original activation scope and deadline. It sends
ACCEPT, PROOF and APPLY to the fixed selected cohort in bounded parallel phases,
fetches original vote receipts from their permanent owners, forces the local
certificate and applies it through the typed native application. An ACK digest
cannot replace an original receipt or add a voter.

For each remote publication it first records the exact future target at a
governing quorum, then dispatches the original request. Local publication is last.
The final return rechecks the actual completed publication, including its original
ballot fence. Losing completion after durable publication returns failure rather
than inventing a successful client outcome. A failed invocation is single-use;
the future automatic owner must reconcile retained work before continuing.

One control reservation excludes another local slot coordinator. Payload,
completed receipts and queued peer work remain accounted through their use.
Cancellation reaches the actual socket-write guard, cancels child exchanges and
drains owned tasks. Queued tasks that never start keep their reservation until the
worker pool has stopped. A failed drain keeps ownership for a subsequent close.
No phase renews the original deadline; transport retries remain three identical
attempts and protocol rejection is not retried.

## Current-image reuse during maintenance

The first four-voter integration exposed duplicate application-image reservations:
complete prefix receives coexisted with the current/inactive/original generations
and the separately persisted floor copies. The seven-image bound correctly refused
that overlap. The original failed run is retained.

Maintenance now borrows exact physical current-generation images through the
existing prefix owner. A borrowed image is checked against its original inode,
extent and digest; generation replacement, owner close or the original deadline
revokes the borrow. Receiving scratch holds no duplicate image for an exact local
match. The remote source packet, original generation manifest, ancestry and every
remaining member still have to be acquired and verified from the actual peer.
This is image reuse, not a new vote or proof inferred from a STATUS hint.

Floor images are still separate physical copies with separate reservations.
Only a complete original governing floor permits inactive-generation retirement.
After forcing the floor and peer observations, maintenance deletes receiving
scratch before reserving the retirement copy. The durable floor now owns those
bytes; keeping both sets would also exhaust the six-source bound at four voters.
The frozen seven-image limit, six-source limit and shared staging bound are
unchanged. Arbitrary joint/maximal combined headroom remains a later gate.

## Qualification

The [local receipt](phase3-evidence/slot-driver.json) binds ten final coordinator tests,
seven earlier dispatcher regressions on identical production Java, sixteen earlier
prefix-owner tests, 676 Python tests, four independently replayed three-voter
histories and 100 exact negative mutations. Archive relocation
repeats those original-first checks under optimized Python. All three stable Java
profiles complete both slots. These are local component results; public/protected
and full Phase 3 acceptance remain open. The immutable attempts and original failure are in
`target/v53-slot-driver`. The local checks cover continuous BARRIER/DATA
at stable sizes 3/4/5, original receipts, lost and invalid replies, cancellation,
deadline/capacity refusal and higher-ballot fencing at completion. Independent
physical/network replay uses the three-voter original history and exact negative
mutations, including portable optimized replay. Larger profiles require their own
complete independent audit before full protocol closure.

The four-voter default-request profile subsequently completed the first slot and
second maintenance but exhausted its 5-second socket attempts before the second
ACCEPT completed. That failure remains retained. Qualification of the larger
stable profiles explicitly uses the existing caller-configurable 30-second
request timeout; three voters and fault cases retain the 5-second default. Both
slots still share one original 180-second invocation budget. Production defaults,
resource limits and the maximum three identical attempts are unchanged. This
configured profile cannot establish default-timeout progress or a timing SLA.

This component does not own election timers, autonomous discovery/adoption,
fresh-ballot recovery or public READY. Learner ADD/REPLACE, all seven joint
profiles, carried-entry readiness, repeated maintenance and complete 3B–3E
qualification remain open. No public API, wire/storage format, frozen workload,
cloud workflow, release pin or V5.2 Runner is changed.
