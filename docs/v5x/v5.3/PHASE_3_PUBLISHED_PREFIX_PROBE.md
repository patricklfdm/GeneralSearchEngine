# Phase 3 published learner-prefix probe

This connects the successful local published-prefix probe to the
[explicit ownership reader](PHASE_3_PROBE_EXPORT_OWNERSHIP.md) and the original
required-four history. It complements
[direct exports](PHASE_3_REQUIRED_FOUR_DIRECT_EXPORTS.md) and
[joining metadata extents](PHASE_3_JOINING_METADATA_EXTENTS.md).
Phase 3 remains OPEN.

## Actual call and independent authority

With export observations enabled, the existing successful probe records three
events: before opening the export, after obtaining its reference inventory, and
after normal cleanup. The BEGIN event retains the exact original request frame;
all three events correlate through its digest and actual owner. Existing event
capture attaches each event to that owner's resource sequence. Constructor,
reference and cleanup exceptions propagate; unsuccessful calls cannot acquire a
successful-return marker. The original nonempty-reference assertion remains.

The independent reader requires exactly those three observations in order. It
derives the proposer from the original INTENT round's SELECTED record, finds the
generation spanning the complete call, and checks the original joint cut,
permanent learner identity, initial CHUNK request and progress-prefix alias.
The source packet and image bytes determine every reference, digest, extent and
kind; unrelated records cannot become transfer contents.

The same original retention-permission check used by network learner transfers
now also accepts explicit local-call boundaries. Its confirmed-head window is
derived from the admitted original quorum and head exchanges. Local markers
never invent a network exchange, confirmation or permit. The exact reservation
and learner must match, and permission must precede opening and survive return.

The original generation manifest supplies the prefix allocation binding. The
existing ownership reader then checks the actual 4096-byte reservation, its live
reference interval, exclusive ownership and completed release. It does not infer
successful cleanup merely from a zero final resource count.

## Entry and scope

```bash
python3 -m scripts.v53.native_resource_evidence "$RAW" \
  --profile 5-REPLACE-required-four \
  --source-control --control-closes --export-ownership \
  --joining-requests --joining-extents --direct-exports --published-probe
```

The complete original physical, publication, network, content, maintenance and
resource prerequisites still run before this additional check. The option is
limited to required-four with cleanup and export ownership enabled. Other
unqualified resource scopes remain partial.

The probe calls `references()`; it does not read complete content bodies. Its
receipt therefore distinguishes original reference-inventory and permission
qualification from full body reads, whole-runtime resources and Phase 3 closure.
The INTENT expiry/capacity/fencing guard probes execute only without joint
publication, so they are not invented as required-four calls.

## Validation and remaining work

Twenty focused Java tests pass, including seven new tests for actual call count,
ordered markers, disabled markers, constructor/reference/cleanup failures,
exception suppression and the original nonempty assertion. The tests explicitly
reject unexpected content-body reads. They qualify helper behavior, not a
complete native published learner history.

The thirteen new Python tests and adjacent suites total 307 passing tests. They
cover original request/alias/generation/identity binding, exact inventory,
permission expiry, missing or forged observations, resource boundaries and
cleanup. Synthetic fixtures are not native evidence. An initial fixture used
an ENTRY ballot field that does not exist; the reader now uses the actual
SELECTED ballot. Failed development logs remain retained, including a mistyped
test-module command; they are not positive qualification.

The retained required-four original passes complete physical/network/content/
maintenance admission and the refactored control/permission replay. The new
probe reader rejects that unchanged historical capture with
`published probe complete original observations`, because it predates these
markers. This compatibility and rejection check took 235.656 seconds; it did
not rerun the native workload or qualify a current-source probe.

The development index is
[published-prefix-probe.json](phase3-evidence/published-prefix-probe.json).
Local reports and input hashes are under `target/v53-published-prefix-probe/`.
No production Java, frozen limits, formats, workflows or paid-cloud behavior
changed. A current-source full required-four history with these markers still
needs execution. Constructor rollback interval binding, remaining resource
content extents, physical custody and simultaneous maxima/headroom, complete
cohort admission and final-source hosted qualification remain open.
