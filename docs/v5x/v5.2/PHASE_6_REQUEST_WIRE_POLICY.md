# V5.2 Phase 6AU request-scoped provider wire policy

This stage connects a closed HTTP policy to the actual V5.2 owner, provider and
reconciler. It follows the [credential entry](PHASE_6_CREDENTIAL_ENTRY.md).
`ScopedOfflineApi` drives the existing concrete HTTP fixture through the same
lease, reservation, insertion, operation recovery, receipt and cleanup calls.
There is no native mutable API or cloud dispatch in this stage.

## Shared wire shapes, separate authority

`cloud_provider.Plan` holds the existing pure resource shapes, endpoint builders,
operation IDs and response decoders. `Provider` inherits those same methods and
keeps its adapter/configuration checks. All 13 resource bodies and original
operation IDs remain unchanged. A plan can describe either authority domain;
rendering a native plan grants no execution permission. The concrete scoped entry
still rejects a native request and every live or lookalike transport.

`cloud_wire_policy.Policy` binds one validated configuration, complete original
request, role and exact reservation amounts. Its object scope contains only the
shared V5.2 lease/ledger and that request's context, operation records, cleanup
records and completion. It rejects other attempts, V5.1 prefixes, foreign buckets,
ambiguous encodings, duplicate query parameters, unobserved media generations,
wrong content types and oversized object metadata/media.

Compute calls are limited to the original 13 names, their confirmed numeric IDs,
the configured image, the exact `hostkeys/` query and operations derived from the
original request. Creation must have the complete original body and request ID;
extra fields, public interfaces, different disks, metadata or service accounts
cannot be smuggled through an otherwise allowed endpoint. Deletion requires the
original numeric resource ID and its derived delete operation ID. Name-only
DELETE, unrelated operation polling and arbitrary page tokens reject.

## Validate transitions at the transport boundary

The scoped gate rechecks ownership **after credential acquisition/refresh and
before transport submission**. The API and transport share a reentrant lock;
nested fresh control/resource reads inherit the original exchange deadline.
Individual requests remain bounded while total stage and cost budgets stay soft.

The gate independently checks these transitions, even if a caller bypasses the
higher-level owner method and invokes the generic HTTP API:

- Initial ACQUIRING lease: original request and exact current ledger reservation
  baseline; runner role only.
- Reservation: one append of the original cost, under the observed ledger
  generation and original ACQUIRING lease. Ledger replacement is not allowed.
- Activation: original lease plus its retained pending reservation.
- Renewal: active, unexpired original ownership and unchanged allocation.
- Next creation intent: one next resource, after prior IDs are retained.
- ID publication: only the ID resolved from that original operation; no erasure,
  reassignment or bulk transition.
- CLEANING: the owner may clean immediately; independent cleanup must wait for
  expiry plus grace, unless cleaning has already been claimed. Cleanup cannot
  activate, renew, reserve or create resources.
- Terminal ledger: append only the exact retained completion under the current
  generation. This control-only entry cannot write successful workload completion.
- Lease release: retained completion, no pending reservation, resolved operation
  IDs and a fresh final name-absence scan. Cached absence cannot authorize release.

Creation also requires the retained original context and a submission ticket made
by this same API instance while retaining its original marker. Scoped writes use
the version-two marker with a fresh per-API-instance `submitter` identity. A read-back
must match that exact marker, so a rejected overwrite or a losing CAS cannot adopt
the winner's permit. Lost replies can observe only that same original write. A
reconstructed API cannot turn an old marker into a second POST. The ticket is
consumed before the transport attempt, including an uncertain result. Version-one
markers remain readable for reconciliation and cannot grant a scoped permit. Fresh image/ownership checks
precede boot disk creation. Numeric deletion repeats resource inspection and
ownership checks, so drift during credential refresh does not bypass them.

These checks are not a cross-service transaction between GCS and Compute. A change
immediately after a sample remains possible. Retained intents, generation CAS,
original operation IDs, grace and conservative unresolved outcomes remain necessary.

## Original operation and absence evidence

Poll targets and page tokens must come from the observed original operation
response. Pending operation names/target IDs cannot change during polling.
Pagination has a finite bound and detects duplicate/cyclic pages and multiple
matching operations. A pending operation followed by an empty page, or one that
later disappears from listing, is not proof that nothing was submitted.

Operation receipts must equal the sanitized observed result. An unsubmitted proof
requires a CLEANING owner, retained context and a complete empty original-operation
search. It also requires either no submission marker, or proof within the original
API instance that its own unique marker never reached a provider transport call.
That second branch is available only after fencing into CLEANING, and rechecks the
same API identity; a restarted cleaner cannot infer it from a marker alone.

A marker with unknown dispatch outcome remains unresolved; cleanup retains the
lease and redacted failure rather than manufacturing PASS. Calling the transport
counts as potentially dispatched even if it then raises before the fixture applies
a write. This preserves conservative reconciliation without blindly retrying a
mutation, while a known failure before dispatch can release its own fenced intent.

Cleanup receipts validate their complete attempted-resource inventory and observed
absence. Only fixed phase/type error fields are retained in this scoped path.
A numerical 404 does not prove the original name is absent. Final release repeats
the name scan under the original deadline, using only GET; it never deletes a
replacement resource by name.

## Qualification and remaining work

The measurement unit gate now includes `test_cloud_wire_policy`. Tests exercise
complete allocation followed by independently reconstructed expiry cleanup,
renewals, fenced token refresh, exact ledger transitions, strict wire routes,
immutable receipts, pagination, lost marker responses, lost insertion responses,
unsubmitted intents and unresolved submission markers. Existing provider/control/
identity tests continue to run against their original fixtures. Synthetic provider
results are not GCP compatibility, permission, workload or billing evidence.

Two additional negative tests exposed an initial permit bug: a rejected marker
rewrite and a losing marker CAS could both grant a second API instance a submission
permit. They fail on the retained pre-fix source and pass with the unique marker
binding. The earlier 706-test green suite did not cover those cases; it remains
recorded as an earlier-source result, not validation of the final correction.

Raw local logs and exact executed source hashes are retained under
`target/v52-cloud-wire-policy/`. Native identity/permission deployment, current
project/image admission, exact-master/full-CI proof and paid request admission
remain separate work. In particular, native controller integration must explicitly
bind its authority domain to a trusted concrete capability; changing an offline
flag or relabelling a retained receipt is insufficient.

Next connect that admitted native capability and domain-aware controller, then
owned IAP, actual guest boot/user/data-volume identity, complete whole members and
independent aggregation. Cleanup uses its current workflow identity to reconcile
the original retained resource request; it must not relabel that request to a new
source or wait for a new successful engine workload. Manual cleanup remains
sufficient; the operator still pushes/merges and triggers paid experiments.

## Final local validation

The final source passes **711 V5.2 Python tests in 290.509 seconds**, including
**40 request-scope regressions**. The two isolated submission regressions first
failed, then both passed after the unique submitter correction. The earlier
combined provider/control/identity run passed 120 tests in 235.667 seconds before
that correction; the final complete suite covers those modules again.

All **30 CI classification tests pass in 42.331 seconds**. The six extracted
wire-shape/decoder methods are AST-identical to the original provider methods.
Documentation contract, local links/fences, Python AST, shell syntax and whitespace
checks pass, and the measurement gate only appends the new test module. The full
suite uses the actual local UID with installer ownership checks intact. No Maven,
complete engine-history qualification, actual credentials or paid-cloud execution
was run. Synthetic unit PASS output does not constitute workload evidence.
