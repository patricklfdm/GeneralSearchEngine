# Phase 2 — actual journal publication and covered cleanup

Status: locally qualified for original first-slot publication. This connects the
[actual application owner](PHASE_2_JOURNAL_APPLICATION.md) and
[complete generation representation](PHASE_2_PUBLISHED_GENERATION.md) for the
original selected first slot. Phase 2 remains OPEN and the public factory stays
disabled.

## Durable transaction

`MembershipGrantJournal.publishCurrent` requires the actual local original
certificate, exact original selector/decision, and the complete previously forced
application end. It verifies all supplied checkpoint and phased observations again
through the owner verifier, including all retained source/floor ancestors. It cannot
publish an ACK belonging to another local owner or replace an interrupted plan
with a different endorsement representation.

The inactive slot must already be available through the existing governing-floor
retirement protocol. Publication writes the complete generation and forces its
selector before cleaning any original vote or application stage. It preserves
the exact original PROMISE, BASIS, SELECTED, ENTRY, payload, ACCEPT, PROOF and
certificate; it does not rewrite the original selection to the advanced cut.

On reopen, the covering generation and the exact immutable previous generation
jointly authorize cleanup. Recovery verifies the original parent catalog/image,
old selector, original journal decisions and phased records. It checks every
remaining stage member and any pending empty-vote candidate before deleting
anything. The original `plan.json` is removed last, followed by its empty directory.
The pending vote is then atomically replaced by its existing 12-byte empty
representation. A prefix of that exact replacement can resume; a different
candidate, missing plan with surviving members, changed bytes or hard links fail
without deletion.

Covered cleanup does not grant a new vote, ACK or readiness and may finish after
an in-memory higher-ballot observation. A publication return still checks the
original ballot fence. Before selector publication, normal vote operations remain
blocked by a partial generation install; only replay of the same original applied
certificate can resume that exact publication. A duplicate completed request must
produce the identical manifest.

## Accounting and scope

The existing shared JOURNAL budget reserves the 12-byte empty replacement in
addition to the applied-end/replay metadata. Application and scratch reservations
are released only after covered cleanup. The existing seven image slots, two
generation slots and all frozen size limits are unchanged. Actual DATA, INTENT
and FINAL integration uses the previously documented valid maintenance order
before ACCEPT; this is not complete full-size/all-profile lifetime qualification.

After successful cleanup, a fresh campaign captures the published cut with no
unresolved tail. This batch still covers only the first selected slot. Subsequent
same-round slots, extra ancestry ACK issuance, removed-member recovery, public
provisioning and full coordinated storage lifetime remain later obligations.

## Validation

- The initial seven-test focused suite exercises all 30 publication/cleanup event
  labels with interrupted recovery again, exact-representation rejection, changed
  stage/candidate/selector rejection and higher-ballot fencing.
- Final source-pinned qualification passes **89 Java tests**, including the
  strengthened exact parent check, authenticated reopen negatives, DATA/INTENT/FINAL
  publication and subsequent governing-floor retirement/fresh capture. Existing
  vote, proof, certificate, application, current-generation, end-file, backpressure,
  journal-rotation and predecessor version-boundary regressions pass.
- **16 halt/SIGKILL cases / 48 fresh JVMs** pass on the final source, including
  interrupted recovery. Independent Python reconstructs the expected generation
  from original votes and forced ends and compares exact intermediate files,
  selector publication and cleanup order. Eight mutations reject; relocation and
  Python `-O` replay pass.
- The [evidence index](phase2-evidence/journal-publication.json) retains source,
  JAR, report and raw-file hashes. The intermediate focused run and final
  strengthened-parent qualification remain distinct; counts are not added as
  independent repetitions of the same method.

Fresh-process tests use actual local phased votes and forced ends, while initial
bootstrap and older history remain private fixtures. Independent replay validates
original observation bindings and transaction force order, not network identity
or a replacement core application semantic oracle. Process interruption does not
establish power-loss behavior or distributed runtime acceptance.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53JournalPublicationTest' -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.journal_publication_evidence <v53JournalPublicationEvidence-directory>
```

No workflow, paid cloud run, release, push or predecessor branch is involved.
