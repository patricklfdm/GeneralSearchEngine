# Offline initial projection

Status: private projection and local first-round qualification. Public bootstrap
and learner entry points remain disabled. Phase 2 is **OPEN**: a seed is neither a
committed offline operation nor a durable history reservation.

## Source and exact application

`MembershipBootstrapSeed.project` accepts an explicit nonzero history from its
future coordinator and an absent scratch directory. It checks disjoint authority,
materialization, operation, source and scratch paths, existing parent identities,
all target absences, and matching complete durable storage/codec/bound descriptors.
The captured application descriptor includes schema, indexes, snapshot and planner
configuration. These bindings are checked again after application callbacks.

EMPTY starts at application sequence zero with the requested indexes. A verified
backup must have exactly its three bounded regular, single-link members, matching
schema/codec and requested indexes. Every target's codec decodes the actual backup.
Source member hashes and inode identities are rechecked after callbacks, including
byte-identical inode replacement. The imported sequence, document order and active
indexes are preserved; the core image is re-exported with the **new** history.
Reusing the source history is rejected. All targets must produce identical complete
normalized application bytes; codec names alone do not establish agreement.

Only caller-provided scratch is written. Existing paths and failed scratch are
never repaired or deleted. Each export reserves a complete 64 MiB image allowance
against the request's operation budget before writing. Retained scratch plus all
projected target payloads must fit as well. This is conservative scratch admission,
not the final coordinator budget: plan, decisions, preparations, receipt and seals
still need their own complete reservation before durable admission is enabled.

## Initial records and fence

The seed builds exact 1.3 GENESIS and ROOT frames, the initial catalog and an
empty-items capsule with the separate real core application image. Its capsule
requires **no synthetic historical observations**. The root's embedded checksum
is the root identity; references to ordinary frames use their full-frame hashes.
The image and returned payload arrays are defensive copies.

Each of 3, 4 or 5 target layouts has its own NODE, allocator, selector and complete
generation `a`, plus an empty `sources` directory and empty pending vote. The
initial local allocator and PROMISE both have counter one, local proposer/storage
identity, and **null BASIS identity**. This is only an initial fence. There is no
BASIS, SELECTED, ACCEPT, proof, certificate, leadership or read authority. A same
ballot PREPARE cannot obtain a grant; the first campaign reserves a strictly higher
counter through the actual durable allocator.

This private projection does not force a random history once, create a coordinator,
prepare replicas, publish a receipt or authorize public opening. Test-only code
writes its payloads to exercise the existing private owner. Complete offline
bootstrap must bind these exact bytes to a durable reviewed plan and local seals;
copying these test files is not a supported initialization method.

## Local qualification

[Source/build/raw evidence](phase2-evidence/bootstrap-seed.json) records 44 passing
Java tests, including nine seed tests and the existing application-image,
declaration, legacy bootstrap and version-boundary gates. Seed tests cover EMPTY
and actual backup projection at all three sizes, new/repeated histories, strict
source/index/sequence/capacity checks, changed paths/identities/codecs and defensive
bytes. The concrete initial layouts reopen under the existing complete private
owner, reserve the first counter, force real grants and selection, install, retire
the unused original generation under an exact quorum floor, release that floor,
and complete real ACCEPT/PROOF/certificate/application acknowledgements at all
12 initial voters. No prior synthetic vote/remote ownership observations are used.

The independent Python oracle checks all 12 **initial** file layouts, local fences,
empty votes, original root/genesis/catalog/capsule/image bindings and exact
selector/manifests. Eleven exact-reason mutations, relocated replay and optimized
Python are required. It does not independently establish typed image semantics or
the subsequent Java voting/application trace. No process-crash, power-loss,
committed bootstrap, public runtime or distributed failover claim is made.

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53BootstrapSeedTest,V53ApplicationImageTest,V53DeclarationsTest,V51BootstrapTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.bootstrap_seed_evidence <v53BootstrapSeedEvidence-directory>
python3 -O -m scripts.v53.bootstrap_seed_evidence <v53BootstrapSeedEvidence-directory>
```

## Next integration

The [private plan owner](PHASE_2_BOOTSTRAP_PLAN.md) now binds the initial projection
to one retained exact plan/history and original path/source/configuration descriptors. Complete PREPARING/PREPARED/COMMITTING/
COMMITTED and local seal publication/reopen with repeated recovery interruption.
Retain ambiguous or missing original authority without regenerating it from the
request. Full budget accounting, original-first physical evidence and the public
entry transition remain pending. Transferred-context lifetime and the broader
Phase 2 resource/closure audit remain separate outstanding obligations.
