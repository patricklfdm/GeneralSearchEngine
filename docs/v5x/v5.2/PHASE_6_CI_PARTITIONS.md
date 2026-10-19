# V5.2 required CI partitions

Phase 6BH separates the growing V5.2 Python inventory from runtime qualification.
Previously foundation discovered every V5.2 Python test inside its 15-minute job,
and the measurement wrapper repeated most of them inside the 20-minute hardening
job. Native adapter models made that serial dependency increasingly expensive.
This is a scheduling change; it grants no cloud or measurement acceptance.

## Exhaustive Python inventory

`scripts.ci_v52_python` discovers every `scripts/v52/test_*.py` module and assigns
it to exactly one required job. The existing V5.1 process-generation suite also
remains included. New modules enter conservative default partitions; duplicate
or foreign module names reject. Test discovery failures are test errors, and an
empty suite or a mismatch between discovered and executed counts fails.

| Partition | Migration snapshot cases | Responsibility |
| --- | ---: | --- |
| core | 64 | Public read and token evidence |
| measurement | 181 | Frozen measurement, histories, replay and aggregation |
| transport | 316 | Remote transport, processes, Python/Java installation |
| cloud-provenance | 176 | Protected CI, input packages, preflight and cleanup provenance |
| cloud-control | 216 | Authority, provider policy, state, restoration and set replay |
| native-admission | 65 | Native admission/acquisition and cleanup factories |
| native-storage | 43 | IAP, original storage and installed Java factories |
| native-evidence | 26 | Whole-member staging, retention and member replay |

At migration commit `1b814da`, the 1,087 cases were 1,082 V5.2 tests plus five
existing process-generation cases. New source modules continue to enter the
exhaustive inventory; this table preserves that measured validation snapshot.
These are inventory counts, not an assertion that a hosted run has passed.
Each job retains discovered/executed/failed/skipped counts and per-test timings,
including failure, and prints progress every minute. Python is pinned to 3.11;
these tests use modeled provider effects and do not acquire native credentials.

At that migration tree, retaining both old Python entry points would execute 1,082
foundation cases plus 1,023 measurement-wrapper cases. Their union is 1,087,
so moving that union removes 1,018 duplicate invocations. This is a source-based
comparison of those two entry points, not a measured hosted saving. Other existing
runtime gates keep their small evidence-specific unit suites unchanged.

## Complete runtime lanes

Foundation keeps version alignment, build-coordinate checks and its foundation,
public-read, application and compaction qualifications. Its CI-only
`--skip-build --skip-python` invocation delegates the discovered Python inventory
to the eight required jobs. All five pre-existing read lanes remain,
with measurement removed from the combined hardening lane.

The measurement wrapper has three independent runtime lanes:

| Lane | Original complete commands |
| --- | --- |
| consumers | measurement runtime with load, bootstrap qualification, remote runtime qualification |
| commands | remote command qualification, complete owned history |
| installed | isolated-volume qualification, installed Java qualification |

Each lane restores the exact producer artifact ID, validates source/JDK/build
hashes, and retains its restore provenance and complete failure evidence. The
consumer lane preserves the `v52-measurement-runtime-<sha>` artifact name; the
command and installed lanes add distinct artifact names. Evidence retains 14 days.
The installed lane packages its entire evidence directory as
`v52-installed-runtime.tar.gz` before upload, including on qualification failure.
It uses the existing provider-evidence packer with symlink dereferencing disabled:
the intentional volume-rejection fixture linking to `/var` stays link metadata,
and host files outside the evidence directory are not traversed. Artifact name
and retention are unchanged; no fixture is deleted to make the upload succeed.
No individual history, lease, source or fault/recovery sequence crosses jobs.
All seven original runtime commands and their arguments/timeouts remain.

Without a lane option, the local measurement wrapper still runs its entire
original unit/runtime sequence. `--lane unit` is also available. Foundation's
ordinary local invocation still discovers all Python tests. This preserves local
operator and experimental branch entry points.

## Required and external consumers

The closed registry and generated inventory now contain 52 suites, 54 static job
IDs and 62 expanded full jobs. Integration executes 59 instances, skipping only
the existing complete V5.1 canonical matrix. Docs retains its two meta jobs and
52 skipped suite placeholders. Every new job is required in full/integration;
a missing, failed or cancelled partition cannot be hidden by the others.

V5.1's fixed matrices, protected build/owned step identifiers and release contract
stay unchanged. V5.2 exact-master/exact-attempt preflight derives the complete
updated inventory and required step set from source. It rejects a copied green
job with a skipped verification step. Local default entry points, public Java,
POMs, frozen measurement parameters and the release workflow do not change.

## Verification and limits

The partition tests compare every discovered test ID with the disjoint combined
inventory and inspect the real required workflow calls. Shell capture compares
the complete default wrapper with concatenated lanes and verifies exact command
order, arguments and timeouts. Existing Required/profile, composite, artifact,
fixed-matrix and independent cloud-consumer contracts remain in force.

Local logs and per-test receipts live under `target/v52-ci-partitions`. A sandbox
run whose root ownership was mapped to UID 65534 rejected safe installation
fixtures; those results remain separate from normal-host verification. No safety
check was weakened to accept the mapped directory owner. Initial stale topology
fixture failures are retained alongside the corrected checks.

Local partition receipts cover all 1,087 distinct test IDs with no skips or
failures; 183 CI/preflight contract checks also pass. Most partitions used the
system Python 3.10, while the corrected provenance partition and CI contracts
used Python 3.11. The slowest local partition, native-storage, took 1,321.318
seconds while historical replay and other models shared the host. Exact-source
hosted Python 3.11 qualification remains required; these local durations do not
isolate hosted execution cost.

Hosted duration, runner queue effects and total runner-minutes remain unmeasured
for this split. More parallel jobs can increase startup/artifact overhead; no
specific wall-time reduction is claimed before exact-source CI completes.

### Hosted fixture and artifact correction

[CI run 39177909775](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39177909775)
attempt 2 still failed three jobs. The measurement failure test supplied a local
launch identity while the runner supplied a GitHub run/attempt; the V4.4 Java
selector test omitted the eight registered Python lanes from its no-Java set;
and installed qualification passed but artifact upload followed its deliberate
fixture link into the host's protected `/var` tree. These require fixture and
packaging corrections rather than repeating the unchanged run.

The measurement regression now covers local and hosted identities, verifies one
failed execution with no retry, and rejects mismatched run/attempt before launch.
The V4.4 selector check derives only registered Python domains from the suite
registry; unknown lanes and Java selector drift still reject. The archive
regression executes the workflow's actual packaging command against a failed
receipt and an inaccessible external-link fixture, checking upload wiring,
retained bytes and absence of external content. Production execution and exact
run/attempt checks, workload parameters and Required outcomes are unchanged.

Original logs and local correction checks are retained under
`target/v52-ci-fix-39177909775`. Corrected-source protected CI remains required;
local checks do not turn the failed hosted run into acceptance evidence.
