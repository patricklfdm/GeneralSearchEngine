# Native backup seed prerequisite

The complete required-four joining fixture previously constructed only an EMPTY
bootstrap. A physical maximum-image joining experiment needs an explicit verified
backup at that same native entry, rather than fabricated images or images held by
an unrelated external receiver.

## Implemented entry

`V53NativeDispatchTest.Network` accepts a complete
`MembershipBootstrapRequest<Integer, Doc>`. The existing size-based constructors
still request EMPTY. Endpoint rebinding changes only loopback endpoints: source,
source path, group/configuration, permanent node/storage identities, target paths,
materialization configuration and admission limits remain those of the caller.
The real `planBootstrap` / `applyBootstrap` path admits the seed before retention
initialization, preparation or network actors are opened.

`V53JoiningIntentExportTest.requiredFourFromVerifiedBackup` explicitly requires a
five-voter verified backup and enters the existing complete required-four history.
It is a fixture hook, not a new accepted hosted profile. No default test, workflow,
resource limit, lifetime, transport retry or cohort membership changes.

The low-level `joining_catalog_evidence.Replay` accepts an explicit
`bootstrap_source` contract. It validates that contract against original bootstrap
bytes before reducing any history. The default is still EMPTY, and existing full
validators retain that default. A producer receipt cannot opt an old gate into
the new source contract. Unknown values and non-string truthy values are rejected
before reading originals.

## Focused validation scope

`V53NativeSeedTest` covers request preservation, a five-voter TCP bootstrap from
three documents at sequence 731, a real initial BARRIER, the unchanged EMPTY
entry, refusal of an undersized source budget before actor startup, and rejection
of EMPTY / wrong-size requests by the required-four backup hook. The backup test
checks the new history identity, unchanged application bytes and typed documents
on the actual publication voters, unchanged original backup and zero resource
leases after close.

Development logs and small original evidence are retained under
`target/v53-native-backup-seed/`; the native collector prints its original evidence
directory under the replication module's `target/v53-native-dispatch/`. These
checks do not fill a final-source cohort slot. The complete backup joining hook
and a maximum-image native history still need their own whole-history execution.

The [development evidence index](phase3-evidence/native-backup-seed-development.json)
records six Java cases, 36 focused Python checks and 19 contract checks. The
five-voter seed/BARRIER original passed in about 62 seconds; independent bootstrap,
catalog/certificate/checkpoint and typed-image replay passed over 654 files
(2,418,046 bytes). Both a false EMPTY source contract and an altered application
image were rejected, with the original inventory unchanged. The unchanged EMPTY
two-slot round also passed. The first invocation used the wrong reactor path;
its log remains retained. In the first actual test invocation, the new source
refusal assertion expected the wrong exception type. The admission correctly
rejected the budget; the exact `ReplicationException` type/message assertion was
corrected and that single case passed on recheck. This is development testing,
not a claim that the original whole invocation was green.

## Bounded native wire storage

For the explicit verified-backup network, `V53EvidenceSpool` now writes each
canonical wire row to its own original `wire.json` immediately. It retains only
row offsets/lengths in memory and materializes one row when a caller reads the
list. The completed file has the exact existing canonical-array format. The
EMPTY entry retains its existing in-memory collector; no cohort or reader
format changes. The spool uses the unchanged 64 MiB aggregate wire budget,
65,536-row limit and 16 MiB per-row encoding/token/depth limits.

The file is exclusively created and its identity/extent checked at append,
read and close. An invalid row, byte/row refusal, I/O failure or observer Error
poisons the collector. A later close cannot add the final array delimiter to
disguise a missing row; the incomplete original stays retained. Network close
closes the spool even when other shutdown work fails, preserving suppressed
failures. Actor-construction failure also closes the newly opened collector.
These are observation files, not forced protocol records or deletion authority.

Validation under `target/v53-wire-spool/` includes 14 spool tests, six unchanged
array tests and two native seed/default checks. A separate JVM with a 32 MiB
heap writes and reads 200 rows totaling over 50 MiB, demonstrating that the
collector no longer retains all payloads or builds a second full array. It does
not establish the whole runtime's memory peak. Tests cover exact boundaries,
concurrent per-producer order, mutable input capture, file replacement, invalid
rows, sticky failure and close behavior. The native original passes independent
bootstrap/BARRIER/typed-image replay and its two source/image negatives. The
unchanged canonical reader accepts 292 wire rows (584 frame decodes,
1,039,201 bytes). This is frame-format compatibility, not full network admission.

All 59 focused Python checks pass after correcting a stale source assertion
that still expected the pre-existing writer to use a literal constant rather
than its admitted `wireEvidenceLimit`. The original failure log remains retained.
The [spool development index](phase3-evidence/wire-spool-development.json) records
the invocation scopes and original hashes. No complete large-image joining run
has been executed by this batch.

## Auxiliary wire cuts

`V53AuxiliaryWire` now owns all five auxiliary histories in the complete joining
fixture: INTENT metadata (8 MiB), pending ACK (1 MiB), sealed head confirmation
(1 MiB), retention initialization (8 MiB) and continuation (64 MiB). Each keeps
its original filename and original snapshot call site. EMPTY histories keep
their previous in-memory encoding, including the old per-message checks where
`canonical` was used. Verified-backup histories use the same per-row/row-count
policy as the main spool and the corresponding unchanged byte limit.

A backup observer continues writing its original under
`auxiliary-wire-spools/` until network shutdown. At the existing snapshot cut,
the spool copies the current prefix with a fixed 64 KiB buffer and appends the
array delimiter to a separately, exclusively created file. Later callbacks do
not change that earlier snapshot or get silently discarded. Both original
staging files and emitted snapshots remain in the evidence tree and count
toward its inventory budget. A partial path that never reached a snapshot does
not acquire a fabricated snapshot on close. Closing one failed spool does not
prevent the other descriptors from closing; distinct failures are suppressed
onto the first, including safe handling of a shared exception object.

In addition to identity/extent checks, each row is hashed at capture and the
complete prefix digest is accumulated as bytes are written. Row reads, prefix
snapshots and final close reject same-length content changes. Snapshot copying
rebuilds the continuing digest while checking the captured prefix; it does not
require digest-provider cloning, a whole-history byte array or a workload retry.
These hashes protect observations, and grant no storage or deletion authority.

The [auxiliary development index](phase3-evidence/auxiliary-wire-development.json)
retains 34 passing Java checks: eighteen spool tests, eight registry tests, six
existing array tests and two native seed/default checks. The 32 MiB child heap
also creates both a half-history prefix snapshot and a complete snapshot of
the over-50-MiB history, then checks that closing preserves the complete bytes.
Registry tests cover every channel in both modes, continued callbacks after a
snapshot, exact prefix bytes, missing/duplicate snapshots, no overwrite, partial
execution, symlinks and closing multiple failed observers. All 75 focused Python
checks pass. The small native seed original still passes independent BARRIER,
typed-image and source/image-negative replay; its 292 main wire rows remain
readable by the unchanged canonical/frame reader.

This is bounded collector and snapshot validation. The complete joining method
has been rewired and compiled, but its full auxiliary backup history has not
been executed here; that long original remains required. The new staging files
cannot be used to extend a historical snapshot's authority or replace missing
whole-history/causal replay.

## Remaining combined-resource work

The [maximum transition](PHASE_3_MAXIMUM_TRANSITION_EXECUTION.md) is still a
synchronous storage probe. This seed entry does not convert it into native learner
or required-four qualification. The [complete EMPTY required-four
original](PHASE_3_REQUIRED_FOUR_ENTRY.md) remains a separate development result.

Before executing a full physical maximum, complete bounded evidence capture for
large images and all auxiliary joining/retention/lifecycle observations, propagate
the explicit source contract through a dedicated complete validator, and declare
the feasible combined pressure and refusal/continuation boundaries. The main
and auxiliary backup wire spools remove their aggregate in-memory allocations;
event arrays, copied snapshots and existing full-array readers remain to be
addressed, along with complete auxiliary-history qualification. Their limits
must not simply be increased. Respect the
unchanged seven-application and per-owner staging limits;
independent maxima cannot be added as if observed together.

All Phase 3 closure gaps remain OPEN. No maximum-image, full backup joining,
combined-resource, final-source or workflow execution qualification is claimed by
this prerequisite.
