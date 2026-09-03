# GeneralSearchEngine V4.1 Phase 3 local baseline

## Entry

Phase 3 starts from accepted Phase 2 commit
`a17ad20d3cd03128abf6c4f7fbeb0b752b523b02` (PR #95), whose exact-master CI run
`33720179867` passed.

## Local evidence

The focused Java matrix covers exact public descriptors and immutable values,
writer-ordered `B`, exclusion of later mutations, sequence-zero backup, deterministic
structural verification, repeated backup identity, path overlap, existing targets,
close rejection, explicit capacity failure, target I/O rollback, target collision,
single-operation admission, close waiting, one-byte short writes, checkpoint pinning,
and a later checkpoint while copy remains active.

The production harness materializes a real bundle which the independent Python
`backup_format.py` parser accepts. The abrupt-halt matrix exercises all 16 Phase 3
authority barriers. Before any reopen, `storage_inspector.py`,
`backup_crash_inspector.py`, and `backup_format.py` classify the source and any
staging/final artifact. Each source then reopens in a separate JVM at sequence 1,
accepts a continued durable mutation, and closes at sequence 2.

The complete reactor reports 457 core tests and 5 processor tests with zero
failures. Exact published artifact compatibility passes for every configured 1.x
through 4.0 baseline, and independent v1-, v2-, v3- and v4-style consumers compile.
The release profile produces all six expected main/source/Javadoc JARs, their
integrity checks pass, and two independent release builds reproduce identical
SHA-256 values.

## Commands

```bash
scripts/verify-v41-phase3-backup.sh
./mvnw -Dtest=V41PublicApiFoundationTest,V41BackupPublicApiTest,V41LiveBackupPhase3Test test
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase2-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

All local gates above passed. Protected PR #96 merged the implementation as
`f5516dfc05ff0e878a72f60d56792c30d480d2c3`; exact-master CI run `33723841861`
passed on that commit. No paid cloud execution belonged to Phase 3.
