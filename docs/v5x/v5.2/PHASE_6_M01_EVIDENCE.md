# V5.2 Phase 6M full M01 member evidence

**Status:** implemented; local component validation passed. Full-size M01
execution and its integrated negative replay have not run. M02–M04 and the complete
machine freeze remain required before formal measurement.

## Independent member admission

The full member validator uses the separate large-package inventory and exact
source/build/attempt binding. It verifies the three loaded artifact names/hashes,
compiled consumers, original loaded paths, JVM vendor/version and three clean
process exits. Metadata reads have explicit byte bounds. A short-smoke profile,
shortened offered program or incomplete close cannot qualify as M01.

Every member retains the full 60/120-second program and exactly one initial strong
setup read. Actual captured sequence one and later status observations must show
that the frozen read/write targets reached the initial strong cut before offers.
The validator independently reconstructs chosen mutations, including uncertain
updates that actually became chosen; only those chosen updates advance query
replay. Rejected mutations cannot appear in the chosen prefix.

General force/quorum/selection validation, forced generation and received snapshot
validation, the complete consumer/ownership ledger, successful read cuts and the
real V4.4 query oracle all remain mandatory. Warmup/measured counts, all outcomes,
late calls, original API timing and process resource windows are reconciled.
Neither a controller OBSERVED receipt nor a member PASS closes the five-mode,
three-repetition set. `qualifiedMeasurement` stays false until complete-set and
machine admission, with the other M02–M04 histories, are implemented and passed.

## Bound aggregate state before reconstruction

The lossless trace bounds limit individual rows and cumulative decoded bytes.
Before the general validator builds its retained maps, an additional streaming
scan admits at most:

| Retained category | Distinct records | Raw bytes |
| --- | ---: | ---: |
| Accepted entry identities | 8,192 | 16 MiB |
| Voter/ballot acceptances | 65,536 | 64 MiB |
| Proof identities | 65,536 | 64 MiB |
| Response frames | 131,072 | 512 MiB |
| Frozen basis descriptors | 128 | 8 MiB |
| Basis transfer offsets | 131,072 | 64 MiB |
| Selected choices | 64 | 4 MiB |

The scanner keeps fingerprints, not those full records. Equal retries count once;
changed bytes at a retained identity reject. Every selected pair is charged for
its referenced images, even if another choice reused the same bases. Total
selected reconstruction is limited to 128 MiB. These checks precede all general
physical and selected-prefix collectors; they do not establish authority themselves.

M01 permits at most 8,192 forced-selector observations, matching its 8,192-entry
evidence ceiling and allowing complete long histories to retain their generation
observations. The existing short profile still permits 256. Each generation packet
is independently decoded and checked; no packet is skipped. Resource rows are
bounded at 1,024 per process before list allocation. This changes evidence capacity
for the new profile only; runtime storage/admission limits remain unchanged.

## Negative and portable qualification

The closed negative driver first validates the unchanged complete history against
actual query answers. It then requires exact declared rejection reasons for missing
offers, shortened windows, moved due times, hidden retries, retargeting, substituted
answers, missing command receipts, missing proof force, leaked admission, forged
resource counters/markers and a missing mandatory read-capture record. Normal
M01 operation need not install a snapshot, so selector events cannot be required
as negative targets. Actual selector bytes remain mandatory whenever an install
occurs; the M02/M04 negative matrices still exercise missing generation bytes. Explicit modes additionally
check capture sequence, fresh strong epoch, ownership settlement and completion;
minimum adds changed carried-token rejection. Each mutation changes one decoded
row or a bounded controller copy. Raw authority inventory remains unchanged.

Original and relocated full member results must be equal in the later execution
wrapper. This stage supplies the replay implementation but does not claim that
wrapping or a full-size history has passed. All failures and original data remain
retained. All 157 V5.2 Python tests passed. Ten unchanged raw/relocated short
histories passed the new aggregate scan and preserved their complete existing
physical/query/lifecycle/resource results. The larger selector-count admission
produced identical authority results, and removing the leader's proof force was
rejected for the exact physical reason in all ten histories. This component
replay took 16.928 seconds; it did not execute any M01 window. CI inventory,
documentation contract, changed local links, shell syntax and whitespace passed.
No new reactor, full-size measurement or hosted result is claimed. Checks and
original bindings are retained at `target/v52-m01-evidence`.

Next finish portable full-member/set execution and M02–M04 schedules, then commit
the complete machine freeze under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
