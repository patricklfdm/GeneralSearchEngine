# V5.2 Phase 6AV build inputs and exact preparation review

This stage adds a deterministic input package and an operator review contract
after the [request wire policy](PHASE_6_REQUEST_WIRE_POLICY.md). Both are local,
non-executing checks. A copied receipt, a prepared request or a confirmed approval
does not open the native provider. GitHub provenance, exact-master full CI, fresh
provider/IAM/cleanup observations and concrete native integration remain required.

## Actual inputs, not a PASS receipt

`scripts.v52.cloud_inputs` reads the existing `ci_v51_bundle` format, which already
supports the V5.2 reactor. It does not restore outputs, run Maven, execute an
archive program, contact Maven Central or modify the shared build implementation.

The public entry observes the actual clean Git checkout, exact commit, tracked
file/executable-bit digest and Java vendor/runtime. It requires V5.2 coordinates
and the same binding in the original shared-build manifest. The complete bounded
archive is authenticated, every member is checked, and the existing executed-test
prerequisites are replayed, including the V5.2 token/API suites. A supplied build
success receipt is ignored. This validates retained report bytes, not a new Java
test execution or proof that GitHub produced them.

The package contains eight files plus its inventory:

- Candidate core and replication JARs, taken from the verified build archive.
- The published V4.4 core, V5.1 core and V5.1 replication JARs, checked against
  the source-frozen `published-controls.json` hashes.
- Original shared-build manifest bytes, original published-control manifest bytes
  and the source/Java binding.

`inputs.tar.gz` uses regular USTAR members, sorted paths, fixed mode/owner/time and
a gzip header without a timestamp or filename. The same original inputs produce
the same package bytes across destination paths and creation times. The archive
SHA becomes the suite's `packageSha256`. There is no per-attempt SSH key, member
name, session path or current time in the package; all nine execution units can retain one
shared input identity. Per-history receiver capsules continue to carry their own
topology, compiled helpers, seed and ownership. This input archive is not a guest
installer or a substitute for those existing receiver capsules.

Both build and package have a 256 MiB compressed/expanded bound. Build inventory
is limited to 20,000 files; package inventory is exactly the eight original files.
JARs are at most 64 MiB and JSON metadata at most 8 MiB. Linked paths, duplicate or
unlisted members, extension records, sparse entries, missing bytes and substituted
JAR/report/source/toolchain data reject. Output directories must be new. Original
build outputs, reports and packages are never overwritten by this entry.

The public inspector rechecks the clean checkout after inspecting the bytes.
These are fresh bounded observations, not a filesystem transaction or an API
capability. Local input provenance must later be joined to independent original
GitHub artifact and producing-attempt observations.

```bash
python3 -m scripts.v52.cloud_inputs create --source "$(git rev-parse HEAD)" \
  --build target/ci-v52-build --controls target/v52-controls \
  --output target/v52-cloud-inputs-new

python3 -m scripts.v52.cloud_inputs inspect --source "$(git rev-parse HEAD)" \
  --build target/ci-v52-build --package target/v52-cloud-inputs-new/inputs.tar.gz
```

These commands require an already produced matching build and locally available
published controls. They neither build nor download missing inputs. The command
examples do not mean that a current-source package was produced during this batch.

## Preparation and approval

`cloud_prepared.prepare` combines the inspected input identity, provider
configuration and numeric project number, per-attempt guest public key, original
resource layout/ownership policy, one whole suite member, sequence and attempt.
It retains the exact ledger generation and content, including the distinction
between an absent ledger and a newly created empty ledger. It exercises the
existing reservation rules without writing a lease, ledger or resource.

The estimate is explicitly operator-supplied and dated, with its configuration,
layout, USD amount, coverage duration, required cost categories and public source
links bound into the plan. No hard-coded current prices or provider rates are
claimed. Its categories include three VMs, boot/data disks, control/evidence,
cleanup and failed attempts. The amount is the new reservation estimate; the
existing ledger retains all previous attempts. An estimate exceeding the soft
budget threshold produces a warning and remains reviewable. Coverage duration is
informational and does not set an execution deadline.

The approval template is unconfirmed. Confirmation binds the exact plan and
request hashes, original cumulative cost, new estimated reservation and expiry.
All fields are compared by canonical JSON, so `true` and `1` cannot alias. Any
source, package, member, attempt, key, quote, configuration or sequence change
requires a new review. The expiry is at most one hour after preparation and no
later than the dated estimate's expiry. This bounds how long an unused approval
can start work; it does not terminate an already running experiment.

`review` checks the approval and compares separately obtained current inputs,
provider configuration/project number and exact ledger snapshot. Any active lease
or changed generation rejects, even if the ledger amount is unchanged. Its caller
must own fresh observations; passing stored copies back into this pure checker
does not establish freshness. It returns `APPROVAL_BOUND_NOT_ADMITTED`, with all
admission/resource/workload/remote-qualification flags false.

All nine execution units may start first. Shared source/sequence/build/package/control,
layout and ownership-policy rules remain enforced by the existing ledger. A
failed attempt remains charged; another attempt must be fresh and run the entire
member. A passed member cannot be replayed under a new attempt. Native request
data remains incompatible with the concrete offline provider entry.

## Validation and next connection

The measurement unit gate adds `test_cloud_inputs` and `test_cloud_prepared` and
preserves all previous commands. The 45 initial tests cover real Git cleanliness,
synthetic shared-build/archive prerequisites and corruptions, deterministic
packaging, exact approval, stale generations, all member starting choices, shared
cohort binding, failed-attempt costs and soft budgets. Synthetic report/JAR
fixtures are not executed Java evidence. External network calls are not used.

Validation logs, source indices and any historical-package replay are retained
under `target/v52-cloud-prepared/`. Historical source hashes are preserved, not
rebound to this implementation. Complete current-source protected CI, native
admission, ownership/controller integration, IAP/guest preparation and whole
member/set qualification are still open. No provider permission or workflow is
enabled by this stage.

Final local validation passes **756 V5.2 Python tests in 320.457 seconds** and
**30 CI classification tests in 43.236 seconds**. The new 45-test targeted suite
passes in 26.361 seconds. The complete Python suite runs with the actual local UID,
preserving the existing installer ownership checks. Documentation contract, 192
changed-file local links, Python AST, shell syntax and whitespace checks pass.

Three retained real shared-build archives, each with 348 members, also pass the
new integrity/package checker with the actual published control JARs. Their
original sources remain `7c6b9e126295490bcace3f8e1ea2b500724f3ee9`,
`45e59505166b3cd02246dae4973d7e0322ead8a0` and
`493837abb0b76b2699ddab7de174eeb722b8a4f0`. Each generated package is byte-identical
to a second packaging at a different path. This replay trusts their retained
source metadata for comparison; it does not independently qualify those checkouts,
GitHub provenance or this implementation's current-source build. No Maven build,
engine history, real credential exchange or cloud experiment was run.
