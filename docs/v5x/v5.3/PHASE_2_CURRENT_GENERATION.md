# Phase 2B2b — current local generation capture

Status: **locally complete for immutable current-generation capture**. Phase 2
remains open. The grant journal now samples the physically selected local source;
generation installation/switching and remote historical ownership verification
remain separate obligations. The public membership runtime is still disabled.

## Authority and scope

`MembershipGrantJournal.openCurrent` holds the same exclusive `replica.lock` as
the allocator, journal and retained sources. It opens only a pre-provisioned
directory with this additional authority:

```text
selector.gsr
generations/a/                 # or b, exactly as selected
  generation.gsr
  source.gscp
  promise.gsr
  owned-tail.gsr               # present exactly when the manifest names a tail
  <application SHA-256>.image
```

The existing 1.3 SELECTOR and GENERATION schemas are unchanged. SELECTOR binds the
full manifest digest, root, node and generation name. The manifest binds the exact
packet/capsule, parent cut, catalog, application and original PROMISE bytes. That
PROMISE must exist in the journal and belong to the current view. Each image is
checked against both the manifest and the packet. The local node's full identity
and voter eligibility must match the verified capsule.

A retained local tail requires a separate original ACCEPT file matching the packet
and manifest, with the correct parent/index, ballot and entry. `currentOwnedTail`
returns the verified local node/storage/record/parent observation. This establishes
which bytes this local owner retains; it does not prove a remote force or create
a protocol vote. Historical remote observations are still supplied to the capsule
verifier. The verifier receives the actual disk packet/images and must return a
capsule containing those same packet bytes; it cannot substitute another source.

This entry supports one immutable selected generation. It refuses extra/inactive
generations, non-null manifest `basis`/`selection`, missing/torn/corrupt files,
links, unexpected inventory and mismatched journal cuts. Either slot `a` or `b`
works when explicitly selected; there is no search for a fallback slot or legacy
open. The fixture provisioner is test-only, not the public bootstrap contract.

## Grant serialization and durability

`prepareCurrent(ballot)` accepts no caller capsule, images or accepted-tail override.
It checks the selected files and samples their verified authority under the journal
writer monitor. The generic prepare/observe methods cannot substitute a different
source/context on this entry. Concurrent duplicate calls return the same original
BASIS. A verified higher-ballot observation can still fence an in-flight writer
without waiting for that monitor.

Open validates all bindings, then forces the files, generation manifest/directories,
selector and parent directory before making the source available. Its five cuts are
`CURRENT_VALIDATED`, `CURRENT_FILES_FORCED`, `CURRENT_GENERATION_FORCED`,
`CURRENT_SELECTOR_FORCED` and `CURRENT_DIRECTORY_FORCED`. Capture adds
`CURRENT_BEFORE_CAPTURE`; the existing retained-source/PROMISE/BASIS force order
then applies. Physical ownership and the observation fence are checked again before
returning a newly recorded grant.

Directory identities, single-link regular file identities, lengths, hashes and
inventories are rechecked during use. Replacing a selector/file with byte-identical
contents but a different inode is refused. No installation method runs concurrently:
Phase 2C must put the eventual generation transaction under this same owner/monitor
and define crash recovery before switching is enabled.

All retained BASIS cuts must currently equal the selected capsule cut. This rejects
replacing the selected generation with an older valid generation while a later
grant remains. It deliberately prevents normal cut advancement until Phase 2C
implements ancestry/adoption and lifetime rules. It cannot detect replacement of
the entire authority with an internally consistent old snapshot without the later
durable floor.

## Bounded resources and restart

The selected generation reserves one existing GENERATION slot for its actual
metadata, including manifest, packet, PROMISE and optional tail, within 32 MiB.
Each physical image consumes the existing APPLICATION count/byte and shared staging
limits; current and retained source copies count separately. The current authority
reserves the existing 2 MiB MISC allowance. These reservations share the journal's
resource owner and preserve the frozen limits; they are not additional pools.

Failed open and close release process-local reservations and the lock. They never
delete or rewrite authority. Complete files are forced again on reopen. The earlier
retained-source rules still govern partial source directories and incomplete grants.
No current-generation install, selector rewrite, repair, deletion, adoption or
retirement API is supplied by this batch.

## Qualification

[Summary and exact implementation hashes](phase2-evidence/current-generation.json)
bind parent `88ea248` plus the local implementation bytes before final reporting
edits. Raw evidence and the initial development test failure remain at
`target/v53-phase2-current-generation/`.

- 89 focused Java tests passed, including nine current-generation methods covering
  both slots, 3/4/5 members, tail/no-tail, reopen, duplicates, concurrent fencing,
  force failures, replaced files, exact manifest bindings, rollback, capacity and
  owner/accounting cleanup.
- 49 Python/build-contract tests and 33 optimized-Python tests passed. One initial
  Python fixture mutation was rejected by the encoder before reaching the reader;
  it now uses a valid nested path to exercise the reader's flat-file restriction.
- All 90 fresh-process cases / 360 JVMs passed: 3/4/5 members, tail/no-tail, clean
  capture, and halt/SIGKILL at the five open cuts, capture and grant return. Independent
  replay checks actual bytes, process outcomes, force order, original duplicate
  replies, local owned-tail observations and retained sources. The matrix took
  159.032 seconds on this machine.
- Thirteen original-first, exact-reason evidence mutations and relocated replay
  passed. Unrelated original failures cannot count as negative successes.
- Unchanged source retention (69 cases / 258 JVMs / 11 negatives), grant journal
  (45 / 180 / 8) and allocator (48 / 186 / 10) matrices passed against the new
  implementation, with portable replay. Their elapsed times were 72.782, 48.711
  and 28.719 seconds respectively. All four raw receipt inventories were verified.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_current_generation_evidence \
  scripts.v53.test_basis_sources_evidence scripts.v53.test_grant_evidence \
  scripts.v53.test_allocator_evidence scripts.test_ci_v51_bundle
python3 -m scripts.v53.current_generation_qualification \
  "target/v53-phase2-current-generation/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. Source/JAR/fixture bytes must stay fixed throughout the
run. The 30-second per-process guard is a local test bound. Halt/SIGKILL retains
the operating system's cache and does not emulate power loss. Structural physical
replay does not independently authenticate the fixture's remote certificate history.

The shared 5.3 build contract requires this suite/worker/fixture in addition to all
previous prerequisites. No workflow, POM, inherited runtime, public API or frozen
format changed. Complete physical S/N qualification, protected CI and unified
acceptance remain pending. No push, hosted workflow or V5.2 cloud action was performed.

## Next batch

Phase 2C starts with durable selected-source installation and selector recovery
under the journal owner, including adoption/ancestry and source lifetimes. It then
adds ACCEPT/PROOF persistence, complete generation/floor recovery and bounded
retirement. These transactions must preserve every retained original grant and
replace the immutable-entry restrictions only after their own crash qualification.
