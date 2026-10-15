# V5.2 Phase 6I local durable publication authority

**Status:** local qualification passed. Formal M01–M04 runs and the complete
execution freeze remain pending. This stage adds observation and independent
validation; it does not change the replication runtime or public API.

## Additional proof for follower-local publication

The original short consumer profile reconstructs the quorum-chosen application
prefix and each read's actual local publication. The new `forced-generation-v1`
profile additionally requires the local durable boundary before exposing a follower
publication. New evidence binds that profile explicitly; earlier retained evidence
cannot be relabelled as having observations it never captured.

The measurement worker observes `SELECTOR_BEFORE_ACK`, after the generation files,
selector rename and containing directories have been forced. It records the exact
selector, generation seal, snapshot and two journals. The independent source decoder
checks their inventory, hashes, manifest, voter, journal identities and prefix. A
selected generation also needs the independently reconstructed frozen basis pair.
The chosen-update projector checks the whole installed application state.

For an incoming snapshot, reconstruct the exact image from the recipient's observed
offer and acknowledged chunks. Retries must repeat the same offer, ballot, offset
and bytes. Only complete contiguous bytes matching the offer can qualify an install;
an interrupted transfer remains incomplete. The IMAGE must contain the exact
installed snapshot and no acceptance tail. The install requires its matching forced
generation and promised ballot. A LOCAL_PUBLISHED cut then needs either its exact
locally forced terminal proof or that complete forced snapshot generation.

The existing general physical validator still verifies wire exchanges, acceptance
quorums, selected basis bytes, proof/ACK ordering and retained storage. This added
layer does not replace those checks or treat an observation label as durable bytes.
No copied evidence directory is opened as a live product voter.

Published V5.1 predates APPLICATION_RESTORED and follower-local read observations.
That exact bound artifact is not required to emit nonexistent events; its strong
publication, transfer and generation checks still run. Every candidate process
must emit its actual initial genesis restoration. No generation/cut is fabricated
for the old control.

## Bounded replay and retained qualification

Selection reconstruction permits at most 64 selections, 128 frozen descriptors
and 64 MiB of distinct basis chunks. Incoming snapshot replay permits at most 128
transfers, 16 MiB per offered image, 64 MiB retained chunk bytes and 131,072 chunks;
each chunk is at most 65,536 bytes. At most 256 selector observations qualify.
Overlapping, missing, altered and foreign transfer data reject. These are explicit
decoder bounds; the final machine execution freeze must bind them before measured
runs. Existing runtime resource and API deadline limits remain unchanged.

The five-mode short gate recompiles the public consumer/observer against its bound
published/candidate artifacts, then checks original and relocated evidence. The
large-package qualification uses the same profile and checks again after packing.
New negatives remove generation bytes or the exact selector witness used by a
rejoin. Existing lifecycle, chosen-prefix, query and all other negatives remain.

## Local evidence

- Complete `run.IlyS4r` five-mode short qualification: 15 JVMs, 55 reads and 15
  updates; all original and relocated physical/V4.4 query replays pass. The new
  checks observe 18 selector boundaries, 11 installs and 46 follower publications.
- All 190 original/relocated negative checks pass. The large package retains
  4,387 files and passes baseline/raw/relocated replay with 23 negatives each.
- All 125 V5.2 Python tests pass, including transferred-image holes, overlaps,
  changed retries, foreign transfers, allocation bounds and the published-control
  restoration boundary. CI inventory, documentation contract, changed local links,
  shell syntax and whitespace checks pass. No new Maven reactor result is claimed.
- The first execution, `run.MgK7WG`, remains FAIL: eight published-control reads
  returned QUORUM_UNAVAILABLE and one follower proof force took 4.622 seconds,
  longer than the unchanged 1.2-second request deadline. Its independent physical,
  publication and failure-ledger inspection passes; that does not establish the
  source of the delay or turn the smoke into PASS.
- `run.byjAIm` executed its published-control calls successfully but exposed the
  checker's invalid restoration-event assumption. Its original failed validation
  remains retained; the corrected five-mode execution is the qualifying result.

The qualifying runtime binds base `410fad755cb928aa1a70f2e903f59d6e29353e73` and
checkout `8679f27ee367cdc4ed395bf884d82f0c08e613a8a6b417593d3f9e624e7b2052`.
Local validation reports and failures are retained at
`target/v52-measurement-publication`. Full measured outcome/window admission and
M02–M04 schedules remain the next work under the
[local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
