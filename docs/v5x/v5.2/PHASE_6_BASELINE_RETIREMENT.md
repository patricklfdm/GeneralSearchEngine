# V5.2 Phase 6W baseline retirement observation

**Status:** the real-TCP regression and complete eleven-case authority suite pass
locally. A prior reactor build exposed the preparation timeout described below.
This correction is separate from M01 measurement qualification. Continue under
the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).

## Original failure and diagnostic limit

The build following `ea9bdb9` ran 997 tests with four existing skips and one
failure: `confirmedBulkThenStrongTokenWaitsForTheLaggingFollowersActualPublication`
timed out in `Group.baseline`, before the bulk/publication schedule began. Its
JUnit report and build log remain in `target/v52-baseline-retirement-review/`.
JUnit removed the original temporary runtime directories. That run did not retain
wire responses or the last recovery error, so its precise transport cause is
**unconfirmed**; a later green run cannot establish it.

Two predeclared normal diagnostic histories passed. Between them, a controlled
history lost every response retry for node 3's first source export from each peer.
The real server leases remained undelivered, producing 98 observed
`SOURCE_OFFER / CAPACITY_EXCEEDED` replies. The original 30-second baseline wait
failed while nodes 1 and 2 had retired through index 3. Without any new business
request, node 3 also reached floor 3 at 66.166 seconds after startup, once the
original leases expired. No production authority or lease was changed by the probe.

This establishes a concrete mismatch in the test: its recovery exchange lifetime
is 60 seconds, longer than its 30-second baseline convergence observation.
It does not establish that every earlier timeout had this cause.

## Correction and regression

Only this test fixture's baseline retirement observer changes. It now permits
the configured 60-second operation/lease interval plus the existing 30-second
convergence allowance. It still requires all three actual `RECOVERY_FLOOR` events
to cover the original strong token. A FAILED voter fails promptly. The observer
submits no extra mutation, checkpoint, recovery request or read retry.

Timeout diagnostics include the requested index, observation allowance, observed
floors, public statuses and a bounded tail of 32 peer rejections. These are
diagnostics, not replacement authority. Other 30-second fault waits and the
bootstrap-bound protocol/operation timing are unchanged.

A new real-TCP regression loses both original export responses, leaves their
leases untouched, and requires natural expiry followed by baseline retirement
and compatible minimum reads on all voters. It fails against the original
30-second observer. All eleven authority cases pass after the correction, with
zero failures/errors/skips. A new exact-source reactor build is still required
before the next machine freeze.

The failed reactor build cannot supply a valid shared-build bundle. Its logs,
original test reports, diagnostic histories, source-export rejection ledger and
before/after regression evidence remain at `target/v52-baseline-retirement-review/`.
No production Java, runtime JAR contract, M01–M04 business parameter, workflow or
paid-cloud behavior changes in this correction. Complete measurement and final
protected CI acceptance remain pending.
