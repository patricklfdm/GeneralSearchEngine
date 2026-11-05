# Required-four temporal content and control exports

Status: **composed entry implemented; corrected-source native qualification
pending**. The ordinary profile catalog remains unchanged. This entry continues
the [required-four network gate](PHASE_3_JOINING_CONNECTIONS.md) and cannot replace
its original owner-file, connection, phase-force or lifetime preconditions.

## Binding and coverage

`scripts.v53.required_four_exports` explicitly selects the existing required-four
catalog replay: old members 1/2/3/4/5, new members 1/2/4/5/6, with only common
members 1/2, departing member 3 and joining member 6 available. All eleven slots,
34 owned publication transactions, the nonvoting departing end and cold originals
must pass the preceding physical/network gate first. An ordinary `5-REPLACE`
result, source label or recorded profile name cannot supply that authority.

The shared export context now accepts an explicit `required_four=True` only for
this five-member replacement shape. It keeps all six actual owners, including
offline members' unchanged original generations. Ordinary context calls keep
their previous behavior. Generation/source/record lifetime derivation and content
authorization are reused, rather than copied into a new algorithm.

Every committed content and session is accounted for. The three old INTENT
voters must each have read the joining owner's original pending checkpoint;
absence is a failure rather than a skipped negative. The control reader derives
retained-head confirmation voters from the original INTENT certificate. Actual
delivered retention majorities, local forces, generation boundaries and owner
lifetimes remain mandatory. No single remote ACK can stand for a joint majority.

The composed negative entry keeps all twelve content and fourteen control
mutations. Each copy may change only `events.json` and `wire.json`; original
authority inventories stay fixed. Complete network replay must pass before the
intended negative stage. Control negatives also require valid content replay,
except the existing owner-closure mutation whose intended rejection belongs to
the shared content lifetime gate. Missing targets, unrelated errors, accepted
mutations and invalid originals fail qualification. No negative is skipped.

```bash
python3 -m scripts.v53.required_four_exports "$ORIGINAL" --qualify
```

## Current evidence and limits

Twelve conditional entry tests cover topology selection, all six original
owners, joint delivered majorities, exact INTENT confirmations, complete session
accounting, original-first refusal and negative isolation. The related ordinary
profile and network regressions also pass. These test the entry; they are not
twenty-six executed native negatives.

Before another long execution, the retained original at runtime source
`25d80cb3` was independently checked through its complete required-four physical
gate. Shared temporal derivation then produced 59 generation windows, 26 source
windows and 546 original record windows, including the departing member and both
offline original owners. Using the existing explicitly scoped transfer-only
reader, diagnostic content replay checked 777 sessions / 1500 contents and 51
joining export lifetimes. The remaining nine control sessions / contents were
reported as unqualified. Three pending checkpoint sessions were actually present.
No frame, event or missing socket observation was added or altered.

This diagnostic does **not** bypass the complete entry's network precondition:
the historical original still lacks unambiguous overlapping ACCEPT attribution.
The newer native original at source `2f5cce27` likewise remains rejected for its
[missing endpoint connection observations](phase3-evidence/endpoint-connections.json).
Its rejection was exercised through the new complete entry before any negative
mutation. The endpoint correction is at `198649ae`; neither historical trace
qualifies that changed runtime. Diagnostic receipts, source hashes and scope are
retained in the [development index](phase3-evidence/required-four-exports.json).

Corrected-source original and all 26 negatives remain pending. Continuous
maintenance/peer/learner/future ledger composition, whole-runtime resource maxima,
process fault schedules and final-source cohort admission/execution remain separate
obligations. The twelve hosted subsets / 544 planned histories are unchanged;
this entry does not dispatch a workflow, add a frozen profile or close Phase 3.
