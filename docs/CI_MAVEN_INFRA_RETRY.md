# Bounded Maven infrastructure retry

The [helper](../scripts/run-maven-with-infra-retry.sh) addresses transient remote
artifact/plugin resolution failures such as Maven Central throttling. It runs the
original command, streams combined stdout/stderr unchanged, and permits **one**
additional attempt after **15 seconds** only when the complete first log supplies
positive infrastructure evidence. No failed test or qualification is rerun.

## Classification

The [standard-library classifier](../scripts/maven_infra_retry.py) requires a Maven
`[ERROR] Plugin ... could not be resolved: ...` or `[ERROR] Failed to execute goal ...`
diagnostic containing exactly one `Could not transfer artifact ... from/to ...
(http[s]://...): ...` (or `metadata`) transfer. Its **same diagnostic** must contain
one of these causes:

| Allowed cause | Recognized form |
| --- | --- |
| HTTP throttling/server failure | `HTTP` (optionally `/1.1` or `/2`), `status code`, or `return code is:` followed by **429, 500, 502, 503, 504**; or `Too Many Requests` |
| Interrupted connection | `Connection reset`, optionally `by peer`; `Connection closed prematurely` |
| Explicit timeout | `Connection timed out`, `Connect timed out`, `Read timed out` |
| Temporary DNS failure | `Temporary failure in name resolution` |

A resolution exception name alone is insufficient. A timeout in one log line and
an unrelated artifact error elsewhere cannot qualify. Every non-boilerplate
`[ERROR]` diagnosis must qualify; unknown errors, multi-line diagnoses and multiple
transfers in one diagnosis fail closed. ANSI color is removed only for matching;
retained and streamed bytes are unchanged. Classification scans the retained log
line by line rather than loading the whole build output into memory.

### Conditions that prevent retry

These take precedence even if a valid 429/503 transfer error appears elsewhere:

- **Any Surefire/Failsafe test-goal banner, test-start line or `Tests run:` result**,
  including passing tests and a nonquiet skipped-test banner. A late dependency
  failure cannot rerun an earlier module's tests.
- Compilation errors (`COMPILATION ERROR/FAILURE`, missing symbols/packages,
  incompatible types), positive test failure/error counts, assertion failures and
  Surefire fork failures.
- Automatic replication exceptions/rejection codes; election, protocol, recovery,
  evidence, linearizability, compatibility, version, release or format failures.
- Checksum/hash/signature/reproducibility mismatch or failure, corrupt evidence,
  missing artifacts, malformed POMs/coordinates, Enforcer and certificate/PKIX/TLS
  handshake errors.
- HTTP **401/403/404**, authentication/authorization/access failures and Maven's
  cached-resolution-failure diagnostics.
- Exit statuses other than Maven's normal failure code **1**, cancellation, or an
  unreviewed `MAVEN_ARGS` environment. CI's current batch/no-progress/no-color value
  and an empty value are accepted.

Unknown-host, connection-refused, generic socket/EOF exception names, generic TLS
interruptions and Maven Wrapper distribution downloads are intentionally outside
the whitelist. They can reflect configuration or trust problems and remain manual
investigation cases. No `-U`, cache deletion, resolver setting or test rerun option
is injected; a cached resolution failure on attempt two still fails the job.

## CI integration and retained output

Only these exact command shapes are currently approved; any other command supplied
to the helper exits 2 before starting it:

```bash
scripts/run-maven-with-infra-retry.sh ./mvnw -f reactor/pom.xml clean package
scripts/run-maven-with-infra-retry.sh ./mvnw -f reactor/pom.xml package
scripts/run-maven-with-infra-retry.sh ./mvnw -DskipTests package
scripts/run-maven-with-infra-retry.sh ./mvnw -q clean -DskipTests package
```

The four shapes cover **16 steps in 15 jobs**:

| Jobs | Wrapped steps |
| --- | --- |
| `reactor-core` | Clean reactor package |
| All eleven `v51-*` jobs and both `v50-*` jobs | Each job's prerequisite reactor package |
| `v4-regression` | Initial core/harness package; final non-JMH clean package |

All arguments, test selection, build order, gate dependencies and job timeouts are
preserved. Python 3 from the Ubuntu runner is the only extra execution dependency.
The independent helper/topology tests run in `changes`, including docs-only CI.

Each invocation writes `attempt-1.log`, optionally `attempt-2.log`, and
`attempts.json` with completed-attempt exit codes and retry diagnoses in a unique
`$RUNNER_TEMP/gse-maven-infra-retry/run.*` directory. Local use defaults to the
system temporary directory. Keeping logs outside `target/` preserves them across
Maven `clean`. Every affected job always uploads these directories as
`maven-infra-<job-id>-<sha>`, retained for fourteen days, including recovered failures.
The console identifies attempts, the reason/backoff and recovery or exhaustion.
The final failed Maven exit code is preserved. SIGINT/SIGTERM stop the owned Maven
process group, never trigger a retry and return 130/143 respectively.

The JMH test, compatibility profiles, release verification/publishing, canonical
reproducibility builds, consumers and Maven invocations inside other scripts remain
unchanged. V5.x phase gates, crash matrices, election/rejoin tests and evidence
validators remain single-attempt. No production Java, POM or Surefire rerun setting
changes are required.

## Validation and limits

```bash
python3 -m unittest scripts.test_maven_infra_retry scripts.test_ci_changes \
  scripts.v44.test_phase7_release_fixtures
```

The tests run actual fake Maven subprocesses to check recovery, exhaustion,
stdout/stderr retention, exit status, argument preservation, signal cleanup and
cancellation during backoff. Classification fixtures cover the above causes,
unknown failures and correctness-over-infrastructure precedence. Workflow tests
restrict wrapped commands and ensure every affected job uploads all attempt logs.

A successful retry records an infrastructure recovery, not evidence that a flaky
correctness test was fixed. Matching is deliberately conservative: changes to
Maven's diagnostic format can result in no retry and should be reviewed against
retained logs. The additional attempt remains subject to the existing job timeout;
no new 20-minute retry loop or larger timeout is introduced. This mechanism does
not reduce concurrent repository requests or guarantee recovery during a prolonged
Maven Central outage.
