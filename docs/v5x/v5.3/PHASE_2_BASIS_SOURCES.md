# Phase 2B2a — retained original basis bytes

Status: **locally complete as a private storage component**. Phase 2B2 remains open
for binding a grant to the selected current generation and actual owned parent/tail.
The public membership runtime stays disabled. The test inputs' authenticated remote
ownership observations remain synthetic; copying their records locally does not
turn them into evidence of remote force or voter ownership.

## Layout and ownership

`MembershipGrantJournal.openRetained` owns the allocator, journal and pre-provisioned
`sources/` directory under the same `replica.lock`. It never creates a missing root
or sources directory and never falls back to the metadata-only open. The older
allocator and metadata-only entries reject the additional directory.

Each frozen basis UUID names one immutable directory:

```text
sources/<basis UUID>/
  source.gscp
  <application SHA-256>.image
```

The source packet contains the original capsule, catalog, genesis/root, referenced
metadata and optional ACCEPT/ENTRY/payload bytes. Images are separate original bytes.
No frozen record or wire schema changes. Reopen reads every historical journal
PROMISE/BASIS, rejects UUID reuse, and binds each completed BASIS to its exact packet.
All packet images must exist at their declared lengths and hashes. Extra entries,
unbound directories, links, missing/torn/corrupt bytes and live inode replacement
are refused. Every still-retained source is checked, including older grants.

## Ordering and resource accounting

The retained path verifies the supplied capsule/basis and image inventory, reserves
the source/image capacities, and copies the caller's image buffers before PROMISE.
Its successful sequence is:

1. Append and force PROMISE.
2. Create the original source directory; write and force packet and every image.
3. Force the child directory and its `sources/` parent.
4. Recheck physical ownership, original bytes and the observed-ballot fence.
5. Append and force BASIS; check the fence before returning.

A same-ballot duplicate verifies the retained original files and returns the original
BASIS; it never resamples the caller's progressed capsule or images. The retained
entry requires the materialization-aware overload, preventing accidental use of
the metadata-only prepare path. Inspection accessors remain private, not wire APIs.

The shared `MembershipResources` reserves the full 32 MiB journal, actual encoded
packet bytes per SOURCE (at most six, each at most 32 MiB), and all physical image
copies per APPLICATION (at most seven, each at most 64 MiB). Duplicate physical
images count separately. Source and image bytes also consume the supplied shared
staging allowance. Open reconstructs these reservations; close/failed open releases
process-local accounting, never durable files. Tests use a 512 MiB staging allowance;
production caller limits and the frozen catalog are unchanged.

Insufficient retention/staging capacity returns `CAPACITY_EXCEEDED / NOT_SUBMITTED`
before writing a new PROMISE. Partial reservations roll back. This component has
**no reclamation method**: six retained sources can stop further fresh grants until
later certified retirement/rotation exists. That conservative boundary prevents an
unbounded second source set or deletion of authority still referenced by a grant.

## Restart decisions

| Physical state | Result |
| --- | --- |
| PROMISE, no source directory, no BASIS | Same ballot refused; a fresh higher ballot may proceed |
| Partial source directory/file inventory | Open refused; retain all original bytes for later exact repair |
| Complete source, no BASIS | Validate/seal the complete original files; same ballot refused; a fresh ballot may proceed within capacity |
| Completed BASIS plus complete original source | Validate/seal files and return the exact original on a duplicate |
| BASIS with missing/different original source | Open/prepare refused; no repair from caller-supplied replacement bytes |

Visible complete files are forced again on reopen before use. Real halt/SIGKILL
tests retain the operating system's cache; they are not power-loss experiments.
Checksums and an exclusive owner also do not establish a generation selector or
detect replacement of the entire authority with a valid older snapshot.

## Qualification and retained evidence

[Summary and exact hashes](phase2-evidence/basis-sources.json) bind parent `8b9ebce`
and the local implementation/fixture bytes before reporting edits. Originals and
development failures remain at `target/v53-phase2-sources/`.

- 80 focused Java tests, including eight source-storage methods covering duplicate
  progress/reopen, all source cuts and fencing, shared capacity, missing/corrupt/
  linked/replaced files, original accepted tails, lock and accounting release.
- 41 Python/build-contract tests and 25 optimized-Python tests.
- 69 cases / 258 fresh JVMs: each initial size 3/4/5, clean progress/duplicate,
  halt and SIGKILL at eight source boundaries and three completed-BASIS/return cuts.
  Independent replay checks actual files, exact force order, process outcomes,
  original prefixes, rejected partial recovery and subsequent higher ballots.
- Eleven original-first, reason-specific evidence mutations and relocated replay
  passed. Qualification took 74.304 seconds on this local machine.
- The unchanged earlier grant matrix passed 45 cases / 180 JVMs, eight negatives
  and relocation in 49.199 seconds. The allocator matrix passed 48 cases / 186 JVMs,
  ten negatives and relocation in 28.671 seconds against the extended owner.

The development reader initially used Python 3.11's `hashlib.file_digest`; it now
uses bounded streaming compatible with the local Python 3.10. The first crash replay
also expected the wrong missing-file exception type; the assertion now checks the
actual shared filesystem helper's precise `ReplicationException` and member suffix.
The failed attempts are retained; neither correction retries a workload measurement.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_basis_sources_evidence \
  scripts.v53.test_grant_evidence scripts.v53.test_allocator_evidence \
  scripts.test_ci_v51_bundle
python3 -m scripts.v53.basis_sources_qualification \
  "target/v53-phase2-sources/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. Source/JAR/class hashes must remain unchanged throughout
qualification. Its 30-second per-process guard is a local test bound, not a cloud
budget. Current 5.3 shared-build prerequisites add the new suite/worker without
removing any inherited requirement.

## Next storage obligations

2B2b must derive the sampled parent/tail from current owned generation authority,
serialize generation installation with the grant, and replace caller-asserted
ownership with observations from the actual storage path. 2C must add durable
SELECTED, complete generations/selector/floor, adoption, ACCEPT/PROOF persistence
and bounded retirement/rotation. Those steps must preserve the original references
qualified here. Phase 2 closure, public service, full S/N physical coverage and
unified acceptance remain pending. No workflow, cloud run or release was performed.
