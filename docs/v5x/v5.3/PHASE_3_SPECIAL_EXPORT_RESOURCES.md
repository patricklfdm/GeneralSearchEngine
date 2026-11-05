# Phase 3 vote and learner ROOT export resource bindings

The [development evidence index](phase3-evidence/special-export-resources.json)
retains the source hashes, original collections and validation reports for this
follow-up to [source/record/prefix exports](PHASE_3_EXPORT_RESOURCES.md).
Phase 3 remains OPEN; the 12 review requirements and 544 planned hosted histories
are unchanged.

## Runtime change

Two CONTROL owner names now include their original reference and a fresh UUID:

| Export | Independently derived binding | Existing reserved extent |
| --- | --- | --- |
| Pending vote payload | Actual pending DATA payload hash | Payload length |
| ACCEPT or PROOF receipt | Namespaced receipt lookup reference | Canonical original-owner receipt length |
| Learner ROOT metadata | Original ROOT record digest | Twice the ROOT length plus 4096 bytes |
| Nested prefix borrow | Original current generation manifest digest | 4096 bytes |

The receipt lookup reference differs from the receipt content hash. Substituting
the latter cannot create a receipt export. ROOT metadata and its nested prefix
borrow remain separate allocations, sharing the existing six-export registry.
No record/wire format, quota, deadline, protocol decision or public API changes.

## Native executions and independent checks

Three public-bootstrap histories, at stable sizes 3, 4 and 5, perform actual TCP
ACCEPT/PROOF exchanges with every original voter. Their original files, payload,
phase receipts and network transfers pass the existing native-voting reader.
After network drain, each same live owner overlaps three direct exports: DATA,
ACCEPT receipt and PROOF receipt. Explicit-close and injected-clock-expiry modes
account for six reservations per history.

One three-voter learner history performs native activation, BARRIER and RESERVE,
then ROOT discovery from two original voters with two lost replies. Two direct
ROOT probes account for four allocations, including both nested prefix borrows.
The existing capacity test still fills the shared registry and verifies rollback
of the refused seventh borrower. The history continues through a second native
activation, its fresh BARRIER, and CANCEL on the same stores.

The older ROOT physical reader did not model current confirmed-copy retention,
the second campaign, or its retained hidden endpoints. Its explicit
`current_retention=True` profile now derives those bytes from the preceding
admitted states, pre-merge peer ledgers and retained original sources. It requires
both selections and all four applied/published slots. Missing second-campaign
evidence cannot silently downgrade to the historical profile. Historical replay
remains available with its original default semantics.

Resource replay follows physical replay. Exact observation points require each
expected reference and extent, unique allocation/release, simultaneous ownership
during reads, continuous baseline custody and restoration before close returns.
Vote expiry releases its copied bytes during refusal; ROOT expiry refuses access
while explicit close releases the wrapper and nested borrow. Both must reject
reuse after the injected clock is reset. Final owner close must reach zero.

```bash
python3 -m scripts.v53.special_export_resource_evidence RAW
python3 -m scripts.v53.special_export_resource_negatives RAW
```

There are four native histories, 22 direct export allocations and 72 exact
accounting mutations (18 per history). ROOT physical/discovery mutation coverage
also checks missing/forged second selection, installed ancestry and the retained
ancestor statement at CANCEL. Negative observations are copied; original files
are retained unchanged. Initial compilation and reader failures remain in the
development report directory alongside the corrected results.

## Remaining scope

These points qualify direct export ownership inside native histories. They do
not yet bind every network session to its exporter or independently qualify the
clock and socket-write boundary. Joining retention, intent, preparation and
completion exporters still need resource binding/composition coverage. Whole
runtime physical peaks, phase-wide admission and final-source hosted execution
remain pending. This batch adds no hosted history, dispatch or cloud execution.
