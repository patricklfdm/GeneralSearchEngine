# Phase 2 — typed bootstrap revalidation

Status: private callback integration locally qualified; **Phase 2 remains OPEN**.
This connects actual source reads and typed exports to the
[private transaction](PHASE_2_BOOTSTRAP_TRANSACTION.md). The public offline entry
points remain disabled pending complete admission and recovery integration.

## Exact checks at both decision boundaries

`MembershipBootstrapSeed.revalidate` runs under the transaction's existing owner,
before PREPARING and before COMMITTING. It compares the request with the original
retained plan, including all identities, paths, materialization bounds and operation
budgets. It freshly reads the source inventory and application/index/core descriptor
and checks exact canonical agreement before creating a scratch directory.

Every target invokes the real core backup reader and exporter. All normalized
application image bytes must equal the original planned image. The original
history is reused, and rebuilt ROOT/GENESIS must remain byte identical. Member
inode/hash stability is checked around codec callbacks, as during planning. This
checks source identity during each invocation, not continuity of member inodes
between separate invocations. Prepared replica directories are never opened by
this helper; core materialization directories must still be absent.

The caller supplies the actual bytes of earlier retained scratch. Admission reserves
the complete original transaction, those retained bytes and one maximum-size export
for each target before creating the next scratch. Successful validation returns its
actual new scratch bytes. Occupied or aliased paths are refused, and failures retain
any partial derived files. The helper does not delete, overwrite or silently repair
such files; public resume still needs bounded scratch tracking.

## Validation and evidence limits

[Source/build/raw index](phase2-evidence/bootstrap-revalidation.json) records the
six successful 3/4/5-voter × EMPTY/real-backup combinations. Each executes both
transaction callbacks and a separate post-commit check. Retained evidence includes
the original plan/image/source, planning scratch, all three validation exports and
the exact committed receipt: **96 actual target exports** in total.

Java rejection tests cover changed builder/request/source, same-name codecs with
different behavior, byte-identical source inode replacement during decode, exhausted
completion/scratch capacity, occupied/aliased paths and a real source failure at
PREPARED. That failure leaves the two original decisions and no receipt; resume
refuses the changed source without repairing authority. First-target codec rejection
occurs before scratch creation; later-target rejection retains earlier scratch.
The first development run incorrectly expected scratch in the former case. Its
failure log is retained and excluded from accepted validation.

Independent Python replay derives all target metadata and the receipt from the
original plan, checks exact exported checkpoint/metadata bytes and CRC-protected
manifest normalization, reconciles source inventory and all retained scratch bytes,
and checks the completion reserve at each validation. **13 exact-reason negatives**,
normal/optimized Python and relocated replay pass. The unchanged older plan and
transaction/process evidence are also replayed after generalizing the decoder to
all supported sizes and backup sources; their default three-voter EMPTY profile
remains required.

```bash
python3 -m scripts.v53.bootstrap_revalidation_evidence <v53BootstrapRevalidationEvidence-directory>
python3 -O -m scripts.v53.bootstrap_revalidation_evidence <v53BootstrapRevalidationEvidence-directory>
```

The Python oracle verifies physical exports and receipt binding, not arbitrary Java
codec semantics or callback execution. Callback placement and typed behavior are
checked by the Java tests. This batch adds no process-death, power-loss, public
bootstrap, voting, leadership, protected CI or cloud acceptance claim.

Public random-history planning, resumable bounded scratch ownership, complete-store
seal admission/accounting and mutable-store result inspection remain required.
Transferred-context lifetime, maximal headroom and the full S/N audit remain open.
