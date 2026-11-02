# Phase 3 — complete selected installation write sequences

The callback audit reproduced a gap after the
[grant capture correction](PHASE_3_GRANT_WRITE_CHAIN.md): removing node 1's first
`INSTALL_MANIFEST_WRITTEN` from the retained `3-REPLACE` original still passed the
complete prior ballot/learner/future/authority/network/physical reader. The audit
retains this changed copy and its passing result. Original storage and wire bytes
were unchanged. This is a reader omission; it does not establish a runtime write
failure or require a new native run to reproduce.

## Shared installation contract

`joining_install_storage` uses the existing independent generation transaction
derivation for all three selected-installation paths: ordinary proposer, remote
selected voter, and final same-view recovery proposer. Installed members come
from original snapshots already checked against independent physical derivation.

The sequence follows `MembershipGenerationFiles.install/complete` and
`MembershipCurrentGeneration`: reservation; directory creation; manifest write
and force; each sorted image/member write and force; generation force; pending
selector write and force; atomic selector rename and parent force; CURRENT
validation and all four reseal forces; installation return. The manifest is
checked once, separately from the member inventory. Image/member multiplicities
come from the original installed bytes, not a reported counter.

Every required callback has its exact owner, scope and row shape. Prefix-based
collection also rejects unknown INSTALL/CURRENT callbacks inside the transaction
interval, even when all expected events are present. Existing authority and
causal boundaries remain required:

- Remote selected installation completes before its original INSTALL_ACK is
  offered, after the original SELECTED request is received.
- Ordinary proposer installation starts after every selected peer's delivered
  ACK and completes before the next slot's ACCEPT validation.
- Final recovery installation starts after every delivered ACK and completes
  before the original cold reopen. Delivery positions must be integers.

This shares an existing full writer derivation instead of maintaining a second
force-only sequence. Publication and adoption already use complete installation
transactions; they are not newly implemented in this batch. Continuous retention
updates between installation and return retain their separate original readers.

## Original-first qualification

The tests list the native fixture sequence explicitly, without generating their
observations from the reader helper. They exercise the three installation roles,
missing creation/write/validation boundaries, wrong scope or shape, duplication,
write-after-force, and unknown callbacks both replacing and accompanying writes.
The corrected fixture preserves causal indices when it inserts an event, so an
unrelated shifted ACK cannot count as a successful rejection. Thirty-six negative
subcases were incorrectly accepted by the previous reader.

Thirty-six new original-evidence negatives cover twelve variants in each of the
three roles. The untouched original must pass first. Each mutation changes only
observation metadata; original physical members and directories must remain
identical. Every rejection must match its declared reason. Existing transport,
grant, slot, terminal-attempt and installation boundary negatives remain enabled.

The [batch receipt](phase3-evidence/selected-install-writes.json) records the
frozen reader, original composed replay, current network negative matrix,
historical ADD replay, Python tests and extracted-archive replay. The retained
native producer source/build remains distinct from the corrected reader source.

## REMOVE consumer compatibility

The consumer audit also found `remove_network_evidence` calling the former
force-only helper and inheriting shared grant negatives while still using its
own force-only capture predicate. REMOVE now calls the complete shared capture
and installation predicates, binds every capture-specific callback exactly once,
and declares its own exact rejection reasons for those shared negative cases.
Its ordinary proposer continues to use the same delivered-ACK boundary.

Four adapter regressions exercise real shared predicates with conditional
activation fixtures. Separate original-first replay uses both retained 4-REMOVE
and 5-REMOVE histories, including their complete 107-case network matrices, and
the retained interrupted-retirement SIGKILL/reopen history through the ballot
composition. These are reader compatibility checks on historical inputs, not new
native profile/process executions or a completed 52-member process cohort.

The ADD/REPLACE and subsequent REMOVE adapter checks retain separate frozen
reader manifests. Every common `scripts/v53` file from the first reader must be
identical in the final reader except the explicitly changed REMOVE adapter;
the final reader also contains the new adapter tests. Portable replay uses the
final reader for REPLACE and all three REMOVE inputs, comparing exact original
results and every retained input member after archive extraction.

The complete original chain passed in 54.103 seconds;
all 136 network negatives passed in 696.979 seconds.
All 1,755 V5.3 Python tests and the historical ADD replay pass. Both original
REMOVE profiles pass all 107 network negatives each, and the retained
SIGKILL/reopen history passes the complete ballot composition. The archive
contains 27,676 files and 4,598 directories in
42,678,189 compressed bytes. Extracted `python -O -B` replay matches
the complete original result, with source/input inventories unchanged. These
observations qualify the historical original against this reader, not a new
current-source native cohort.

## Remaining scope

This qualifies the complete selected-installation sequence within the fourteen
original installations: six ordinary proposers, seven remote voters and one final
recovery proposer. It does not qualify every callback elsewhere in the history,
SELECTED journal writes, interrupted/resumed transactions, every profile,
the complete process/fault cohorts or the frozen S/N acceptance mapping.
Unknown or orphan callbacks outside these intervals still require their owning
whole-history checks. Phase 3 and full physical/network/process flags remain open.

No runtime Java, POM, protocol bound, workflow or paid-cloud change. Rollback
reverts this reader/tests increment while preserving the original audit evidence
and recording the known omission.
