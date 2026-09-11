# GeneralSearchEngine V4.4 Phase 5 stabilization baseline

- **Status:** Accepted through protected PR #138
- **Phase 4 protected merge:** `263883b832413d0c9f1c5f20b2f8fbec444a2f98`
- **Phase 4 exact-master CI:** `34646352576` (`success`)
- **Phase 5 protected merge:** `e47e60472939cb8331d4d96302acf3d818622266`
- **Phase 5 exact-master CI:** `34649742450` (`success`)
- **Exact-master canonical artifact:** `v44-canonical-reproducibility-e47e60472939cb8331d4d96302acf3d818622266`
- **Product/API/format/authority change:** None
- **Paid cloud execution / IAM mutation / registration:** None

## Stabilized gates

Phase 5 binds the full V4.4 local matrix and zero-change admission to the published
4.3 API/behavioral control, all independent consumers, release packaging, Javadocs,
strict evidence validators and the existing V4 regression suite. The Phase 4 result
remains `PASS_NO_MEASURED_REGRESSION`; no product correction or optimization is
introduced.

The canonical supply-chain lane uses the digest-pinned Linux/amd64 Eclipse Temurin
`21.0.12+8` image, Maven Wrapper `3.9.11`, `C.UTF-8`, UTC and umask `0022`. Two clean
source workspaces build independently inside that exact container. Their two POMs and
six unsigned main/sources/Javadoc JARs must have identical SHA-256 inventories. The
checksummed result is written under `target/v44-canonical-reproducibility/`; it is
candidate-build evidence, not yet the Phase 7 hash record or Phase 8 Central proof.
The Maven ZIP is downloaded once, checked against the frozen Wrapper SHA-256, mounted
read-only, checked again inside each container and extracted with the JDK `jar` tool.
This avoids dependence on a host Maven cache or an `unzip` package absent from the
minimal image. The extracted launcher is invoked explicitly through `bash` because
JDK extraction does not restore its executable bit; no mutable package installation
is permitted in the canonical lane.

The [cloud readiness contract](PHASE_5_CLOUD_READINESS.md) adds a manual-only,
trusted-master-only, serial replacement-host workflow plus strict member/set
validators and no-GCP dry-run coverage. The workflow exists for Phase 6 but is not
executed in Phase 5. IAM remains unchanged until the user separately reviews and
authorizes the exact workflow/prefix conditions.

The [V5 handoff](V5_HANDOFF.md) records inherited guarantees, supported formats,
known limits and explicitly deferred architecture without claiming pending release or
cloud identities.

Phase 4 entered protected `master` through PR #137. Exact-master CI run
`34646352576` passed on merge commit
`263883b832413d0c9f1c5f20b2f8fbec444a2f98`, satisfying the final Phase 5 entry
condition.

Run the aggregate local gate with:

```bash
scripts/verify-v44-phase5-stabilization.sh
```

The aggregate gate builds through Maven `package` (with tests enabled) because its
closed-surface API check consumes the resulting main JAR; a clean `test` lifecycle is
not sufficient to create that input.

Phase 5 entered protected `master` through PR #138 as
`e47e60472939cb8331d4d96302acf3d818622266`. Exact-master CI run `34649742450`
passed. Its canonical artifact ID `10283910457` contains a checksummed receipt bound
to that exact merge commit and records `EXACT_UNSIGNED_BYTE_IDENTITY` for two clean
workspaces, six JARs and two POMs.

All repository-controlled Phase 6 entry gates are now accepted. Paid execution still
requires user-reviewed WIF/IAM/budget checks and explicit user initiation.
