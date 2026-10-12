# Frozen image policy and one-batch native continuation

**Status:** local correction, 2026-10-12; corrected-source protected CI is pending.
The operator explicitly authorized this one batch to reuse canonical-1 and
canonical-2. Subsequent phases/batches continue to require one source and one
sequence. The native five-member set and Phase 6 remain incomplete.

## Failure and image policy

[Prepare 38319063804](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38319063804)
failed both attempts in observer admission; Runner execution was skipped. Its
frozen image still had name `ubuntu-2404-noble-amd64-v20260918`, ID
`763874002631433611`, status READY and architecture X86_64. The publisher had
marked it DEPRECATED and suggested `ubuntu-2404-noble-amd64-v20261009`.
The old observer and Runner permission checks rejected any deprecation metadata.

Google permits explicit use of DEPRECATED images with a warning; OBSOLETE and
DELETED images cannot be used for new requests.
[Provider semantics](https://docs.cloud.google.com/compute/docs/images/deprecate-custom#deprecation_states).
Both admission checks now share this policy:

| Observation | Result |
| --- | --- |
| Exact name/ID, READY, X86_64, absent deprecation or ACTIVE | PASS |
| Same identity/readiness with DEPRECATED | PASS with visible warning |
| OBSOLETE, DELETED, unknown/malformed state | BLOCKED |
| Changed/missing identity, readiness or architecture | BLOCKED |

The original explicit image URL stays frozen. No family lookup or replacement
selection occurs. Permission evidence retains only the deprecation state; raw
descriptions, replacement text and other provider fields are not copied into it.
Fresh same-run observations, actual disk image-ID checks, credentials and
required permissions still apply. This fixes the deprecation blocker, not every
possible provider failure.

## Authorized batch

The machine policy is [native-image-continuation.json](native-image-continuation.json).

| Member | Original run | Source/sequence |
| --- | --- | --- |
| canonical-1 | [38280933954](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38280933954), attempt 1 | original source and sequence |
| canonical-2 | [38300809738](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38300809738), attempt 1 | original source and sequence |
| canonical-3 | pending | corrected source, new sequence |
| experiment | pending | same corrected source and new sequence |
| failure-drill | pending | same corrected source and new sequence |

Original source: `f46f9a4ea624df2b42902efd0b633c30933ae2f2`.
Original sequence: `eb7859da90c94c468215f2867638b0bf`.
**Only authorized continuation sequence: `68efdd6b99df497fb1b1dd6d87947fb4`.**
Use `any-order`; the three remaining members can run in any order. Do not run
canonical-1/2 again or place inherited reservations into the new ledger sequence.

The policy pins both original request hashes and completion/evidence/inventory
hashes. Both historical runs passed all fifteen cells, 1080 measured calls,
independent physical/history and backup replay, immutable retention and cleanup
of thirteen exact resources. Their original ledger entries remain PASS.
Local replay of the retained completion records confirms these bindings; it
does not rerun their raw physical traces or constitute new cloud execution.

## Compatibility and acceptance boundary

`scripts.v51.native_image_continuation` is an explicit offline audit tool, outside
normal admission. It never writes cloud objects, migrates receipts, resets the
ledger, grants paid admission or relaxes normal sequence identity checks.

1. The corrected source must descend from the old source. A closed path list and
   approved script hashes allow only this image repair, audit, tests and docs.
   Engine, workload, workflow, POM, timing and provider configuration edits fail.
2. Every new prepared package is authenticated and safely unpacked. All payload
   file paths, hashes, sizes and executable bits must equal the old package,
   including JARs, compiled adapters, JDK, guest Python and workload.
   `ci-build-manifest.json` is excluded from payload comparison. In
   `startup-helper.json`, only the `source` field is normalized for comparison,
   after checking it against the package source; every embedded file stays exact.
   Original checkout/source/CI bindings remain separately verified and are never
   rewritten in either package or stored evidence.
3. Each member keeps its own request, source, sequence, original retained records
   and terminal ledger hash. Exactly two pinned inherited members and three new
   members on one corrected source/sequence are eligible. Wrong, duplicate,
   incomplete, failed or tampered members cannot establish completion.
4. Current ledger/lease observation must be reconciled. Completion audit checks
   native execution, physical/history results, applicable backup qualification,
   exact cleanup and evidence inventory bindings. Historical failures and costs
   remain recorded. At the last observed canonical-2 completion, cumulative
   reservations were USD 150; this is conservative accounting, not an invoice.
5. A two-/three-/four-member review reports PARTIAL. Five eligible PASS members
   report `batchComplete=true` in this **one-batch completion audit**. It still
   reports `fullRemoteQualification=false`: final raw evidence review and Phase 6
   acceptance are separate. No new cloud performance claim is made by this patch.

If a runtime/workload/image change becomes necessary, this frozen continuation
fails compatibility checks and needs a new explicit decision. It is not a
general permission to mix arbitrary green runs across releases.

## Local validation

- Complete preflight admission lane: 302 tests plus original-artifact, provider,
  identity/permission and generated-deployment qualifications passed.
- Thirty CI path-selection tests, documentation contract, changed local links
  and whitespace checks passed. The final fifteen focused image/continuation
  tests were rerun after refining the helper source-field comparison.
- Original failed prepare observations reproduce BLOCKED in both old checks and
  PASS with warning in both corrected checks. Unusable-state mutations reject.
- Both pinned historical members replay as valid completion records; the batch
  remains PARTIAL. The original authenticated package has 172 byte-exact files
  and one source-normalized helper in the 173-file comparison. A diagnostic
  source-only change preserves this comparison; helper program changes do not.

Receipts and logs: `target/v51-image-continuation/`. New-source protected CI and
the actual new-source prepared package still require verification after merge.

## Operator procedure after merge

The operator runs commit/push/PR/merge and every paid dispatch. From the clean,
synchronized corrected master checkout (with original source history available):

```bash
mkdir -p target/v51-image-continuation/post-merge
python3.11 -m scripts.v51.native_image_continuation source \
  --source "$(git rev-parse HEAD)" \
  --output target/v51-image-continuation/post-merge/source.json
```

Then run manual cleanup for that source, refresh the quote if expired, and prepare
canonical-3 using the new sequence above. Download/authenticate its prepared
artifact using the existing producing-run review. Before approving execution:

```bash
python3.11 -m scripts.v51.native_image_continuation prepared \
  --source "$(git rev-parse HEAD)" --prepared PATH_TO_AUTHENTICATED_PREPARED_DIRECTORY \
  --output target/v51-image-continuation/post-merge/canonical-3-package.json
```

Use fresh approval for each remaining member and perform the same package check
for experiment/failure-drill. Preserve their prepared directories. The failed
old-source canonical-3 prepare is not a reusable approval.

After reconciliation, collect current generation-pinned control/completion
metadata with the already configured local read identity. This command only
reads exact objects; it does not run experiments or clean resources:

```bash
python3.11 -m scripts.v51.native_image_continuation collect \
  --source "$(git rev-parse HEAD)" \
  --output target/v51-image-continuation/post-merge/observations.json
python3.11 -m scripts.v51.native_image_continuation review \
  --source "$(git rev-parse HEAD)" \
  --observations target/v51-image-continuation/post-merge/observations.json \
  --prepared canonical-3=PATH_TO_CANONICAL_3_PREPARED \
  --prepared experiment=PATH_TO_EXPERIMENT_PREPARED \
  --prepared failure-drill=PATH_TO_DRILL_PREPARED \
  --output target/v51-image-continuation/post-merge/batch-review.json
```

For an interim review, supply prepared directories only for new PASS members.
Use new output filenames for each observation; receipts are never overwritten.
Archive the original member evidence together with this mapping for final review.
