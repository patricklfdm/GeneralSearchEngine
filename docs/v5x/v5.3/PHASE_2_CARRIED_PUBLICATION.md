# Carried original vote through new-round publication

Status: private storage integration; Phase 2 remains **OPEN**. A selected first
entry may originate in an earlier ballot. Its ENTRY and payload stay unchanged
while the new ballot obtains its own ACCEPT, PROOF and certificate. This batch
connects that rule to actual local installation, application and maintenance.

## Retained authority and bounded completion

Installing a selected generation at the same published parent can leave a local
pending vote from the former round. That vote still requires its exact original
selector, generation, PROMISE, SELECTED and round coverage. Reopen verifies those
retained bytes, the identical parent and the strictly newer installed ballot.
It cannot borrow the new generation's authority. The old generation remains
pinned until exact reacceptance replaces the old local vote; missing or changed
original coverage is refused without repair.

An applying owner already reserves the future publication image before accepting
a vote. Selected installation transfers that reservation to its inactive image
instead of counting a second future image. The former active generation then
owns that slot until authorized retirement.

At this point two generations, two original sources and three unused application
buffers fill the seven-image ceiling. Governing-floor copies and a retirement
backup must also fit before deleting the old generation. Maintenance therefore
releases only **empty** replay input/output and applied-end reservations. Actual
application files continue to pin their references and prevent this transfer.
The durable floor identifies this maintenance state on reopen. New acceptance or
application must reacquire all completion reservations; failed admission returns
newly acquired empty reservations so it cannot starve retirement. Floor release
restores application completion capacity. No resource ceiling or durable format
is enlarged.

## Qualification

The [local source/build index](phase2-evidence/carried-publication.json) records
the complete commands, hashes, development failures and raw evidence locations.

The three-owner integration covers one, two and three holders of the actual old
vote. A fresh selected set carries its original DATA entry, installs at the old
published parent, reaccepts under the new ballot, reclaims obsolete copies,
publishes the DATA and continues with a BARRIER in the same new round. Repeated
calls preserve original results. The core backup decoder checks the inserted
document occurs once. Fresh PREPARE captures the advanced cut with no resurrected
tail; duplicate old PREPARE still returns its original frozen BASIS.

Focused injected-I/O tests interrupt installation and interrupt reopen again,
refuse premature old-generation retirement, and interrupt floor publication,
retirement and floor release. Capacity rejection must preserve both the physical
inventory and resource usage. Reopen must release every lease on failure and
finish maintenance from its original authority. These tests are same-JVM fault
injections, not process-death or power-loss evidence.

The independent Python replay validates originals before mutation, derives the
exact old/new grants, sources, selected generation, pending vote, phased records,
applied ends, catalogs, ACKs and both published generations, and compares complete
physical inventories. Ten negative variants cover lost or substituted original
votes, payloads, sources, decisions, old coverage, new acceptance, applied ACKs,
first-round proof, premature clearing and resurrected tails. Portable replay and
Python optimized-mode checks remain separate. This byte oracle does not infer
force ordering or independently decode the core application image.

Initial failures demonstrated double-counted installation capacity, lost access
to original round coverage on reopen, and insufficient maintenance headroom when
unused application buffers remained reserved. Those failures remain retained;
the correction does not suppress rejection or retry a different selected entry.
A later test-driver failure also remains retained: recovery attempted floor
establishment during a pending retirement. The driver now resumes the saved
retirement and tests capacity rollback only at the two full-floor checkpoints,
requiring the exact capacity rejection reason.

## Remaining boundaries

Historical bootstrap observations remain conditional. [Dedicated halt/SIGKILL qualification](PHASE_2_CARRIED_PROCESS.md) now covers
this carried-vote maintenance path with repeated interruptions. Maximal
image/metadata lifetime, staged application after a higher promise, membership
boundaries and complete offline provisioning remain open.
No distributed activation, public runtime, protected CI or cloud qualification
is claimed by this local storage gate.
