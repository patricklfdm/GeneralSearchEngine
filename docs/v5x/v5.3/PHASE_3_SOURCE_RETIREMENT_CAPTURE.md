# Original source-retirement transaction prefixes

The test-only `V53SourceRetirementCapture` records writer-held inventories from
`SOURCE_RETIREMENT_CREATED` through `SOURCE_RETIREMENT_BEFORE_RETURN`, including
every intervening journal replacement and individual deletion boundary. The
original `sources.retirement.gsr` survives in the observations after the runtime
has cleared it. Its RETIREMENT/PROMISE/BASIS/CAPSULE bytes bind the source, current
selector, governing floor and exact files; callback names alone cannot do that.

Each observed file is read through the existing lock-preserving file access.
Objects are retained once by SHA-256 and each boundary has a canonical complete
inventory, including empty directories and files. Copies never authorize a
runtime decision. Missing or altered objects, extra unreferenced objects,
overlapping transactions, missing boundary copies and mismatched owner/scope
are rejected. Limits are diagnostic only: 512 captures, 512 entries per capture,
64 MiB per file and 256 MiB of unique objects. Production limits are unchanged.

The observer is enabled only for the complete early-start joining fixture. It
shares the original event sequence with both old voters and the joining owner.
Its markers are not force callbacks. The preparation reader checks any new
capture collection before filtering those markers from its existing local order
check. Collection v3 now requires retirement captures before ledger validation;
old collection-v2 evidence is retained with its original claims.

## Independent comparison

`scripts.v53.joining_source_retirement.compare` takes the independently derived
initial state, original decision bytes, compacted journal and source identity.
It uses the existing source-release transaction model to compare **every**
captured prefix, not only the final inventory. No captured decision or checksum
defines expected bytes. Identical bytes before and after a force remain distinct
mandatory event boundaries.

A small real three-voter writer exercise records 15 boundaries. The existing
independent source-release fixture derives its initial governing copies, source
packet/images, decision and compacted journal, then checks all 15 prefixes and
the final state. A separate JVM confirms that observation did not release the
writer lock. This exercise is a component check, not a joining history.

Seven targeted Java tests pass, including two new observer tests. All 176 joining
Python tests pass, including eight new boundary tests and the new collection-v3
refusal test. Twelve original-first evidence mutations reject with exact reasons:
missing capture, event digest, missing/altered/extra object, substituted floor or
source-file digest, early journal pruning, wrong deletion, extra final file,
missing force and foreign scope. The initial Python fixture error and its corrected
passing log remain retained. The [receipt](phase3-evidence/source-retirement-capture.json)
records source/build identities, portable replay and archive hashes.

```bash
python3 -B -m scripts.v53.joining_source_retirement <component-raw> --qualify
```

## Remaining closure work

The complete new joining fixture has not run in this batch. Its next uninterrupted
execution will collect these prefixes. The following reader must derive the
original governing-floor copies and each source-retirement transaction from that
same history, then feed those expectations to `compare`; collection alone must
not qualify them. The prior `c8f5d616` archive cannot acquire new observations.

Complete force/network composition, actual process-death boundaries, all seven
profiles and frozen requirement mapping remain open. Phase 3 is **OPEN**. No
production Java, POM, workflow, frozen workload or timing parameter changed.
