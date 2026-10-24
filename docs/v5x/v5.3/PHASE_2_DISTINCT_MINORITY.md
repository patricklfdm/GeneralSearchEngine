# Distinct minority ENTRY at the same published parent

Phase 2 remains **OPEN**. This extends
[admitted bootstrap publication](PHASE_2_BOOTSTRAP_PUBLICATION.md) with two
different real DATA entries. It does not use fabricated ownership, a fabricated
certificate or a caller-selected cleanup authority.

Each EMPTY / verified-backup group has 3, 4 or 5 admitted voters. All install
ballot 2 at the original published parent. The non-majority subset then accepts
`Doc(403, "minority-original")`. A disjoint majority captures and installs ballot
3 and accepts `Doc(404, "majority-selected")`; neither branch is given a synthetic
PROOF or certificate. At ballot 4 all voters offer their actual original sources.
Selection carries the second ENTRY because its ACCEPT ballot is higher. The
ENTRY's original ballot-3 origin and payload remain unchanged.

The old minority vote and its inactive generation remain intact after installation.
Premature generation retirement and another attempt to accept the losing ENTRY
both reject without changing authority files. All owners then force the exact
ballot-4 replacement vote, retire the inactive generation and obsolete prior
source under a governing floor, and actually prove, certify, apply and publish
the chosen DATA. The local frozen ballot-4 source still contains the losing
minority ENTRY/ACCEPT/payload. Only after the slot is published and a later ballot
captures that published prefix is that source retired under its later floor.
A subsequent BARRIER completes the chain.

The Java producer checks that each typed application contains the chosen document
exactly once and never contains the losing document, with the expected original
history and application sequence. It also checks duplicate responses, immutable
bootstrap records, settled reservations and no leaked leases. Across six profiles
this covers 24 admitted voters, 48 node publications and 768 subsequent node
snapshots. This is a stable-view storage sequence, not a distributed campaign or
public membership-runtime execution.

The independent Python model derives the original bootstrap authorities, each
per-voter source packet, the original minority/majority votes, highest-ACCEPT
selection, complete installed generations, preserved originals, replacement
votes, phased proof/certificate, application metadata, checkpoints and exact
retirement inventories. Only the original plan/image, fresh UUIDs and typed DATA
image bytes are observations. Required force-before-response events, exact
owner-call order, actual observation sets and typed image files are checked too.
The original must validate before any negative mutation can count. Normal,
optimized and relocated replay must agree.

The [retained evidence index](phase2-evidence/distinct-minority.json) records
the exact source/build inputs, raw snapshots, logs and qualification results.
No production Java, POM, workflow, frozen format or bound changes in this batch.
The producer's typed semantic check is distinct from the Python byte/catalog
check; reservation callback peaks do not establish maximal physical capacity.
This batch does not duplicate the original backup input files, as described in
the preceding bootstrap publication gate.

Still open: a pending minority vote whose parent is behind an already published
selected prefix; interrupted cleanup and fresh-process recovery for the distinct
ENTRY path; configuration-changing adoption; complete old/joint/new lifetime and
maximal byte/headroom qualification. The same-parent result must not be used to
claim those paths are implemented or qualified.
