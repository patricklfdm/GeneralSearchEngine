# Phase 3B — owned selected-history reopening

Status: component locally qualified; exact results and inputs are retained in the
[source-bound receipt](phase3-evidence/owned-generation.json). This component restores complete
historical proof from the actual selected local generation without a caller-held
set of historical voter observations. Automatic adoption/election integration and
complete Phase 3 closure remain open.

## Exact local authority

`MembershipGrantJournal.readRetainedHistory` acquires the exclusive, bootstrap-bound
storage owner and replays the actual original grant journal. It reserves and checks
the retained BASIS files before reading the selected generation. Caller-supplied
PROMISE/BASIS/SELECTED collections cannot mint the internal history capability.
The capability is privately constructed and checks the exact live journal, immutable
identity, storage lock, selector, manifest, file identities, complete inventory,
packet and application bytes. It is invalidated before constructor return.

The complete capsule walk retains every original structural, identity, authority,
certificate and old/new majority check. Supplemental ancestry remains bounded to
six original bridges and 96 KiB. Original selection coverage also retains its exact
first and latest certificate/parent pairs; the complete selection/round validator
then checks them against the actual persisted PROMISE/SELECTED and final cut. A
hash in an unrelated inventory does not authorize another certificate or parent.

This follows the existing authentic-exclusive-replica/crash-fault assumption. It
adds no Byzantine tolerance or signatures. Historical copies never become new
`Owned` ACCEPT/PROOF observations, voting grants, installation ACKs or READY.
The raw capsule verifier still requires explicit observations. The network copy
path and its original deadlines and limits remain unchanged.

## Lifetime and scope

The returned read scope owns the journal lock and all selected/source reservations.
Every getter checks those owners and original bytes. Close, journal mutation or
selector/file replacement invalidates further reads. The constructor reseals only
already present original bytes; it neither creates a new generation nor selects,
repairs, truncates or retires history. Failure releases all acquired reservations
and the lock. Unknown, missing, linked or corrupt authority fails closed.

This is a selected-history reader, not the full automatic runtime open path.
Pending transaction completion, governing-floor and inactive-context historical
provenance, original-source continuation, typed incoming adoption and autonomous
fresh elections still require integration. It must not be used to bypass those
obligations or to infer that a read-only successful open admits new service.

## Qualification

Qualification uses public offline bootstrap followed by actual phased BARRIER and
DATA publication and existing maintenance. Fresh JVMs receive only the replica and
materialization paths; no fixture observations or serialized caller grant lists
are inputs. Original physical replay reconstructs publication, typed application
images and ancestry before checking each reader result and unchanged storage.
Halt/SIGKILL cuts during resealing retain their original snapshots and recovered
reader outputs. Process death does not establish power-loss durability.

Final qualification passes **49 Java tests across six suites**, **585 Python tests**
in both normal and optimized modes, **12 fresh-JVM readers** at stable sizes 3/4/5,
and **10 halt/SIGKILL resealing/reopen cuts**. Independent original-first replay
rejects **17 evidence mutations** and agrees in normal, optimized and portable
archive modes. The 43 related tests and six final reader tests run against identical
774 compiled production classes; the only final adapter correction changes test
output and its Python evidence reader. Earlier fixture/output failures remain in
the retained logs and are not counted as passing attempts.
No public API, byte format, resource limit, POM, workflow or paid experiment changes.
