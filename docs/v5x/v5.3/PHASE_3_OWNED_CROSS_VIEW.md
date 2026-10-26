# Phase 3B — native adoption of verified cross-view history

Status: locally qualified on the development branch. The
[source-bound receipt](phase3-evidence/owned-cross-view.json) retains the original
failures and final verification. Complete Phase 3 and the public membership runtime
remain open.

## Boundary and authority

The native owner deliberately refuses an incoming raw prefix which is not already
in its original stored history. Reusing that reader as an incoming verifier stopped
a real removed node at the first certified FINAL. The correction adds private
typed-prefix overloads for adoption and certificate-derived fencing. A
`MembershipCapsule` has a private constructor and is produced by the existing
complete-history validators; an unverified packet cannot use this entry.

The typed entry checks the exact local ROOT bytes and full image inventory before
using the original ancestry, retained-source, pending-vote, governing-floor,
certificate fence and generation-install rules. It does not create a BASIS,
SELECTED, installation ACK, fresh vote or public READY. Duplicate adoption must
still reproduce the original manifest. The raw entry keeps its verifier and source
substitution check; native unknown raw history remains rejected.

The network integration first obtains a root-bound STATUS hint, then the complete
current prefix, images and original generation/ancestry through bounded TCP
transfers. Proof originates from the contacted owner's actual selected storage.
The receiver keeps its original view/ballot guard through acquisition, then adopts
the typed result under the storage writer. Adoption fences further reads under
the old pull scope. An original history's copied endorsements are not new voting
observations. This retains the trusted-private-network/crash-fault assumptions;
it does not introduce Byzantine authentication or mixed-version support.

## Qualification scope

- Actual public bootstrap, with native owner opens at every phase, for 5→4→3 and
  4→3 on EMPTY and verified-backup sources. Votes and campaigns are driven by the
  test walk; six removed-node adoptions use real TCP. New DATA after removal must
  preserve the original application history and exact document results.
- A new JVM reopens each removed node using only its actual admitted paths, then
  refuses a fresh election without writing authority.
- Foreign verified roots, altered images, range-only fencing and higher-ballot
  interruption at every installation boundary are negative checks. A successful
  complete copy does not rescue an unknown raw prefix.
- One actual 4→3 EMPTY history exercises each of 19 adoption boundaries under
  halt and SIGKILL, another death during recovery, then completion. Workers read
  actual original source storage and receive no serialized historical observations.
  These process cases do not establish power-loss durability or cover the complete
  Phase 3 distributed fault inventory.
- Independent Python readers reconstruct the complete original REMOVE histories
  before checking transferred bytes, original forces, adopted manifests, worker
  results and interrupted storage. Intended negative cases require their exact
  rejection; a broken unmodified history cannot count as successful negatives.

The final Java run passes the two native integration suites. Six unaffected suites
passed in the preceding build, whose complete production class inventory matches
the final build byte for byte: 63 tests across eight suites in total. That preceding
build as a whole failed because the new inspection worker mistakenly requested a
governing floor from an already removed node. The corrected worker checks the
native selected history and explicitly verifies both floor-copy and election
refusals. The earlier failed output remains retained.

The four normal profiles contain 60 committed slots, six TCP adoptions and six
fresh-process removed-node reopenings. The separate crash history contains 38
cases, 114 child JVM executions and 19 lock probes. Halt and SIGKILL are process
failure checks; they are not power-loss durability evidence.

Complete normal, optimized and unpacked portable replay agree, including all 22
intended evidence rejections (16 network/history and six crash variants). The 23
focused Python regressions pass in normal and optimized modes. The receipt binds
the final build inputs, all 779 compiled production files, two JARs, 61,205 raw
evidence files, the original run logs and eight JUnit reports. No whole-reactor
test count or protected-CI acceptance is inferred from these focused checks.

## Still required

Automatic election/discovery ownership and scheduling, native pending-context
turnover across configurations, learner ADD/REPLACE delivery, joint completion,
generalized distributed voting/publication and the complete Phase 3 audit remain
open. This component does not enable public operations or claim the frozen S/N
matrix is closed. No format, resource limit, deadline, public factory, POM,
workflow, V5.2 Runner, paid experiment or remote push is changed.
