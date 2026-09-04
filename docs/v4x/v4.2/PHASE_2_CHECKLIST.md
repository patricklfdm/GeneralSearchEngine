# GeneralSearchEngine V4.2 Phase 2 checklist

- **Status:** Implementation candidate; protected acceptance pending
- **Scope:** Exact `1.1` format bytes and codec-free dual-minor inspection

## Entry

- [x] Phase 1 merged through protected PR #107 as
  `8e9aec0b07921fe2b43169cf930c628561db40f9`.
- [x] Exact-master CI run `33834603280` passed.
- [x] Work is isolated on `feat/v4.2-phase2-format-inspection`.

## Public API and open policy

- [x] Format and report records match the Phase 1 declaration fixture.
- [x] `DurableBackupFormat.V1_1` is additive; published enum/reason orders do not
  change.
- [x] The configuration default remains exact `V1_0`.
- [x] Explicit `V1_1` selection is represented but production open/write is rejected
  before directory creation.
- [x] Migration API/implementation remains absent.

## Exact format

- [x] Profile encoding, capability order, bounds, digest domain, and digest are
  frozen.
- [x] Metadata stores the complete profile and digest.
- [x] Checkpoint, checkpoint manifest, and WAL header bind the metadata digest.
- [x] WAL frames declare the owning minor and retain published framing semantics.
- [x] Backup `1.1` retains three members and uses the new `v2` digest domain/identity.
- [x] Published `1.0` parsing and writing remain unchanged.
- [x] Production and independent parsers accept the same immutable exact bytes.

## Inspection and classification

- [x] Live inspection is synchronous, codec-free, read-only, and exclusive.
- [x] Backup inspection is synchronous, codec-free, read-only, and permits readers.
- [x] CRC-valid unsupported/incompatible declarations are retained in reports.
- [x] Missing or checksum-invalid declarations remain absent rather than guessed.
- [x] Higher minor, unsupported family/major, unknown intact profile, mixed minor,
  malformed profile, checksum damage, and profile mismatch are distinct.
- [x] Unknown profiles remain inspectable while member-binding disagreement takes
  corrupt precedence.
- [x] Before/after directory SHA-256 maps prove inspection does not mutate bytes.

## Published V4.1 feasibility correction

- [x] Exact fixtures are executed in a child JVM containing only the checksum-pinned
  published `4.1.0` artifact.
- [x] The probe proves exact extended live and backup `1.1` bytes fail closed as
  `CORRUPT` before the old higher-minor policy is reached.
- [x] Phase 0/charter wording is corrected to require fail-closed rejection rather
  than an impossible exact status from an immutable artifact.
- [x] Untouched-source rollback remains exact `1.0` and is unaffected.

## Local acceptance

- [x] Focused Java format, V4.1 structural regression, and public fixture tests pass.
- [x] Independent Python encoder/parser and corruption tests pass.
- [x] Full reactor tests pass: `484` core tests and `5` processor tests, with no
  failures or errors.
- [x] Published artifact compatibility, Japicmp, pinned checksums, and the isolated
  V4.1 probe pass.
- [x] V1/V2/V3/V4 consumers, six release artifacts, Javadocs, bounded JMH smoke,
  two-build byte reproducibility, and whitespace gates pass.
- [x] CI runs the exact Phase 2 shell/Python gate in both the reactor and no-GCP
  lanes.

## Protected acceptance

- [ ] Phase 2 pull request passes all required checks.
- [ ] Phase 2 merges to protected `master`.
- [ ] Exact protected-master commit and CI run are recorded.

Phase 3 may begin only after protected acceptance. It owns explicit fresh `1.1`
creation/open/write, exact-format backup/restore continuation, and format-only
`1.0`-to-`1.1` migration; Phase 2 does not authorize them.
