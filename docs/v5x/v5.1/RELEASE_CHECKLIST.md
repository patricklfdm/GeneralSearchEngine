# V5.1 release checklist

**Status:** preparation only. No final candidate hashes, signed V5.1 tag, Central
deployment or GitHub Release have been created by this batch. Stable remains 5.0.0.

## Before a tag

- [x] [Phase 6](PHASE_6_NATIVE_SET_ACCEPTANCE.md) accepted through PR #320 and
  exact-master CI `38457745089`, attempt 1, all 46 jobs.
- [ ] [Phase 7A](PHASE_7_CHECKLIST.md) consumer/API/documentation changes accepted.
- [ ] Phase 7B final `5.1.0` candidate accepted, with canonical toolchain, nine
  unsigned JAR/three POM identities and protected exact-source CI.
- [ ] Core, processor and replication remain separately publishable; independent
  V1–V5.1 consumers pass at final coordinates in an isolated Maven repository.
- [ ] Strict Javadoc, public API/format compatibility and source/fixture exclusion
  pass for all three artifacts. Final candidate source is explicit; measured
  cloud sources and their accepted continuation remain separately recorded.
- [ ] Final release workflow and post-publication verifier have V5.1-specific
  candidate-byte checks and the V5.1 consumer. Generic V5 handling is insufficient.
- [ ] Dated release notes, migration guide and release title/body reviewed; remote
  version absence checked. No tag may point to a snapshot or unqualified commit.

## Operator-controlled publication

1. From the exact accepted candidate commit, the operator creates and verifies an
   annotated signed `v5.1.0` tag, then pushes it. Provide the exact commit and commands
   only after Phase 7B acceptance; no moving or replacing a published release tag.
2. The release workflow validates tag/signature/versions and all final release
   gates. The operator approves the protected production environment.
3. Central deploy must preserve frozen unsigned bytes through signing/deployment.
   Record the actual deployment ID and final state before treating publication as done.
4. Download all three POMs and nine JARs with signatures/checksums into fresh
   storage; compare all canonical artifact identities and compile/test clean
   remote V1–V5.1 consumers. Local installs cannot stand in for published artifacts.
5. Reconcile the GitHub Release, tag, deployment IDs, published bytes and final CI;
   only then mark 5.1.0 stable in README/roadmap and close Phase 8.

If publication partially succeeds, inspect immutable remote state and use the
existing exact-tag recovery path. Do not select a new commit under the same tag
or run the paid cloud measurements again to repair publication metadata.

## Explicit limits to retain in release notes

- Automatic mode is opt-in, one shard and exactly three fixed voters.
- Strong automatic reads belong to the ready leader; no public follower reads.
- No dynamic membership, mixed-version rolling upgrade or in-place configured
  authority conversion. Migration uses a quiesced verified backup and a new group.
- Indeterminate writes require application reconciliation, not unconditional retry.
- Registered latency/resource observations apply to the frozen test workload and
  do not establish a production throughput, p99 or general failover SLA.
- The five-member cloud baseline preserves its narrowly authorized two-source
  continuation. Future batches retain their ordinary common-source/sequence rule.
