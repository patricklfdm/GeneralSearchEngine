# Phase 3 — carried control replay scratch capture

Phase 3 remains **OPEN**. This batch extends the
[ledger collector](PHASE_3_CARRIED_LEDGER_CAPTURE.md) with original core replay
scratch inventories and continuous completion-reservation binding. It implements
the next composed native entry but does not run or admit that long history.

## Exact control-record scratch

The [independent model](../../../scripts/v53/native_replay_files.py) derives the
claim from the original selector, certificate and node/storage identity. It derives
input members from the selected original application image, requires the applied
control image to be byte-identical and rejects changes outside the applied end.
It supports only INTENT, FINAL and BARRIER; DATA is explicitly rejected.

At each original `REPLAY_*` callback it projects the complete replica inventory:
reservation before any scratch, directory creation, empty/half/full claim,
claim force, pre-application, completed typed input, every children-first deletion,
and return with the original replica restored. Input consists of the exact three
backup members. The claim is deleted only after work; the scratch directory is
last. No unrelated file or directory may change. There are 23 callbacks per fresh
control application. There is no output backup for these control records.

The seventh optional recorder uses the same original event index, owner, PID,
root, lifetime and terminal digest as the other six. It copies while the owning
writer is held, checks the original inventory before/after, preserves the existing
2048-capture and 256-MiB-child limits, and keeps the fresh-process writer-lock
probe. An unfinished replay cannot claim CLOSED or use the vote-rename crash
exception. Empty pre-application crash coverage remains explicit.

## Continuous reservations

The [resource binding](../../../scripts/v53/replay_resource_binding.py) first
replays the entire original owner's accounting trace. Every original checkpoint
must have its exact event index, owner, ordered integer sequence and derived usage.
From `REPLAY_RESERVED` through `REPLAY_BEFORE_RETURN`, the actual
`application-replay-input` and `application-replay-output` charges must each retain
64 MiB, with no release/reacquisition even between callbacks. This is reserved
capacity, not measured physical consumption. The retained-completion path keeps
these charges after return; only the original later retirement/close may release
them. The first process's crash prefix is never called a successful drain.

The [native reader](../../../scripts/v53/native_carried_replay_prefixes.py)
requires the complete original ledger/completion/vote/campaign/FLOOR/retirement/
resource/process chain before inspecting the new sidecars or earning mutation
credit. Its wrapper contains `previous/` (the entire ledger wrapper) and
`replay/life-1`, `replay/life-2`. It defines 25 file/header mutations with exact
rejection reasons. Original bytes cannot supply their own expected file plan.

## Development qualification

The [development index](phase3-evidence/carried-replay-prefix-development.json)
separates these results:

- 27 distinct focused Java tests pass across two invocations (25 first, seven
  shared/FLOOR checks second, with five shared tests repeated). Two real control
  applications retain 46 writer-held inventories, complete accounting traces,
  successful writer-lock probes and zero leases after actual owner close.
- The [short component reader](../../../scripts/v53/replay_prefix_component.py)
  validates all 46 inventories and 18 exact physical negatives. Both originals
  replay identically after relocation with assertions disabled. Their provisioning
  is conditional; these are not new native crash histories or protocol admission.
- 279 related Python tests pass, including 20 new tests; the 20 also pass under
  `python -O`. They cover full reservation extents/owners, release and reacquisition
  between callbacks, checkpoint identity, unsupported DATA, early/missing files,
  deletion order, unrelated changes, original-first guards and exact negative reasons.
- The unchanged original FINAL and INTENT process histories independently yield
  115 and 184 **expected** scratch prefixes. All 13 replay transactions bind to
  their continuous original reservations across 16 owner lifetimes. The default
  force receipts are unchanged. Twelve mutations of those original traces preserve
  their balanced totals but rename the input/output owner; every binding rejects
  with its exact reservation-ownership reason. Originals remain unchanged. This
  projection is not captured-byte qualification.

Deferred composed entry:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedReplayPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_replay_prefixes \
  general-search-engine-replication/target/v53-native-carried-replay-prefixes/run-<id> \
  --qualify
```

Remaining: actual composed native vote/completion/ledger/replay qualification,
internal core file-write interruption and DATA output capture, complete simultaneous
resource maxima, six other carried-process axes, application-ACK recovery and
final-source hosted admission. Control callback inventories do not establish every
internal core write or process-death durability. Production Java, POM, workflows,
frozen parameters and the twelve-subset hosted catalogue remain unchanged. No
hosted or paid-cloud experiment is run in this batch.
