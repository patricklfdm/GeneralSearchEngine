# Phase 2C5d — exact next-catalog projection

Status: **local component PASS; durable publication OPEN**.

The private reducer checks the original ENTRY root, eligible ballot identity, exact
parent/view/index and payload digest before projecting the complete next catalog.
It uses the existing control-state validator and binds the application replay index
and sequence. DATA advances application sequence exactly once; every control keeps
the original image hash and sequence. Inputs are immutable and remain unchanged.

RESERVE permanently retains identities and advances the operation allocator;
PREPARE binds the exact prior cut, catalog and application and resets old readiness;
READY binds that preparation; SEAL fixes its full descriptor; INTENT/FINAL project
the prescribed joint/stable views. CANCEL preserves identities; RETIRE removes only
the allowed terminal detail prefix. The terminal allocator sentinel cannot be used
for another reservation. No frozen command, record or resource bound changes.

## Exact prepared image

A negative test reproduced an existing context gap: READY could name a different
image already present in the inventory. Both READY admission and catalog reopen now
require the receipt image to equal the exact prepared application image. Merely
possessing another valid image never establishes this preparation's readiness.
The original red run is retained; the corrected checks and tests pass.

## Evidence and limits

**60 focused Java tests passed**, including **seven new catalog tests**. All **63**
transitions in the seven existing ADD/REMOVE/REPLACE profiles yield byte-identical
catalogs. Further cases cover re-preparation, stale receipts, irreversible sealing,
cancellation, retirement, identity permanence, counter exhaustion and hostile
parent/application bindings. One actual core DATA replay feeds its exact image and
sequence into the catalog reducer. Historical transition/near-exhaustion fixtures
remain conditional inputs; this does not claim a complete real bootstrap.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53CatalogTest,V53ContextTest,V53CapsuleTest,V53SelectionTest,V53Application*Test,V53DeclarationsTest,V53FormatTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
```

[Implementation/build/log index](phase2-evidence/catalog-projection.json).
Raw evidence: `target/v53-catalog-projection/`. The reducer does not establish
actual receipt ownership, ACCEPT/PROOF quorum authority, checkpoint endorsement,
force ordering, source lifetime or public publication. The integrating owner must
validate those separately before exposing a result. Phase 2 remains OPEN.
