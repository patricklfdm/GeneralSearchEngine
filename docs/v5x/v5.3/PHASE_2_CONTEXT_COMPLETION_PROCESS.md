# Context completion across repeated process death

Status: local process qualification; Phase 2 remains **OPEN**. This gate joins
[predecessor source retirement](PHASE_2_CONTEXT_SOURCE_RELEASE.md) and
[exact successor acceptance](PHASE_2_CONTEXT_ACCEPTANCE.md) under actual fresh
journal owners. It complements the clean
[three-owner publication](PHASE_2_CONTEXT_PUBLICATION.md) history.

## Scope

The original owner has a ballot-20 certified DATA entry, a ballot-21 installed
selection carrying that same entry, an exact retained context, its separately
owned backing source and the governing floor that permitted old-generation
retirement. Each worker derives root/node identity and original ENTRY/payload from
retained files; it does not generate a replacement origin or recovery certificate.

The matrix has 43 first-interruption points in each of two modes, halt and external
SIGKILL: source-retirement authority, journal compaction, deletion of both original
source files, successor candidate prefix/force/rename, context withdrawal and floor
release (including the second and fourth member deletion). Each of the 86 cases
then starts another JVM and kills recovery again with halt at the successor's
active-file force. A third JVM completes recovery and makes two explicit identical
acceptance requests. There are 258 worker processes and 43 external live-lock
probes at the initial SIGKILL boundaries. Probe processes and prerequisite producer
work are reported separately from those 258 workers.

Workers check the shared resource bounds at force events. Completion has six
APPLICATION reservations and releases every lease on close. Reopen itself returns
no acceptance acknowledgement. Only the exact explicit requests after reopening
return the same forced successor. No proof, application publication or network
acknowledgement is invented by this gate.

## Independent replay

The Python validator replays the original generation/floor/source evidence before
examining interrupted cases. It derives the new ACCEPT container and floor-release
inventory from those original bytes. For every case it predicts both interrupted
physical inventories, the final inventory, journal rotation and force/delete
ordering. It separately checks that the original ENTRY origin remains 20 while
the acceptance ballot becomes 21, and that acknowledgements occur only after open
and the explicit requests. Observed interrupted files are never their own oracle.

Nineteen exact-reason negative variants cover original corruption, missing cases,
changed prefixes and final votes, retained context/floor, lost backing source,
force-order changes, incorrect death boundaries, unrelated/early/wrong returns,
resource/scope/input changes and linked files. Original, optimized-Python and
relocated replay must all agree. The
[retained source/build/raw index](phase2-evidence/context-completion-process.json)
records the executed results.

The prerequisite's live floor snapshot now recreates empty `.lock` placeholders
without opening the live lock inode; an external probe verifies ownership survives
that snapshot. All process-case snapshots are taken after the child has exited.
Production class bytes and frozen storage/resource limits are unchanged.

## Limits and reproduction

This is one local three-voter-derived profile with one actual recovering owner per
case. Historical bootstrap and remote ownership observations remain conditional.
Halt/SIGKILL on the tested filesystem do not emulate power loss. This does not
qualify later campaigns from a still-fenced context, all maximal image/metadata
profiles, complete old/joint/new lifetime or distributed runtime readiness.

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53ContextCompletionProcessTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the directory printed as v53ContextCompletionProcessEvidence.
python3 -m scripts.v53.context_completion_process_evidence <evidence-directory>
python3 -O -m scripts.v53.context_completion_process_evidence <evidence-directory>
```
