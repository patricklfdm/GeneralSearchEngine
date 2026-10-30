# Current-view heartbeat admission

Phase 3 remains **OPEN**. The private activation endpoint now handles the frozen
`HEARTBEAT` / `HEARTBEAT_ACK` messages. This is an inbound component for subsequent
automatic election ownership; it does not start a scheduler, grant service or
qualify automatic failover.

## Admission and fencing

The exact current root, view, permanent sender/recipient identities and ballot
proposer are validated before observation. The sender must be a remote current
voter. A joining learner or removed member cannot send or receive a voting
heartbeat. The advertised cut must belong to the same governing view; newer-view
discovery still requires the existing original-prefix acquisition path.

An authenticated higher ballot updates the existing volatile root fence before
waiting for the storage writer or incoming control queue. Old in-flight work
therefore cannot continue just because that writer is busy. The actual reply
rechecks the owned original storage, current view and exact observed ballot under
the writer monitor. A lower heartbeat cannot lower the fence or receive an ACK.

The ACK contains only the receiver's actual durable cut. The peer's advertised
progress and `activated` flag remain hints: they cannot install a prefix, force
a promise/basis, contribute to a vote or retention majority, open an activation
scope, restore READY, or authorize a read. An ended scope stays ended, and its
deadline is unchanged. The heartbeat request itself also keeps its original
deadline across a writer wait. No heartbeat timer is persisted or restored.

## Validation and evidence

The [receipt](phase3-evidence/heartbeat.json) binds the exact native source
snapshots, test results, original TCP traces and reader inputs.

- Nine new Java tests pass, covering immediate fencing while the writer is held,
  both activation flags, untrusted progress, stale ballots, foreign root/view or
  recycled identity, learner/removal exclusion, ended/closed scopes and deadlines.
- All thirteen existing activation endpoint tests pass on the same production
  source. Conditional joint/learner fixtures are used only for eligibility checks.
- Real native 3/4/5-node groups complete 6/12/20 heartbeat exchanges over loopback
  TCP. Every original file is unchanged, all scopes remain unactivated, and close
  releases all resource ownership.
- The independent reader derives public bootstrap and initial retention files,
  checks complete before/after inventories and all 38 correlated wire exchanges,
  and permits only the exact response/delivery events. Nine evidence mutations
  per group (27 total) reject altered storage, cut/correlation, missing delivery,
  hidden writes and hidden failures. Twenty-one focused Python tests pass.

The first compilation caught a generic type in the new test; the next execution
found a test referencing a nonexistent joining identity. Both test fixes and
their original logs are retained. Final qualification passes without changing
the production implementation or weakening an assertion to accept the errors.

Replay each original native directory with:

```bash
python3 -m scripts.v53.heartbeat_evidence /path/to/original/run --qualify
```

This batch does not provide outgoing heartbeat scheduling, bounded automatic
campaign ownership, peer-loss handling, continuous native election/rejoin
qualification or a public runtime. Those remain required Phase 3/4 work.
No frozen format, workload parameter, POM, workflow or paid-cloud change occurs.
Rollback removes the private heartbeat helper, its journal/endpoint routes and
the added tests/reader; original evidence remains retained.
