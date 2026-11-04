# Required-four original owner and retirement replay

Status: **owner-file and slot-force replay PASS; complete network/resource
qualification OPEN**. This extends the [required-four semantic/publication
result](phase3-evidence/required-four-pinned-native.json) without rerunning or
changing that native execution. It is a development topology, not another frozen
membership profile or an accepted final-source cohort.

## Original authority and reconstruction

The retained native run used runtime `25d80cb3`, passed all eleven slots, FINAL,
the successor BARRIER and cold reopen in 1353.704 seconds. Java sources and built
classes were unchanged across that run. The current Python reader is newer;
its hashes are recorded separately in the
[physical replay index](phase3-evidence/required-four-physical.json). No current
source claim is inferred from the older runtime receipt.

`scripts.v53.required_four_physical` independently derives the old owner files,
joining placement, owner handoff, initialization, selected installations and
continuation from original generation/source/record bytes. Captured snapshots
are comparisons, not expected-state inputs. Original UUIDs are accepted only
inside the exact reconstructed grant suffix. An unselected same-cut source can
be reclaimed after the new durable PROMISE and before the next BASIS capture;
the current generation's own source remains protected.

For installed maintenance, the reader derives the local pin decision from the
preceding selected generation, inactive generation, source ownership and actual
four-voter cohort. It constructs the complete FLOOR from the original peers and
checks both governing majorities and covering ancestry. The already owned local
generation is referenced through its exact selector; only its redundant physical
copy is omitted. The other three copies and all four FLOOR references remain.
No observed pin marker or producer success flag authorizes this derivation.

The same derivation supplies the authority, journal replacement and expected
files at every source-retirement boundary. It compares **22 transactions / 330
prefixes**, binds 22 governing-floor force windows, and encounters three pinned
maintenance floors. It also compares 115 snapshots through old-side INTENT,
42 continuation snapshots and 26 captured grants. Initialization includes some
of those earlier snapshots; these overlapping counts must not be added as
distinct histories or coverage rows.

The departing member applies FINAL but cannot endorse the successor checkpoint.
Its exact nonvoting applied end contains six files, no ACK and no ancestor ACKs.
The force reader requires the nonvoting directory boundary and a null wire ACK;
ordinary owners still require the full voting sequence. After FINAL the departed
owner cannot run successor maintenance. Its inactive predecessor remains owned
through close and is compared exactly, not silently treated as garbage.

The separate slot-force replay checks **34 owned slot transactions, 5,234 storage
callbacks and 144 phase responses** through all eleven slots. It derives future
retention and publication ordering from original records. This is a slot-force
result; it does not establish correlation of every failed network attempt.

## Negative qualification

```bash
python3 -m scripts.v53.required_four_physical "$ORIGINAL" --qualify
```

The unmodified history must pass first. Four mutations are applied only to
copies: an extra prepared file, an extra installed file, deletion of the
departing owner's inactive predecessor, and removal of the local pin marker
from an actual retirement capture. The last mutation refreshes its metadata
hash so it exercises physical derivation rather than checksum rejection.
Each modified history must still pass semantic replay and capture collection;
only the declared exact physical rejection can qualify the negative. The
original inventory must remain unchanged throughout. Unit tests also reject
weaker pin prerequisites, substituted local copies, an insufficient joint quorum,
selected/pending/backing sources and unrelated or prerequisite failures.

## Network evidence limitation

The strict network gate rejects this retained history at
`joining failure missing caller terminal`. For the three remote FINAL ACCEPTs,
the first caller times out and an identical retry starts before the first
server invocation finishes. Original events record request hashes, but do not
carry an invocation identity that reliably binds the late inbound terminal and
the identical responses to the first or second attempt. The existing reader
assigns the late terminal to the newer send and correctly refuses to qualify
the resulting unmatched terminal. A compact original-event index and the failed
reader log remain retained alongside the successful physical results.

This is a demonstrated evidence-correlation gap, not proof of a protocol safety
failure or proof that GitHub scheduling caused a timeout. A passing Java return,
a later matching response, or valid final files cannot reconstruct the missing
transport identity. No terminal is dropped, no timeout is changed and no gate
is relaxed. The next implementation must collect unambiguous transport-attempt
identity, exercise overlapping identical retries deterministically, and bind
all observations through the independent reader before qualifying a new native
history. Historical traces without that information retain their limited scope.

The [connection-observation follow-up](PHASE_3_CONNECTION_ATTEMPTS.md) now
passes two native TCP component histories and exact negatives. Its whole-history
collector/reader integration is still pending; it cannot supply missing identity
to this historical trace.

## Remaining qualification and rollback

`completePhysicalQualified`, `forceAndNetworkQualified`,
`processDeathQualified`, `finalSourceCohortQualified` and `phase3Complete` remain
false. Complete network/export/control composition, native interrupted
maintenance histories, combined resource maxima, frozen coverage mapping and
final-source hosted execution remain required. The conditional
[pinned-floor process matrix](PHASE_3_PINNED_FLOOR_PROCESS.md) is separate evidence;
it does not turn this no-fault native run into process-death qualification.

No Java implementation, POM, workflow, frozen format, resource limit, deadline
or hosted history count changes in this batch. The twelve planned subsets /
544 histories remain unchanged. Rollback removes the new reader and tests and
reverts the explicit required-four/nonvoting reader extensions together; ordinary
profile defaults and runtime behavior remain unchanged.
