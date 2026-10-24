# Context-backed predecessor source retirement

Phase 2 remains **OPEN**. This local storage batch connects one previously blocked
reclamation step after context-backed original-generation retirement. Online
membership, later campaigns and full transferred lifetime are not enabled here.

## Authority and resource boundary

A pending vote normally pins its original PROMISE/BASIS source. Once the original
generation has retired under a complete governing floor, the exact original vote
and generation can instead be reconstructed from `pending.context` plus its
separately retained backing source. The owner now permits retirement of that exact
predecessor source, using the existing retirement record, exact file inventory,
forced journal rotation and deletion recovery.

The prerequisite checks remain mandatory: complete context, exact installed
PROMISE/BASIS/SELECTED, original entry/vote bytes, separate backing source, complete
governing floor and retired old generation. The backing source cannot use this
permission to retire itself. Other context-gated authority mutations remain gated.
A higher volatile observation does not authorize an old voting acknowledgement.

The actual owner fixture drops from six APPLICATION reservations to five without
changing the seven-image limit. This establishes available headroom; it does not
by itself establish successful reacceptance, application or later campaigning.

## Local verification

`V53ContextSourceReleaseTest` uses an actual context/floor/retirement owner. It
checks clean deletion and reopen, fourteen first IOException cut points followed
by a second interruption during context-source resealing, corrupt/missing authority
refusals, backing-source protection, higher-observation refusal and an external
JVM ownership probe. All snapshots are copied after the owner closes; live lock
files are never reopened to collect evidence.

The independent `scripts.v53.context_source_release_evidence` validator first
replays the complete original retirement. It derives the predecessor and backing
from physical grant/context bytes, derives the exact retirement authority and
journal suffix, and compares all retained bytes/directories to the existing
source-retirement transaction model. Each first/second/final snapshot and force
prefix is checked. Twenty-three evidence mutations across clean and interrupted
profiles must fail for their exact reasons; normal Python, `-O` and relocated
replay must agree.

This batch uses injected exceptions, not fresh-process crash qualification. The
underlying source-retirement and context components have separate process tests;
those do not substitute for a new combined process-death qualification. Historical
bootstrap and remote observation fixtures remain conditional; locally retained
backing ownership is exercised directly. See the [receipt index](phase2-evidence/context-source-release.json).
