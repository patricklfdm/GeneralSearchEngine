# Phase 2C3b — local membership prefix adoption

Status: locally qualified adoption transaction; Phase 2 remains **OPEN**.
This transaction joins the [certificate-derived promise fence](PHASE_2_ADOPTION_FENCE.md)
to a complete local generation/selector installation. It returns no network ACK,
application result or READY state, and does not enable the public runtime.

## Transaction and recovery

Under the exclusive generation/journal owner, revalidate the entire incoming
capsule and image inventory. Require ancestry to the current selected parent and
every retained original BASIS parent. A new transaction must advance the proven
index and membership authority. An owned tail above that prefix cannot disappear;
covered tail bytes remain in the old generation and original sources.

Build the exact candidate and check any inactive files/pending selector against it
before changing PROMISE. An occupied different old generation requires the later
governing-floor retirement protocol; this operation never deletes it. Reserve the
complete inactive generation and its images using the existing shared bounds.
Capacity failure cannot write a higher promise. Failed reservation/force invalidates
the owner rather than leaving it usable with incomplete accounting.

Force the certificate-derived promise before candidate writes, preserving any
already higher promise byte-for-byte. Copy the exact referenced certificate into
`adopted-certificate.gsr`, included in the existing GENERATION file inventory; no
new frame kind or frozen field is introduced. The adopted generation has null
BASIS/SELECTED/tail references. Its copied promise retains its original governing
view, which can differ from the adopted cut's next authority. Reopen authenticates
the marker through the complete capsule walk and checks its promise bound.

A crash between the new null-BASIS fence and candidate writes must recover the
prefix before any new PREPARE, even a higher old-view ballot. Once staging exists,
only the exact candidate may resume. All files, generation directories, selector
and parent are forced before returning. Exact installed replay makes no new vote.
The old generation and original grant history remain untouched. A later eligible
grant captures the new view under a fresh ballot; an obsolete original source
cannot be selected for voting. Known removed identities retain authenticated
history on reopen but cannot grant.

The common installer also rechecks inode identity after write/force callbacks. A
same-content replacement must not silently become the new owned file. Selected
installation now checks ancestry to the current parent as well as retained BASIS
parents, so a prior grant cannot roll back subsequently adopted state.

## Qualification boundaries

The fresh-process matrix covers initial sizes 3/4/5 and adoption of joint/final
prefixes. Clean and halt/SIGKILL executions cover validation, promise writes,
materialization, selector and return boundaries. Independent replay derives the
candidate from original inputs, verifies physical snapshots and force order,
requires same-ballot rejection and a fresh new-view grant, and rejects evidence
mutations only after validating the original. Unit checks additionally cover a
higher old promise, known removal, compacted ancestry, capacity before mutation,
repeated interrupted recovery, altered buffers and replaced file identities.

Remote historical record ownership remains a fixture assumption. Application
images remain fixture materializations, not complete real application storage.
No power-loss durability, network installation ACK, service readiness or complete
Phase 2 acceptance follows from this local component. Governing floor/retirement,
rotation, actual phased vote/application storage and complete offline recovery are
still required by the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).

The final source passed 234 cases / 1170 fresh JVMs, all 14 exact-reason negatives
and relocated replay in 567.824 seconds. Common selected installation
regression passed 174 cases / 12 negatives, and the fence regression passed 66
cases / 12 negatives. All 129 focused Java, 69 Python/build-contract and 53
optimized-Python tests passed. The [retained hash index](phase2-evidence/adoption-install.json)
records source/JAR/class bindings, complete raw inventory hashes and development
failures. The earlier 234-case pass precedes the reservation-retention adjustment;
the reported final result was rerun on the adjusted source.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_adoption_install_evidence \
  scripts.v53.test_adoption_fence_evidence scripts.v53.test_generation_install_evidence \
  scripts.test_ci_v51_bundle
python3 -m scripts.v53.adoption_install_qualification \
  "target/v53-phase2-adoption-install/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new evidence directory and retain every failed run. No push or V5.2
experiment changes are part of this qualification.
