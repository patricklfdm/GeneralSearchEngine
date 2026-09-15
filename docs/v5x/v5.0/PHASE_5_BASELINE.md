# V5.0 Phase 5 hardening baseline

- **Status:** Locally validated candidate; protected acceptance pending
- **Branch:** `feat/v5.0-phase5-hardening`
- **Coordinates:** `5.0.0-SNAPSHOT`
- **Starting master:** `a67e654eff5e5aeb1571c1497f194c9c5de9c2b0`
- **Phase 4 acceptance:** [PR #149](https://github.com/patricklfdm/GeneralSearchEngine/pull/149),
  [exact-master CI 34950041552](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34950041552)
- **Published V4.4 control SHA-256:** `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`

## Delivered boundary

Internal shutdown now permits cleanup retries after interruption or timeout, retains
storage ownership while the writer remains active, completes an in-progress authority
record before interrupting its writer, and handles concurrent/callback
close. Bounded queued tasks release their admission on rejection and shutdown, while
cancellation keeps accepted work admitted. Transport shutdown avoids sender self-waits
and drains peer queues. Invalid chunk envelopes reject before staging.

[The hardening design](PHASE_5_HARDENING.md) describes the production fault hooks,
independent wire-attempt validator, deterministic replay and 16 three-JVM cases.
[The checklist](PHASE_5_CHECKLIST.md) separates local evidence from protected acceptance.

## Validation

Final results use a clean release reactor and fresh Phase 1–5 process workspaces.
Toolchain: OpenJDK `21.0.12+8`, Maven `3.9.11`, Python `3.11.15`, Linux WSL2;
existing offline dependency caches. V4.4 semantic comparison pins artifact SHA-256
and verifies the actual loaded SearchEngine code source in a separate JVM.

The initial three regression tests failed on the Phase 4 close implementation:
interrupted close left READY/owned state, timed-out close could not finish ownership
release, and callback close waited for its own sender. All pass with the fixes;
the existing lifecycle/ownership tests remain intact. A further partial-proof-write
regression reproduced interruption inside a record; store quiescence now prevents it.

Final local results:

- clean release reactor: core 541 tests (4 skipped), replication 113 and processor 5;
  no failures or errors;
- all 89 existing replication tests retained, plus 14 network, 6 lifecycle and
  4 pressure hardening cases;
- full V5 Python suite: 66 tests pass, including 7 independent trace-validator cases;
- Phase 1 model, wire, separate-process and fake-cloud foundation: pass;
- Phase 2: 19 SIGKILL storage cases and 9 cross-language corruptions pass;
- Phase 3: 8 three-JVM TCP cases, including 7 SIGKILL publication barriers, pass;
- Phase 4: 17 three-JVM recovery cases and 6 cross-parser corruptions pass;
- Phase 5: 16 three-JVM hardening cases pass, including eight exact-process SIGKILLs,
  two identical serialized wire replays and a named ACK-loss plan repeated in a fresh group;
- all final histories preserve observed proofs and acknowledged boundaries; application
  state, sequence, document/query order and index lifecycle match independent replay
  and the checksum-pinned published V4.4 control;
- network transcripts validate exact wire bytes, retry bounds, correlations, executed
  faults and their owned JVM process identities;
- independent V1–V5 consumer projects and checksum-pinned published V1–V4.4 API
  comparison pass using retained offline caches;
- nine-JAR release integrity, production fixture exclusion, Python compilation,
  shell syntax, 486 local documentation links and diff whitespace pass;
- core/processor source, POMs, public signatures and prior storage/wire fixtures remain
  unchanged; and
- two clean release builds produce byte-identical nine-JAR output. Final artifacts
  retain those hashes after the clean release, consumer and compatibility checks;
  test workers, fault controllers and fixtures are excluded from production JARs.

Final generated evidence (not committed):

- `target/v50-foundation/run.zlgG6q/`
- `target/v50-storage/run.saaqtL/evidence/`
- `target/v50-leader/run.3Xdj7r/evidence/`
- `target/v50-recovery/run.x5DoNU/evidence/`
- `target/v50-hardening/run.fo2bt2/evidence/`

## Reproduction

```bash
MAVEN_ARGS=-Dgpg.skip=true scripts/verify-reproducible-build.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-v50-phase1-foundation.sh --skip-build
scripts/verify-v50-phase2-storage.sh --skip-build
scripts/verify-v50-phase3-leader.sh --skip-build
scripts/verify-v50-phase4-recovery.sh --skip-build
scripts/verify-v50-phase5-hardening.sh --skip-build
scripts/verify-consumer-projects.sh
./mvnw -Partifact-compat -DskipTests verify
scripts/verify-release-artifacts.sh 5.0.0-SNAPSHOT
```

Run reproducibility before collecting target evidence, since clean removes generated
workspaces. Network tests/process gates need loopback TCP permission. Maven supports
offline caches. Phase 4/5 gates resolve the published V4.4 control into `target/v50-control`
unless `GSE_V50_CONTROL_JAR` names an existing checksum-verified file.

CI retains `target/v50-hardening` including source status, exact process ownership,
wire attempts, fault plans, raw controls/events, minimized replay, crash markers,
pre-reopen storage, hashes, independent comparisons and failed cases. Local working-tree
runs are candidate evidence; protected PR and exact-master CI use their own source.

## Remaining admission

Public builder/bootstrap and complete checkpoint/backup/lifecycle integration remain
reserved. The [entry plan](PHASE_5_ENTRY_PLAN.md) explains the missing manifest/source
binding and any necessary explicit API-contract review. Complete this admission before
the end-user runtime/cloud lane; Phase 5 does not imply Phase 6 paid-run readiness.

Shutdown wait bounds do not force arbitrary synchronous user callbacks/codecs to
terminate. A writer termination timeout retains ownership and requires a later close
attempt or process exit. The process matrix is not kernel/device power-loss evidence.
No new performance, election, membership, hostile-network, paid-cloud, signed-release
or completed-V5 claim is made.
