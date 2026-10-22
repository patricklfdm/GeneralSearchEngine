# V5.2 bounded read retries

## Incident and scope

Run [39640228986/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39640228986)
used source `0de9a8b6c3bef6723d97c2f208a7d156bf022a7d`. Its SDK startup passed;
all 14 IAP channels closed successfully. During node 2's Python-install precheck,
native exchange 3750 lost a numeric disk GET response. The same endpoint had
returned 200 on 44 earlier reads. The failure journal contains one
`ConnectionError` among 4386 exchanges; the transport does not distinguish its
underlying socket/TLS/individual-timeout cause. No workload history started.
Cleanup passed with all 13 resources absent and the lease released.

The correction is scoped to V5.2. It does not change V5.1 HTTP behavior, Java
replication, workload parameters, evidence acceptance, stage budgets or cost budgets.

## Audited paths

| Surface | Retry behavior | Preserved boundary |
| --- | --- | --- |
| Compute resource identity, host attributes, original-operation GETs | New shared bounded GET retry | Exact endpoint, original request ID/IDs, source and scoped policy rechecked |
| Lease/ledger metadata and generation-pinned media | Same shared GET retry, including nested ownership checks | Original deadline, generation/CAS and active-owner validation |
| Cleanup discovery, operation polling and absence checks | Same shared GET retry | Expiry/grace, exact ownership/IDs; deletion itself is never replayed |
| Retention readback and restoration of selected originals | Same shared GET retry | Same generation-pinned object; length, JSON, manifest/hash and source checks still reject |
| Preflight GETs and fixed read-only permission-test POSTs | Three attempts per read | Generated allowlist only, source/configuration/credential binding and 128-exchange bound |
| OIDC, STS and impersonation | Three attempts per exact stage | Shared original token-acquisition deadline; no full-chain restart, identity or lifetime bypass |
| GitHub build/cleanup/original-artifact GETs | Existing three-attempt reader also handles HTTP 408/429 | Original run/attempt and source, pagination/count/byte bounds, strict JSON/ZIP validation |
| GitHub credential-context GETs | Now reuse the bounded GET reader | Latest → exact attempt → latest must all still identify the same in-progress run |
| Guest link-local metadata GETs | Three attempts within the original three seconds per fixed path | No proxy/redirect, same path, Google header, byte/ASCII bounds and exact guest identity |
| IAP admission and native volume/storage queries | Bounded reads only | At most two IAP admission attempts; three clock-read exchanges; three mount-read attempts within one 300-second window and current authority; initialization queries retain their original grant |
| Remote original-command recovery | Existing finite result-query mechanism retained | Consumed command is never resubmitted; permanent rejection or exhausted reads stop |
| Install/start, Compute/Storage writes, measurement operations | No new automatic replay | Original-result query/reconciliation remains the only way to resolve uncertain submission |

## Independent archive publication and retention readiness

Run [39678504498/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39678504498)
on source `73f3bd5c21c97eee564397ab11af7b66bc1b13a3` completed all 13 failure-drill
histories and their individual replays, then failed at `retention-originals`.
Its `build.zip` and `cleanup.zip` each shared an inode with their retained HTTP
response (`st_nlink=2`): `Network.download` had published them with a hardlink.
Final evidence framing correctly required single-link original files. This was
a deterministic local publication defect, not an exhausted stage-time budget or
a failed workload measurement. Cleanup removed all 13 resources and released
the lease; the failed attempt remains unqualified and charged in the ledger.

The shared GitHub downloader now copies only the complete successful response
into a private file beside its destination, in bounded 1 MiB reads, checking the
exact advertised length. It publishes the complete copy without overwriting an
existing destination, then removes the temporary name before returning. The raw
response and published ZIP therefore have independent inodes and each has one
link. Failed download attempts remain separate; publication/copy failures do not
restart downloads or measurements. The final hardlink rejection remains intact.

The [native factory](PHASE_6_NATIVE_RUNNER.md) also checks the complete original
provenance file inventory before provider access and repeats that check at final
capture. This catches filesystem incompatibility before a paid workload starts,
without caching an exemption from later identity, source, hash or upload checks.

Regressions exercise the real downloader through native admission and evidence
framing/restoration, changed copy lengths, failed publication, competing existing
destinations, early build/cleanup hardlink rejection, and late alias creation.
An offline smoke check on the actual self-hosted Python 3.11.17 used the corrected
downloader with the failed run's retained ZIP bytes: all 46 original evidence
files (322598025 bytes, 111 chunks) passed framing and chunk/hash validation.
The old evidence and Runner checkout were not modified. This verifies storage
framing only; it cannot retroactively grant that attempt a native PASS or replace
a new source-bound prepare and run. Review artifacts are under
`target/v52-retention-publication/`.

## Attempt and deadline contract

`cloud_read_retry` allows three attempts total (the original plus two retries),
with 0.25 and 0.5 seconds between attempts. Only exact transport `ConnectionError`,
`TimeoutError`, or HTTP 408/429/500/502/503/504 qualify. No new time is granted:
each call keeps its original deadline, and every attempt rechecks scope and
authority. Permission rejection, missing original object, source/ownership drift,
wrong generation/identity, malformed/oversize payload and failed integrity checks
remain terminal. HTTP 404 is still interpreted only by existing caller semantics.

The existing GET-401 refresh allows one authentication retry inside each GET
attempt: the worst case is six resource wire exchanges, all within the same
deadline. A credential stage has at most three token-service exchanges. GitHub
reads retain their existing one- and two-second backoffs and original deadline.
No layer grants unlimited retries or resets a stage budget.

An exhausted shared read raises `ReadError` with `retryable=False`, so outer
storage, control CAS/release reconciliation and original-launch recovery cannot
multiply its retry count. IAP has one narrow exception before SDK spawn: a
`provider-read` deadline that reaches the current admission attempt's own deadline
may use the second already-budgeted admission attempt. It must fit the original
60-second connection deadline, repeat ownership/identity checks and use a fresh
private credential directory. A read attempt-count exhaustion, earlier nested
deadline, different read scope or security rejection remains terminal. This does
not make `ReadError` generally retryable or permit another business submission.
The [operator entry](PHASE_6_OPERATOR_ENTRY.md) records the reproduced incident,
matching cold-connection allowances and local verification.
An unmodified measurement's failure remains a failure; this is not a successful
sample selected from repeated workload executions.

Both stage time and cumulative expense remain soft limits. Individual network
exchanges, response sizes, retry counts and evidence validation remain finite.

## Diagnostics and validation

Each transient failure emits `stage=cloud-read-retry`, scope, attempt, closed
reason, retry decision and stop. Terminal failures retain
`V52_READ_RETRIES_EXHAUSTED` or `V52_READ_DEADLINE` and a validated `readRetry`
record in native/operator/evidence failures. Credential failures preserve their
stage-specific code as well. Existing native journals retain every physical
exchange. Tokens, response bodies and credential URLs are excluded from retry
progress and public diagnostics.

Focused tests cover successful recovery, persistent failure, shrinking deadlines,
bounded 401 refresh, terminal HTTP/validation failures, reauthorization and
single-submission mutations. Native-factory fault injection reproduces the
numeric data-disk disconnect through real scoped guest observation code, then
checks persistent exhaustion and resource/lease cleanup. Evidence restoration
tests verify the original generation and rejection of changed/absent originals.
All external cloud effects in these tests are modeled; they are not a paid-cloud
qualification or a claim that every future network failure can recover.

Local logs, the isolated self-hosted smoke result and review instructions are
retained under `target/v52-cloud-read-retries/`. The corrected source requires a
new Cloud Build, cleanup observation and prepare/approval; an earlier prepared
request cannot authorize the changed source.
