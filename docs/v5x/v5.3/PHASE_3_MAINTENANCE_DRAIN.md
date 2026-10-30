# Maintenance drain ownership

Phase 3 remains **OPEN**. The retained three-owner competition in
[deferred source maintenance](PHASE_3_DEFERRED_SOURCE_MAINTENANCE.md) failed its
finite campaign gate and also reported `live scratch children remain`. That
original run did not inventory the remaining live scratch, so it cannot establish
which cleanup failed. The regression below independently reproduces a concrete
ownership defect; it does not retroactively explain every earlier failure.

## Original ownership survives a failed cleanup

A source pull can fail while its receive directory still contains original files
and charged leases. Cleanup deliberately refuses a foreign file or changed inode.
Previously, maintenance removed that pull from its registry in a `finally` block,
even when `close()` threw. Its endpoint/activation parents likewise unconditionally
discarded the maintenance reference. A higher incoming scope was also published
before the old scope finished closing. These paths could lose the only live
reference capable of safely retrying the physical drain.

Maintenance now removes a pull only after its close succeeds. It attempts every
registered cleanup, retaining failed owners and reporting their errors. Both
incoming and outgoing parents keep the maintenance object until it reports a
complete drain. A higher incoming scope can replace the previous scope only after
that old scope closes successfully; concurrent handoff receives the existing
capacity failure. Higher-ballot observation still precedes admission and does not
wait for this cleanup. No list of abandoned scopes grows behind the resource cap.

A later explicit close may release the same original files after the blocking
condition is resolved. It cannot resume the failed protocol operation or renew
its deadline. Unknown bytes remain untouched, and protocol errors are not retried
as ordinary I/O. Formats, public APIs, time/resource limits, campaign counts,
workflows and the single client DATA rule are unchanged.

## Validation and remaining gates

`V53MaintenanceDrainTest` injects an ordinary source interruption after a real
receive file is created. A deliberately foreign file then prevents deletion.
The original implementation fails all three initial cases: direct maintenance,
endpoint close and higher-scope handoff. The corrected suite also covers outgoing
pre-grant maintenance. After removal of only the test-owned foreign file, close
must drain the original receive, restore the prior resource usage and leave
authority unchanged (except the explicitly admitted higher local promise).
All **24** corrected-source checks pass: the four new regressions, fourteen
endpoint tests (including real TCP at three group sizes), four existing maintenance
cases and two pre-grant cancellation/fencing checks. The run took 198.453 seconds.

The competing-node producer now retains per-node post-close file inventories,
hashes, bytes and remaining lease counts. It saves the original failure before
writing supplementary diagnostics. A first diagnostic execution itself failed
because the protocol JSON encoder rejects slash-containing object keys; the
inventory now uses path values in an array. That failed attempt is retained, and
is not a successful competition observation.

Measured results and source bindings are recorded in the
[qualification receipt](phase3-evidence/maintenance-drain.json). Component
regressions are separate from complete three-owner convergence, physical/network
replay, process cuts and all membership profiles. Long acceptance matrices may be
collected later with the planned hosted measurement workflow; they have not been
dispatched by this batch.

The complete competition ran for 146.473 seconds and remains **FAIL**. Nodes 3 and
2 each completed startup before a higher ballot revoked their observed readiness.
Node 1 later failed selected-retention merging with
`peer retention unresolved endpoint capacity`. There was no completed client DATA.
All three nodes nevertheless closed successfully with zero leases and only the
small owner/lock markers remaining in every scratch scope. This finite result
supports the observed drain; it neither proves all cancellation schedules nor
qualifies whole convergence. Selected-retention capacity and its actual original
history are the next integration investigation, without enlarging the bound.

Another source-layout boundary remains to qualify: incoming maintenance creates
direct `source-<uuid>` children, while existing incoming cold scratch recovery
recognizes only nested selected-source directories. This change concerns live drain
ownership; it does not claim to close crash recovery at every maintenance cut.

Rollback reverts the three private lifecycle changes and their regression tests.
No on-disk migration is required. Original failed evidence remains immutable.
