# V5.1 Phase 1 entry candidate: independent foundation

**Status:** Phase 1 authorized by the user after PR #184 and exact-master CI 35487644896.
The [local foundation implementation](PHASE_1_FOUNDATION.md) awaits its own protected acceptance.
**Governing contract:** [Phase 0 contract](PHASE_0_CONTRACT.md).

## Entry and stop conditions

Start only after protected acceptance of the complete Phase 0 contract, successful
exact-master CI with its actual scope recorded, and the user's Phase 1 instruction.
An accepted planning-entry PR alone is not that contract acceptance. Re-read the
accepted source and reconcile this candidate with review changes before coding.

This plan permits declarations and independent foundations after that entry. It
does not permit production election, automatic bootstrap writers, transport handlers,
runtime admission, new-format store writers, paid experiments or publication.
Existing configured-mode runtime and its inherited regression gates stay enabled.

## One coherent foundation batch

1. Open all active Maven coordinates atomically as `5.1.0-SNAPSHOT`, preserving
   historic fixtures, published baselines and V5.0 canonical/release inventories.
   Pin exact published V5.0 replication/core artifacts and the inherited V4.4 truth
   control independently. Do not regenerate old compatibility expectations.
2. Add exactly the [proposed public inventory](API_FORMAT_AND_COMPATIBILITY.md#additive-public-surface),
   adjusted only by accepted review. Constructors/configuration validation may work;
   automatic build/start/bootstrap/runtime entry points reject before side effects
   until their later owning phases. Keep old descriptors/constants unmodified.
3. Freeze the complete automatic 1.2 byte and wire catalog: filenames, field order,
   JSON schemas, optional discriminants, domain hashes, receipts, frame IDs, bootstrap
   decisions, recovery generations and negative rejection classifications. Include
   all kinds/messages selected by Phase 0. This catalog and its independent fixtures
   are a Phase 2 prerequisite, not permission for Phase 1 production parsers/writers.
4. Implement a separate logical model and deterministic network scheduler. Run the
   bounded explorations and deliberate checker negatives from the
   [evidence contract](TESTING_AND_EVIDENCE.md). Preserve complete failing traces and
   state-space bounds. Do not share algorithms/decoders with production classes.
5. Add a separate-process worker/controller scaffold, stable cut commands, evidence
   inventories and abrupt-halt/external-kill recording. Its foundation qualification
   uses controlled fixtures/scaffold processes and is explicitly not automatic-runtime
   evidence. Crash points must be assigned before later production transitions land.
6. Add independently compiled public consumer source for the complete automatic
   lifecycle and inherited overload inventory. In this phase it proves declaration
   compatibility and fail-before-side-effect guards only. Runtime service restoration
   must wait for the public enablement gate.
7. Extend no-GCP planning with the new suite identities, concurrent voter topology,
   resource accounting, failure retention, cleanup authority and cost-envelope inputs.
   Run fake control-plane positives/negatives without cloud credentials/resources.
8. Wire one explicit foundation verifier into the existing CI structure. Preserve
   documentation classification and Required semantics; full-code changes must run
   existing configured-runtime, compatibility and packaging gates as well as the new
   foundation. Report skipped/non-production paths accurately.

Use a single reviewable foundation PR if practical; avoid one PR per declaration or
fixture. If an implementation detail contradicts a Phase 0 safety decision, stop
that path and submit the concrete counterexample for contract review rather than
silently choosing another protocol in code.

## Foundation acceptance inventory

| Deliverable | Required evidence |
| --- | --- |
| Version/compatibility | Exact coordinate alignment, old-to-new API inventory, published V1-V5.0 consumers and isolated V5.0 control identity |
| Public declarations | External compile/reflection checks for every new type; constructors and every disabled side-effecting entry classified |
| Byte/wire catalog | Independent encoder/decoder agreement, immutable checksummed positives, recomputed-checksum negatives, cross-mode/version rejection |
| Model/scheduler | I01-I08 checked, E01-E12 foundation mapping, exhaustive finite bounds/counts and reproducible seeded traces |
| Crash scaffold | Real separate PIDs, actual exit causes, stable barriers and pre-reopen file inventories; no fabricated force events |
| Consumer scaffold | All bootstrap/start/read/write/bulk/index/checkpoint/backup/close surfaces covered outside implementation packages |
| Fake cloud | Concurrent-topology plan, bounded lease/budget/retention, safe cleanup negatives; zero real cloud operations |
| CI/artifacts | Exact-source receipts and checksums, unchanged dependency direction, no internal workers/fixtures in shipped main/sources/Javadoc JARs |

The independent model has priority over optimizing the production design. If the
candidate selection/read rules fail a required counterexample, reopen D01/D03/D05
and keep Phase 2 closed. Passing a bounded model is still not a universal proof.

## Later ownership boundaries

Phase 2 implements reviewed durable promise/accept/proof/recovery storage with each
crash cut. Phase 3 implements election, activation, normal replication and retained-
disk rejoin. Phase 4 enables the complete public automatic lifecycle, strong-read
barriers, outcome reporting and backup/checkpoint paths through real three-JVM
consumers. Phase 5 combines faults and resource pressure. Phase 6 owns separately
authorized measurements/cloud evidence. Phases 7/8 own release qualification and
separately authorized publication. These later entries require their own review;
Phase 1 acceptance does not authorize them all at once.

No public-performance or cloud claim may precede complete public enablement. No
internal worker may stand in for unavailable automatic bootstrap or service-ready
operations. Preserve the user-owned commit/push/PR and manual cloud-trigger workflow.
