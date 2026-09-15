# V5.0 Phase 5 hardening entry plan

- **Status:** Accepted through protected PR #150 and exact-master CI
- **Branch:** `feat/v5.0-phase5-hardening`
- **Starting master:** `a67e654eff5e5aeb1571c1497f194c9c5de9c2b0`
- **Acceptance:** [PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150),
  `4a8fd3dfd9e398d712e896c9af511cf55f4cb16e`,
  [exact-master CI 34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066)
- **Phase 4 acceptance:** [PR #149](https://github.com/patricklfdm/GeneralSearchEngine/pull/149),
  [exact-master CI 34950041552](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34950041552)

## Deliverables

1. Exercise deterministic drop, duplicate, delay, reorder, disconnect and stale-message
   schedules against the production node/wire/storage path. Retain the exact fault
   plan, attempts and real responses; model-only schedules cannot substitute for this.
2. Verify bounded retry, peer/client queue admission, slow followers, malformed frames,
   incomplete/corrupt snapshot transfer and retained/staging-capacity rejection.
3. Harden close, interruption and cancellation: every accepted future resolves;
   queued work releases admission; storage ownership is retained while a writer can
   still mutate and is released after safe shutdown, including a retried close.
4. Repeat recovery, checkpoint and catch-up after faults, preserving all successful
   boundaries and valid proofs. Compare resulting application state with independent
   replay and the checksum-pinned published V4.4 control.
5. Add a real three-JVM hardening gate, deterministic replay checks and CI evidence
   retention while retaining Phase 1–4 gates and artifact/consumer compatibility.
6. Record Phase 4 protected acceptance and the exact remaining public-admission gap.

## Public admission gap

`ReplicatedSearchEngineBuilder.build()` and group bootstrap plan/apply are reserved.
The declared bootstrap input does not yet bind the full three-voter manifest, schema,
codec and genesis source authority required by the frozen contract. Completing that
workflow and public checkpoint/backup/close integration needs a concrete admission
plan and explicit API-contract review if signatures must change. This hardening
implementation does not fabricate bootstrap receipts or enable partial public construction.

Public-admission acceptance remains required before calling V5.0 complete or running
its end-user production/cloud admission lane. Performance, paid cloud, elections,
membership changes and release publication remain outside this phase.

The next [public-admission entry plan](PUBLIC_ADMISSION_ENTRY_PLAN.md) proposes the
complete contract, explicit API delta and genesis-version amendment before implementation.
