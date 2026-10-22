# Phase 2C5d — actual journal application and checkpoint ACK

Status: **locally qualified for the original selected first slot**. The public
factory and complete Phase 2 remain OPEN. This batch connects the
[applied-end component](PHASE_2_APPLIED_END.md) to the actual exclusive journal
owner and actual persisted phased votes. It does not move the selected generation.

## Original authority and bounded staging

`openApplying` explicitly recognizes the two private staging directories. Older
open modes refuse them. `applyCurrent` takes its certificate, selector, selected
decision and promise from local storage, validates supplied original ACCEPT/PROOF
observations, and runs the existing typed core replay. Every storage cut rechecks
the owner, original bytes and observed ballot before issuing a local ACK. A higher
promise/observation or same-byte selector replacement cannot return that ACK.

The caller cannot supply an arbitrary projected application or no-op owner guard.
Ordinary DATA and INTENT/FINAL tests use real images. Three separate local owners
produce identical DATA ends; checkpoint assembly requires their actual forced ACKs.
Joint ends need both successor majorities; removed voters cannot endorse FINAL.
The original certificate and selector remain unchanged after a successful ACK.

Replay reserves two full 64 MiB application slots before creating scratch; the end
reserves a third. Metadata/claim/core operation markers are accounted within the
existing 32 MiB shared JOURNAL allowance, including completion space before ACCEPT.
No frozen count or byte ceiling increased. Partial scratch is charged on reopen.

The scratch claim binds exact selector/certificate/root/node/storage. Only bounded
known input/output members and the existing core writer's single staging/operation
pair can be removed. Every deletion checks the captured inode, length, digest and
inventory. Unknown files, links, changed claims and changed identities refuse while
preserving bytes. Successful replay removes derived files; sources, generations,
certificates and applied ends are never deleted by this helper.

A reproduced development defect released scratch reservations too early: later
PREPARE captures could consume the capacity needed to reopen an unresolved applied
certificate. The corrected journal retains those two reservations while the
certificate remains unresolved. The focused regression first fails at reopen on
the earlier implementation, then passes with bounded capture refusal and successful
reopen. Original failed logs, including the first test's exception-wrapper mistake,
remain available; they are not relabelled as successful executions.

## Validation and retained evidence

- Final targeted reactor: **66 Java tests PASS**, including eight actual
  journal application tests, six scratch tests and affected generation/resource/
  backpressure/version boundaries. Earlier broad storage execution: **77 PASS**
  before the final reservation correction; its source hashes are recorded separately.
- Actual journal: **22 halt/SIGKILL cases / 66 fresh JVMs**. Each case is interrupted
  again during recovery. Original selector/source/vote bytes remain exact, and the
  completed ACK binds the same new end. Initial provisioning is a private fixture.
- Scratch/core writer: **36 crash cases / 108 fresh JVMs**, including all seven
  actual core backup barriers used by application export. Every case is interrupted
  again during deletion/recovery and eventually removes only its disposable work.
- Independent Python replay validates the journal originals and supplied phased
  receipts against all three actual local stores, exact partial end bytes and ACK
  force ordering. **Seven original-first evidence mutations reject**; relocation
  and Python optimized mode produce the same result. Typed semantics are checked by
  the actual core Java reader/replay, not inferred from Python hashes.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53JournalApplicationTest,V53ReplayFilesTest,V53JournalBackpressureTest,V53CurrentGenerationTest,V53GenerationInstallTest,V53ResourceTransferTest,V53DeclarationsTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53JournalApplicationEvidence path printed by that test:
python3 -m scripts.v53.journal_application_evidence <retained-journal-process-directory>
```

[Source/build/log/raw-byte index](phase2-evidence/journal-application.json).
Local material is under `target/v53-replay-storage/`; fresh-process originals remain
under `general-search-engine-replication/target/v53-journal-application-process/`
and `general-search-engine-replication/target/v53-replay-process/`.

## Still required

Complete capsule/ancestry selector publication, covered-tail retirement and stable
same-round next slots remain pending. A fenced old staged end is preserved until
covering publication/retirement exists. Full-size coordinated source/image lifetime,
all-profile integrated physical coverage, public provisioning/runtime and protected
acceptance remain required. Local process crashes do not emulate power loss.
No POM, workflow, fixed-three production runtime or V5.2 cloud experiment changed.
