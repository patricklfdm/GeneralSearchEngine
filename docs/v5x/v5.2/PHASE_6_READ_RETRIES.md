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

The retry policy is scoped to V5.2. The later shared HTTP classification fix
(below) also changes V5.1's error types, without adding V5.1 automatic retries.
Java replication, workload parameters, evidence acceptance, stage budgets and
cost budgets are unchanged.

## Audited paths

| Surface | Retry behavior | Preserved boundary |
| --- | --- | --- |
| Compute resource identity, host attributes, original-operation GETs | New shared bounded GET retry | Exact endpoint, original request ID/IDs, source and scoped policy rechecked |
| Lease/ledger metadata and generation-pinned media | Same shared GET retry, including nested ownership checks | Original deadline, generation/CAS and active-owner validation |
| Cleanup discovery, operation polling and absence checks | Same shared GET retry | Expiry/grace, exact ownership/IDs; deletion itself is never replayed |
| Retention readback and restoration of selected originals | Same shared GET retry | Same generation-pinned object; length, JSON, manifest/hash and source checks still reject |
| Preflight GETs and fixed read-only permission-test POSTs | Three attempts per read | Generated allowlist only, source/configuration/credential binding and 128-exchange bound |
| OIDC, STS and impersonation | Three attempts per exact stage, at most 10 seconds per exchange | Shared original 30-second token-acquisition deadline; only typed transient deadline exhaustion before SDK spawn can use the second predeclared IAP admission |
| GitHub build/cleanup/original-artifact GETs | Three attempts; JSON reads use 30 seconds per attempt within 100 seconds total; HTTP 408/429 also retry | Original run/attempt and source, pagination/count/byte bounds, strict JSON/ZIP validation |
| GitHub credential-context GETs | Now reuse the bounded GET reader | Latest → exact attempt → latest must all still identify the same in-progress run |
| Guest link-local metadata GETs | Three attempts within the original three seconds per fixed path | No proxy/redirect, same path, Google header, byte/ASCII bounds and exact guest identity |
| IAP admission and native volume/storage queries | Bounded reads only | At most two IAP admission attempts; three clock-read exchanges; three mount-read attempts within one 300-second window and current authority; initialization queries retain their original grant |
| Remote original-command recovery | Existing finite result-query mechanism retained | Consumed command is never resubmitted; permanent rejection or exhausted reads stop |
| Install/start, Compute/Storage writes, measurement operations | No new automatic replay | Original-result query/reconciliation remains the only way to resolve uncertain submission |

## OIDC socket headroom and IAP credential deadlines

Run [39905260525/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39905260525)
on `25d1ea8798687f3bc4766f332938fb7194e5761f` completed seven drill histories,
then failed in the eighth history's placement. One OIDC exchange consumed its
entire 30-second credential grant; the typed `OIDC_EXCHANGE_FAILED` was not eligible
for the existing second IAP admission. Exact-ID cleanup passed and released the
lease. This evidence does not establish a WSL crash or an engine failure.

Each OIDC/STS/impersonation socket now receives at most ten seconds, bounded by
the same original thirty-second grant and three-attempt limit. A typed transient
credential deadline may use the second existing IAP admission before SDK spawn;
that admission rechecks identity/ownership and obtains fresh credentials. Only
closed phase-matched diagnostics permit this path. Attempt-count exhaustion,
403/unknown status, invalid claims, malformed responses and arbitrary lookalike
exceptions remain terminal. The two-admission/240-second connection ceiling is
unchanged. No SSH stream, workload or business command is resubmitted.

## GitHub source-read timeout recovery

Prepare runs [39897761678/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39897761678)
and [39898300798/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39898300798)
on source `24947a535833269a57977d37351c955ae55e5691` both passed original-build
ZIP download, then failed during `final-ci` source revalidation. The first
stalled on `release.yml`, the second on `ci.yml`: each retained zero response
bytes after 30 seconds, with `attempts=1`, `retry=false` and `stop=deadline`.
The old JSON reader gave one exchange the entire 30-second read window, so an
owned exchange timeout left no opportunity to retry. Later public reads from
the same Runner returned 200 in under a second; the cause of the original stalls
is not established. Neither prepare launched a paid workload.

Each GitHub JSON read now has one fixed 100-second total window, at most three
30-second exchange attempts and the existing 1-/2-second backoffs. The owned
child is stopped and reaped before another attempt launches. A shorter exchange
timeout emits `V52_GITHUB_ATTEMPT_TIMEOUT`; exhaustion of the total deadline
remains `V52_GITHUB_DEADLINE`. Three timed-out exchanges normally stop after about
93 seconds, without waiting for unused headroom. A late successful exchange is
not accepted. Permission/unknown HTTP errors, malformed JSON, byte bounds and
source/attempt/hash validation remain terminal. No whole collector, workflow,
cloud mutation or measurement is retried.

The caller-provided credential deadline and the 300-second ZIP-download window
remain unchanged. Cleanup, prepared-artifact and Runner provenance JSON readers
inherit the correction and retain their individual path allowlists. Each
physical attempt consumes the existing 256-request bound and retains its own
body and receipt, including allotted/elapsed seconds and received byte count.
Progress excludes URLs, bodies, stderr and credentials.

Local regressions cover one/two timeout recoveries, three-attempt exhaustion,
a shorter caller deadline, late success/rejection, backoff oversleep, inherited
readers and real timed-out child reaping before a successful retry. These are
offline transport checks, not native admission or a guarantee against network
outages. Review evidence is retained under `target/v52-github-timeout-retry/`.

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

## Shared HTTP timeout classification

The shared HTTP adapter reports elapsed transport-lock waits, socket timeouts,
late successful responses and API deadline expiry as `TimeoutError`. V5.2's
existing read retry loop converts exhaustion into its bounded `ReadError`;
IAP may then use the already declared second pre-SDK admission attempt. Neither
the retry count nor any original deadline is increased. Direct pooled GCP and
unpooled proxy/credential paths use the same timeout classification.

A received HTTP rejection keeps its status even if the response/body arrives
late or its body read times out. The credential wrapper retains that HTTP status
instead of classifying it as an unknown transport error. Redirects, invalid
configuration and oversized successful bodies remain validation failures. Only
already declared transient HTTP statuses can use the existing retry policy;
POST/DELETE provider mutations remain single submissions, and a timed-out
mutation is still uncertain rather than replayed.

This also bounds acquisition of the shared transport lock by the original
exchange allowance. Credentials, response bodies and raw exception messages are
not added to public diagnostics.

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
reads retain their existing one- and two-second backoffs. JSON metadata reads
use the fixed 100-second window described above; credential-context callers
retain their original remaining deadline, and ZIP reads retain 300 seconds.
No attempt resets its read deadline or grants unlimited retries; stage budgets
remain soft.

An exhausted shared read raises `ReadError` with `retryable=False`, so outer
storage, control CAS/release reconciliation and original-launch recovery cannot
multiply its retry count. IAP has one narrow exception before SDK spawn: a
`provider-read` deadline that reaches the current admission attempt's own deadline
may use the second already-budgeted admission attempt. It must fit the original
240-second connection deadline (at most 90 seconds per admission), repeat
ownership/identity checks and use a fresh
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
