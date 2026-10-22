# Phase 2C3a — certificate-derived adoption fence

Status: locally qualified fence component. Phase 2 remains **OPEN**.
This component persists a root-wide promise bound before installing a newer
membership prefix. It does not install that prefix, acknowledge a vote or provide
the complete cross-view recovery path.

## Fence authority

`MembershipCapsule` records the highest full ballot only among membership
certificates actually authenticated during its complete capsule walk. Unreferenced
inventory certificates do not count. A compacted RANGE checkpoint alone cannot
invent a certificate ballot. INTENT and FINAL certificates retain their original
governing authority, which can differ from the capsule's terminal next authority.

Under the existing exclusive generation/journal owner,
`fenceMembershipPrefix` revalidates the incoming packet/images and ancestry to the
current prefix. It refuses an unfinished selected installation. Only then may it
raise the volatile observation and append the already-frozen PROMISE representation
with `basisId: null`. The new durable promise uses the certificate's original view
and full ballot. Its append is forced and fenced before return. This is not a
PREPARE grant and creates no source, BASIS or SELECTED record.

If a retained promise already covers the certificate ballot, its exact bytes and
any existing original BASIS stay unchanged. No receipt, vote or new configuration
is inferred from that no-op. A higher concurrent observation rejects an obsolete
write/return. Old sources and generation/selector bytes remain intact throughout.

Reopen retains a complete visible adoption frame and re-forces it conservatively.
The frame has no original basis; same-ballot PREPARE cannot resample one. A lower
ballot is fenced. A torn frame or an invented BASIS after adoption refuses open
without truncating or repairing authority. Historical non-null BASIS identities
remain separately indexed and retained; multiple increasing adoption frames do
not manufacture duplicate source identities.

## Qualification and remaining integration

The local matrix covers sizes 3/4/5 and certificates under old and joint authority
(incoming terminal cuts 6 and 7): clean operation plus halt/SIGKILL at validation,
promise-before-write, written, forced and before-return. It checks exact duplicate
replay, same/lower PREPARE refusal, original sources and unchanged selected prefix.
The reader reconstructs the fence from original capsule certificates, phased
bytes/receipts and checkpoint/configuration transitions, and checks actual force
events and snapshots. Remote historical observations remain conditional fixtures.

The final source passed 66 cases / 330 fresh JVMs in 182.312 seconds, all 12
exact-reason negatives and relocated replay. The directly affected source gate
passed 69 cases / 11 negatives in 104.222 seconds. All 118 focused Java, 72
Python/build-contract and 56 optimized-Python tests passed. The
[retained hash index](phase2-evidence/adoption-fence.json) distinguishes final
source evidence, earlier grant/selection regressions and replay of the prior
installation artifact. No workload was rerun to relabel that older artifact.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_adoption_fence_evidence \
  scripts.v53.test_generation_install_evidence scripts.v53.test_grant_evidence \
  scripts.v53.test_basis_sources_evidence scripts.test_ci_v51_bundle
python3 -m scripts.v53.adoption_fence_qualification \
  "target/v53-phase2-adoption-fence/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. The next integrated adoption transaction must retain
and force the new prefix/removal authority, preserve current and original ancestry,
invalidate old-view selected work, then require fresh activation. This fence-only
entry must not be wired directly to a runtime campaign: a later grant against the
old selected generation does not prove that the known newer prefix was installed.
Stable-range synchronization, actual phased vote ownership/application storage,
floor/retirement, journal rotation, offline initialization and complete physical
old/joint/new qualification remain mandatory in the
[Phase 2 checklist](PHASE_2_CLOSURE_CHECKLIST.md).
