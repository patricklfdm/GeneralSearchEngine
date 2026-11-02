# Competing activation network and incomplete selection

Phase 3 remains **OPEN**. This composes the remaining original activation
exchanges with [installation/publication](PHASE_3_COMPETING_PUBLICATION.md),
using the same immutable `e1af4813` native history. Production Java, bounds,
retries and workflows are unchanged. No workload is rerun to select a simpler
campaign schedule.

## Both original campaigns

`scripts.v53.competing_activation_network` first requires the full preceding
grant, retirement, installation and publication replay. Its inputs include both
original local choices and every captured grant, not just the eventual winner.

For each local proposal, it checks the original sorted peer probes and their
delivered cut/nonce/ready replies before allocation. The remote voter must fetch
the exact original proposer promise before writing its own promise. The proposer
must receive the remote PROMISE and complete original BASIS/promise/source
transfer before choosing its pair. Source images may be reused only when the
already derived bootstrap files contain those exact bytes.

The successful remote voter must receive the original SELECTED request, fetch
the exact decision and proposer source, then force its own selection and complete
installation. Its INSTALL_ACK must arrive after remote installation returns and
before local installation starts. PREPARE/SELECTED keep their original shared
trace and sequence numbers; each source session is distinct. Original sends,
server reads, responses and client deliveries must occur in causal order, with
the next source request following the preceding response delivery.

## The losing transfer remains incomplete

The original losing node-1 selection reaches node-2 as a SOURCE_OFFER and one
complete data chunk. Its three byte-identical TRANSFER_COMMIT requests receive
no response, and the enclosing SELECTED has no INSTALL_ACK. The new reader
checks these original bytes, endpoints, ballot, trace, transfer ID, offsets,
extent and all five source requests explicitly. It never supplies a synthetic
commit, drops the failed transfer, or treats received bytes as installation.
The losing pair remains absent from the remote durable selections.

This is an observation of unanswered original attempts, not proof of their
transport failure cause. There is no new timeout/retry allowance. Arbitrary
unanswered requests, extra attempts, changed commits and invented installation
or transfer acknowledgements refuse the scoped replay.

`MembershipGrantJournal.exportSource` and `checkRecordExport` permit retained
old originals to coexist with a newer promise. A higher ballot alone is not
used as an invented export expiry. The reader binds a source's retirement to
its already checked original `SOURCE_RETIREMENT_CREATED` event and decision;
the earlier floor reservation is not substituted for that boundary. These
activation dependency checks do not yet establish every whole-history export
lifetime or expiry/close property.

## Coverage and validation

The retained original has two campaigns, four discovery probes, 45 activation
exchanges and ten previously checked maintenance exchanges. Seven activation
source sessions include one incomplete selection; the other six complete.
All **55** preinstallation exchanges and four unanswered attempts are accounted
for. Together with publication and heartbeat replay, the entire original has
**250** answered exchanges and **269** requests. Phase and maintenance traces
cannot be reused after installation.

Fourteen original-first mutations cover missing proposer/source delivery,
changed BASIS/winning/losing selection bytes, missing/changed/forged transfer
commits, a forged losing INSTALL_ACK, an early successful INSTALL_ACK, discovery
delivery/cut corruption, PREPARE/SELECTED sequence drift and an unaccounted send.
Capture indices remain bound to the same original events and clocks; originals
and their physical files are preserved. Invalid originals or unrelated errors
cannot qualify negatives. The [development receipt](phase3-evidence/competing-activation-network.json)
records portable optimized replay, lightweight tests and input hashes.

```bash
python3 -B -m scripts.v53.competing_activation_network "$RAW" --qualify
```

The original's complete network composition now qualifies; the overall result
remains **PARTIAL**. Whole-history temporal exports, complete automatic lifecycle
and recovery, transient retirement bytes, process/failure coverage and final-source
competition admission remain open. This does not close the six hosted subsets,
428 declared histories or five Phase 3 audit work groups.
