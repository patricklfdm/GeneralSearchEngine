# V4.0 Phase 5 checklist

**Status:** accepted on protected `master`; exact-master CI passed

## Entry and compatibility

- [x] Phase 4 protected PR #81 merged at
  `32e9c84c944ebd4f5c0b9f2d69efd690d25058cc`.
- [x] Exact-master Phase 4 CI run `33594843119` completed successfully.
- [x] No public API or format `1.0` byte change is introduced.
- [x] Published V1–V3.4 and the in-memory `build()` path remain unchanged.

## Lifecycle and concurrency

- [x] Every single/bulk mutation and successful no-op survives checkpoint/reopen.
- [x] Equality, range, prefix and text dynamic create/drop transitions survive reopen.
- [x] Concurrent producers create one contiguous committed sequence.
- [x] Readers observe valid immutable snapshots throughout concurrent publication.
- [x] Checkpoint serialization overlaps post-cut WAL mutation without losing either.
- [x] Concurrent checkpoint requests coalesce at one active cut.
- [x] Close drains accepted checkpoint/WAL work and rejects later admission.

## Faults, capacity and cleanup

- [x] Data rename, manifest force and manifest rename fail safely before authority.
- [x] Post-manifest directory-force ambiguity makes the current writer terminal.
- [x] Cleanup deletion failure is diagnostic and a later checkpoint restores bounds.
- [x] Three-byte writes make progress across metadata, WAL, manifest and checkpoint
  trailer paths.
- [x] Twenty-four checkpoint cycles remain inside the configured retained-byte limit.
- [x] Existing capacity rejection and decode-corruption gates remain active.

## Repeated crash and independent evidence

- [x] Eight hard-halt cycles reuse one exact durable history.
- [x] WAL publication, checkpoint authority-before-cleanup and post-cleanup barriers
  alternate in the schedule.
- [x] Independent byte inspection validates every durable prefix.
- [x] A separate verifier recovers and performs a second reopen after every crash.
- [x] Retained pre-manifest WAL generations require real-header sequence continuity.
- [x] Checksummed repeated-crash and fake-cloud hardening evidence validate.
- [x] No paid cloud resource is required or used.

## Acceptance

- [x] Focused Java and Python fixture suites pass.
- [x] Repeated-crash and fake-cloud Phase 5 gates pass.
- [x] Clean reactor tests pass (421 core and 5 processor tests, zero failures).
- [x] Published compatibility and independent consumers pass.
- [x] Strict Javadocs, six release JARs, reproducibility and JMH smoke pass.
- [x] Required PR #82 merged through protected `master` at
  `c9a8b4725f3c44bced40764d1a9b3e9a4eb37b51`.
- [x] Exact-master Phase 5 CI run `33597658600` completed successfully.

Phase 6 may measure and optimize only from reviewed evidence. It must not weaken the
force, authority, corruption, terminal-failure or cleanup semantics closed here.
