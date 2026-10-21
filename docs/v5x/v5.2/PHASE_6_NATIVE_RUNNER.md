# V5.2 Phase 6BA owned native Runner resources

This stage connects [prepared inputs](PHASE_6_PREPARED_INPUTS.md),
[original CI/build provenance](PHASE_6_CI_PROVENANCE.md),
[provider preflight](PHASE_6_PROVIDER_PREFLIGHT.md) and
[manual cleanup provenance](PHASE_6_CLEANUP_PROVENANCE.md) to one concrete resource
owner. It follows the existing request wire policy and shared cleanup algorithm;
it does not replace either with a second implementation.

## Factory-owned admission

`cloud_native_runner.open_native(source, plan_path, approval_path, confirmation,
package_path, output)` opens a session to be used with `with` or explicitly closed.
It accepts operator data and actual package bytes, never an injected client,
credential, clock, resource request or a copied PASS receipt as capability.
There is no provisioning-only CLI. The eventual whole-member workflow will call
this resource scope as part of its complete execution and retention path.

Before creating resources, the factory:

1. Checks actual clean source and the fixed tracked provider configuration. It
   validates the complete prepared plan and exact confirmed approval early, before
   any remote observation.
2. Collects and independently replays the original exact-master build job, producing
   attempt, uploaded ZIP and extracted shared-build bytes. The temporary
   [CI admission policy](PHASE_6_CI_PROVENANCE.md) does not wait for other CI jobs.
   It accepts the dedicated manual cloud build, or the regular CI producer when
   no dedicated build exists for this source. Workflow identity, exact attempt
   and original producer execution remain independently bound.
   It inspects an owned package copy against those bytes and the pinned published controls.
3. Collects and independently replays the latest original manual-cleanup artifact.
   WAITING, stale, failed and substituted attempts cannot stand in for recent PASS.
   The Runner cannot use its own in-progress run as a completed cleanup execution.
4. Creates its dedicated runner-role credentials and read-only provider observer.
   The approved layout/policy must equal the source-controlled configuration,
   including exact image, disk layout and original ledger generation/absence.
5. Rechecks source, build contract and exact credential invocation before opening
   a native API. Existing per-exchange deadlines and decoder bounds remain hard.

The native API transfers the still-valid preflight access token from that exact
in-memory reader after these checks. It does not request a second token merely
because observation and resource calls use different clients. Its cache expires
no later than the original token's usable deadline or the existing 2400-second
API cache limit. Missing/expired tokens still require a fresh, context-bound
exchange; a GET 401 still permits one refresh. Mutation requests are not replayed.
Tokens never come from a receipt, another workflow invocation or persisted cache.

The two failed self-hosted runs `39556724370/1` and `39557495298/1` both stopped
before resource writes. The latter completed preflight, then failed its redundant
second credential exchange. Their old failure files retained `CredentialError`
but lost its reason code, so neither an IAM denial nor a timeout is established.
The cache correction removes that extra exchange; the diagnostic correction
makes any remaining initial/refresh failure classifiable. Local synthetic tests
exercise the native factories but cannot certify live WIF or IAM availability.

The factory retains original observations and an admission review, not just a
boolean. Its admission window is at most 15 minutes, also bounded by approval,
estimate and cleanup freshness. This is first-acquisition freshness, not an
experiment duration or financial cap. Time and cost budgets remain soft.

## Original writes and resource lifetime

NativeRunnerApi and NativeOwner are concrete factory-created types. OfflineOwner
and NativeCleanupApi cannot be repurposed through a native request or role change.
The transport retains the existing wire policy and checks admission again after
credential refresh, immediately before context/lease/reservation/activation writes.
Same-value ledger rewrites with a different generation reject. Acquisition and
reservation submissions are consumed once; a lost reply can only observe the
original value. Uncertain business/resource requests are not resubmitted.

Original context is still retained before the first lease CAS. A session starts
its owned renewal thread after ACQUIRING has been reserved and made ACTIVE, then
provisions the same thirteen resource intents. Renewal preserves the stable
allocation claim and original cost. Its failure is visible at the next owner
checkpoint; the whole-member integration must check that boundary before further
work. Source/run changes during
a credential refresh still reject, and an expired lease cannot be revived.

Once ACTIVE, the resource owner does not reapply expired initial approval or old
cleanup freshness to continued ownership or cleanup. Closing stops and joins the
renewal thread before fenced cleanup, then closes credentials, transport and the
journal. Each in-flight exchange retains its existing finite deadline; there is
no newly imposed stage timeout. Cleanup errors retain original authority for
later manual reconciliation. A workload exception remains the original exception,
with a separate cleanup failure diagnostic if needed.
Failed context-manager entry also closes the already acquired session: Python
does not call `__exit__` when `__enter__` fails. A diagnostic write failure cannot
bypass cleanup or replace the original exception; a closed, non-sensitive stderr
marker reports unavailable diagnostic storage.

## Result and failure semantics

`RESOURCES_PREPARED_NOT_QUALIFIED` binds source, request SHA, exact allocation claim
and soft-budget warning. `resourceAdmission: true` means this process completed
its input/admission gates and created that resource scope. It does not assert
effective IAM, guest readiness, engine execution or full remote qualification.

The session has no API for inventing workload PASS. Closing without separately
qualified immutable workload evidence records the original failed completion and
cost; a successful cleanup cannot promote it to an experiment success. Pending or
unknown original operations remain unresolved, even when a name is absent. In
particular, the implementation does not infer safe non-submission solely from a
rejected transport response after the request was dispatched. Such uncertainty
preserves the lease; a denied submission-marker write before dispatch instead
allows the existing fenced non-submission proof and cleanup.

Failure files use closed phase codes, exception types and HTTP status where
applicable, without provider bodies or tokens. Credential failures additionally
retain the closed [exchange diagnostics](PHASE_6_CREDENTIAL_ENTRY.md), including
the failing service code, failure kind and credential-service HTTP status.
Generated request routes and
send/response/uncertain journal entries retain the original attempt. The full
original observations, failed completion and charges are never reset or rebound
to a later source. Package bytes and synthetic fixtures are not run as Java code
by the native-factory tests.

## Local validation and remaining connection

The measurement gate preserves every existing check and adds native factory
regressions. External source, GitHub, credential-file and provider I/O is mocked;
all original parsers and admission/control paths run. Coverage includes early
approval rejection, real archive parsing, current CI/cleanup, required permission,
layout/policy, source/run/generation drift, lost acquisition replies, partial
resource failure, renewal and shutdown, and retained uncertain cleanup. Original
development failures and final source/log hashes are retained in
`target/v52-native-runner/validation-summary.json`.

Final local validation passed all 920 V5.2 Python tests (including 27 new cases)
in 700.621 seconds and all 171 related CI/V5.1 contracts. The two lifecycle bugs
were independently reproduced before correction; focused regressions and the
complete corrected-source suite pass. All 1,842 frozen executable paths remained
unchanged during the final suite. Python syntax, shell syntax, documentation
contract, 203 local links and unchanged existing gate commands also pass.

No V5.2 configuration, identity or workflow is deployed here, and no real token,
resource, engine measurement, workflow dispatch or paid cloud run is executed.
The next connection is owned private IAP plus exact host keys, boot/UID/data-mount
observations and installed Placement. Then complete verified immutable member
retention, all whole members and independent five-member replay, and the protected
Runner workflow/operator instructions. All five members remain runnable in any
order, with one original source/sequence and whole histories; no retry fragments
or different-source results can be spliced into acceptance.
