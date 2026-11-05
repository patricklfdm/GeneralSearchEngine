# Native resource accounting and original event binding

The optional `v53.resource.transitions` fixture flag creates the actual old-owner
and joining-owner budgets with mutation observation enabled before their first
reservation. The joining budget remains the same object across initialization,
retaining/repeated/continuation owners and cold reopen. Bootstrap preparation
before `before-network` is outside this observed lifetime. The old owners' loaded
reservations, endpoints, transports and outgoing driver share their original
budget. A temporary empty wrong-budget rejection probe is not a runtime owner.

The shared native event append captures that node's exact resource sequence and
usage under the resource monitor. This covers writer, transport, source-retention
and lifecycle callbacks without changing the existing event rows. Checkpoints do
not copy or append to the mutation journal. No resource operation calls back into
the collector or performs file I/O. Duplicate registrations, unknown event owners,
missing event positions, observation failure/overflow and duplicate save fail the
fixture. Each trace is written once, including an incomplete original when close
did not release everything; writing evidence does not label it qualified.

The collection contains an index, complete event checkpoints and one journal per
registered original identity. It retains the root and exact event/trace hashes.
Identity includes node, storage UUID and endpoint. The native reader derives the
expected owner set from the independently replayed original history, rather than
accepting the collector's list. This includes all six required-four owners,
including offline nodes 4/5 and departing node 3. Each budget must contain actual
accounting mutations, original events and a complete zero-usage close.

Journal encoding applies protocol parsing bounds to each change, not to a whole
multi-thousand-event history. Existing journal capacity remains 262144 changes;
each file is limited to 128 MiB, each encoded change to 512 KiB, the collection to
256 MiB and event checkpoints to 65536 rows / 32 MiB. Independent replay requires
canonical JSON, exact member inventory, digest binding, typed fields and continuous
sequences. Exceeding an observation bound is a failed qualification, never a retry
or permission to drop a prefix. Runtime admission limits remain unchanged.

## Independent entry and scope

`scripts.v53.native_resource_evidence` first requires original physical/network
and publication-storage qualification. The required-four profile additionally
requires the complete export, maintenance and continuous-ledger entry. It then
replays every charge delta, binds every original event to its budget sequence,
and compares publication storage counters to independently derived original file
captures. Concurrent CONTROL/WAITER changes do not falsely become storage changes.
Default stable readers still reject the extra collection unless explicitly opted in.

The required-four entry additionally invokes
[exact transport resource binding](PHASE_3_TRANSPORT_RESOURCE_BINDING.md) for
connected frame buffers. Pre-connection allocations remain explicit unmatched
lifetimes, and service/export/cache CONTROL ownership remains unqualified.

[Floor resource binding](PHASE_3_FLOOR_RESOURCE_BINDING.md) additionally derives
exact copy extents and continuous local-pin coverage from original files. It
checks all floor leases, including changes between callbacks, through directory
cleanup and resource release. Receiving scratch and other storage owners remain
separate from this scope.

`scripts.v53.native_resource_negatives` validates the untouched original before
15 exact-reason mutations. They cover missing/foreign owners, foreign root,
missing/duplicated/misattributed boundaries, sequence/usage forgery, late
registration, altered limits, incomplete journals, a foreign release and live
charges at close. A failure in the original cannot count as a rejected mutation.

```bash
# Short native development check; never uses Maven clean.
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 /opt/maven/bin/mvn -o -B -ntp \
  -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dv53.resource.transitions=true -Dv53.publication.resources=true \
  '-Dtest=V53NativeDispatchTest#nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener' test
python3 -m scripts.v53.native_resource_negatives "$ORIGINAL"
```

For a fresh required-four producer, add `-Dv53.resource.transitions=true` to its
existing native command alongside `-Dv53.joining.requiredFour=true`,
`-Dv53.transport.connections=true` and `-Dv53.publication.resources=true`; qualify
with `--profile 5-REPLACE-required-four`. Never add reconstructed traces to an old
original. A complete required-four execution and corrected original replay now
pass; [floor resource validation](PHASE_3_FLOOR_RESOURCE_BINDING.md) records the
exact source, first reader failure, unchanged original and current scope.

## Local development evidence

The short actual TCP run completed both stable slots in 55.92 seconds of test
execution. All three budgets independently replayed 3576 changes and 1788
original event checkpoints; all four publication transactions / 44 original
storage boundaries matched. All 15 exact negatives rejected. Node 1's largest
observed queue reservation was 1163567 bytes / 45 CONTROL leases; the largest
per-owner staging reservation was 268442795 bytes. These are this run's charged
maxima, not a timing guarantee or a simultaneous cross-node physical peak.

All 48 component Java tests and the short native test passed. The long component
trace replayed 6001 changes beyond the one-message token limit. An unfinished
owner trace, observation overflow and diagnostic failure were all independently
refused. Python regression and contract results, raw inventories, source/report
hashes and the initial negative-test error-message mismatch are retained in the
[development index](phase3-evidence/native-resource-accounting.json).

Whole-runtime physical storage and control-message lifetime derivation, the
complete negative matrices, frozen coverage and final-source
admission/execution remain open. Twelve hosted subsets / 544 planned histories
remain unchanged. This development evidence does not close Phase 3.

Rollback removes the optional fixture flag/capture, checkpoint accessor and new
entry/tests together. Existing disabled observers, durable files, authority
decisions, wire formats and CI topology do not depend on the new collection.

The [receiving resource reader](PHASE_3_RECEIVE_RESOURCE_BINDING.md) additionally
binds original transfers and complete learner generation metadata to their exact
SOURCE/LEARNER/APPLICATION reservations. It shares one admitted maintenance model
with floor resource replay and requires receiving scratch to remain charged
until the corresponding remote copy is forced. Post-handoff learner file custody
and other storage/control lifetimes remain unqualified.

The [persistent BASIS reader](PHASE_3_BASIS_RESOURCE_BINDING.md) now binds original
packet/image charges to creation, retirement and cold-owner lifetimes. It shares
the admitted maintenance model used by floor and receiving readers. Three observed
reopens preserve exact source bytes; ordinary current-generation validation never
authorizes a resource gap. Old-owner final shutdown order remains unqualified
where the original contains no explicit close callback.
