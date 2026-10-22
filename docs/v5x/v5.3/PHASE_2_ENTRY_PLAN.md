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
| 2B2b | Bind sampling to current owned generation/parent/tail authority and serialize generation installation with the journal; replace conditional caller ownership |
| 2C | Selected-source installation, ACCEPT/PROOF/certificate persistence and complete application/catalog generation; exact selector/floor recovery and bounded retention |
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
