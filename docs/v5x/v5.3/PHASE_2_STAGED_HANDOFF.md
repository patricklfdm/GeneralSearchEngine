# Fenced application staging handoff

Status: private implementation; local qualification is recorded below. Phase 2
remains **OPEN**.
The public membership runtime remains disabled.

## Recovery authority

An actual certificate may leave replay scratch or an applied end before a higher
PROMISE fences its application and publication. Reopening must preserve this
fence. A strictly newer installed SELECTED may choose the exact original ENTRY
and payload at the same published parent. In that case the private journal owner
can explicitly retire derived old application work before reaccepting the entry
in the new round. The old vote, generation, source, certificate and ENTRY origin
remain intact until their existing separate retirement rules authorize removal.

Admission checks the original inactive generation and coverage; the current
forced selector, generation, PROMISE, BASIS and SELECTED; and the local new-round
frozen source containing every old ACCEPT/PROOF/certificate byte. The current
selected generation must retain the exact carried entry and payload. The source
check is necessary even when the selected generation did not copy the old proof
and certificate. A different entry, parent, authority, owner or missing original
cannot authorize cleanup.

Typed replay reconstructs the old plan using its own selected source set, round
coverage and ancestry, plus still-retained source/floor endpoints. It does not
issue an old checkpoint ACK. Existing staged members must be legal exact prefixes
of this plan, including the original ACK ordering constraints.

## Private retirement transaction

The applied-end directory retains a bounded private GSAT 1.3 transaction. Its
candidate is written and forced, then atomically promoted to an active manifest
and its parent forced before deletion. The active manifest binds the authority,
expected plan and original file inventory. Partial candidate recovery reconstructs
the exact unchanged request; a truncated or corrupt active manifest is rejected.
This private format adds no frozen record or wire kind.

Remaining members must match their recorded bytes and known paths. Removal keeps
the plan until the other members are gone, then deletes the retirement manifest
and directory last, forcing the relevant parents. Ordinary authority mutations
are refused while either retirement file exists. Another new campaign also waits
until the old vote has been reaccepted under the current selection, including the
interval after staging disappears. Exact already-forced PREPARE replay remains
read-only; identical completed installation can be replayed before a retirement
marker exists, after revalidating the complete original plan. Every step retains the exclusive
owner and exact installed PROMISE/BASIS/SELECTED, pending vote and selector. A
later volatile observation fences acknowledgements, but does not revoke permission
to finish this same derived-work cleanup. The observation is neither lowered nor
persisted as a substitute PROMISE; no old ACK is produced. Reopen still requires
the exact original transaction and all retained authority bytes.

The marker uses additional reserved metadata within the existing JOURNAL ceiling.
No extra application image is copied and the seven-image ceiling is unchanged.
Only after cleanup may the new round reaccept, maintain its bounded storage,
reprove, apply and publish the original logical entry.

## Qualification boundary

Qualification must cover real three-owner certificates, partial scratch/end/ACK
states, exact refusal and retained originals, repeated interruption of retirement,
and completion under the newer round with actual typed application semantics.
Fresh-process physical replay, full-size lifetime, configuration boundaries and
offline provisioning remain separate Phase 2 closure obligations. Local injected
I/O failures alone do not establish process-death or power-loss durability.

Cleanup now completes under later volatile observations, while voting remains
fenced. This alone does not establish another campaign or full lifetime progress; retaining an
independent original pending context through another generation/source turnover
requires separate storage work. Reopening a cleanup owner does not restore an old
leader callback, public readiness or permission to forget a durable promise.

## Local validation

The final targeted reactor passes **70 Java tests**, with zero failures/errors.
The gate and source/build hashes are indexed in
[the retained evidence record](phase2-evidence/staged-handoff.json). Its new
integration methods cover actual three-owner old certification, new selection,
retirement, reacceptance, bounded maintenance, typed publication and a subsequent
slot; a proof-only selected source with a separately retained local certificate;
nine initial scratch/end cuts; repeated retirement failures; missing original
observations; and later volatile fencing at four cleanup boundaries. The marker
component separately covers fourteen cuts, torn candidates, corrupt active
manifests, authority/member drift and competing transactions.

Independent Python replay reconstructs all three owners across ten retained
stages before attempting fifteen evidence mutations. Every mutation must reject.
Normal and optimized Python modes must agree, and relocation must preserve the
result. Additional directory-inventory checks reject extra owners and symbolic
links. Typed core semantics remain a Java check; Python hash/inventory validation
does not independently establish those semantics or resource-allocation peaks.

```bash
# Read the v53StagedHandoffEvidence path from the completed Java gate.
python3 -m scripts.v53.staged_handoff_evidence <retained-staged-handoff-directory>
python3 -O -m scripts.v53.staged_handoff_evidence <retained-staged-handoff-directory>
```

Raw evidence stays under
`general-search-engine-replication/target/v53-staged-handoff/`; logs, compiled
source snapshots and independent replay results stay under
`target/v53-staged-handoff/`. Development failures are retained with their original
source snapshots. No protected CI or paid cloud execution is claimed.

## Later-observation cleanup qualification

The local owner can now finish derived staging retirement after observing a
strictly later ballot, including observations during marker write, force and
deletion. Every force/deletion still checks the exclusive owner, original vote,
current selector and exact installed PROMISE, BASIS and SELECTED. None of these
checks is replaced by the volatile observation. A same-byte original-inode
substitution stops before member deletion.

[The additional evidence index](phase2-evidence/fenced-staging.json) records
**56 passing Java tests**, including four new integration methods and the existing
grant/adoption fencing regressions. Three new positive recovery tests fail on
the earlier implementation. Seven retained boundary cases cover observation
before/during cleanup; separate tests cover two interrupted attempts followed by
recovery, and cleanup followed by exact context retention/redundant withdrawal.
Every case keeps the original certificate, vote, journal, sources and generations.
Old ACCEPT and exact old PREPARE remain rejected after cleanup.

Independent replay verifies both original generations, grant groups, certified
source, original derived end, unchanged protected files and force/delete order
before eleven exact-reason negative mutations. Normal/optimized Python and a
relocated replay must agree. These are local callbacks and injected IOException
tests; fresh-process staging qualification and transferred-context lifetime remain
open. Image semantics are executed by Java, not independently proven by Python.

```bash
python3 -m scripts.v53.fenced_staging_evidence <v53FencedStagingEvidence-directory>
python3 -O -m scripts.v53.fenced_staging_evidence <v53FencedStagingEvidence-directory>
```
