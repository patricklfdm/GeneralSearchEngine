# V5.3 Phase 1 foundation

Status: **in progress**, local isolated development only. The operator authorized
continuing through local Phase 1 closure with intermediate commits. No push,
protected CI, paid experiment or release is included.

## Worklist and boundaries

| Batch | Deliverable | Local state |
| --- | --- | --- |
| 1 | 5.3 coordinates, additive declarations, disabled entry, old consumers | PASS locally |
| 2 | 24 storage / 21 wire kinds, exact bytes, bounded transfers, independent contextual readers | [Syntax codec PASS](PHASE_1_BYTES.md); [context/transfer foundation PASS](PHASE_1_CONTEXT.md); complete frozen-source capsule/selection pending |
| 3 | Same-round/catalog/compacted-source composition; complete S/N inventory | Pending |
| 4 | Fresh public process scaffold, source/JAR binding, portable negatives | Disabled-entry scaffold, three JVMs and ten portable negatives PASS; later runtime evidence pending |
| Closure | Requirement-by-requirement audit and retained receipts | Pending; Phase 1 is not closed |

The [entry plan](PHASE_1_ENTRY_PLAN.md) remains the acceptance checklist. Separate
Phase 0 references are not relabelled as the composed Phase 1 model. Declared
public/halt/SIGKILL cases cannot count as physical execution while runtime is disabled.

## Batch 1 implementation

- Align all five reactor coordinates and eight compatibility consumers to
  `5.3.0-SNAPSHOT`; current regression readers remain bound to exact checkout POMs.
- Add 24 public membership types and a reviewed 358-line reflection fixture. See
  [contract amendments](PHASE_1_CONTRACT_AMENDMENTS.md) for the actual-source
  fixed-three status incompatibility and independent membership status API.
- Check immutable bounded identities, operation phases, view consistency,
  history-bound tokens, maintenance survivors and disjoint directory requests.
  Constructors perform no disk or network inspection.
- Pure builder returns a disabled handle. Neither `start`, mutations, reads,
  bootstrap nor learner operations enable storage/transport; absent diagnostics
  are not filled with invented membership. Legacy engines and read callbacks keep
  their existing contracts and factories.
- Build a separate public-only consumer and execute it in three fresh JVMs for
  stable-size declarations 3/4/5. This is disabled-entry evidence, not force/wire
  or successful membership mutation evidence.

Focused declaration checks can be repeated with:

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53DeclarationsTest,V53PublicApiInventoryTest,V52ReadTokenTest,V52PublicApiInventoryTest,V51DeclarationsTest,V51PublicApiInventoryTest,V50PublicApiInventoryTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.test_build_coordinates scripts.test_ci_v51_bundle \
  scripts.v51.test_release_preparation scripts.v51.test_phase7_release_fixtures
python3 -m scripts.v53.foundation target/v53-foundation/run-UNIQUE
```

The foundation driver refuses existing output, retains process stdout/stderr and
failure receipts, verifies exact public JAR origins, and records source inventory,
artifact and consumer-class hashes. Use a new output name each time. Full consumer
verification additionally requires installing the local artifacts and executing
`mvn -o -f compatibility/pom.xml test`; do not publish them.

## Qualification record

[Batch 1 receipt](phase1-evidence/declarations.json) records:

- Complete reactor install: 1,018 tests, zero failures/errors, four existing skips;
  approximately 12 minutes. No Maven clean or publication.
- Eight independent compatibility consumers: 26 tests, all passing.
- 199 V5.3 Python tests and 28 coordinate/build-bundle/release-fixture tests passed.
- Three fresh public JVMs passed; ten original-first evidence corruptions rejected;
  copied evidence replayed successfully at a different path. No runtime enabled.
- Version alignment, documentation links and whitespace checks passed. The first
  default-wrapper alignment invocation exited without a diagnostic; an explicit
  offline invocation using the installed Maven then passed all thirteen POM checks.

Logs live at `target/v53-phase1-foundation/`. The receipt binds parent `1a7c2b6`
plus the actual dirty source inventory and JAR/consumer-class bytes. Final reporting
edits differ from that inventory; this is not represented as clean-source CI.
The toolchain is local
Ubuntu OpenJDK 21.0.12.1 / Maven 3.9.11, not the pinned hosted Temurin toolchain.
A protected/unified acceptance run remains deferred. V5.2 cloud measurement inputs
and its independent running checkout remain unchanged.
