# Phase 2 — bounded read-only bootstrap recovery checks

Status: private integration locally qualified; **Phase 2 remains OPEN**.
The [export-based revalidation](PHASE_2_BOOTSTRAP_REVALIDATION.md) establishes the
actual source/image relationship. `MembershipBootstrapRecheck` now allows recovery
to validate that relationship using the original retained planning exports without
allocating another set of scratch directories.

## One retained projection

The caller retains the planning projection: exactly one `application-N` directory
per target, each containing the three original core backup members. The helper
requires the exact original request, application/index/core descriptors, source
inventory and path bindings. It checks all materialization directories remain
absent and refuses projection aliases, links, unknown members and missing bytes.

For every target it uses that target's real codec to read the unchanged source and
the original planning backup. The core reader checks key/document round trips.
The normalized planning image must equal the image in the original exact plan;
source sequence/indexes and distinct original/new history are also checked. No Java
document `equals` result substitutes for canonical encoding checks.

Member hashes, directory/file identities and path bindings are checked around the
callbacks and again before return. These are per-invocation mutation checks;
derived exports do not acquire authority merely through an inode or filename.
The function performs no writes, allocates no new history, and never repairs or
deletes invalid retained files. It counts the entire actual retained projection
with the full transaction completion reserve before invoking the typed reader.
The returned byte count does not include the separately bounded input source.

The transaction remains responsible for exclusive coordinator/replica ownership,
original decisions, forced receipts and local seals. This helper is called under
that owner; it does not independently claim ownership of live replicas.

## Local qualification

The [source/build/raw index](phase2-evidence/bootstrap-recheck.json) records six
Java tests. The successful matrix covers EMPTY and real backup at 3/4/5 voters.
Each case interrupts the transaction after PREPARED, resumes under the same plan,
and runs two additional read-only checks after completion. All **24 typed checks**
reuse **24 original target exports**, with unchanged projection hashes/inodes and
unchanged authority during each callback.

Rejections cover missing, changed, extra and linked projection members, same-name
codec behavior drift, changed configuration/source, byte-identical source or export
replacement during decode, exact full-completion-plus-projection capacity, aliases
and occupied materialization directories. Invalid files remain inspectable.

Independent replay checks original plan/image/source, all normalized projection
bytes, exact completion reserve, and every final target's original payload,
preparation and seal together with the four coordinator decisions and receipt.
Fourteen exact-reason evidence negatives, relocated replay and normal/optimized
Python pass. The oracle checks retained byte relationships; it does not independently
establish callback execution, absence of writes or arbitrary codec semantics.

```bash
python3 -m scripts.v53.bootstrap_recheck_evidence <v53BootstrapRecheckEvidence-directory>
python3 -O -m scripts.v53.bootstrap_recheck_evidence <v53BootstrapRecheckEvidence-directory>
```

## Remaining integration

The public planner must bind the location of this retained projection to its
operation and preserve it across recovery. Public random-history planning,
complete-store seal admission/accounting and result inspection after mutable
runtime progress remain pending. Public entry points stay disabled. No new
process-death, power-loss, protected CI, cloud or Phase 2 closure claim is made.
