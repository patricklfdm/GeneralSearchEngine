# Selected installation while retaining the original voting context

Phase 2 remains **OPEN**. This extends [protected selection](PHASE_2_CONTEXT_SELECTION.md)
through one later installation, intermediate-generation retirement and exact
successor acceptance. It preserves the original pending context and governing
floor until the successor is forced.

## Generation identity and recovery

Generation slots `a` and `b` are reusable locations. The old selector's manifest
identity, not its slot name alone, identifies the original generation. A retained
context can therefore describe generation 20 after generation 22 reuses its slot,
while generation 21 remains in the other slot.

The owner verifies the exact reconstructed original vote, current parent and
carried ENTRY, backing grant and current installed ballot. A complete governing
floor must retain the same original parent and owned tail, with its ballot after
the original vote and no later than the installed decision. An intermediate
generation must additionally pass the normal full retirement plan: exact current
selector, floor ancestry, complete inventory and preservation of above-floor tail
bytes. Reused slots do not authorize deleting unrelated generations.

An unfinished selected installation admits only bounded retained state for
reopening and re-sealing the old context. It does not reconstruct missing remote
sources or finish a selector automatically. Explicit installation must supply the
original selected sources and images; every existing candidate/selector prefix
must match the exact verified plan before writing. Other context maintenance and
new voting remain blocked while installation is pending. A retry after a completed
selector validates the original plan and returns the existing local receipt.

## Qualification scope

The local [source/build-bound evidence](phase2-evidence/context-installation.json)
records actual sources from three local owners. They install ballot 22 while
retaining vote 20 and floor 21, retire generation 21, then force the exact ballot
22 successor and release obsolete context/floor copies. It does not claim a
network installation acknowledgement.

Focused checks cover the installation and intermediate-retirement force boundaries,
another interruption during context re-sealing, exact duplicates, changed material,
lost/corrupt floor and candidate bytes, higher-observation fencing and unchanged
refused state. Independent replay derives selected material, generation/selector
bytes, old-vote preservation, retirement inventories and the new vote. It also
checks explicit response ordering and original-first evidence mutations.

The frozen seven-image limit remains unchanged, including empty completion
reservations. This gate uses small actual payloads and a conditional historical
bootstrap fixture. Exception interruptions are separate from fresh-process and
power-loss claims. [Repeated installation/reclamation](PHASE_2_CONTEXT_INSTALLATION_LIFETIME.md)
subsequently covers six later rounds and completion reservations with small images;
maximal coordinated lifetime still needs qualification.
This path currently requires the materialized tail's original ACCEPT digest to
match the retained context, not merely the ENTRY. Mixed higher-ballot acceptances
of the same entry require separate context-backed retirement qualification.
[Small-image publication after repeated installations](PHASE_2_CONTEXT_INSTALLED_PUBLICATION.md)
now has local composition evidence. Maximal old/joint/new lifetimes, public
runtime and Phase 2 closure remain open.

[Dedicated process recovery](PHASE_2_CONTEXT_GENERATION_PROCESS.md) adds 84 twice-interrupted cases across installation and intermediate retirement. It retains the small-image and conditional-bootstrap limits above.
