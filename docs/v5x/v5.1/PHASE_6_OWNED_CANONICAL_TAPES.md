# V5.1 owned canonical tapes

**Status:** offline implementation candidate; corrected-source protected CI is
required. This is the rich-tape slice of the
[full-preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md), following accepted
PR #308 / master CI `37837221623` for the complete twelve-cell failure drill.

## Frozen execution

| Mode | Cell | Calls | Measured seconds |
| --- | --- | ---: | ---: |
| published V4.4 local | healthy | 260 | 260 |
| published V5.0 configured | healthy | 260 | 260 |
| candidate V5.1 automatic | healthy | 260 | 260 |
| candidate V5.1 automatic | read-heavy | 120 | 120 |
| candidate V5.1 automatic | sustained | 180 | 180 |

The five tapes retain all 1080 calls and 1080 seconds from the frozen machine
plan. Healthy retains warmup and the four ABBA windows. Concurrent tapes keep
four persistent JVM lanes, original guest-clock arrivals, 250 ms lateness,
10 ms burst spread and the original drain budget. No resubmission of calls or
measurement retries are added. A lost SSH submit reply queries its original
command claim; all attempted JVMs still close and retain failure evidence.

An explicit `workload` field binds the canonical cell and preset into the
offline service configuration. Missing selection retains the existing experiment
contract. Native configuration rejects the new selection, as do fault services,
unknown cells, configurable durations and concurrent published controls. The
owned probe checks the selection against the admitted configuration and requires
physical history plus backup/restore for both replicated modes.

## Independent evidence

Replay derives the expected windows and call count from that closed selection.
Concurrent pipe arrival and response order may differ from ordinal order. Replay
requires exact ordinal coverage and binds each request, original operation ID,
response digest, dispatch interval, API interval and durable command receipt.
It rejects duplicate/missing ordinals and cannot promote the shorter experiment.
Concurrent tapes also require actual cross-lane Java API overlap. Configured
retained sequence comes from the selected frozen program: 76 for the reduced
experiment and 212 for full healthy, never from a guest-reported final value.

The static model checks serialized healthy answers. It only computes the final
projection for concurrent tapes; it does not certify concurrent read semantics.
Those reads still require the independent physical oracle: unique post-invocation
barrier, actual captured published prefix, original release and exact answer.
The original ten automatic history negatives, configured-history negatives,
resource samples, retained authority inventories and backup restore checks remain
required. An evidence-only logical pass is not full physical qualification.

Full tapes use the existing rich plan's 128-MiB **stored** trace bound per node
and cell, 32-MiB members, 4-MiB logical rows and shared 6-GiB decoded trace budget.
Joint physical replay shares that budget across all three members, including its
logical and physical passes. Reduced experiment checks retain their stricter
128-MiB decoded member bound. These are the existing two scopes, not changes to
the frozen machine plan. Local qualification retains all stopped collections
before validation, so a bad member does not hide the others' original evidence.

## CI and local entry points

`v51-owned-canonical-tapes` is a five-entry matrix depending on the existing
exact-source verification build. Each job restores that immutable build, packages
the guest, and runs one whole tape through real loopback SSH and independent
mount views. Each keeps its own package/provenance/failure artifacts. Matrix
fail-fast is disabled; Required rejects any unsuccessful matrix result. Docs-only
skips are preserved. No repeated Maven build or paid cloud permission is added.
The read-only cloud preflight's closed CI inventory explicitly expands these five
reviewed names and rejects changed cells, modes or extra matrix dimensions. A
missing, skipped or failed tape cannot disappear from the exact-attempt review.

```bash
python3 -m scripts.v51.guest_owned_qualification target/canonical-tape \
  --bundle target/guest-package --source "$(git rev-parse HEAD)" \
  --canonical-cell healthy --mode candidate-v5.1-automatic \
  --allow-sudo-namespace
```

Where mount namespaces are unavailable, `scripts.v51.guest_qualification` accepts
the same canonical cell/mode flags to verify the packaged real JVM tape and
physical evidence using shared local paths. That receipt explicitly reports
`shared-local`; it cannot replace the owned independent-mount CI gate.

## Remaining acceptance

These jobs are independent component qualifications. Their modeled requests are
still experiment-shaped offline lease fixtures; neither individual nor combined
green jobs form a canonical cloud member. All receipts retain
`fullRemoteQualification=false`. They do not share a source backup/lease across
jobs and cannot be combined as the final fifteen-cell aggregate.

Next implement repetition-bound control placement and one immutable shared seed
with distinct group identities in the complete canonical aggregate. Then review
native preset request/configuration/lease/pricing/time admission and run the new
same-source five-member cloud set with explicit approval. The native experiment
entry, USD 200 ceiling and cleanup requirements are unchanged.
