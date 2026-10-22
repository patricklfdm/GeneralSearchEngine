# Phase 2C5d — certified checkpoint construction

Status: **local composition PASS; durable publication OPEN**.

The private checkpoint plan binds an unchanged verified base packet to the original
ENTRY, payload, ACCEPT, PROOF and certificate. Both phased ownership sets must
validate before typed application replay creates scratch files. Replay uses the
actual existing core semantics and produces the exact next catalog/application.
An internal projection entry accepts a caller's already semantically verified
result; its caller remains responsible for that semantic premise.

## Exact new endorsements and finite retention

The checkpoint statement binds exact before/after cuts, catalog hashes and image
hashes. Stable progression replaces the trailing RANGE with an enlarged range.
INTENT and FINAL remain explicit membership edges with all original descriptor,
certificate, phased records, ENTRY and payload bytes. Prior complete items remain
byte-identical. Only the current catalog and terminal application materialization
are included in the new packet; obsolete ordinary records are not accumulated.

Completion requires original CHECKPOINT_ACK frames and explicit new applied-end
ownership observations for every supplied ACK. ACCEPT/PROOF witnesses, old range
endorsements or unrelated observations cannot substitute. The existing independent
capsule walker rechecks continuity, exact statements/identities and next-authority
majorities: both sides after INTENT, only new voters after FINAL. Replaced range
observations are not accumulated across extensions.

The plan **does not force an application, write an ACK, move a selector, retire a
source or publish a public result**. Different valid endorsement sets are possible;
the later durable owner must retain its first exact chosen representation. A range
extension can hide an old cut anchor. Retained source/floor ancestry therefore
still needs separately authenticated bridges under the existing bounds; a new
capsule never invents such a bridge or grants deletion permission.

## Retained qualification

**292 V5.3/version-boundary Java tests passed**, including seven new checkpoint
composition tests and the existing storage suites. The focused preceding gate
passed 45 tests. All 63 transitions across seven member/change profiles produce
byte-identical packets to the existing independent compaction fixture. One hundred
successive stable barriers keep one RANGE and a constant metadata object count
below 16 KiB in that fixture. This measures construction size, not engine throughput.

The actual core DATA test independently exports its expected image, then connects
certificate validation, typed replay, catalog reduction and capsule construction.
Negative cases reject missing phases, changed bases, stale/duplicate/foreign ACKs,
wrong parent watermarks, old-only/new-only INTENT quorums and removed FINAL voters.
Missing source ancestry remains a rejection. The new tests' historical and
checkpoint observations are explicit conditional fixtures, not real remote forces.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
```

[Source/JAR/test index](phase2-evidence/checkpoint-extension.json).
Raw results: `target/v53-checkpoint-extension/`. Source-bound fresh-JVM publication,
actual checkpoint force, full resource/scratch admission and complete owner recovery
remain required. No workflow, public API, frozen limit or V5.2 cloud change.
