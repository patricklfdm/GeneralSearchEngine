# GeneralSearchEngine V4.2 Phase 5 lifecycle hardening

- **Status:** Accepted on protected `master`
- **Scope:** Migration authority, interruption, safe-remnant cleanup, rollback and
  published-4.1 compatibility

## Authority model

Phase 5 does not automate traffic cutover or rollback. It makes every state left by
the production migration publisher independently resolvable:

| Durable boundary | Target authority | Exact migration remnant |
|---|---|---|
| before marker publication | absent | none |
| marker forced, before staging creation | absent | marker only |
| staging creation through staged verification | absent | marker plus staging |
| final rename through final source comparison | valid `(1,1)` | marker only |
| marker deletion through return | valid `(1,1)` | none |

Rename-before-parent-force remains publication durability indeterminate after a real
machine failure. The local process-halt matrix can prove only that the visible target
is structurally and semantically valid; operators still require the exact plan
identity and supported-filesystem durability rules before selecting it.

## Migration operation marker

Migration uses the exact sibling pair:

```text
.gse-v42-migration-<32 lowercase hex>.staging
.gse-v42-migration-<32 lowercase hex>.staging.operation
```

The bounded CRC32C-protected marker is `GSEOP100 (1,1)`, kind `3`. It binds the
operation UUID, staging and final-target names, absolute normalized source path,
plan/source-authority/projection identities, and the ordered name, length and SHA-256
of every authoritative source member. The marker remains exclusively locked through
target verification and the final source comparison.

V4.1 kind `1` backup and kind `2` restore markers remain byte-compatible. No live or
backup storage format changed.

## Safe-remnant cleanup

The existing public `OPERATION_REMNANT` scope recognizes the exact kind-3 marker. A
cleanup plan is admitted only when:

- the named staging or marker has the exact UUID-bound name and valid CRC/layout;
- the source is a closed structurally valid store whose authoritative member set,
  lengths and hashes still match the marker;
- staging and target do not coexist;
- staging contains only exact live-store member names; and
- an existing final target is a structurally valid store.

Planning is read-only. Apply reconstructs the complete authority and inventory before
deleting anything. Prepublication cleanup deletes only the operation-owned staging
members, staging directory and marker. Postpublication cleanup deletes only the
orphaned marker. Source, final target, unknown siblings, aliases, changed bytes,
ambiguous ownership and corrupt authority are never deleted.

Migration apply still cleans its own ordinary prepublication Java failures. Abrupt
process remnants are handled separately and explicitly; apply never scans the parent
for remnants from another attempt.

## Cutover and rollback window

The verified operational sequence remains external to GSE:

1. create and verify a `(1,0)` backup outside source and target;
2. stop the source writer and record its exact member identity;
3. plan and apply to an absent target;
4. independently verify the `(1,1)` target;
5. open it normally, perform bounded continued mutation, checkpoint, close and reopen;
6. stop target writing before any rollback exercise; and
7. prove the untouched source reopens using the pinned Maven Central `4.1.0` artifact.

Target-only writes are deliberately absent from the source. Returning to the source
therefore discards those writes unless the application performs reconciliation. V4.2
does not provide reverse migration, history merge, source deletion or routing APIs.

## Evidence

`scripts/verify-v42-phase5-lifecycle.sh` runs 25 real production-byte barriers with
`Runtime.halt(86)`. Each case is prepared in one JVM, halted in another, verified in
a third, cleaned through the public dry-run/apply API, and reverified. It also runs a
normal typed migration followed by target mutation, checkpoint and reopen. Evidence
uses the Phase 1-frozen `gse-v42-migration-evidence-v1` schema.

`V42PublishedV41RollbackCompatibilityTest` creates and verifies the pre-migration
backup, migrates, continues target operation, proves source bytes unchanged, then
compiles and runs `PublishedV41RollbackProbe` against only the SHA-256-pinned
published `4.1.0` core artifact.

## Deferred work

Phase 5 performs no paid execution, workflow/IAM mutation, baseline registration or
performance optimization. Phase 5 merged through protected PR #111 as
`5687a05aa2f495f58d8acc904ab1e663361cf6e3`;
exact-master CI run `33880571096` passed. Scale, persistent-disk replacement-host
exercise, canonical cloud evidence and registration remain Phase 6 responsibilities.
