# Carried transition attempted-network qualification

Phase 3 remains **OPEN**. The two four-voter REMOVE carried histories now have
an original attempted-network reader, composing the previous
[physical/lifecycle reduction](PHASE_3_CARRIED_TRANSITIONS.md) with native
transport, durable replies and CURRENT ownership. Complete temporal export
capabilities and retention/maintenance composition remain separate gates.

## Observation gap and new originals

The previous INTENT and FINAL originals contain 886 and 456 response records,
respectively, but no request-send observations. They remain valid within their
documented physical scope. The attempted-network reader rejects both with
`joining network response without request`; responses are not converted into
invented sends or receives.

The test wrapper now enables the existing `observeRequests` switch before the
first native campaign. Two new originals retain sends, receives, offered replies,
delivered replies and both caller/receiver failure terminals. Each method executes
once, without a native retry. Production Java, default resource bounds, the
declared 30-second request and 600-second round profiles remain unchanged.
The new executions took 320.112 and 304.174 seconds, including preparation.
Neither the older originals nor their receipts were modified.

| Original | Requests | Delivered responses | Failed attempts | Committed transfers | Durable slot callbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| INTENT | 901 | 886 | 15 | 275 | 1120 |
| FINAL | 465 | 456 | 9 | 141 | 700 |

These counts describe the retained observations, not a performance SLA. The
source comparison also confirms all 531 production inputs match the earlier
physical-only captures.

## Network and durable authority

[The reader](../../../scripts/v53/carried_transition_network.py) requires the
exact original physical/lifecycle result first. It reuses the REMOVE network
reduction with three phases at indices 5–7 for INTENT and two phases at 6–7 for
FINAL. All actual selected owners, old voters and publication cuts come from
the physically checked records. Final status windows follow the real number of
phases; no third FINAL campaign is invented.

The reduction checks every request/response pair, original permanent identities,
full ballot/view correlation, non-overlapping finite retries and complete terminal
failure observations. Transfers must preserve their original bytes, extents,
offsets, sequence and commit. PREPARE/SELECTED replies bind the durable original
grant and installation, including the proposer's installation after received
peer acknowledgements. ACCEPT/PROOF/APPLY/PUBLISH and future-retention replies
bind original physical bytes and force order. Initial opens, CURRENT captures,
generation changes, source-selected journal writes and all slot storage callbacks
must have their exact owners. Failed attempts stay in the accounting even when
the selected quorum completes successfully.

Each original must pass before **153 network negatives** run. The vector reuses
the existing REMOVE catalogue: missing sends/deliveries, foreign identities,
unbounded attempts, altered transfers, grants/installations, terminal failures,
status cuts, CURRENT ownership, slot force/write order and future/publication
acknowledgements. Every rejection requires the exact expected reason. Disposable
mutations may alter only observation files; all physical files and directories
must retain the passing original inventory. The original remains unchanged.
Replay supports one to four workers with deterministic catalogue-order output.
Only independent disposable negatives run in parallel, not the ownership history.

## Concurrent-reply mutation correction

The new INTENT original exposed a bug in the existing `early-promise` mutation:
it moved the first PROMISE before node-2's force regardless of which peer had
actually answered first. With node-3 answering first, that edit could remain a
valid order and the negative qualification correctly failed. The mutation now
moves the reply before its actual receiver's preceding BASIS force. A regression
covers either responding peer and either force order; it fails on the old driver.
The network acceptance predicate and original records are unchanged.

## Evidence and remaining work

The [development receipt](phase3-evidence/carried-transition-network.json) records
native source/build/toolchain identities, current reader identity, raw inventories,
network counts, complete negative results, portable replay and test logs. It also
retains the old-observation refusals and the initial failed negative qualification.
Both original replays and all 306 negatives pass. Pack/unpack relocation followed
by `python -O` replay gives identical results and preserves the original inventories.
All 2,456 V5.3 Python tests pass, as do 63 focused tests in normal and optimized
mode, the unchanged historical noncarried network original and documentation checks.
These new source snapshots were recorded while the reader was being developed;
this is development evidence, not final-source cohort admission.

The result qualifies observed attempts and durable activation/slot replies. It
does not yet establish temporal authorization of every export, complete
retention-revision/maintenance composition, process death, other membership
profiles, public service or Phase 3 closure. These remaining checks must compose
with the same whole originals. No hosted subset was added or workflow triggered;
the nine existing hosted subsets still contain 460 planned whole histories.
