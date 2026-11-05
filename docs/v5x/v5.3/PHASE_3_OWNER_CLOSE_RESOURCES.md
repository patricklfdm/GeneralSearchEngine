# Native owner close resource boundaries

The optional fixture flag `v53.resource.owner.close` records the actual close
invocation and successful return for every original network owner. It requires
`v53.resource.transitions`; it is intended for whole-owner histories whose
endpoints, transports and outgoing driver have already stopped. The normal
fixture mode and production close implementation are unchanged.

The collector verifies the owner is still open before `RESOURCE_OWNER_CLOSE_BEGIN`,
calls the real journal `close`, and appends `RESOURCE_OWNER_CLOSE_RETURNED` only
after success. A second invocation, previously closed journal or failed close
cannot produce a successful original interval. The original event append takes
the same budget checkpoint used by all other native callbacks. No synthetic
lease release is inserted by this instrumentation.

## Independent checks

The observation index uses version 2 and declares the sorted `closingOwners`
list when this feature is enabled. This is a test-evidence schema, not a runtime
disk or wire format. Independent physical/native admission derives the expected
original network owner set: three owners for the short stable history, and five
old owners for required-four, including the departing owner. Joining owner
reopens retain their separately admitted lifecycle boundaries.

The reader requires exactly one ordered begin/return pair for each expected
owner. Extra scopes, missing owners, unknown or duplicate markers, and events
after a return are rejected. Exact event checkpoints bind the interval to the
complete original resource journal. There must be live storage but no CONTROL
or WAITER reservation at begin; every interval mutation must be a RELEASE; all
originally live leases must be released by return; return must coincide with the
terminal zero-usage resource sequence. A later balanced reserve/release pair
cannot hide behind the same final totals.

For persistent BASIS sources, the existing original packet/image reader uses
the explicit begin as the last required live boundary and return as the release
deadline. It still requires immutable original extents and continuous leases
before begin. A balanced premature release, early release of only one image, or
release after return is rejected. Earlier retired sources retain their exact
forced-deletion and retirement-clear boundaries.

Historical version-1 collections remain readable and report `NOT_OBSERVED` for
this scope. Their final business callback is never promoted to a close call.
Version 2 with missing observations fails instead of falling back to version 1.
The new negative entry requires an independently admitted original with actual
close markers before any mutation can count as a successful rejection.

## Development qualification

The new short native TCP history completes activation and two published slots,
then closes all three original owners. Independent original physical/network,
publication-resource and accounting replay passes with 3576 resource changes,
1794 event checkpoints, 44 publication boundaries and 20 lease releases inside
the three observed close intervals. All twelve close negatives and the existing
fifteen native accounting negatives reject for their exact expected reasons.
The native Java test took 57.6 seconds; original replay and both negative groups
took 7.2 seconds. The raw input inventory remains unchanged.

Eight Java collector tests pass, including actual journal close, exclusive
reopen and rejection of an already closed owner. The first socket test attempt
was denied by the sandbox (`Operation not permitted`); its output is retained.
The authorized loopback run then passed. Python counts, source/input hashes and
the historical compatibility receipt are retained in the
[development index](phase3-evidence/owner-close-resources.json).

This qualifies the observed accounting interval, not the precise operating-system
lock release instant or every physical-file lifetime. The old complete
required-four original retains its six unmarked final packet/image leases; a new
required-four execution with this flag is still needed to qualify that larger
history. Other receiving/control lifetimes, combined physical maxima, completion
headroom, negative matrices and final-source qualification remain open. Phase 3
is OPEN; twelve hosted subsets / 544 planned histories are unchanged.

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 /opt/maven/bin/mvn -o \
  -f reactor/pom.xml -pl :general-search-engine-replication -am \
  '-Dtest=V53ResourceTransitionCaptureTest,V53NativeDispatchTest#nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener' \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.publication.resources=true \
  -Dv53.resource.transitions=true -Dv53.resource.owner.close=true test
python3 -m scripts.v53.owner_close_negatives "$ORIGINAL"
python3 -m unittest scripts.v53.test_owner_close_evidence scripts.v53.test_basis_resource_evidence
```

Use the newly printed native evidence directory as `ORIGINAL`. Do not copy
markers into an older original. The larger required-four producer can enable the
same flag; its reader selects `--profile 5-REPLACE-required-four`. It has not been
rerun for this batch, and no hosted workflow has been dispatched. Rollback removes
the opt-in fixture mode, version-2 reader and BASIS close integration together;
preserve originals in both versions and their receipts.
