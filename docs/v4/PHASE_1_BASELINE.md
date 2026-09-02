# V4.0 Phase 1 foundation baseline

## Boundary

Phase 1 begins from Phase 0 protected merge
`d5a32538f5eea5f419fe77d024171b4fbaabea20` (PR #77), whose exact-master CI run
`33563515761` passed. It changes all active development coordinates to
`4.0.0-SNAPSHOT`, pins published `3.4.0`, and establishes test infrastructure before
production persistence. No main-source durability type, WAL frame, checkpoint,
recovery implementation, or paid cloud workflow is present.

## Published compatibility input

The immediate baseline is Maven Central
`io.github.patricklfdm:general-search-engine:3.4.0`, SHA-256:

```text
e4dee61efacbff8d042b1ffda50f8b4ec1117b90689b55e621464f0c3a1c525f
```

The artifact-compat profile copies and verifies that exact JAR in an isolated Maven
repository and adds it as the eighth published Japicmp gate after V1, V2, V2.1, V3.0,
V3.1, V3.2, and V3.3. The three independent consumer projects compile against the
reactor `4.0.0-SNAPSHOT` artifact.

## Pre-change semantic controls

`V40Phase1FixtureTest` freezes the V3.4 in-memory mutation, internal-order tie break,
ranked query, and no-op removal behavior before durable production work.
`V40DurableHistoryOracle` is a test-only model with no production-engine dependency.
It owns canonical slots, `nextDocId`, supported index descriptors, atomic units, and
contiguous committed sequence replay. Its tests prove candidate failure consumes no
sequence, duplicate-ID bulk is atomic, successful missing removal consumes a sequence,
and replay rejects gaps.

The declaration-only V4 durable public fixture records the Phase 0 API shape while
`V40PublicApiFoundationTest` proves those types are not prematurely shipped in Phase 1.

## Local crash infrastructure

The executable scaffold includes:

- Python parent controller with bounded barrier acknowledgement;
- separate Java child JVM using `Runtime.halt(86)` or external OS kill;
- shutdown-hook marker proving graceful close did not run;
- independent Phase 1 storage inspector;
- separate recovery-verifier JVM;
- schema-versioned canonical evidence JSON and SHA-256 manifest; and
- validator rejection for tampering, unexpected members, symlinks, missing fields, and
  unauthorized production storage names.

Every bundle records a full lowercase source commit plus an explicit `clean` or
`dirty` source state. The validator rejects malformed or missing identity instead of
silently treating a dirty development run as release-quality evidence. Case,
configuration, submitted history, Future outcomes, process, inspection, recovery,
bounded logs, and verified cleanup are mandatory schema sections even while their
Phase 1 production-storage values are empty or explicitly not applicable.

The stable Phase 1 barrier is `phase1-scaffold-v1`. It deliberately produces no WAL or
checkpoint. Phase 2 replaces scaffold-only state with the first production boundaries
without changing the parent/child or artifact protocol.

## Fake cloud durable lane

The no-GCP control-plane model freezes suite
`v4.0-durable-single-node-suite-v1`, preset
`v4.0-durable-single-node-v1`, and experiment/canonical/failure-drill profiles. Its
ordered lifecycle separates writer VM, persistent disk, abrupt writer termination,
recovery VM attachment, verification, simulated upload, and verified cleanup. It
explicitly rejects an auto-deleted boot disk as machine-failure evidence and performs
no paid execution.

## Local commands

```bash
./mvnw -Dtest=V40DurableHistoryOracleTest,V40PublicApiFoundationTest,V40Phase1FixtureTest test
scripts/verify-v40-phase1-foundation.sh --skip-build
scripts/verify-version-alignment.sh 4.0.0-SNAPSHOT
```

The bounded fixture suite and both abrupt-termination modes pass locally. Experiment
and failure-drill fake-cloud profiles, independent validation, checksums, and cleanup
also pass. The full reactor, isolated published compatibility through exact `3.4.0`,
independent consumers, release artifact integrity, and two-build byte reproducibility
pass locally. Required PR and exact-master CI remain open acceptance gates.
