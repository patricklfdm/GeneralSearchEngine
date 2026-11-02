# Competing-owner observed export authority

Phase 3 remains **OPEN**. This continues the same immutable `e1af4813`
three-owner history used by [activation network replay](PHASE_3_COMPETING_ACTIVATION_NETWORK.md).
No native workload is rerun or replaced with a simpler election schedule.

`scripts.v53.competing_export_evidence` requires the complete original grant,
retirement, installation, publication and network replay before interpreting
export authority. It derives nine generation windows from the original selector
renames and completed installation/publication returns. Their contents come from
the independently derived initial, installed and published inventories. The
unused voter keeps its original generation; neither its failed choice nor its
received bytes invent a successful installation.

Four frozen-source windows bind the captured original BASIS, promise, source
packet and image bytes. Retirement uses the already checked original
`SOURCE_RETIREMENT_CREATED` boundary, not a higher promise or the earlier floor
reservation. A newer ballot may coexist with retained old originals.

Fifty-seven record windows cover retained journal entries, pending slot records,
payloads, vote receipts and applied/published local checkpoints. Journal SELECTED
windows use actual local durable writes. The losing choice names node-2 but
node-2 never forces that decision; its presence in the selected pair cannot
create a local export capability. Pending capabilities retain the existing
force, promise, generation and publication boundaries of the shared reader.

All 43 completed source sessions, containing **68 committed transfers**, are
checked against these windows. Current-generation aliases resolve only to their
exact metadata/packet/image sequence. Frozen sources require their original
ballot and view. Record, payload and vote references require the original owner,
identity, bytes and live capability. Unused packet checkpoint ACKs do not become
authenticated evidence. No observed export family is silently skipped.

The losing SELECTED session remains separate: one real offer and one real DATA
response provide bytes, while all three commit attempts remain unanswered. The
shared record-authority helper checks only through the actual DATA response.
It never supplies a synthetic commit or counts that session among the 68
committed transfers. The original whole-network gate remains mandatory and
accounts for all 250 responses and 269 requests, including unanswered attempts.

## Validation and limits

The original passes before 26 derived capability claims are mutated. They cover
generation aliases/bytes/members/storage identity/replacement, frozen-source
aliases/ballot/promise/capture/window boundaries, vote receipt aliases/bytes/
ballot/force, pending payload and view, application checkpoint availability,
journal retirement, published bytes and incomplete-selection ownership,
durability and retirement. Each requires its exact rejection reason. Native
files and the derived original claims remain unchanged and are rechecked.

These are **capability-reader negatives**, not new native fault injections or
altered whole-history replay results. They deliberately exercise the authority
reader after the original physical/network precondition; changing an actual
transcript could instead be rejected earlier by that precondition. The
qualification output labels this scope explicitly. Synthetic unit fixtures are
also separate from the native evidence. The [development receipt](phase3-evidence/competing-exports.json)
records portable optimized replay, test results and input hashes.

```bash
python3 -B -m scripts.v53.competing_export_evidence "$RAW" --qualify
```

This qualifies **observed temporal export availability** in the retained
history. Export deadline expiry, close/revoke behavior under faults, complete
automatic lifecycle/recovery, transient retirement bytes and final-source
competition admission remain open. The result stays PARTIAL and
`completeExportLifetimesQualified` stays false. Production Java, protocol/time
budgets, workflows, the six hosted subsets, 428 planned whole histories and five
open Phase 3 work groups are unchanged.
