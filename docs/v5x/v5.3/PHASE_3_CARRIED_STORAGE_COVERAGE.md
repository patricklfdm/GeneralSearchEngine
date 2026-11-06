# Phase 3 — carried file and resource composition

Phase 3 remains **OPEN**. This batch joins whole-replica file inventories to
the actual resource reservations at the same original callback. It reuses
existing producers; it changes no runtime Java, POM, workflow or frozen limit.

Subsequent native execution and the publication scheduling correction are
tracked in [publication handoff](PHASE_3_PUBLICATION_HANDOFF.md). The unexecuted
seven-family statements below describe this earlier batch, not that later pilot.

## One boundary, one owner

The [coverage reader](../../../scripts/v53/replica_storage_coverage.py) first
replays the complete owner's accounting trace, including transitions between
file callbacks. It then joins each file inventory by lifetime, node, original
event index and resource sequence. Checkpoint usage must equal the derived trace
state. A different owner, later reservation or final close cannot supply capacity
to an earlier file state.

Every physical file path contributes its full length exactly once. Identical
images in different directories remain separate copies; active and candidate
journals/ledgers coexist and are added together. Files are grouped under their
actual GENERATION, SOURCE, APPLICATION, JOURNAL or MISC owner. Each group's
simultaneous extent must fit that live reservation. A pending transfer claim
cannot impersonate an original stored owner. Empty files and owned storage
directories still require a live charge. Unknown members and DATA replay output
are rejected instead of being silently left out.

FLOOR image ordinals come from the independently admitted complete immutable
copy. Retirement image ordinals come from that original retirement operation.
Deleting the first image cannot renumber the remaining image; reusing the
retirement directory for a later operation starts a new ordinal set. No captured
partial inventory supplies its own expected image order.

Each reported peak retains the complete single callback witness, its file groups,
resource usage and unbound charges. Separate time peaks and separate node peaks
are never added together. Reserved capacity is reported separately from actual
file lengths. Unbound reservations are preserved, not treated as missing files:
receiving data, network buffers and other directories have separate evidence
obligations. This measures logical file extents, not filesystem blocks, heap/RSS,
every internal write, a saturated worst-case envelope or a cluster-wide
simultaneous peak.

## Original-first entry points

The [complete native reader](../../../scripts/v53/native_carried_storage_coverage.py)
requires the entire [seven-collector chain](PHASE_3_CARRIED_REPLAY_CAPTURE.md)
before resource composition. It independently checks the exact union of the
seven families' callbacks, respecting selected-install/publication context and
the ledger's actual write/reseal points. FUTURE ACK, promotion, clearing and
protocol-return notifications are not extra file captures. Missing a family or
duplicating an event rejects the receipt. The all-family entry is implemented;
the native seven-family producer has not yet run.

The [existing-campaign entry](../../../scripts/v53/campaign_storage_coverage.py)
requires the full earlier native campaign/FLOOR/retirement/resource/process
chain. It qualifies only those three captured families, explicitly leaving
`allSevenFamiliesCaptured=false`. It cannot satisfy the all-family entry. The
[short replay component](../../../scripts/v53/storage_coverage_component.py)
first checks its actual file captures against the independent control replay
model; its protocol provisioning remains conditional.

```bash
# Reuse a complete original campaign capture (three families only).
python3 -B -m scripts.v53.campaign_storage_coverage \
  general-search-engine-replication/target/v53-native-carried-campaign-prefixes/run-<id>

# After the deferred native seven-collector producer has completed.
python3 -B -m scripts.v53.native_carried_storage_coverage \
  general-search-engine-replication/target/v53-native-carried-replay-prefixes/run-<id>
```

The subsequent `--qualify` entry additionally renames ten actual required storage
owners in memory while preserving accounting totals. It first requires the
complete original seven-family chain and then demands the exact physical-owner
rejection. These targeted accounting mutations do not claim that the deliberately
changed trace passes the unmodified full prerequisite.

Both keep Phase 3, cohort admission and whole-runtime resource qualification
false. File equality derives from original transaction authority before the
composition helper runs; the helper alone is only a projection.

## Development results

The [retained development index](phase3-evidence/carried-storage-coverage-development.json)
distinguishes actual captures from expectations:

- The unchanged FINAL and INTENT native histories pass the complete earlier
  original-first chain and storage composition over 2,050 and 3,081 captured
  campaign/FLOOR/retirement callbacks. Their original files remain unchanged.
  The largest observed single-owner file extent is 627,179 bytes across 69 files
  at FINAL life 2/node 1, event 2015/resource sequence 1851. This is one observed
  callback, not a bound for the workload or all runtime resources.
- All seven independent models produce 3,082 and 4,713 expected inventories
  with original resource bindings across sixteen owner lifetimes. These 7,795
  projected inventories **include** the 5,131 already captured boundaries;
  they are not 7,795 additional captures. The remaining 2,664 require the
  deferred producer. Sixteen mutations of the original resource traces retain
  balanced totals but replace a needed owner; all reject with the exact ownership
  reason after the original prerequisite passes.
- The two existing short control writers pass composition at all 46 captured
  callbacks, with observed peaks of 46,138 and 80,051 bytes. Both replay
  identically after relocation under `python -O`. These component results are
  separate from native process qualification.
- 391 related Python tests pass, including 36 new tests. All 36 also pass with
  assertions disabled. They cover simultaneous sums, duplicate-content copies,
  exact owner/extent, original image ordinals, callback coverage/ordering,
  checkpoint integrity, peak witnesses, crash versus close and original-first
  guards. No Java build or new workload execution is needed for this Python-only
  validation change.

Initial development failures remain in the local logs: one invocation lacked
`PYTHONPATH`, two test-fixture expectations were corrected, and the first combined
callback selector incorrectly included future-retention protocol notifications.
The selector now uses the existing exact file-write/reseal vocabulary and has a
regression for those non-file events. No original failure or evidence is removed.

Still open: actual native seven-family composition, unobserved internal core
writes/DATA output and interruption, full simultaneous runtime resource maxima,
six other carried-process axes, application-ACK recovery and final-source hosted
admission. The frozen twelve-subset hosted catalogue and acceptance plan remain
unchanged. This batch dispatches no hosted or paid-cloud run.
