# V5.2 native original evidence retention

Phase 6BF connects the [whole-member scope](PHASE_6_NATIVE_MEMBERS.md) to immutable
evidence storage and the existing exact-ID cleanup/ledger path. This is local
pre-cloud implementation. There is still no paid Runner CLI, protected operator
workflow or accepted five-member cloud set.

## Original capture and bounded storage

`Session.run_member` creates an in-memory capture only after every selected
history passes original and relocated replay and its guest scope closes cleanly.
`Session.retain_member` consumes that capture once. A copied execution receipt,
resource-only Session, incomplete history list or failed guest close cannot enter
retention. The same live source/input handle and stable resource claim are checked
before collection, during uploads and after the final read-back.

Collection selects only the original input package, original protected-build
provenance, original recent-cleanup evidence, member receipt, per-history archives
and results, and public admission/host/storage/installation bindings. It excludes
SSH private keys and credential files. Retained build provenance is replayed at
its original admission observation time; a long workload does not renew admission
or incorrectly expire an already admitted build.

The storage format has a closed, sorted file inventory. Each 4 MiB binary part is
encoded as JSON with the request hash, complete manifest hash, original ordinal,
size and content hash. The existing 8 MiB provider object bound remains sufficient.
There are at most 256 files and 54 GiB of total original bytes: thirteen existing
4 GiB bounded history archives plus provenance. Individual files still obey the
existing 4 GiB compressed-archive bound. These are parser/resource ceilings, not
new workload parameters. Links, missing/extra parts, reordered files, directory
collisions, changed bytes and another request's parts are rejected.

Objects are confined to the original request's `evidence/` prefix. Each immutable
manifest/part is submitted once with `ifGenerationMatch=0`, then read back at its
returned generation. An uncertain reply permits at most three queries for that
original write; it never resubmits the upload. Unresolved or partial retention
fails promptly and leaves the original evidence visible. No history is rerun.

The retained status is `EVIDENCE_RETAINED_AWAITING_CLEANUP`. Stage changes and the
existing 60-second heartbeat expose progress. Overall time and cost remain soft;
original exchange, lease, grace, query and parsing bounds remain enforced.

## Completion and reconciliation

Only complete read-back creates an in-memory retention certificate bound to the
original native API instance and request. The existing cleanup path may write a
member `PASS` completion only when its retained cleanup proves all original
resource IDs absent, its original manifest generation is unchanged, and that live
certificate still belongs to the same Session. The terminal ledger event follows
immutable completion; lease release follows terminal accounting and fresh absence
checks. The reserved cost is preserved.

Execution-only, partial evidence or failed cleanup retains `FAIL`. Later manual
or scheduled cleanup can remove leftovers but cannot upgrade that failed member.
If immutable `PASS` was already written and ledger/release was interrupted,
reconciliation can finish accounting and release using that exact original
completion. A cleanup process cannot mint a new `PASS` from copied JSON or an
unclaimed evidence prefix. A fully uploaded member interrupted before its original
completion remains conservatively failed.

Member completion is not full cloud qualification. The independent portable
validator must still authenticate original authority/build/input bindings, replay
all complete histories, correlate cleanup and ledger, and require the five
members from one source and sequence in any execution order. The protected
workflow and actual configuration/identity review remain open as well.

## Local validation

`test_cloud_evidence_parts` and `test_cloud_retention` join the existing measurement
unit gate. They cover part/inventory mutations, original capture drift, bounded
wire scope, upload-response loss, partial uploads, cleanup failure, changed
manifest generation and interrupted terminal accounting. Native factory tests use
modeled external provider/auth/build/workload I/O and do not qualify GCP behavior.

The storage round-trip also uses the unchanged earlier local SSH/JVM smoke and
SIGKILL history archives. It restores identical bytes without rerunning those
histories or relabeling them as this source's native evidence. Original logs and
scope-separated results are retained under `target/v52-native-retention`.
Corrected-source protected CI and native cloud qualification remain pending.
