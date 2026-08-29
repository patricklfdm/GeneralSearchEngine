# CI/CD and release operations

GeneralSearchEngine separates continuous integration from release publication:

```text
pull request or master push -> CI validation only
signed vX.Y.Z tag           -> release validation -> approval -> publication
immutable-tag recovery      -> explicit dispatch -> same validation and approval
```

A merge to `master` never publishes Maven artifacts. Publication requires an exact,
annotated, signed semantic-version tag and approval of the `production-release`
GitHub Environment.

## Toolchain

- Java 21;
- Maven 3.9.11 through `./mvnw` or `mvnw.cmd`;
- Maven Wrapper distribution SHA-256 verification;
- Ubuntu GitHub-hosted runners for required checks.

The wrapper is the canonical Maven entry point. A system Maven 3.9 or newer remains
supported for the local emergency release procedure.

## Continuous integration

`.github/workflows/ci.yml` runs for pull requests, pushes to `master`, and manual
dispatches. It has read-only repository permission and receives no release secrets.

The workflow runs four parallel gates:

1. `Reactor tests` checks version alignment, compiles all reactor modules, runs the
   core and processor tests, and executes the travel example.
2. `Compatibility` runs the frozen source/reflection fixture, compares the public API
   with published 1.0.0, 2.0.0, and 2.1.0 artifacts from an isolated Maven repository,
   and compiles all three independent consumers.
3. `Release artifacts` builds sources and strict Javadocs with GPG intentionally
   skipped; checks all six JARs, Manifest versions, and processor service isolation;
   then verifies that all six publishable JARs are reproducible.
4. `Cloud runner (no GCP)` validates shell syntax, the manual cloud-performance
   workflow, fake Compute/GCS lifecycles, and deterministic Cloud Benchmark V2 evidence.
   It receives no OIDC permission or cloud Environment and creates no paid resource.

The stable required status check is:

```text
CI / Required
```

Configure the `master` ruleset to require this check rather than each internal job
name, so the workflow can be reorganized without changing branch protection.

## Required repository rules

Create an active branch ruleset targeting the default branch `master`:

- require a pull request before merge;
- require `CI / Required` to pass;
- require the branch to be up to date before merge;
- block force pushes;
- block branch deletion;
- require zero approvals for a solo-maintainer workflow, or one approval when a
  second regular maintainer is available.

Create a separate active tag ruleset targeting `v*`:

- restrict tag creation to the release owner;
- restrict tag updates;
- restrict tag deletion;
- keep the owner as the only emergency bypass actor.

Never update or delete a tag after its Maven version has been published.

## Cloud benchmark Environment and WIF

`.github/workflows/cloud-performance.yml` is a separate, manually dispatched paid
workflow. It does not run on pull requests, pushes, tags, or schedules. Its no-cloud
preflight validates the bounded input matrix and requires the selected source commit to
be reachable from protected `master`. The paid job then waits for the GitHub Environment:

```text
cloud-benchmark
```

Configure a required reviewer and restrict deployment branches to `master`. A solo
maintainer may allow self-review; when another maintainer is available, prevent
self-review. Repository-wide non-cancelling concurrency permits only one paid cloud
workflow at a time.

The Environment stores six non-secret variables:

```text
GSE_CLOUD_WIF_PROVIDER
GSE_CLOUD_SERVICE_ACCOUNT
GSE_GCP_PROJECT
GSE_GCP_ZONE
GSE_CLOUD_IMAGE
GSE_BENCHMARK_GCS_BUCKET
```

The provider value is the full
`projects/NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER`
resource name; the service-account value is its email. Image is one immutable image
name, not a family. Bucket is one existing `gs://bucket` URI. No service-account JSON
key or Maven release secret belongs in this Environment.

Create the WIF pool, provider, service account, IAM bindings, and bucket outside the
workflow. Map at least `google.subject`, `attribute.repository`, `attribute.ref`,
`attribute.workflow_ref`, and `attribute.environment` from the corresponding GitHub
claims. The provider condition must require all of:

```text
assertion.repository == 'patricklfdm/GeneralSearchEngine'
assertion.ref == 'refs/heads/master'
assertion.workflow_ref == 'patricklfdm/GeneralSearchEngine/.github/workflows/cloud-performance.yml@refs/heads/master'
assertion.environment == 'cloud-benchmark'
```

Grant `roles/iam.workloadIdentityUser` on the dedicated service account only to the
provider's repository principal set. In the dedicated benchmark project, grant only
the Compute instance lifecycle and existing-network use needed by the V1 runner. On the
dedicated evidence bucket, grant object creator plus object viewer; do not grant object
admin, bucket admin, project owner, IAM admin, or service-account-key admin. The VM is
still created with no service account and no OAuth scopes. Projects using OS Login or
IAP need their existing narrowly scoped SSH/IAP roles; the frozen workflow uses the
reviewed external-IP path.

After setup and merge, manually dispatch the least expensive smoke first:

```text
evidence_profile = experiment
mode             = quick
repeats          = 1
provisioning     = spot
machine_type     = c3d-standard-30
soak_duration    = 30m
retention        = actions
source_commit    = <empty, meaning the selected master commit>
```

Review Environment approval, OIDC authentication, the dry-run plan, VM cleanup, the
bounded 14-day artifact, and the final summary. Only then dispatch Standard/GCS
canonical evidence. The workflow never registers or replaces a baseline.

## Production release Environment

Create a GitHub Environment named exactly:

```text
production-release
```

Configure at least one required reviewer. A solo maintainer must allow self-review;
when a second release maintainer exists, enable prevention of self-review. Restrict
deployment tags to the `v*` pattern.

Store these Environment secrets, not repository files:

```text
CENTRAL_USERNAME
CENTRAL_PASSWORD
GPG_PRIVATE_KEY
GPG_PASSPHRASE
```

`CENTRAL_USERNAME` and `CENTRAL_PASSWORD` are the Maven Central Portal user-token
credentials for Maven server ID `central`. `GPG_PRIVATE_KEY` is the ASCII-armored
private release key matching `.github/release-signing-key.asc`. The expected primary
fingerprint is:

```text
91AA B7A2 B0FB 55C3 BBB3 3453 4B61 0314 8D64 3AB3
```

The private key is imported only into the ephemeral release runner. Maven GPG receives
the passphrase through its recommended `MAVEN_GPG_PASSPHRASE` environment variable;
the workflow never writes it into Maven settings. The workflow uses the built-in
`GITHUB_TOKEN` to create the GitHub Release, so no additional personal access token is
required.

## Preparing a release

Before creating a tag:

1. change core, processor, reactor, example, and consumer versions from the snapshot
   to the same final `X.Y.Z` value;
2. add a dated `## X.Y.Z — YYYY-MM-DD` section to `CHANGELOG.md`;
3. freeze `project.build.outputTimestamp` in both publishable POMs;
4. complete the version-specific release checklist;
5. merge the approved release commit to `master` and rerun the local release gates;
6. create an annotated signed tag on that exact commit.

Example:

```bash
git switch master
git pull --ff-only origin master
git tag -s v2.2.0 -m "GeneralSearchEngine 2.2.0"
git tag -v v2.2.0
git push origin v2.2.0
```

The release workflow rejects malformed tags, snapshots, module/consumer version
mismatches, missing changelog sections, lightweight or incorrectly signed tags, a tag
checkout that does not match `HEAD`, and commits not reachable from `origin/master`.

## Automated release flow

After the signed tag is pushed, `.github/workflows/release.yml` performs:

```text
validate the exact tag without secrets
-> reject a version already present on Maven Central
-> wait for production-release approval
-> import the ephemeral private key and Central token
-> clean, test, package, sign, and verify all 8 detached signatures
-> deploy core + processor
-> wait for Central state PUBLISHED
-> resolve both coordinates from a clean Maven repository
-> create the GitHub Release with Maven links and the matching changelog section
```

The release job sets `central.autoPublish=true` and
`central.waitUntil=published`. The POM defaults remain `false` and `validated`, so the
trusted local release flow continues to require manual publication in Central Portal.
The reactor and travel example keep `maven.deploy.skip=true` and are never published.
Normal Maven library JARs are not copied to GitHub Release assets.

Release workflow concurrency is scoped to the tag and never cancels a running release.
The manual dispatch accepts an existing signed tag only as a recovery mechanism. Both
tag push and recovery use the selected tag as the concurrency key, and both validation
and publication jobs explicitly check out that exact tag.

## Failure and recovery

### Validation fails before approval

No secret is exposed and nothing is uploaded. If release source, metadata, or the
signed commit is defective, fix it under a new reviewed commit and patch version; do
not move the pushed tag.

If the immutable tag is correct and only the release runner or orchestration failed,
merge the infrastructure fix to protected `master`, wait for `CI / Required`, and
manually dispatch `Release` with the existing tag. The recovery run still validates
the tag signature and exact commit, checks that the commit is reachable from
`origin/master`, reruns every release gate, rejects an existing Central version, and
waits for `production-release` approval. Legacy validator dependencies may be added to
the ephemeral runner, but files used to build the release continue to come from the
exact tag.

Never delete, recreate, or force-update a pushed signed release tag as a recovery
shortcut.

### Central upload or validation fails

No GitHub Release is created. Inspect the Central deployment. If it is not published,
discard it before retrying an unchanged tag or prepare a corrected patch version.

### Central succeeds but GitHub Release creation fails

Do not rerun the Central deployment. The workflow deliberately rejects versions that
already exist. Create the GitHub Release manually from the existing signed tag and the
matching changelog section.

### A defect is found after publication

Maven Central versions are immutable. Fix the defect under a new patch version such as
`2.2.1`; never overwrite artifacts or move the original tag.

## Trusted local fallback

CI/CD does not remove local release capability. From an exact signed tag on a trusted
machine with Maven server `central` and the release private key configured:

```bash
./mvnw -f reactor/pom.xml clean -Prelease verify
./mvnw -f reactor/pom.xml clean -Prelease deploy
```

The default local deployment stops at Central state `VALIDATED`. Inspect the two
coordinates and publish the deployment manually in Central Portal, then create the
GitHub Release.

## Deferred hardening

After the core workflows have run successfully, evaluate Dependabot for Maven and
GitHub Actions, dependency review on pull requests, CodeQL for Java, and GitHub artifact
attestations. These are additive controls and do not replace the required correctness,
compatibility, signing, or reproducibility gates.
