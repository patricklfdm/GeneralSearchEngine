# Phase 2 — exact bootstrap commit metadata

Status: **private metadata derivation qualified locally; Phase 2 OPEN**.

`MembershipBootstrapCommitMetadata` derives the original preparation inventories,
four BOOTSTRAP decisions, coordinator receipt and local seals from an exact
metadata-only plan. It shares the initial layout with the full image-backed path.
`MembershipBootstrapCommitData` delegates these bytes and accounting, and still
supplies the verified actual application image to the transaction. No write,
force, publication order or private byte format changes.

The decoder does not access original filesystem paths or load application bytes.
It can account for all five targets declaring 64 MiB images without allocating
those images. It checks the complete operation bound, including both plan copies,
coordinator image, candidate/active receipt, all decisions and target payloads,
preparations and candidate/active seals. Returned byte arrays are defensive copies;
target and identity collections are immutable.

Deterministically deriving a COMMITTED row or receipt does **not** establish that a
transaction occurred. This helper is neither a durable admission reader nor a
permission to initialize or open a replica. The existing transaction still owns
all original-byte, path, force, ownership and typed/source boundary checks.

## Validation

[Source/build evidence](phase2-evidence/bootstrap-commit-metadata.json) retains the
exact inputs, JARs, producer classes, logs and raw evidence indices. The pinned
106,420-byte test fixture was extracted from the accepted original coordinator
run in commit `a66bd08`, after verifying its retained file inventory and independently
deriving its original transaction bytes. It records six size/source profiles and
all 24 local preparation/seal hashes; the new encoder did not generate the expected
values. No image is embedded in the fixture.

Five focused tests cover those original bytes, agreement with real EMPTY/backup
plans at sizes 3/4/5, inspection after moving the entire original workspace, exact
completion capacity with five maximum declared images, and defensive copies.
The existing coordinator, layout and twice-interrupted transaction suites are
also run. The unchanged independent Python coordinator/transaction replays check
actual original images, all final authority and force order, exact negatives and
portable replay under normal and optimized Python. These checks do not establish
power-loss behavior or a new process-crash qualification.

## Next admission boundary

Copying the entire plan to each voter is not the next implementation: the plan's
2 MiB bound cannot share the existing 2 MiB MISC reservation with runtime
maintenance. In particular, source retirement can retain 1,138,688 bytes and a
compact journal can retain 565,248 bytes before accounting for other local
metadata. The next admission representation must retain the original compact
commit/receipt/local-preparation bindings, then prove its combined completion
headroom. It must not add a second MISC reservation, lower unrelated frozen limits,
or rely on the original application image surviving later runtime compaction.

Self-contained local admission publication/recovery, complete-store opening,
post-runtime result inspection, full typed coordinator process qualification and
the remaining lifetime/physical requirement audit remain pending. Public bootstrap
and runtime remain disabled; no cloud, workflow, POM or frozen catalog change.
