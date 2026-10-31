# Governing-floor and source-retirement replay

`scripts.v53.joining_retirement_replay` composes the
[original preparation reader](PHASE_3_JOINING_PREPARATION_REPLAY.md) with the
[writer-held retirement prefixes](PHASE_3_SOURCE_RETIREMENT_CAPTURE.md). It requires
one new history containing both original grant captures and retirement captures;
older evidence cannot acquire observations from another execution.

## Expected authority comes from prior derived state

Maintenance hooks expose the calculated local state after conservative peer
observations and inactive-generation pruning, before source removal. The reader
builds complete governing copies from the preceding derived current generations.
It verifies permanent identities, equal cuts/catalogs/applications, the exact
local generation and both governing majorities. FLOOR and proposal bytes, each
copied generation and all its files are encoded from those inputs. An observed
floor record or digest is never the expected authority. The latest local floor
transaction must have written and forced authority, forced its parent and returned
before source retirement; a released floor cannot authorize deletion.

For the explicit old-owner maintenance after the joining owner is installed, the
copies include that original joining generation. Before that point the original
old majority supplies them; during joint/stable continuation all three live owners
supply the governing copies. The expected voter sets follow this declared history.

Each obsolete source is handled in the original deterministic source-ID order.
The reader binds its original PROMISE/BASIS and packet, verifies complete images
and retained-obligation coverage, keeps current/highest grants pinned, derives the
RETIREMENT record and compacted journal, then compares every transaction prefix.
The exact forced decision remains present through journal pruning and individual
source deletions; its clearing follows the last deletion. All observed transactions
must be consumed exactly once. The existing installation, FINAL/BARRIER and cold
inventory comparisons remain mandatory.

The current history contains no carried accepted tail at source retirement. The
reader rejects such a tail rather than pretending the healthy-history derivation
qualifies that separate protocol path. Future carried-history qualification must
compose its own exact ownership derivation.

## Validation and scope

One uninterrupted native `9136083f` execution passed without retries in 879.386
seconds; collection v3 passed separately. Its 21,576 events and 2,208 wire pairs
retain 19 grants and all 240 source-retirement prefixes. Independent replay derives
16 retirement transactions and 16 governing-floor force windows, together with
72 preceding owner comparisons, 28 continuation comparisons and both cold snapshots
through cut 11. All 188 joining Python tests pass, including 12 new tests.

Ten original-first mutations pass collection but reject at their declared
derivation/order boundary: wrong floor/selector/file/PROMISE, early journal
pruning, wrong deletion, early floor release, retained decision, missing floor
force and use of a released floor. Invalid originals, collection failures,
accepted mutations and unrelated errors cannot count as successful qualification.

The initial reader incorrectly looked for `generation.gsr` in the helper's member
map, which intentionally excludes the manifest. The corrected reader takes that
file from the independently derived current directory and explicitly checks the
local copy's manifest too. The initial failure remains retained. Only the reader
changed; the native execution and original evidence were not rerun or altered.

The [batch receipt](phase3-evidence/joining-retirement-replay.json) retains the
producer, reader, original-first validation, negative qualification and portability
results. A passing result qualifies the recorded history's governing copies and
source-retirement prefixes. It does not establish complete cross-node force/network
causality, process death, all seven profiles or the frozen requirement mapping.
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
and `phase3Complete` remain false until their complete gates pass.

```bash
python3 -B -m scripts.v53.joining_retirement_replay <collection-v3-raw> --qualify
```
