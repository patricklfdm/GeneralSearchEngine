# Phase 2C4c4c — captured original sources without a BASIS

Status: locally qualified only when complete source bytes are covered by a strictly
later governing floor. This extends [original-source retirement](PHASE_2_SOURCE_RELEASE.md)
without fabricating a BASIS or weakening full-copy, ancestry or ownership checks.

## Accepted case

A process may die after forcing the original source packet/images but before
writing BASIS. A later certificate can advance the local generation, and a full
old/joint/new governing floor can cover the older source's possible unresolved slot.
The reclaiming owner now permits retirement when:

- The original PROMISE, complete source packet/images and durable newer promise
  remain bound to this root, owner and original configuration.
- The current generation and full floor prove exact ancestry from that original
  capsule, and the floor cut is strictly later than the original cut.
- Every well-framed ACCEPT belonging to this root in the original packet is
  covered by that floor. Opaque application bytes are not classified from magic
  alone; a valid but ambiguous same-root ACCEPT is conservatively retained.
  An absent BASIS never implies an empty accepted tail.
- No current/floor generation still references the original promise/BASIS.

The same force/journal/deletion transaction applies. The saved authority contains
RETIREMENT, original PROMISE and CAPSULE. Completed grants retain their original
four-frame form including BASIS; the third frame's exact type distinguishes the
forms. Both remain within the existing bound and frozen record inventory.

On recovery, the original source must remain complete while its PROMISE is still
in the journal. Only after exact journal replacement may the saved complete
authority admit the remaining file subset for cleanup. A truncated decision cannot
resume after losing the original promise or source. A captured-only marker cannot
hide a real persisted BASIS, and a completed decision cannot conceal the loss of
its original BASIS frame while the original PROMISE remains in the journal. Surviving resource leases remain continuously held.

## Qualification

All **44 cases / 178 fresh JVMs**, **14 exact negative results** and portable
replay passed in **203.686 seconds**. The focused reactor passed
**218 Java tests**, including nine captured-source tests. **47 Python/build tests**
passed normally and under `-O`. All **297 original completed-BASIS cases** also
passed replay through the shared validator. The [hash index](phase2-evidence/captured-source-release.json)
retains the precise source/build/inventory bindings; raw results and draft failures
remain under `target/v53-captured-source-release/`.

The physical matrix covers clean capture-only recovery at sizes 3/4/5, joint/new
views, with and without an original accepted tail; halt and external SIGKILL at
all fifteen transaction boundaries for a 3-node joint profile; and repeated
recovery death with a 5-node new-view original tail. The independent validator
replays the retained original capture, certified adoption, exact full peer copies,
forced floor, journal and deletion inventories. It does not manufacture a BASIS
for the implementation. Historical remote ownership and application bytes are
still fixtures, not live public-runtime evidence or power-loss testing.

The normal completed-BASIS matrix remains a separate retained baseline. Its
original immutable artifact can be replayed through the shared event validator;
new source/build-qualified captured cases do not relabel those older runtime bytes.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.captured_source_release_qualification target/v53-captured-release-new
```

## Outstanding lifetime work

Same-cut sources without BASIS, physically incomplete packets/images, maximal
source/image headroom and complete coordinated campaign/read/transfer lifetimes
remain OPEN. These tests do not establish that six occupied source slots can
stage another full floor. Actual phased vote/application persistence, complete
store bootstrap/reopen and the Phase 2 closure audit remain required.

No public factory enablement, frozen budget/format change, workflow, push, paid
cloud execution or separate V5.2 Runner modification is included.
