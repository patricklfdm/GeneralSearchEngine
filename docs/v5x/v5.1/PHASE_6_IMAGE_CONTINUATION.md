# Frozen image policy and one-batch native continuation

**Status:** all five authorized members completed successfully by 2026-10-13.
PR #319 source `7100b61e752647c52246cc86f2887fefa00821ea` passed exact CI
`38339508687`, attempt 2 (46 jobs). Its canonical-3, experiment and failure-drill
completed on the replacement sequence. The completion audit is PASS, with USD 250
cumulative reservations and no active lease/PENDING entry. The separate
[raw-set review and baseline candidate](PHASE_6_NATIVE_SET_ACCEPTANCE.md) must
receive protected acceptance before formal Phase 6 closure.
Only this batch may inherit the two pinned original canonical members. Subsequent
batches retain their normal same-source/same-sequence requirements.

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
| canonical-3 | [38346492463](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38346492463), attempt 1 | `7100b61`, replacement sequence |
| experiment | [38363263163](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38363263163), attempt 1 | `7100b61`, replacement sequence |
| failure-drill | [38372566659](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38372566659), attempt 1 | `7100b61`, replacement sequence |

Original source: `f46f9a4ea624df2b42902efd0b633c30933ae2f2`.
Original sequence: `eb7859da90c94c468215f2867638b0bf`.
**Only authorized continuation sequence: `c4d557b802ec49cd843081326608becb`.**
Use `any-order`; the three remaining members can run in any order. Do not run
canonical-1/2 again or place inherited reservations into the new ledger sequence.

The policy pins both original request hashes and completion/evidence/inventory
hashes. Both historical runs passed all fifteen cells, 1080 measured calls,
independent physical/history and backup replay, immutable retention and cleanup
of thirteen exact resources. Their original ledger entries remain PASS.
Local replay of the retained completion records confirms these bindings; it
does not rerun their raw physical traces or constitute new cloud execution.

### Failed canonical-3 and replacement sequence

[CI 38324679812](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38324679812)
passed all 46 jobs on source `50a4fae2f0af7479ba42cb11409234b9ddf825a6`.
[Prepare 38329864714](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38329864714)
passed the new-source package comparison. Then
[run 38330325048](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38330325048),
attempt 1, failed with `RUNTIME_RETRY_EXHAUSTED` while configuring node 1's
published V5.0 control for healthy window `instrumented-b`. The retained command
store has no claim/start/terminal record for that command; its offline query
returns NOT_FOUND. All 140 preceding V5.0 workload calls succeeded and all three
worker stderr files were empty. Per-exchange transport errors and query replies
were not retained, so the exact SSH/IAP interruption cause is undetermined.
The candidate V5.1 workload had not started. No runtime defect is established
by this evidence; this correction changes only the batch mapping, its pinned
test and documentation.

The failed request remains
`9948e0c79a154419ffa04ddef34815d6edd089ae421aa5354eac1641ed2dda94`, on superseded
sequence `68efdd6b99df497fb1b1dd6d87947fb4`. Retention was VERIFIED and exact
cleanup passed for all thirteen resources. The last authenticated control
observation has no active lease or PENDING attempt and USD 175 reserved,
including this failed attempt's USD 25. This accounting is not an actual bill.

The existing ledger rejects reuse of a failed canonical sequence with
`sequence changed/failed canonical set`. The operator authorized a fresh
continuation sequence for the same remaining three members. Only the new
sequence above is eligible; the failed sequence contributes no accepted member
and remains charged. The inherited requests, completion hashes, payload pin,
closed source-change allowlist and normal failed-sequence rule stay unchanged.
All three remaining members must use the next corrected source and new sequence.
Subsequent batches still require their normal single source/sequence.

Retained diagnosis: `target/v51-canonical-failure-38330325048/`.
Local replacement audit: `target/v51-continuation-retry/`. The previous prepared
plan and approval were used and cannot authorize the next attempt.

Replacement validation passed all fifteen image/continuation tests and all
69 Change scope tests. Offline replay of the retained ledger and completion
metadata confirms both historical members, the failed completion hash, USD 175
accounting and rejection of the superseded sequence. Pure local reservation
simulations allow each remaining member to start the new sequence; they neither
write the ledger nor qualify a paid attempt. All ten approved script hashes and
the unchanged closed path list match the working tree. Committed-source and
prepared-package checks remain required after merge.

## Compatibility and acceptance boundary

`scripts.v51.native_image_continuation` is an explicit offline audit tool, outside
normal admission. It never writes cloud objects, migrates receipts, resets the
ledger, grants paid admission or relaxes normal sequence identity checks.

1. The corrected source must descend from the old source. A closed path list and
   approved script hashes allow only this image repair, audit, tests and docs,
   including the exact `scripts/test_ci_v51_python.py` inventory correction below.
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
   remain recorded. Reservations were USD 150 after canonical-2 and USD 175
   after the failed canonical-3; this is conservative accounting, not an invoice.
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

Receipts and logs: `target/v51-image-continuation/`. CI and the prepared package
subsequently passed on `50a4fae`; the replacement mapping still requires CI and
actual package verification on its own merged source. Those checks subsequently
passed on `7100b61` for prepared runs `38345952012`, `38362642098` and `38371664898`;
their native runs are recorded above.

### Change scope inventory follow-up

Manually dispatched [CI 38323762567](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38323762567)
on merged source `6faae5cec54a70be1cfb0598e6be7e57e9f3a054` failed before
classification. The preflight script already ran `test_cloud_image_policy` and
`test_native_image_continuation`, but its independent expected-module list in
`scripts/test_ci_v51_python.py` omitted them. The same test failed locally;
rerunning the unchanged source would not repair this inventory mismatch.

The follow-up adds exactly those two module names and pins the corrected test
file in the continuation policy. Exact module identity/multiplicity and full
versus split command/timeout checks remain active. That inventory correction
preserved historical member records, the then-current continuation sequence,
payload comparison and runtime bytes.
All 69 tests from the exact Change scope command and all 15 focused image and
continuation tests pass locally. Logs: `target/v51-preflight-ci-inventory/`.
It was accepted by CI `38324679812` on `50a4fae`. The replacement-sequence
correction above must separately pass CI on its final merged source.

## Operator procedure after merge

This procedure was completed for the five runs above; it is retained for audit,
not an instruction to rerun them. The operator runs commit/push/PR/merge and every
paid dispatch. From the clean,
synchronized corrected master checkout (with original source history available):

```bash
mkdir -p target/v51-image-continuation
continuation_review_dir=$(mktemp -d target/v51-image-continuation/post-merge.XXXXXX)
python3.11 -m scripts.v51.native_image_continuation source \
  --source "$(git rev-parse HEAD)" \
  --output "$continuation_review_dir/source.json"
```

Require a successful CI run for that exact master source, including its build
and package artifacts. If the merge used a CI-skip directive, dispatch
`gh workflow run ci.yml --ref master` manually after synchronization.
Then run manual cleanup for that source, refresh the quote if expired, and prepare
canonical-3 using the new sequence above. Download/authenticate its prepared
artifact using the existing producing-run review. Before approving execution:

```bash
python3.11 -m scripts.v51.native_image_continuation prepared \
  --source "$(git rev-parse HEAD)" --prepared PATH_TO_AUTHENTICATED_PREPARED_DIRECTORY \
  --output "$continuation_review_dir/canonical-3-package.json"
```

Use fresh approval for each remaining member and perform the same package check
for experiment/failure-drill. Preserve their prepared directories. Neither the
failed old-source prepare nor the used canonical-3 plan/approval is reusable.

After reconciliation, collect current generation-pinned control/completion
metadata with the already configured local read identity. This command only
reads exact objects; it does not run experiments or clean resources:

```bash
python3.11 -m scripts.v51.native_image_continuation collect \
  --source "$(git rev-parse HEAD)" \
  --output "$continuation_review_dir/observations.json"
python3.11 -m scripts.v51.native_image_continuation review \
  --source "$(git rev-parse HEAD)" \
  --observations "$continuation_review_dir/observations.json" \
  --prepared canonical-3=PATH_TO_CANONICAL_3_PREPARED \
  --prepared experiment=PATH_TO_EXPERIMENT_PREPARED \
  --prepared failure-drill=PATH_TO_DRILL_PREPARED \
  --output "$continuation_review_dir/batch-review.json"
```

For an interim review, supply prepared directories only for new PASS members.
Use new output filenames for each observation; receipts are never overwritten.
Archive the original member evidence together with this mapping for final review.
