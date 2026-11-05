# Phase 3 export constructor rollback ownership

This follows [joining request bindings](PHASE_3_JOINING_EXPORT_REQUESTS.md).
The [development index](phase3-evidence/export-constructor-rollback.json) retains
three actual conditional failure paths. Phase 3 remains OPEN; a successful
constructor and its later direct probe are different ownership scopes.

## Observation and cleanup

With export ownership observations enabled, five joining metadata constructors
record `EXPORT_ROLLBACK_BEGIN` immediately before their existing failed-constructor
cleanup and `EXPORT_ROLLBACK_RETURNED` only after that cleanup returns normally.
The metadata lease is the actual owner. Retention/INTENT constructors also record
the actual nested prefix handle if acquisition succeeded. A failure before metadata
reservation creates no allocation and needs no invented resource marker.

The existing cleanup order, rethrown exception, limits, formats and deadlines are
unchanged. Export descriptors are inspected outside the resource monitor; only
bounded record emission occurs inside it. Foreign, malformed or truncated
observations invalidate evidence without replacing cleanup. When observations
are disabled, the methods do not inspect the nested exporter.

An already revoked child still has its original identity. This is distinct from
borrowing a replacement or obtaining permission to omit the child. A failed
cleanup has no successful-return marker, even if later work releases every lease.
Normal rollback requires the child to release before the metadata and both to
release before the recorded return.

## Independent replay and scope

The close reader requires an exact live metadata invocation, original children,
matching call/return, release order and complete bounded observations. Export
inventory separates session, direct-operation and rollback ownership and rejects
any handle claimed twice. Rollback allocations remain immutable RESERVE/RELEASE
pairs. Unmarked allocations remain explicitly unclaimed; final zero usage does
not classify them.

`export_rollback_evidence` independently binds the component call boundaries and
its original first request digest to the metadata owner, fixed extent and expected
child group. For these synchronous probes, it also verifies unchanged baseline
ownership across failure. The capacity case retains all six original prefix
borrows while the seventh attempt fails. This synchronous baseline equality is
not imposed on a concurrent native runtime.

The three original cases are:

| Case | Failure point | Rollback group |
| --- | --- | --- |
| retention-capacity | Existing six-borrow registry is full | Newly reserved retention metadata |
| retention-expiry | Acquired prefix expires during constructor validation | Metadata plus the exact already-revoked prefix |
| preparation-guard | Original guard rejects after export-copy reservation | Export metadata; shared publication remains owned |

The outer component receipts stay PARTIAL. These conditional fixtures neither
initialize a native joining member nor qualify every constructor, served-content
capability, physical peak or whole-runtime custody. In particular, adding generic
rollback inventory does not set `failedConstructorExportsQualified` to true.

## Retained checks

- Three real constructor regressions fail with the earlier constructor cleanup
  sites: all fail specifically because the two rollback markers are absent.
- Nine new Java tests cover actual failures, disabled observation, all five
  metadata roles, foreign groups, descriptor lock ordering, prior revocation,
  failed cleanup, missing release and truncation. The complete focused run has
  54 passing tests and no skips/errors.
- Fourteen new Python tests plus adjacent readers total 167 passing tests.
- Final original captures pass 35 exact mutation checks: eleven per case plus
  missing-child and parent-before-child mutations for the nested case. Original
  accounting/cleanup must pass before mutations; unrelated rejection is failure.
- The retained stable native original still passes its complete physical/network/
  resource/export replay. It has no constructor rollbacks and is not promoted to
  joining or new-runtime qualification.

Logs, source hashes, copied JUnit records and original capture paths are retained
under `target/v53-export-constructor-rollback/`. The first Python development run
exposed an invalid dict/set union, and the first new fixture run lacked updated
transition sequence metadata; both failed logs remain alongside corrected runs.
Two corrected Java executions are retained; the second follows a whitespace-only
checkpoint source correction and binds the final exact Java input bytes.

Remaining work includes successful direct probe ownership, full joining/
required-four composition, failure cases beyond these three, independently bound
physical content/custody and final-source hosted qualification. No workflow,
paid execution or frozen phase coverage changes are included.
