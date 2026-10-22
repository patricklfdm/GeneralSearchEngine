# Phase 2C5c — original pending certificate over actual phased quorums

Status: local component qualification PASS. Phase 2 and the public runtime remain open.

## Certificate admission and original records

The private owner now accepts an exact CERTIFICATE only while it physically owns
the matching local ACCEPT and PROOF under its installed selection. First admission
uses the existing strict certificate/inventory validator with actual ACCEPT and
PROOF observations from eligible permanent voter identities at the exact parent.
Both witness sets independently require the governing old/new majorities. Missing
one phase, phase/record/identity/parent substitution, alternate ballot/ENTRY, or an
incompatible PROOF representation refuses before certificate writes.

The original CERTIFICATE follows PROOF in the existing bounded private pending
container. Actual candidate write/force, parent force, atomic replacement and final
parent force precede return. A complete original candidate may recover only over
its matching actual active PROOF. Reopen validates exact framed originals and
phased witness structure; it does not manufacture new remote observations.

An exact duplicate preserves all originals. Repeating ACCEPT or PROOF cannot
replace a pending certificate candidate, even when the candidate is still empty.
A complete/forced certificate fixes its original witness representation for this
local ballot. A higher observed ballot or same-byte inode replacement cannot
return success for an earlier certificate request.

## Partial requests, completion space and capture

A partial candidate binds **every surviving prefix byte**. An unwritten witness
suffix has no durable identity yet: a fully revalidated equivalent representation
may fill it only if every surviving byte and the actual active ACCEPT/PROOF match.
Missing quorum evidence still refuses without changing that prefix. A complete
candidate and an already forced original cannot be relabelled. This clarifies the
older component wording that called every partial suffix an exact original request;
no chosen ENTRY, selected set or forced authority can change through this rule.

ACCEPT and PROOF admission reserve the remaining certificate replacement and next
maximum PROMISE/BASIS within the existing **32 MiB JOURNAL**. Source admission also
reserves remaining phased objects/index rows within the existing **32 MiB source**.
No new lease, frozen record/wire kind or application encoding is introduced.

Fresh PREPARE retains original ACCEPT/PROOF/CERTIFICATE bytes in its source, while
BASIS continues to name the actual ACCEPT. Current application, catalog, cut and
immutable generation remain unchanged. **A stored certificate is not publication**:
materializing and publishing its application/catalog result is the next transaction.

## Qualification scope

Separate actual local voters produce matching ACCEPTs and PROOFs, then reopen their
original files before their observations are used by the certificate driver. The
initial certified prefix/application images remain historical fixtures. Independent
Python reconstruction checks original selected installs, both phased quorum records,
complete pending certificate bytes, force/return order, duplicate preservation and
fresh source capture. It never imports the production Java validator.

Completed process matrix: **45 cases / 396 fresh JVMs** across 3/4/5 stable/joint/new-stable profiles,
halt/SIGKILL at nine certificate boundaries and repeated death at seven recovery
and two active-reseal boundaries. All **14 exact original-first mutations** and portable
replay passed in **333.972 seconds** overall. No network/public bootstrap, power-loss or cloud claim.

## Retained validation

The reactor passed **265 Java tests**, including eight new certificate tests and
unchanged earlier storage/format/API gates. **36 Python/build tests** passed normally
and under `-O`. Prior unchanged ACCEPT and PROOF artifacts and their original exact
negative sets replayed successfully with the shared reconstruction code.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.pending_certificate_qualification target/v53-pending-certificate-new
```

[Source/build/evidence index](phase2-evidence/pending-certificate.json).
Raw logs/snapshots remain under `target/v53-pending-certificate/`. The receipt binds
parent HEAD and the exact then-uncommitted implementation/JAR/class bytes; it is
local evidence, not protected CI or application publication.

## Remaining integration

Actual application/sequence/catalog publication, stable same-round contiguous
progress, INTENT termination, covered-tail and incomplete-request retirement,
maximal source/image completion headroom and complete bootstrap/reopen remain
required before Phase 2 closure. Later protocol/public/workload/pre-cloud stages
remain required and are not replaced by this local component.
