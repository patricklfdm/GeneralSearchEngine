# Phase 2 — configuration-aware storage

Status: **OPEN**, local development only. Phase 1 is locally closed; its conditional
context/capsule/selection helpers do not provide durable ownership observations.
The public membership factory remains disabled throughout this storage entry batch.

## Batches and dependencies

| Batch | Work and exit condition |
| --- | --- |
| 2A — locally complete | Private exclusive owner and separately forced ballot counter; exact pre-provisioned root/node binding; fresh-process lock, halt/SIGKILL and restart evidence |
| 2B1 — locally complete | [Root-wide promise and original basis frames](PHASE_2_GRANT_JOURNAL.md); exact duplicate response, incomplete-grant refusal and concurrent observation fencing; physical source retention still pending |
| 2B2a — locally complete | [Original source retention](PHASE_2_BASIS_SOURCES.md): packet/image force before BASIS, exact original replay/reopen and bounded reservations; no source reclamation |
| 2B2b — locally complete for capture | [Current local generation](PHASE_2_CURRENT_GENERATION.md): derive grant parent/tail/images from exact selected disk authority under the journal owner; immutable generation only, remote historical ownership remains conditional |
| 2C1 — locally complete for decision persistence | [Durable SELECTED](PHASE_2_DURABLE_SELECTION.md) under the journal owner, physical original local source and exact same-ballot replay; no installation ACK |
| 2C2 — locally complete for selected install | [Selected local generation installation](PHASE_2_GENERATION_INSTALL.md): exact original decision, carried tail, ancestry, shared reservation and forced selector with interrupted recovery; remote historical ownership remains conditional |
| 2C3–2C4 | Cross-view adoption and source lifetimes, ACCEPT/PROOF/certificate persistence, complete application/catalog generation, floor/retirement recovery and bounded journal rotation |
| 2D | Complete offline provisioning/open, legacy rejection and configuration-aware storage qualification; real ownership observations replace synthetic inputs; physical S/N coverage and closure audit |

The [2A storage foundation](PHASE_2_STORAGE_FOUNDATION.md) qualifies an isolated
component. Its exact six-name directory inventory must be incorporated into the
complete storage authority layout in later batches. It cannot open a legacy
replica directory or one containing future unrecognized records. The test producer
does not implement the public empty/backup bootstrap contract.

Before Phase 2 closure, all complete-store recovery rules must account for missing,
truncated, corrupt and stale authority, directory/selector replacement, capacity
headroom and interruption during recovery itself. Retaining ambiguous bytes and
rejecting an isolated allocator open is safe, but is not a substitute for the
complete generation/floor recovery and operational repair contract.

## Boundaries

- No 1.1/1.2 format, fixed-three runtime, API inventory, resource limit or workflow
  change is implied. Ballot identity includes proposer and durable storage UUID;
  the 2A component only allocates the counter from verified local identity.
- The later storage/protocol owner must supply every observed bound, establish
  voter eligibility and integrate current promise/selection. A high counter alone
  never authorizes voting, reads or service readiness.
- Fresh-process tests establish behavior under halt/SIGKILL on the tested local
  filesystem. They do not emulate power loss or prove all disk/network schedules.
- Keep all V5.3 work and intermediate commits local. V5.2 experiment, release and
  eventual predecessor integration remain separate, as specified in the
  [development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).

Phase 3 will connect storage to actual activation and transitions. Phase 4 public
operations and later unified acceptance remain required; no Phase 2 batch alone
turns the current physical S/N inventory from PLANNED into an accepted runtime.

2B2b separates immutable capture from the installation transaction originally
listed in that row. Installation serialization belongs with 2C's selector/adoption
recovery: the current entry exposes no installation API and refuses inactive or
selected-installation generations. This sequencing does not waive any storage
closure requirement or establish remote historical ownership.

The [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) tracks the complete remaining
storage obligations while local batches continue. Component PASS results cannot
close the phase without the integrated recovery, resource and physical audit.
