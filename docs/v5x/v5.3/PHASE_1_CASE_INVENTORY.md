# Phase 1 finite acceptance inventory

The frozen acceptance plan now has a deterministic, materialized **3,310-row S01–S10
inventory** and **24 negative-family rows**. This is planning coverage only. No
physical/runtime/crash case becomes PASS by generating this file; required Phase 5
execution remains outstanding.

| Family | Expanded rows |
| --- | ---: |
| S01 membership | 168 |
| S02 campaigns | 336 |
| S03 learner | 200 |
| S04 capsule/floor | 840 |
| S05 operations | 336 |
| S06 reads | 756 |
| S07 stable rounds | 90 |
| S08 maintenance | 24 |
| S09 resources | 336 |
| S10 recovery | 224 |

Each row binds its scenario, complete profile/era, boundary, cut, mode and required
phase. All seven shapes expand in old, joint and new eras where specified. Joining
profiles include both ADD and all three REPLACE sizes; standalone stable cases use
sizes 3/4/5. Halt, kill, public and deterministic modes retain separate identifiers.
An inapplicable operation must produce explicit refusal with unchanged bytes; the
inventory does not silently drop a cross-product member or call it successful.

N01–N24 each carries a named expected rejection family, requires the original to
pass first, and prohibits counting unrelated setup failures as detection. Source,
build, attempt and control provenance are distinct from protocol, durability,
read, resource and inventory failures. Later validators must report the matching
family; these planned rows are not 24 executed mutations.

The original frozen plan and all indivisible histories/oracles remain unchanged.
`case_inventory.validate` compares every exact row to the frozen axes and separately
checks the reviewed family counts. It rejects omissions, duplicates, altered
contexts/modes, invented cases, source-plan drift and relabelled execution results.
Three focused tests cover those failures and deterministic generation.

```bash
python3 -m unittest scripts.v53.test_case_inventory
python3 -m scripts.v53.case_inventory target/v53-case-inventory/run-UNIQUE
```

Output creation refuses existing directories. The receipt retains the raw plan,
collector and encoded/decoded inventory hashes. The gzip inventory is about 21 KiB;
all 3,310 rows are recoverable without any network or experiment. Current output:
`target/v53-phase1-inventory/finite-final/`. See the [retained receipt](phase1-evidence/case-inventory.json).

The complete same-round/catalog/compacted recovery model and the final requirement
audit are still needed before local Phase 1 closure. Physical S/N acceptance,
published V5.2 controls and hosted qualification remain later gates.
