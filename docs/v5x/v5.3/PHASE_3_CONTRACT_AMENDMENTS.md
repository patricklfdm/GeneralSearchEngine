# V5.3 Phase 3 contract amendments

## A04 — explicit current-target retention intent and acknowledgement

V5.3 remains unpublished. The original Phase 0/1 catalog had 24 storage and 21
wire kinds (45 syntax fixtures). Phase 3 adds two **internal** wire kinds to the
same unpublished minor version 3: `RETENTION_INTENT` (22) and `RETENTION_ACK` (23).
The original 45 fixture frames, existing schemas and all resource ceilings remain
unchanged. Earlier source-bound closure receipts retain their original catalog
and counts; this amendment does not reissue those historical results.

The missing contract is durability of a peer's possible endpoints before its
installation is dispatched. STATUS, HEARTBEAT, source transfer completion and
transport success cannot acknowledge this action. The dedicated request uses the
existing exact root, view, permanent sender/recipient, ballot, trace and sequence
envelope. Its payload binds the original installed SELECTED digest, permanent
target identity and exact lower/upper cut/catalog/application anchors. Both new
frames retain a 32 KiB maximum; neither introduces a storage kind or increases
the existing JOURNAL, CONTROL, staging or two-endpoint-per-peer bounds.

The logical intent hash covers the canonical payload, allowing different current
voters to acknowledge the same intent with their own correlated envelopes. It is
not a signature or an installation certificate. Each voter independently checks
the installed selection and promise, current ballot fence and authenticated
current target, then conservatively merges under the native storage lock. It
cannot remove an older local possibility based on a received claim. A complete
real-copy observation may already have narrowed that voter's knowledge; a late
duplicate must not regress it. A third unresolved endpoint refuses.

The ACK binds that logical hash and the receiver's exact durable ledger revision
and digest. The request does not bind a global ledger revision: different voters
legitimately hold different conservative knowledge, and unrelated peer updates
must not change the identity of an otherwise identical intent. Lost-response
retry repeats the same frame up to the existing three-attempt maximum within
one original deadline. A fresh PREPARE observed before the reply fences it,
including when the ledger force has already completed.

The sender records locally and obtains distinct governing acknowledgements
(both majorities for a joint view) before returning an in-memory permit. The
permit rechecks the exact native owner, ballot, target and original deadline
before dispatch. A partial quorum, malformed reply, expired deadline or closed
owner cannot grant permission. The ledger is the durable state; the permit and
ACK set do not survive a new owner or election. New selection inherits original
forced snapshots through the previously qualified GSRP/GSRS paths.

### Deliberate scope boundary

This component handles a same-view target already authenticated as the current
generation at each acknowledging voter. It does **not** interpret an applied-end
candidate as an installed generation. Future-publication retention, autonomous
owner scheduling, cross-view pending contexts, learner eligibility and the full
offline-survivor continuation still require their real protocol paths. Current
network qualification exercises stable 3/4/5-voter groups; the joint-majority
predicate alone does not establish joint-transition runtime qualification.

Rollback before publication removes the two new messages and their internal
driver/endpoint methods, and restores the earlier catalog/fixture inventory.
It must not reinterpret a retention ACK as an existing protocol message. Existing
V5.0–V5.2 readers, public factories, workflow and release pins are unaffected.

## A05 — native future-target retention acknowledgements

The two new control kinds are FUTURE_RETENTION_INTENT (24) and
FUTURE_RETENTION_ACK (25), each at most 32 KiB including the unchanged 1.3 header.
All previous 47 record/wire fixtures, commands, resource limits and read-token
bytes remain exact. The syntax inventory is now 24 records plus 25 wire kinds.
This amendment does not claim completed quorum dispatch or public runtime.

A logical intent binds the installed SELECTED digest, original CERTIFICATE,
permanent intended recipient, original parent, prior possible recipient endpoint
and exact next applied target. Envelope root/view/ballot/proposer are checked
against the native owner. Every acknowledging voter uses its own forced native
applied result and original selector/application ACK; received hashes never
create application authority or substitute another voter's GSFT. An otherwise
correlated request before local native application returns NOT_READY without
writing any intent.

Before publication, the receiver records the target in its own existing GSFT
transaction. The prior endpoint must equal its single authenticated current
possibility. Different unresolved lower endpoints refuse before any write and
return CAPACITY_EXCEEDED and require later verified complete-copy reconciliation; no oldest/newest guess
replaces the two-endpoint limit. Incoming recording may name the receiver itself
as the intended target. The outgoing self-dispatch prohibition remains separate.

After exact certified publication, an identical request uses the existing
ordinary covered-target ledger transaction. The ACK discriminates FUTURE from
CURRENT and binds the logical intent plus the exact durable store digest and
revision. Existing real-copy narrowing is preserved. A different certificate,
selection, native target or unverified parent refuses. The original ballot is
checked after force and again immediately before acknowledgement; interrupted
ACK delivery never clears the durable intent.

The [native recording qualification](PHASE_3_FUTURE_QUORUM.md) now covers bounded
wire retries and governing-quorum accounting, original-first stable network
histories, receiver restart recovery and explicit complete-copy reconciliation.
The returned recording has no dispatch method. Required next work: actual dispatch
bound to the specific intended operation, native voter/application endpoint
integration, automatic reconciliation and the complete joint/runtime qualification.
Individual ACKs alone grant no send permission. This amendment is not a Phase 3
closure receipt. Rollback before publication removes the two new kinds and this
internal recording path, restoring the previous catalog without reinterpreting ACKs.

## A06 — exact remote publication acknowledgement

`PUBLISH_ACK` (26, at most 32 KiB) explicitly acknowledges the existing PUBLISH
certificate after the receiver has forced its complete selected publication and
finished covered application/retention cleanup. The payload binds original
certificate, SELECTED, full published cut/catalog/application and local generation
digest. It is neither an application ACK nor a quorum certificate, and cannot
narrow retained peer possibilities without a separate verified complete copy.
All earlier 49 fixtures remain exact; the inventory is 24 records and 26 wire kinds.

A future-recording quorum can dispatch only its own exact PUBLISH to its intended
permanent recipient. The native owner, original ballot, pending application and
local retained target are checked before each attempt and immediately before the
transport writes. Up to three identical I/O/deadline attempts share the original
budget. Closing, fencing, malformed acknowledgements and rejection do not grant
permission to retry a different operation. A higher rejection is observed locally.

The receiver scope is minted from actual completed native application. Original
checkpoint ACKs are obtained from their permanent owners, with both old/new
majorities where applicable; expected hashes never count as observations. Reverse
transfers remain available while publication waits. Duplicates share the one
bounded publication operation, then recheck its actual selector and ballot before
replying. A higher ballot after force prevents acknowledgement without undoing
publication. Local recording/dispatch scope does not survive a new owner.

This amendment opens implementation qualification; it is not whole Phase 3 or
joint-transition acceptance. Autonomous ownership, native incoming votes/application,
learner transitions and restart dispatch reconciliation remain required. Rollback
before release removes the new internal message and typed path together, restoring
the prior catalog without changing legacy wire/token formats or limits.

## A07 — original pending payload and phased-vote receipt transfers

The existing bounded `SOURCE_OFFER(kind=RECORD)` channel may carry the original
pending ENTRY payload or the canonical witness-hash preimage. RECORD already
carries bounded unframed ancestry metadata; this does not introduce a new wire or
disk kind. All 50 fixtures remain byte-identical. The payload is bounded by the
existing 8 MiB frame allowance; the canonical receipt is at most 2 KiB. BARRIER
uses its verified empty payload locally and never advertises a zero-length offer.

A receipt contains exactly root, permanent voter/storage identity, ACCEPT or
PROOF phase, and original record digest. Computing it is only a content reference.
The native owner serves it only from its actual complete active pending vote,
under the exact installed selection, current parent and unfenced original ballot.
Candidate files and copied capsule objects cannot attest a vote. A matching
original-owner transfer must complete before the receiver creates an observation;
fetching an ACCEPT or PROOF GSR record alone never suffices. Higher ballot,
selection/publication replacement, changed physical files, expiry or owner close
revoke the borrow. PROOF receipts require this owner's actual forced PROOF.

An incoming ACCEPT from the exact proposer pulls its original ACCEPT, ENTRY and
payload plus the proposer’s own ACCEPT receipt, validates the native journal
context, and forces the local vote before
ACK. An incoming PROOF requires this receiver's own ACCEPT and obtains every
named remote ACCEPT witness from that witness's permanent owner. The pre-existing
quorum rules validate both governing sets. No certificate or application is
created by a PROOF_ACK. The exact already-forced phase can be acknowledged after
reopen without recreating observations, forcing a different record, or applying it.

Transfers and the single bounded voting writer remain independent. Original
buffers stay reserved through their durable use; waiting controls use the existing
64-waiter budget. Identical active controls share completion. Source I/O/deadline
retries remain at most three attempts on the exact request and original deadline;
failed identical controls retain their failure within the scope. Corrupt data,
invalid context and changed authority do not authorize a different retry.
The owner must poll/close the finite scope; automatic lifecycle integration remains
open. Removing this unpublished path requires removing both receipt production
and consumption together; generic historical record transfer remains read-only.

The receipt lookup is SHA-256 of canonical `{schema: "gse-v53-vote-observation/1.3",
receipt: <receipt SHA-256>}`. SOURCE_OFFER and subsequent chunks/commit bind the
receipt SHA-256 itself. A plain receipt hash is not an attestation lookup, and a
normal payload selected by its own hash cannot satisfy the distinct receipt
digest. This separates evidence acquisition from ordinary content possession.

A carried original from a previous installed round is not a current vote receipt.
Native observation and duplicate ACK require the active vote's original ballot,
SELECTED and selector to match the current voting scope; the old original remains
retained for recovery until a separately validated successor replaces it.

## A08 — exact native certificate/application ingress

`APPLY` (27) and `APPLY_ACK` (28), each at most 32 KiB, are internal controls in
unpublished 1.3. All earlier 50 frames, commands, read-token bytes, storage kinds
and resource ceilings remain unchanged. The new syntax inventory is 24 storage
and 28 wire kinds. Historical source-bound receipts retain their earlier counts.

The request binds the original CERTIFICATE and installed SELECTED. Its envelope
must name the exact current proposer, permanent recipient, root, view and ballot.
The receiver must already own its actual current ACCEPT and PROOF; copied records
and carried prior-round votes cannot satisfy that requirement. On first certificate
admission it fetches the original certificate, validates both governing majorities,
and obtains each named ACCEPT and PROOF observation from that original voter.
Only then may it force its own certificate and perform native typed application.

The ACK binds certificate, SELECTED, actual checkpoint statement and the receiver's
own forced checkpoint acknowledgement. It does not publish the selector, authorize
future-target dispatch, prove another peer applied, or enable public service. Those
steps retain the existing future-recording and checkpoint-quorum requirements.
The same bounded writer owns vote/application requests while the independent
transfer service permits reverse original-owner pulls. Invalid input refuses
before certificate force; original deadlines, three identical source I/O attempts,
waiter/control accounting, fencing and close behavior remain in force.

After a lost reply, a live exact completed application can acknowledge without
reapplying. After restart, its own forced certificate permits idempotent native
application recovery without fresh historical observations; receiving the same
request is explicit, not an autonomous redispatch claim. A new selection or higher
ballot fences both work and acknowledgement. A prior slot's cached application
cannot answer a new slot's request. No complete Phase 3 gate closes here.

Rollback before publication removes these two internal message kinds and their
typed ingress together; no existing ACK is reinterpreted as an application ACK.

## A09 — nonvoting completion of an original FINAL

An original joint voter that is absent from the FINAL successor still owes an
exact local application result. It must not issue a successor CHECKPOINT_ACK.
The unpublished applied-end inventory now has two explicitly typed completions:
its existing endorsed form and a departing form containing only plan.json,
selector.gsr, certificate.gsr, catalog.gsr, statement.gsr and application.image.
The canonical plan binds every other file by ordered name, length and digest.
No new storage/wire record kind, acknowledgement sentinel or resource allowance
is introduced. Existing endorsed bytes and force ordering remain unchanged.

The departing form requires exact permanent identity registration, an original
FINAL from a joint parent that includes this node only on its old side, and the
immediate stable successor consisting of that parent's new set. Original entry,
certificate, statement, parent cut/catalog/application and successor hashes must
agree. The original owner must still authenticate the certificate and semantically
replay the application; this inventory's shape cannot establish that authority.
A learner, unrelated nonvoter, changed incarnation or already-removed stable node
cannot use the departing form. Eligible successor voters retain mandatory ACKs.

Every metadata/image file is forced, then the end and parent directories are
forced before a nonvoting completion returns. It creates no CHECKPOINT_ACK,
ancestor acknowledgement, observation or service readiness. Reopen validates exact
original prefixes and re-forces the same end; changed plans, unexpected ACKs,
missing/corrupt complete state, revoked ownership and changed inodes reject.
Derived staging retirement still requires exact covering authority and preserves
its original vote. The existing acknowledgement-only API continues to refuse a
departing identity before writes; the native journal has not switched APIs yet.

This is the storage prerequisite for the original departing-proposer/follower
failure. GSFT representation, native APPLY responses, successor checkpoint quorum,
published generation/reopen and runtime removal fencing must be integrated and
qualified separately before the full path is enabled. A component pass does not
close Phase 3. Before release, rollback removes this typed completion path and
its reader together; legacy formats and existing endorsed histories are unchanged.

## A10 — exact nonvoting future proof

The unpublished private GSFT 1.3 frame now discriminates three inventories:
empty (zero records), endorsed (the original ten records), and departing FINAL
(the same first nine records without ack.gsr). The existing framing, record
order, checksum, metadata, revision chaining and three-MiB maximum are unchanged.
The original empty and endorsed encodings remain byte-identical.

Nine records are accepted only for the exact A09 old-only FINAL owner, with its
permanent catalog identity, immediate joint-to-stable parent, original phases,
certificate, entry, statement and image identity. An eligible owner without its
ACK and a departing owner with an ACK both reject. This structural check never
creates a voting observation; native owners must still authenticate their own
original certificate and complete end before recording or dispatching a target.
The applied-end reader requires matching completion kind and an exact nonvoting
inventory when reopening that target. Unexpected ancestor ACKs remain forbidden.

Inherited GSFS references retain the original GSFT owner's identity, bytes and
digest; the capturing owner does not become the voter or original completer.
This batch qualifies the representation, inheritance and real applied-end
reopening under conditional historical authority. Native application/wire,
publication and removal fencing still require their own complete integration.
The unchanged stable native future/source/selected-proof regressions are listed
in the source-bound receipt. No successor checkpoint quorum or Phase 3 closure
is inferred from these component results.

Before release, rollback removes the nine-record reader/writer variant and its
independent reader together; it must not synthesize a tenth record for a retained
nonvoting proof. Previously produced nonvoting test evidence stays historical.

## A11 — nonvoting native application reply and FINAL publication

The internal APPLY_ACK payload keeps its exact certificate, selection and
statement fields. Its acknowledgement field is now a nullable hash in unpublished
1.3: eligible successor voters must return their actual forced CHECKPOINT_ACK;
only an exact A09 departing original owner returns null. The field is never
omitted, replaced with a sentinel digest or treated as a successor vote. The
native owner binds the reply to its actual typed completion. The sender derives
the expected recipient-specific result from the authenticated plan and permanent
identity, then compares the entire correlated payload; its expectation itself
is not an observed ACK. All 51 other record/wire fixtures, commands and read-token
bytes remain unchanged; the total stays 24 records and 28 wire kinds.

The native journal carries the typed completion into pending retention and
publication. An old-only FINAL owner exports its exact checkpoint statement but
no successor ACK. Publication on that node collects actual ACKs exclusively from
the new eligible set. All future-target recordings still require both original
joint majorities before the first publication send; the removed node's null
application reply cannot relax this requirement.

A published generation may retain the removed local owner only after its full
original selection coverage verifies and the terminal membership certificate
proves that owner's exact FINAL. Initial installation, unrelated nonvoters,
changed incarnations, later stable slots and a selection excluding the local
owner do not receive this exception. Reopening the exact final generation retains
known removal; it creates no next-round eligibility or readiness.

The [native qualification](phase3-evidence/native-departure-round.json) now covers
actual removed-proposer/follower TCP histories, independent physical replay and
the serialized transition regression on the same source. Fresh-process native
interruption and all-seven-profile closure remain open. Conditional generation
reopen tests do not substitute for those obligations. No full Phase 3 acceptance
is claimed.
Before release, rollback restores the original non-null APPLY_ACK schema together
with the journal, sender, publication and generation changes; do not reinterpret
a retained null acknowledgement as a vote.

## A12 — reservation-scoped first-contact ROOT discovery

Unpublished 1.3 now gives the existing ROOT-discovery permission a concrete
first-contact representation. A new node has only the operator-supplied root,
complete change request and permanent identity. It must not fabricate a local
voter generation to contact the group. The contact transport has no listener and
cannot adopt a voter catalog or send voting/service controls.

An initial CHUNK REQUEST uses the SHA-256 of canonical
`{schema:"gse-v53-learner-root-reference/1.3", root, learner, request}` as a lookup
alias. `learner` is the exact node/storage/host/port identity; `request` is the
complete existing root/number/expected/kind/target command object. This alias is
not an authority record, ROOT record hash, admission token or receipt. SOURCE_OFFER
returns the complete original ROOT frame hash and extent; subsequent CHUNK and
TRANSFER_COMMIT use the existing sequence, whole-file and chunk digest rules.
ROOT is bounded to its existing 16 KiB record maximum. No record/wire kind, schema
layout, frozen resource ceiling or HELLO.rootRecord meaning changes.

The serving exclusive native owner must have the matching current certified
pre-joint ADD/REPLACE reservation in RESERVED/PREPARING/READY/SEALED. The joining
identity must equal its permanently registered target and be outside the current
voters. Request view is the original expected configuration; the ballot-shaped
correlation is exactly counter 1, joining node and its storage UUID. This read path
never observes, allocates, promises, votes, installs or applies that correlation.
Unknown senders may only cause a lookup in the owner's independently verified
current catalog; received identity fields are never inserted into the directory.

ROOT borrowing shares the native owner's existing six-prefix-export registry,
small CONTROL accounting, original deadline and generation-replacement revocation.
It does not pin a new image or create an unbounded alternate export registry.
Every chunk checks the original live owner and generation. Session completion
keeps only the existing bounded exact-final-reply marker. Cancellation or changed
reservation cannot reopen the old export under the same trace. Client transport
retries are identical, limited to three or the stricter configured count, and
retain the original deadline. Protocol/capacity/closed failures do not retry.

The receiving node verifies full ROOT bytes, embedded root checksum, group and
history identities and resource contract. That result alone is not certified
learner admission. Complete live reservation/capsule, original generation and
ancestry acquisition, exact forced admission before directory creation, image
and readiness receipt, matching local INTENT before voting, all five ADD/REPLACE
profiles and full Phase 3 remain required. Public learner factories stay disabled.

The first-contact byte/link tests, actual native TCP, owner revocation and shared
export headroom have passed their local gates. The [qualification record](PHASE_3_LEARNER_ROOT.md)
separates those results from complete learner admission and joint voting.
Before release, rollback removes this alias route, contact-only constructor and
root client/export together. Existing ordinary peer transfer bytes are unchanged.

## A13 — complete reservation-scoped learner source acquisition

The unmaterialized learner may obtain a read-only STATUS hint using its existing
exact root/expected-view/identity correlation. This hint is only a location; it
cannot establish a certified reservation, new voter, promise or public readiness.

Complete source aliases use SHA-256 of canonical
`{schema:"gse-v53-learner-source-reference/1.3", root, learner, request, cut, scope}`,
where scope is prefix, ancestry or generation. Every field binds the original
request/identity and hinted cut. The serving native owner requires the exact
current pre-joint ADD/REPLACE reservation. The wrapper borrows the existing native
prefix exporter, six-export registry and original deadline; generation replacement
and cancellation invalidate unfinished exports. This adds no record/wire kind.

The source receiver begins with verified ROOT bytes and operator contact routes,
without a fabricated MembershipCapsule or voter owner. Its incoming source packet
uses the one-LEARNER slot, and application images retain their existing seven-image
budget. An identical lost exchange is retried at most three times under the same
original deadline; permanent failures stop immediately. Closing cancels pending
work and closes transport even when owned scratch cleanup refuses foreign bytes.

Only a completed original download can issue the existing private RetainedCopy
and GenerationCopy provenance. The full verified catalog must authenticate the
exact still-active request, joining identity, original expected configuration and
contacted current voter. Original manifest, all members, ancestry and coverage
are verified against the same source/cut/root/request/deadline. No historical
witness becomes a fresh ACCEPT/PROOF observation. No admission or voter directory,
readiness receipt, service read, or voting message is created by acquisition.

A subsequent separately qualified admission transaction must force the original
plan before directory creation. Typed materialization/readiness revision and
full matching INTENT-before-vote remain required. Rollback removes the scoped
export, read-only learner pull/transport/coordinator and reader together; ordinary
voter transfer encoding and storage remain unchanged.

## A14 — forced original learner admission plan

This unpublished additive companion format is `GSLP 1.3`, kind `1`, flags `0`,
with a 48-byte header and a complete maximum of 65,536 bytes. The header contains
magic/version/kind/flags/body length followed by SHA-256 of the first 16 header
bytes and canonical JSON body. It does not change any GSER/GSRP kind, old release
format, transport bound or public API declaration.

The exact `gse-v53-learner-plan/1.3` body has `schema`, original `root` frame,
`learner`, complete `request`, original `source` identity, `cut`, original
`generation` frame, complete ordered `files` inventory and two filesystem `paths`
bindings (operation, replica). Each file row has `path`, `size`, `sha256`; the
inventory includes the original generation frame itself. Embedded frames use
canonical Base64. Paths bind the existing real parent, file store and parent inode;
replica and operation paths are absent, normalized and disjoint at planning.
Receiving scratch must also be disjoint from both destinations.

The production planner requires the exact live source acquired under A13, checks
its certified pre-joint reservation and original inventory, and rechecks that
source throughout plan force. The operation directory owns `operation.lock`,
`learner.next.gslp` and eventually `learner.gslp`. Force the complete candidate,
force its directory, atomically rename, and force the active file and directory
before returning the reviewed summary. One bounded MISC lease accounts the plan;
no second LEARNER or application image copy is created by planning.

Resume takes the original reviewed summary and reads the original retained plan.
A complete candidate can be re-forced and renamed. Missing/partial original plan
bytes, foreign inventory, nonmatching redundant candidates, changed parent/inode,
links or an occupied replica path are preserved and refused. A valid candidate
cannot repair a corrupt active plan. Exact redundant candidate cleanup occurs only
after the active original has been re-forced. Closing releases the exclusive owner
and reservation; it never deletes the operation directory.

Decoding/resealing this plan establishes only original plan persistence. It is not
a fresh proof observation or a retained-source capability. The source's immutable
inventory is bound, but source bytes are not duplicated into this metadata plan;
subsequent learner admission must retain and validate the full original source
and typed image before publishing any readiness receipt. A later CANCEL or new
PREPARE revision must still be checked during preparation/joint eligibility.
No replica authority directory, allocator, local promise, voting record, readiness
receipt, public read or joint vote is created here. Complete nonvoting store,
revision/image/receipt and matching locally forced INTENT remain required.

## A15 — original nonvoting learner source retention

The unpublished additive `GSLP 1.3` companion adds kind `2`, flags `0`, maximum
262,144 bytes, using A14's 48-byte header/checksum. The exact canonical body has
`schema: gse-v53-learner-retention/1.3`, `plan` (the original A14 frame digest),
`staging` (the original five-field parent binding), `directoryKey` and ordered
`files`. Each row repeats the plan's exact `path`, `size`, `sha256` and adds the
original physical inode `key`. This changes no public API, GSER/GSRP encoding or
resource ceiling. It is an implementation contract, not a qualification claim.

While the original source owner is live, complete its received directory with
every original generation member. Grow the existing single LEARNER lease before
writing metadata, force every member and the directory, and verify the complete
original inventory. The source voter's PROMISE/SELECTED records remain that
source's historical records; they never become fresh learner votes. Existing
application-image reservations and inode handles transfer to the admission owner
without a second learner/image reservation or release/reacquire race.

The operation owner expands its existing MISC lease within the unchanged 2 MiB
ceiling to cover plan/candidate/retention/local admission metadata. Before writing
the retention candidate, detach receiver cleanup so an interrupted decision never
deletes its original source. Force `learner-source.next.gslp`, force its parent,
atomically rename to `learner-source.gslp`, and force the active decision and parent
before creating the nonvoting replica directory. An absent or incomplete decision
is preserved and refused; it cannot be recreated from caller parameters.

The replica owns `replica.lock`, original `root.gsr`, its joining `node.gsr`,
`learner/` and `learner-admission.gslp` (the exact retention decision). Move the
complete original staging directory atomically into `learner/`; force that
directory and both parents before forcing the admission marker last. There is
no cross-filesystem copy fallback. Original source inodes and hashes are pinned;
exact partial local root/node/admission metadata can be completed only from the
persisted original plan/decision. No allocator, local promise or voting journal
is created. The complete exclusive owner alone can authenticate the sealed
StoredCopy capability; the capability supplies no fresh vote observations.

Resume validates the original reviewed plan, decision, complete source and any
partial local metadata before resealing/removing redundant decision files. Exactly
one original source location must exist: staging or retained. Missing, duplicate,
linked, replaced or foreign originals are refused and preserved. While a move is
incomplete, its original staging parent must remain available for the directory
force. A completed original admission marker permits later removal of that parent;
if it still exists it must retain its original binding. Exclusive owners and
resource reservations are reacquired before completion; close preserves all data.

This is durable nonvoting storage only. The complete original reservation may
later be cancelled or superseded, and retained historical bytes do not establish
current eligibility. Typed application materialization, exact PREPARE revision,
readiness receipt and full matching locally forced INTENT must still precede any
joint vote. Public learner factories remain disabled. Rollback must refuse the
new retained companion rather than reinterpret it as a voter or delete it.

## A16 — typed learner backup and forced readiness record

The original nonvoting store may own one typed preparation sidecar at
`operationDirectory.resolveSibling(".gse-v53-learner-" + planDigest)`.
The exact parent/path binding and directory inode are retained. The sidecar is
disjoint from the operation, replica and live materialization directories and is
exclusively locked through an empty `preparation.lock`.

`preparation.json` and candidate `preparation.next.json` are canonical ASCII JSON,
each bounded to 256 KiB. Their exact fields are `schema` =
`gse-v53-learner-typed/1.3`, `plan` (original admission digest), `source` (original
packet digest), `receipt` (canonical base64 of the exact GSER LEARNER bytes),
`configuration` (`application` and `core` descriptors), `path`, `materialization`
(the existing five-field path bindings), and `directoryKey`. This is local private
metadata; no new GSER/GSRP family or public format is introduced.

Reserve one APPLICATION slot at the unchanged 64 MiB ceiling before writes, from
the parent store's existing resource owner. Force the plan candidate and parent,
atomically seal it and force the active plan and parent. `backup/` contains only
the three exact original core backup members. Force members and directories,
perform the actual typed semantic read and verify history, then force
`learner.gsr` and its parent last. Only the complete live owner exposes readiness
bytes; these bytes alone never grant local voting rights.

Resume requires the original directory, bindings and complete original plan or
candidate. Partial backup/receipt bytes are repairable only as exact prefixes of
that plan's originals, with semantic decoding repeated before receipt access.
Missing/partial plans, incompatible configuration and foreign/linked bytes are
preserved and refused. Closing the child releases its lock but retains the
parent's image reservation. Parent reopen conservatively reserves that image
before writes whenever the deterministic sidecar exists. Parent close closes the
child before releasing original sources and reservations; it preserves disk bytes.

The original MISC reservation remains 2 MiB. Its bounded metadata sum is 1,444 KiB,
as detailed in [typed learner preparation](PHASE_3_LEARNER_TYPED.md). Source/image
limits and frozen timing budgets are unchanged. This does not settle successor
PREPARE/revision replacement, cancellation retirement, locally forced matching
INTENT or joint activation. Rollback must refuse retained typed metadata rather
than reinterpret it as a voter or silently erase it.

## A17 — prepared learner generation selection and bounded refresh

After the A16 semantic decode and forced receipt, the live typed owner may select
its exact retained source as an immutable **nonvoting** local generation. Before
writing, reserve one of the existing two GENERATION slots while retaining the
original LEARNER byte/staging reservation. Pending claims count toward the limit;
they do not reserve duplicate bytes or release the receiving owner. Cancellation
or source close revokes an uncommitted claim.

Force canonical ASCII `prepared.json` (at most 16 KiB) in the existing typed
sidecar. Its exact fields are `schema` = `gse-v53-learner-prepared/1.3`, `root`,
`identity` (joining identity), `plan` (original admission digest), `typedPlan`
(digest of `preparation.json`), `source` (original packet digest), `receipt`
(digest of the GSER LEARNER frame), and `location` (original replica directory's
`learner` child). No source file moves or original inode changes. Only after file
and directory force may the original metadata lease atomically change from
LEARNER to GENERATION. Metadata bytes stay charged, while receiving staging and
the unique LEARNER count become available. There is no release/reacquire gap.

The marker requires a complete original typed receipt. A partial marker may be
completed only as the exact prefix of those original derived bytes. An altered
marker is refused unchanged. Reopening the parent conservatively accounts the
source as LEARNER until the typed owner repeats semantic verification and forces
selection again; a marker alone is not an in-memory capability. Closing either
the typed or parent owner revokes refresh access. Reopen can therefore refuse for
capacity before any selection, even when the preceding process had selected it.

The private refresh capability uses the parent's **same** resource pool and
checks live ownership around receiving. The complete successor must match the
root, original reservation, request and contacting voter, and retain the exact
original certified terminal anchor (or an authenticated checkpoint endpoint).
A higher index alone is insufficient. Receiving a new copy neither replaces the
original admission plan nor reuses initial admission to install a second store.
That installation, bounded old-source retirement, cancellation, matching locally
forced INTENT and joint eligibility remain subsequent lifecycle requirements.

The MISC maximum becomes 1,460 KiB (A16's 1,444 plus this 16 KiB marker), within the
unchanged 2 MiB lease. GENERATION, LEARNER, APPLICATION, aggregate byte bounds and
production timing limits stay unchanged. Rollback must refuse unknown selection
metadata, never reinterpret it as authority or delete the retained originals.
