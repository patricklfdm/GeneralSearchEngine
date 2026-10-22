# Phase 2B1 — durable promise and original basis metadata

Status: **2B1 locally complete**, private storage component; **Phase 2B remains open** for physical source
ownership and retention. This batch cannot send a PREPARE grant, vote, publish
READY or enable the public membership runtime.

## One owner and a bounded journal

`MembershipGrantJournal` shares the Phase 2A allocator's exact exclusive directory
owner. Its only additional required file is an already provisioned `grants.gsr`.
Missing files are never recreated. The allocator-only entry rejects this extended
layout, so a second independent writer cannot bypass the journal owner.

The file concatenates existing checksummed 1.3 PROMISE and BASIS frames; no new
record kind or frozen byte schema is introduced. Replay checks exact root/local
identity, strictly increasing full ballot tuples, PROMISE/BASIS UUID/view/ballot
binding, at most one basis per promise, and the basis cut's exact membership view.
It retains all earlier bytes. Unknown, partial, corrupt and conflicting records
fail closed without truncation or repair. A failed open releases the exclusive lock.

The normal limit is the frozen 32 MiB journal reservation. Before writing PROMISE,
reserve the maximum 8 KiB PROMISE plus 16 KiB BASIS together. At insufficient
headroom, refuse `CAPACITY_EXCEEDED / NOT_SUBMITTED`; safe journal rotation is
pending Phase 2C. Tests can lower the private byte ceiling to exercise this exact
pre-write boundary; production defaults and frozen limits are unchanged.

File inode, content, directory, lock and immutable root/node bytes are rechecked
before writes. The journal is an existing forced file; append calls `force(true)`
before proceeding. Reopen seals complete visible records by forcing file and
directory. Actual fsync durability and cooperative exclusive ownership are assumed.
Checksums do not detect replacement by an entirely valid old prefix without a
separate generation/selector anchor; that complete-store authority is still pending.

## Two forces and one original capture

The caller supplies an already verified capsule representing its current owned
cut, full identity and optional accepted-tail reference. The journal checks its
root, local/proposer eligibility, packet/capsule/inventory binding and tail parent,
payload and ballot context. It snapshots the exact BASIS fields once, creates a
fresh basis UUID, then forces PROMISE before forcing BASIS. No successful return
precedes both forces. Numeric ballot inputs are normalized before equality checks.

| Restart state | Same-ballot request | Higher fresh ballot |
| --- | --- | --- |
| No complete PROMISE | May create a grant | May create a grant |
| Complete PROMISE without BASIS | Refuse; never sample a replacement basis | May supersede the incomplete grant |
| Complete PROMISE and BASIS | Return the identical original frame, even if the supplied source progressed | Capture a new basis and retain the old journal bytes |
| Partial/corrupt journal | Refuse open, preserve bytes | Requires later exact recovery/repair; no automatic bypass |

A complete frame visible after process death may be retained even if the former
process never returned. That conservative decision cannot invent a basis for a
promise that has none. Duplicate requests in a different configuration are refused.

Verified higher-ballot observation updates an atomic fence without acquiring the
writer monitor. The writer rechecks before and after each force and before returning.
A concurrent higher observation prevents the old operation from reporting success
at those boundaries. I/O/fencing failure after entering the append path poisons the
handle; close/reopen is required. An observed higher ballot can also fence old
requests when capacity prevents granting the higher one. Only forced promises
survive restart. Counter allocation under the same owner advances beyond the
observed/durable promise bound; a concurrent counter observation is rechecked.

## Explicit integration limits

- This journal persists the **metadata frames and references**, not the referenced
  capsule/application/owned ACCEPT files. The test worker retains synthetic input
  packets outside the authority directory for independent replay only.
- The caller must establish that the capsule is the current physical owned cut,
  exclude concurrent prefix installation, retain every referenced original object
  and keep source leases alive. The journal cannot establish these facts from a
  hash or a remote claimed ownership set. Phase 2B2 will supply that integration.
- Replay of metadata is not enough to authorize a source response. No runtime
  caller uses this component yet. Recovered basis access is internal inspection.
- Certificate-derived adoption floors (`basisId = null`), durable SELECTED,
  ACCEPT/PROOF storage, generation selection, rotation and reclamation are later
  batches. This implementation rejects unsupported adoption records.
- Runtime callback fencing, complete proof ancestry and service readiness remain
  later protocol gates. The local check immediately before returning is its
  metadata operation boundary, not a public asynchronous response guarantee.

## Qualification

The Java suite covers exact duplicates before/after reopen and source progress for
3/4/5 initial voters, all seven write/force/return boundaries, incomplete grants,
full ballot order, invalid identities/configurations, removed voters, capacity
headroom, tail reference preservation, torn/conflicting journals, owner replacement
and a concurrent higher observation while the writer is blocked. The 2A suite also
runs after integrating its owner with the new required journal.

The fresh-process matrix has 45 cases: clean/progress/duplicate plus halt and
SIGKILL at all seven boundaries for each initial size. SIGKILL uses an explicit
cut handshake. Independent Python replay reads original frames, force observations,
every exit code, frozen source packet bindings and unchanged authority snapshots.
Eight original-first mutations must fail for their specific reasons; an unrelated
reader failure cannot be counted as a successful negative. Relocated evidence is
replayed. These are process failures, not power-loss or distributed grant evidence.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_grant_evidence \
  scripts.v53.test_allocator_evidence scripts.test_ci_v51_bundle
python3 -m scripts.v53.grant_qualification \
  "target/v53-phase2-grants/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. The inherited 30-second per-process test guard does
not alter cloud/workload budgets. Shared current-coordinate build bundles require
the executed grant suite and worker alongside all existing prerequisites.

## Retained local result

[Summary and hashes](phase2-evidence/grants.json) bind parent `40e0866` plus the
exact local implementation and fixture bytes before final reporting edits. This
is not protected CI or a clean-HEAD acceptance claim.

- 72 focused Java tests passed, including ten grant regressions and the ten
  allocator regressions; 32 Python/build-contract tests and 16 optimized-Python
  tests passed.
- All 45 grant cases / 180 fresh JVMs passed in 47.966 seconds, with eight exact
  negative results and relocated replay.
- The unchanged 48-case allocator qualification / 186 JVMs passed against the
  modified shared owner in 28.741 seconds, including ten negatives and relocation.
- Originals, failures encountered during development and final logs remain under
  `target/v53-phase2-grants/`. The compile-time use of a private helper was corrected
  to canonical parsing; the removed-voter test fixture now binds both NODE and
  ALLOCATOR to that same identity before testing eligibility.

Full GSE CI, cloud execution, public membership operations, complete source
ownership and power-loss acceptance were not run or claimed in this metadata batch.
