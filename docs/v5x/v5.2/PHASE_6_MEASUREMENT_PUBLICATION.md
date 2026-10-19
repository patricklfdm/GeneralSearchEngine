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
and 64 MiB of distinct basis chunks. The short smoke profile permits at most 128
snapshot transfers and 256 selector observations. Full M01–M04 replay explicitly
selects 2,048 transfers and the existing 8,192-selector profile; the machine freeze
records the same transfer constant used by the validators. Both profiles keep
16 MiB per offered image, 64 MiB retained chunk bytes and 131,072 chunks, each at
most 65,536 bytes. Transfer count is cumulative across all voters and process
generations in one history; different transfers are not merged by image content,
and unfinished transfers still count. Exact retries do not count twice. Invalid
or larger limits reject before replay, and the next distinct offer beyond the
selected count rejects before retention.
Overlapping, missing, altered and foreign transfer data reject. These are explicit
decoder bounds; the final machine execution freeze must bind them before measured
runs. Existing runtime resource and API deadline limits remain unchanged.

### Full-history bound correction

The operator-run cohort at
`target/v52-local-acceptance/runs/prepare-20261016T010123Z-3083043/cohort`
passed nine complete histories before `candidate-stale-r1` exceeded the old
128-transfer smoke bound during independent replay. Its unchanged raw evidence
contains 94 accepted offers on node 2 and 71 on node 3, 150 completed installs and
6,305,688 acknowledged chunk bytes. All observed transfers use epoch 2, all 1,800
offered reads and 180 updates succeed, and the setup read also succeeds. The count
is distinct follower recovery work, not duplicate observation inflation or an
election loop. A 180-update full history can require hundreds of follower
transfers even though the short consumer smoke needs far fewer.

The full profile's 2,048 descriptors provide room for both followers' distinct
transfers and abandoned/restarted transfer identities; this is a finite decoder
allocation allowance, not a maximum proven for every possible runtime schedule.
It does not increase the 64 MiB chunk allocation, change the runtime, modify the
offered load, remove failed outcomes or relax snapshot authority checks. Boundary
tests cover the retained 165-transfer shape, rejection at 2,049, exact retry at
capacity, shared byte accounting and rejection of invalid profile values.

Diagnostic replay under the proposed profile is retained at
`target/v52-snapshot-budget-review/`. The old failed cohort and its 128-transfer
freeze remain unchanged. A new implementation commit and machine-only freeze are
required before fresh formal execution; the prior nine passes cannot qualify a
mixed-source or selectively resumed cohort.

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
