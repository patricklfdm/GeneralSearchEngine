# Phase 3 — completed transfer ownership

Status: **locally qualified component**, 2026-10-28. The complete
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open.

## Correction and evidence

A successful transfer previously kept its original exporter, session and cached
response until the whole campaign ended. Repeated native transfers therefore
exhausted CONTROL reservations before the continuous membership operation ended.
An original diagnostic measured 256/256 CONTROL reservations during subsecond
CHUNK failures. A focused eighty-record workload fails against the original
transfer classes; the first completed record also demonstrably retains four
CONTROL reservations.

Once every distinct immutable content in an export has committed, the corrected
service reserves one terminal marker for the exact final request/reply, then
closes the exporter, session and prior response ownership. A lost final reply may
replay only that identical commit. Changed content poisons the trace; expiry,
higher-ballot fencing and close still reject. A partial multi-content source stays
live. The marker remains bounded and accounted until the original scope ends.
No resource limit, request timeout, retry count, wire or persisted format changes.

The original TCP fixture now emits `gse-v53-transfer-service-v2`, requiring zero
live exports after both clients finish. The independent reader retains exact v1
support with its historical two live sessions. Earlier evidence is unchanged.
These lifecycle counts are source-bound Java observations; they are not inferred
from a successful network ACK or substituted for independent physical replay.

## Local qualification

The isolated build starts at `30fd2d64` and changes only the two transfer classes,
the service test and its Python reader/test. It excludes the pending round-owner
and ancestry changes. The [source-bound receipt](phase3-evidence/transfer-completion.json)
records the exact input inventory, compiled-class hashes, logs and portable archive.

- Forty Java tests pass: sixteen service, fourteen source and ten record cases.
  They include eighty completed records, exact final-reply loss/retry, changed
  requests, fencing, deadline, close, partial multi-content and actual TCP sizes
  3/4/5. All shared reservations are checked at their owning boundary.
- Five reader tests pass in normal and optimized Python modes.
- Both v1 and v2 original physical/wire histories pass before mutation. Each
  reproduces fifteen exact rejections in normal, optimized and relocated optimized
  execution, using the retained readers and catalogs.
- The first archive omitted empty physical directories and correctly failed replay.
  The corrected archive preserves exact directory and file inventories. The failed
  archive/log and all original runtime failures remain retained.

This closes completed-export reclamation only. Continuous automatic transition
qualification, departing proposer/follower FINAL completion, real learner
ADD/REPLACE, all seven profiles, process/fault coverage and complete Phase 3 remain
required. No public service, protected CI or cloud acceptance is claimed.
