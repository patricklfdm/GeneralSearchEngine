# Original joined-voter admission

Phase 3 remains **OPEN**. `MembershipLearnerJoinedAdmission` now forces the
joining proof under the actual completed [placement owner](PHASE_3_LEARNER_PLACEMENT.md).
It is the original admission input for the remaining covered-retirement and
journal takeover. No journal is opened, no predecessor is deleted and no vote
or public readiness is returned by this component.

## Binding and ownership

Require the complete placed generation and its live transferred custody. Match
its actual original typed LEARNER receipt to the original certified INTENT using
the same semantic check as INTENT retention. Require the same full request,
prepared revision, joining identity and sealed descriptor. The original INTENT
still uses old authority; the learner cannot supply its granting quorum.

Read the original selected typed plan and bind its materialization path and
configuration digest. Check the captured application's real descriptor against
that original configuration. Bind the installed generation, complete source,
local certificate-derived PROMISE and allocator. Preserve the original ROOT's
initial membership; a joining admission never fabricates bootstrap preparation,
seal or initial-member admission records.

The private canonical `gse-v53-joined-admission/1.3` record is `joined.json` in the
existing placement directory. It contains the exact original LEARNER, INTENT
ENTRY and CERTIFICATE bytes; sealed descriptor; root, identity and reviewed plan;
source/cut; generation/fence/allocator digests; configuration and materialization
binding; original custody and placement completion fingerprints; and its own
file identity. It is at most 64 KiB. The original directory now permits this
third record only after complete placement. No public byte or wire format changes.

Reserve this 64 KiB before staging, in the existing staged GENERATION. Fixed
companions are now 576 KiB (stage 128 + custody 256 + placement 128 + joined 64),
plus actual staged metadata. Existing GENERATION/metadata/image/staging ceilings
remain unchanged. Writing the admission consumes that reservation and does not
reserve another generation or release any learner charge.

Only the privately constructed joining capability can ask its exact placement
owner to write. Capacity and configuration checks precede creation. Recheck
original custody and the captured configuration around every cut. Bind the
created inode, preserve original prefixes, force the complete record and its
parent, and return the capability only after the final checked boundary. Old
learner closes remain harmless; closing placement revokes the joining capability.
A parsed record or arbitrary byte array cannot request this write or issue a vote.

## Recovery

Live continuation reuses the same file and its exact expected prefix. Cold
placement recovery first reopens the original typed/INTENT/stage owners as in
A40. Before any recovery force it reconstructs the joining record from those
actual originals and the captured configuration, then checks the retained prefix
and bound inode. Missing semantic originals, an altered complete record, a copied
complete inode or foreign configuration refuse without repair. Empty/partial
records grant no admission and still require full semantic recovery before any
completion writes.

Cold placement recovery alone returns no joined-admission capability. Explicit
admission continuation re-forces the exact original record and parent before
returning one. Read-only physical placement inspection still reports placement
only; its result cannot establish that joined admission was forced.

## Qualification and remaining work

`V53LearnerJoinedAdmissionTest` covers real typed preparation, TCP INTENT
retention, staging and original placement; exact record bindings; unchanged
accounting; independent JVM root-lock exclusion and stale closes; six live write/
force cuts with cold reopen; foreign configuration; copied complete records;
and corruption at the final force boundary. Historical quorum fixtures remain
conditional and exception cuts are not halt/SIGKILL evidence.

The source-bound [component receipt](phase3-evidence/joined-admission.json) records
actual executed checks and failures. Long native histories remain in the
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md). The implementation must
still durably retire covered learner predecessors, adopt the actual descriptor
and storage reservations into the native allocator/journal, initialize joined
retention, deliver old-majority INTENT before joint checkpointing, commit FINAL
and a fresh barrier, and qualify original-first physical/process histories.
