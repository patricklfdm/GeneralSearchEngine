# Phase 3 — complete ordinary proposer installation forces

The [ballot audit](PHASE_3_SAME_VIEW_BALLOT.md) also reproduced a second gap:
removing the first node 1 `INSTALL_IMAGE_FORCED` callback still passed the previous
composed reader. Its remote INSTALL_ACK and final joining recovery checks were
complete, but ordinary proposer-local installations lacked the corresponding
force interval. The original workload and its storage bytes remain unchanged.

## Shared reader correction

`joining_network_evidence.installations` now checks every ordinary selected
proposer as well as every remote installer. The independent physical prerequisite
must derive the complete installed snapshot before its member inventory is used
to determine the required image/member force multiplicities.

The proposer must finish forcing its SELECTED record before sending it. Every
selected remote peer must return its original delivered INSTALL_ACK before local
installation starts. The local reservation, manifest, each image/member,
generation, selector, rename, parent force, current-generation reseal and return
must occur exactly once in order, within the original owner scope. Installation
must finish before the first slot's ACCEPT validation. Missing, duplicate, foreign
or reordered callbacks cannot stand in for this sequence.

The final same-view recovery retains its separate cold-reopen boundary because
it does not start another slot. Ordinary installations use the actual profile's
joining identity and snapshot path. The shared change applies to the existing
ADD and REPLACE readers; it does not silently admit an additional profile.

The retained REPLACE original has six ordinary proposer installations, seven
remote installation replies and one final joining-proposer recovery. These
counts are observations of this original, not new protocol limits.

## Qualification and remaining boundaries

The same-view network qualification adds eleven exact observation negatives for
the new proposer boundary. Its existing transport, remote installation, final
recovery and terminal-attempt negatives remain enabled. The untouched original
must pass first; mutations cannot change physical storage or directory members.
A preceding unrelated failure cannot satisfy an expected rejection.

Eight focused regressions cover all selected peers' delivery, complete member
force counts, selector/parent/current ordering, owner scope and the first-slot
boundary. All five conditional ADD/REPLACE profile fixtures now retain complete
local installation and delivered ACK events. They are unit fixtures, not native
profile executions. The retained complete ADD history is checked separately as
a historical compatibility observation.

The [batch receipt](phase3-evidence/proposer-installation.json) binds frozen
source, full composed replay, the full network negative matrix, Python tests,
historical ADD replay and archive portability. The original audit failures and
development diagnostics remain retained. No native workload is rerun.

Frozen-source results: 541 joining Python tests passed; all 51 network negatives
were rejected with their exact reasons in 253.185 seconds. The full REPLACE
composition passed in 52.398 seconds, and the historical ADD network/physical
replay passed in 23.051 seconds with six ordinary proposer installations and
eight remote installation replies. This historical ADD result is not a new
current-source native profile execution.

The 19,572,118-byte archive preserves 8,703 files and 1,206 directories, all
verified after extraction. The extracted frozen reader replayed the full
REPLACE composition with Python assertions disabled (`-O -B`) in 51.900 seconds;
the result exactly matched, and source/input inventories were unchanged.

This closes the two specifically reproduced force gaps when composed with the
ballot reader. It does not establish exhaustive callback coverage or replace
current-source profile, whole-history fault/process and frozen acceptance gates.
Full physical/network/process and Phase 3 completion flags remain false. No Java,
POM, workflow, resource/timing or paid-cloud behavior changes.
