# Runner request inspection before native allocation

**Status:** local implementation and offline qualification; corrected-source
protected CI pending. This follows the accepted
[ordinary resource lifecycle](PHASE_6_EXPERIMENT_RESOURCES.md), PR #288, master
`d1f7b798897b83c51be6d3de53912860005b9f6d`,
[CI 37383808101](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37383808101)
attempt 2 (36 successful jobs). The successful rerun does not diagnose its
earlier failure.

This batch adds a read-only native inspection constructor and its explicit
offline twin. It does not expose a paid resource constructor, workflow input or
dispatch. `REQUEST_BOUND` keeps `paidAdmission`, `resourcesCreated`,
`engineWorkloadExecuted`, `fullRemoteQualification` and `paidCloud` false. A
successful inspection is not a reservation or a reusable authorization to create
resources later.

## Original build and package evidence

`cloud_runner_artifacts.collect` selects the original verification-build and
owned-experiment package artifacts from one exact-source CI run. The collector
uses fixed-repository GitHub GETs, a complete bounded listing, unique artifact
names/IDs, source/repository identity, and the successful producing job and build
step. Creation/update times must be inside that job after the build step.
Metadata is re-read after download; original ZIP size and SHA-256 must match.

`verify` reads both original ZIPs without executing packaged programs. It rejects
links, unsafe or duplicate paths, oversized expansion, encryption, failure
markers and missing required files. The build tar must match its original build
manifest. The package tar is authenticated before bounded extraction by the
source-controlled verifier. Its embedded build manifest must be byte-identical
to the original build artifact, and its manifest must be byte-identical to the
separately retained package manifest. Checks include candidate JAR hashes,
published control pins from this checkout, frozen workload, three isolated
launch checks, Java/vendor/JVM arguments, dirty state and payload inventory.

The native caller independently computes the current source/checkout/Java
binding with `ci_v51_bundle.binding`; a copied PASS receipt cannot supply that
binding. Offline qualification uses tiny, non-executable synthetic JAR/runtime
fixtures with explicit synthetic published-control pins. The native constructor
has no such override. Package verification does not run Java or packaged Python.

Failed-job reruns can retain a successful build from an earlier attempt. The
build name records that producing attempt; the current successful CI may have a
higher attempt. Reuse requires the original attempt's raw producing job to have
the same source, run, execution times, successful status and complete steps as
the build still accepted by current CI. Usually its job ID is unchanged. GitHub
can also copy the completed execution into a new check-run ID: this additionally
requires the same hosted runner ID/name, an earlier producing attempt, original
creation before execution, and copied-check creation after original completion.
A re-executed job has different execution times and cannot satisfy that check.
Both original and current records are retained and freshly rechecked; the proof
reports `ciAttempt`, original `buildProducer.jobId`/`attempt`, and the current
`acceptedJobId` separately. An unrelated old green run, altered origin record or
ambiguous artifact selection fails. Package names have no attempt suffix, so the
current accepted producing job/time binding is also required.

This was checked against PR #288's actual original artifacts: CI attempt 2 still
accepts copied check `112020403395` for original attempt-1 build job
`112012100193`, which produced artifact `11376183986`; guest package artifact
`11376059483` also passes original-byte and
manifest verification. The local read-only archive replay establishes format,
CI/producing-job provenance and internal byte consistency. It does not claim a
fresh native precheck or independently verify the current working tree against
the old build; the native entry must still compute its own checkout binding.

## Quote, approval and control binding

The plan binds the complete configuration, original artifact IDs/digests,
source/build/package/workload, guest public-key identity, sequence/attempt,
observed ledger generation/bytes and maximum reservation. It validates:

- Integer micro-USD pricing for three `n2-standard-8` VMs and 450 GiB of disks,
  covering at least 5400 + 1080 seconds; at least 30 days of evidence retention.
- Explicit request, evidence retention, network, Actions and failure-overhang
  allowances, with official price-source URLs and a quote lifetime of at most
  24 hours. These are supplied quote observations for operator review, not an
  automatic price fetch or proof of a provider bill.
- A maximum reservation covering the estimate, preserving all historical failed
  charges and the existing cumulative USD 200 ceiling; no pending attempt or
  sequence/attempt reuse.
- An unconfirmed approval template. Acceptance requires `confirmed: true`, exact
  plan/request hashes, previous/maximum cost and expiry, plus the plan hash in
  `RUNNER_EXPERIMENT_CONFIRMATION`. Altering the plan invalidates the approval.

The plan expires at the earlier of creation + 900 seconds and quote expiry.
Neither a GitHub wait nor credential refresh renews that time.

`NetworkAdmission` checks exact master workflow/run/attempt identity, forbids a
simultaneous storage selection, and replays the same-run observer and Runner
permission precheck from original raw files. It independently reads current
master, latest exact-source full CI, all required jobs and source configuration.
After authenticating artifact bytes, it performs the bound OIDC → STS → Runner
service-account exchange, then reads lease/ledger twice with generation-pinned
media reads. The ledger must equal the original observer/plan bytes and the
lease must remain absent. It rechecks artifact metadata, workflow attempt and
latest CI/master after inspection, and enforces the original preflight/plan
expiry and a 180-second inspection budget.

The HTTP policy permits only GETs of the two native control objects, including
when called through the base HTTP class. A GET 401 may refresh once under the
same deadline. There is no control write or Compute request in this entry. The
native constructor owns network, GitHub, checkout, credential-file and clock
boundaries; only the explicitly offline constructor accepts test doubles.

## Qualification and integration boundary

Two focused suites cover original-byte corruption, rehashed manifest/candidate/
workload drift, archive attacks, wrong source/toolchain/attempt, expired or
changed approval/price coverage, raw precheck tampering, CI movement, ledger
changes, active leases, historical costs, credential denial/claim drift, bounded
401 refresh and native constructor wiring. Unit tests reuse a validated frozen
plan to avoid repeatedly constructing identical model data; the separate
qualification process runs the original unpatched loaders and checks.

`cloud_runner_admission_qualification` retains synthetic original archives,
prechecks, inspection receipts and credential-stage names. It connects the
inspected resource plan to the existing offline preparer, creates all thirteen
simulated resources, and sends retained state to a fresh cleanup process. Manual
expiry cleanup must remove those exact resources and release the lease while
retaining the synthetic USD 5 failed reservation. No engine execution is claimed.

The two unit modules enter the existing Python admission partition and focused
preflight admission gate. The new standalone qualification has a 180-second
process cap; workload/lease/resource limits and all existing commands remain.
There is no new CI job, reactor build, workflow permission or cloud environment.
Local receipts are under `target/v51-runner-native-admission/` and
`target/v51-cloud-preflight/run.*/runner-admission/`.

Python 3.11 passed 26 new regressions, 35 CI partition/classifier tests and 21
existing storage-entry regressions. The complete focused admission gate passed
177 unit tests; its new four-stage qualification and the earlier preflight,
identity, permission and review checks retain their separate receipts. Final gate:
`target/v51-cloud-preflight/run.mg2oeI/`. Actual original-archive replay is retained
at `target/v51-runner-native-admission/verified-reused-build/`; the source/receipt
index is `target/v51-runner-native-admission/validation-summary.json`.
These are local checks and read-only GitHub observations, not corrected-source
protected CI or native cloud execution.

Next connect this inspection to once-only native allocation, exact-ID IAP and
owned guest/workload execution, with failed-stage evidence, immediate cleanup
and retention. That integration must revalidate admission immediately before
mutation, share the original request/deadlines, and qualify interruptions before
exposing a paid entry. The current resource preparer remains offline-only.
Actual resource/IAP observations should come from the first separately approved
experiment; no extra topology-only allocation or image-read rerun is required
by this change. Manual cleanup is sufficient; schedule remains optional.
