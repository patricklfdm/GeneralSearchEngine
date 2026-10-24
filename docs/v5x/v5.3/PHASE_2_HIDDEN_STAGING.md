# Covered applied endpoint inside a published RANGE

Status: local owner qualification **PASS**. Phase 2 remains **OPEN**.

The earlier [covered staging path](PHASE_2_COVERED_STAGING.md) compared a lagging
applied result with a direct endpoint of the newer selected prefix. An admitted
three-voter reproduction instead published two entries on the majority while the
lagging voter retained its first applied certificate. Its result was now hidden
inside `RANGE(0,2)`, and cleanup refused `generation did not preserve original
proven parent`. The failed evidence is retained unchanged.

The private owner now accepts one optional supplemental RANGE checkpoint for
that exact applied entry/index. It verifies the same root, stable view, exact
catalog/application endpoints and an actually observed eligible quorum of original
ACKs. Combined ancestry keeps the existing six-bridge / 96 KiB bounds. Typed replay
must still reproduce the original result and match this authenticated endpoint.

This proof is used only to retire derived work. Its exact bytes are hashed into
the forced retirement authority. The selected set and installation plan remain
unchanged; passing it as unused installation ancestry is still rejected. The
ordinary cleanup overload retains its previous byte representation. Repeated
cleanup neither emits an old application ACK nor removes the original vote,
selector, source or generation. Those remain under ordinary installation and
floor-driven reclamation.

## Qualification

The completed gate has 24 Java tests and 35 Python tests, six admitted profiles,
56 node publications, eight local interruptions and twelve exact evidence
rejections. Normal, optimized and relocated replay agree. The prior direct-end
path also passes its six profiles and seventeen portable evidence rejections.

The producer uses actual public offline bootstrap for 3/4/5 voters with EMPTY and
verified-backup sources. Each profile preserves applied minority certificates,
advances a disjoint majority, cleans derived state, installs the exact selected
prefix, reclaims old sources and publishes another BARRIER. Typed inspection
checks the original DATA was applied exactly once. Focused cases refuse missing,
extra, unowned or changed proofs and changed forced proof identity.

The independent reader derives admitted originals, both majority publications,
the supplemental checkpoint/ACK bytes, exact cleanup inventory, original vote
retention, selected installation and subsequent publication. It also checks
repeated local interruption states, force/delete ordering and specified evidence
mutations. Original evidence is checked before mutations; normal, optimized and
relocated replay agree. See the retained
[evidence index](phase2-evidence/hidden-staging.json) for measured results.

These are local owner and exception-interruption results, not process-death or
power-loss qualification for this new hidden-endpoint path. Protected contexts,
complete cross-view storage, maximal capacity/lifetime and the final S/N storage
mapping remain in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md). Public
runtime, frozen limits/formats, workflows and V5.2 remain unchanged.

The subsequent [dedicated process gate](PHASE_2_HIDDEN_STAGING_PROCESS.md) now
qualifies repeated halt/SIGKILL recovery for this hidden-endpoint path.
