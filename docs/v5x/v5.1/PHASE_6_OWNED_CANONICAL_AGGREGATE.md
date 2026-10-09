# V5.1 complete owned canonical qualification

**Status:** offline implementation candidate. Corrected-source protected CI is
required for all three repetitions. The five component tapes were accepted in
PR #309, master `6d7273f5861f02d13c442dad76a80dde273a6e0c`, CI `37863567136`.
This batch implements step 3 of the [native preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).
It does not enable a paid canonical preset or close Phase 6.

## One repetition and one lease

Each repetition runs the frozen fifteen cells, in order, under one offline
modeled request/lease and one authenticated package per physical node. Healthy
contains three modes; read-heavy and sustained each contain the automatic mode;
the remaining twelve cells reuse the accepted owned failure-drill implementation.
There are seventeen fresh groups and directories, thirteen rich-tape service
members and thirty-six fault-cell service members. Each tape closes all its
voters before the next tape starts. Failed or uncertain work remains consumed.

| Repetition | V4.4 source producer and local issuer | V5.0 configured leader | V5.1 leader |
| --- | --- | --- | --- |
| 1 | node-1 | node-1 | observed automatic election |
| 2 | node-2 | node-2 | observed automatic election |
| 3 | node-3 | node-3 | observed automatic election |

Physical node identities and endpoints are preserved. The configured control's
`control-node.txt` is included in the sealed topology and its public bootstrap
manifest must contain that leader. Other V5.0 consumers retain their original
node-1 default. Automatic leadership is never forced to the control host.

The closed offline selection adds integer repetition 1, 2 or 3 to the five
existing rich tapes. Their directories are
`canonical-r<N>-<cell>-<mode>` and group IDs bind request plus directory.
Standalone tape directories and reduced experiment placement remain unchanged.
The trusted package, producer, transfer and bootstrap receivers all use that
selection. The native guest still rejects it.

## Immutable source and original execution

Exactly one published V4.4 backup is produced on the selected control host and
independently decoded before every export. All thirteen rich receivers import
identical backup bytes and perform their own public bootstrap and filesystem
seal. Source transfer claims distinguish cells within one attempt. Qualification
hides the remote producer exports after the original authenticated download;
subsequent transfer and replay cannot rely on the producer's live directory.

Fault cells retain their specified EMPTY genesis and two-field model. They do
not import the rich corpus. Every group has a distinct request-bound identity.
Persistent command IDs, original claims, lossy-reply observations, fault cuts,
negative mutations and clean shutdown checks remain mandatory. Observer retries
never repeat a workload, bootstrap, source production or package installation.

## Complete independent replay

`guest_canonical_evidence` accepts the complete original raw set and independently
checks request/package identity, repetition, fixed physical topology, seventeen
distinct groups, fifteen non-overlapping cell intervals and per-mode close
barriers. It reopens every original command request, receipt and observation;
cached PASS summaries cannot replace raw inputs.

All thirteen rich collections are unpacked and replayed. Replicated genesis
must reference the common source bytes. Configured manifests and original
force/publication/read histories bind the rotated leader. Automatic concurrent
reads still require the existing physical captured-prefix oracle. All four
replicated rich tapes retain backup/restore validation and evidence negatives.
All twelve fault cells invoke the original independent fault replay and negatives.

The complete coordinator collects original parts without qualifying individual
tapes first. After collection it stops the idle guest services, then runs one
independent aggregate in a separate process. For replicated tapes, the joint
physical validator already performs every member's logical, receipt, backup and
inventory checks; its freshly computed member results provide the aggregate's
logical reports. No stored PASS result substitutes for a check. Standalone tape
entry points retain their complete validation path.

The aggregate enforces combined stored byte/file ceilings and one shared decoded
trace budget across rich logical/physical passes and fault traces. The original
per-node/per-cell limits also apply. It requires 1080 rich calls and all original
1080 measurement seconds; only a complete repetition can report
`ownedCanonicalQualified=true`. Provider and disk facts remain modeled,
`paidCloud=false` and `fullRemoteQualification=false` throughout. Three independent
offline jobs do not constitute a formal five-member paid cloud set.

```bash
python3 -m scripts.v51.guest_owned_qualification target/owned-canonical-r2 \
  --bundle target/guest-package --source "$(git rev-parse HEAD)" \
  --canonical-repetition 2 --allow-sudo-namespace

python3 -m scripts.v51.guest_canonical_evidence \
  target/owned-canonical-r2/probe/raw --output target/owned-canonical-r2/replay-again
```

Replay output must be a fresh directory outside raw input. An unpacked outer
transport archive's generated `member-index.json` is transport metadata; validate
the archive inventory before passing its raw contents to this entry point.

## CI and time accounting

Three required `v51-owned-canonical` repetitions run in parallel, fail-fast off,
with exact-source build restoration and distinct package/evidence artifacts.
The five shorter component jobs remain required for earlier diagnostics.
Docs-only skips and all existing gates are preserved; the read-only preflight
expands exactly repetitions 1/2/3 and rejects matrix drift or missing jobs.

One complete repetition has 18 minutes of frozen measurement alone. Splitting
cells across jobs would lose this gate's single-lease, shared-source and sequential
handoff coverage. A 6000-second outer command guard and 120-minute job guard
allow setup and artifact upload; they do not override the existing 600-second
preparation, 600-second validation/retention, per-cell budgets or 5400-second
generic topology ceiling. No frozen budget is amended here. Actual hosted
measurements must inform the separate native preset timing/pricing review.

CI `37869232192` exposed duplicate validation work: all three original aggregate
replays passed fifteen cells and 1080 calls, but validation/retention took
968.293, 1078.540 and 1218.665 seconds against 600 seconds. The expired deadline
also prevented service shutdown, followed by per-process reap waits. These runs
are failed qualifications; their passing inner replay does not close this gate.

The correction removes the preceding full tape replays and duplicate logical
passes within the aggregate, keeping the 600-second ceiling. The replay child
is killed and reaped at the remaining original deadline, with partial output and
stderr retained and no retry. Collection and per-tape/fault replay progress appear
in the log. An expired validation deadline no longer consumes a shutdown attempt:
the controller uses its existing cleanup reserve for shutdown and startup receipt
retention. Overshoot remains FAIL and cannot release an incompletely retained
lease. This changes neither the frozen workload nor native/cloud timing admission.

The unchanged repetition-3 raw evidence from that CI was replayed locally with
the correction in 405.574 seconds; packing it for retention took 6.681 seconds.
All fifteen cells, 1080 calls and original negative results passed. The entire
aggregate result matches the original passing inner replay except the decoded
byte count, which now charges only the passes actually performed. Original raw
bytes were compared against the downloaded artifact and remained unchanged.
These local timings exclude live SSH collection/service shutdown and are not a
hosted-runtime guarantee. Corrected-source protected CI must qualify that full
path within the unchanged budgets. The validation index is
`target/v51-canonical-finalization/validation-summary.json`.

## Validation boundary and next step

Local tests exercise exact placement, all five transfers sharing one attempt,
isolated trusted receiver imports, one decoded backup for thirteen receivers,
complete controller cleanup/accounting, terminal handoff failures, portable
binary aggregation and mutations of source/request/package/repetition/topology,
original receipts, coverage and combined trace budgets. Synthetic physical-oracle
fixtures establish validator routing and rejection boundaries only.

This development host lacks mount-namespace privileges. Local shared-filesystem
or consumer validation cannot replace the independent-mount hosted qualification.
After all three protected repetitions pass, review native preset request,
configuration, lease, time/price allocation and fail-closed admission together.
New paid work still requires the user's exact-request confirmation and manual
trigger. The USD 200 ledger ceiling and cleanup requirements are unchanged.
