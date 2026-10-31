# Phase 3B — complete joining history with an initial source reply loss

This batch extends the existing complete native 3-to-4 ADD history with one
declared lost initial learner-source response. The required Phase 3 profile,
process, expiry/cancellation and frozen acceptance gates remain open.

## Execution boundary

`V53JoiningIntentExportTest` accepts the optional test-only property
`v53.joining.sourceFault=SOURCE_OFFER|CHUNK|TRANSFER_COMMIT`. It is allowed only
on the complete early-start history. An unset property keeps the healthy path.
The donor's existing `BEFORE_RESPONSE_WRITE` callback retains the actual wire
bytes and then closes the socket before delivering the selected reply. No fake
successful reply or extra client retry is introduced.

The original `MembershipLearnerSource.fetch` recovers through its existing bounded
retry. The fixture records the same source start and existing twelve-minute
budget before and after that fetch; it does not create another source client to
recover this loss. These markers bind the selected scope, not a latency SLA.
The fault is the first matching response from node 1 to the initial node 4
learner. It may be a source-discovery control record rather than application data.

The same original files then continue through RESERVE/PREPARE/READY/SEAL/INTENT,
old-majority and real joining-side acquisition, joined native ownership,
automatic FINAL, the stable barrier and cold reopen. Original node 3 stays
offline. There is no success splicing between histories, selection of a shorter
test, resetting of the original lease or weakening of a frozen bound.

## Independent replay

The shared phase/network readers allow exactly one declared withheld response.
An undeclared loss, extra loss, missing completion or different source scope
fails. A withheld response cannot satisfy client delivery. Its next request in
the same transfer must retain the exact request and response bytes, permanent
identities, trace, sequence, ballot and view. Original send/server-read/offer and
client-read observations remain separate. A later transfer step cannot overtake
the earlier delivered response.

Transfer assembly consumes only delivered data and counts the recovered loss
once. The successful content still goes through the existing physical,
temporal-export, control, maintenance and continuous peer-ledger readers.
No donor force/rename/delete, new capture, publication or owner-close observation
may intervene between the lost offer and its recovered delivery. This is a
narrow extension for an unchanged original donor, not general authorization to
reuse a later source after an intervening authority change.

`scripts.v53.joining_fault_evidence` first runs that entire original precondition.
It then verifies the declared loss. Original-first negative qualification changes
copies of only the wire/event traces in memory, checking fourteen exact rejection
reasons. The original physical files and complete trace inventories stay
unchanged. Negative cases cover declaration/completion, renewed start/budget,
incorrect reply kind, a hidden loss, false delivery, intervening donor force,
missing sends/reads/retries, a new client scope and changed retry bytes. Synthetic
tests exercise those boundaries for all three reply kinds; they do not establish
three successful native executions.

```bash
python3 -B -m unittest discover -s scripts/v53 -t . -p 'test_joining*.py'

# Each invocation creates a new immutable source/build/raw execution directory.
python3 -B -u -m scripts.v53.joining_history_run \
  target/v53-joining-loss-offer --fault SOURCE_OFFER --maven /opt/maven/bin/mvn

# Use the original raw directory recorded in that execution's receipt.json.
python3 -B -m scripts.v53.joining_fault_evidence /path/to/original/raw --qualify
```

The driver emits progress every minute and never retries a failed history.
`--fault CHUNK` and `--fault TRANSFER_COMMIT` are independent complete histories
available for later hosted execution. Keep each history on one runner, on the
same original files through cold reopen; do not divide a history across jobs.
The driver only collects evidence (`PARTIAL`); full reader acceptance is separate.

## Evidence and remaining scope

The source-bound local result is recorded in
[joining-source-loss.json](phase3-evidence/joining-source-loss.json). SOURCE_OFFER
passed one complete native execution (886.777 seconds in its JUnit report),
without rerunning the workload. All 2209 original exchanges, 2208 deliveries,
686 committed contents, 90 peer-ledger writes and 97 ledger comparisons passed
independent replay. Exactly one reply was withheld and recovered. The transfer
reader separately counts two normal rejected attempts and three identical
retries in the whole history; those are not three injected losses. All fourteen
negative cases and 307 joining Python tests passed. Source, build, raw history
and reader are retained for hash-checked portable replay.

The subsequent [complete three-reply matrix](PHASE_3_JOINING_FAULT_MATRIX.md)
qualifies CHUNK and TRANSFER_COMMIT with two fresh complete histories from this
same immutable producer source, then replays all three originals and 42 negatives
after relocation. The first batch's receipt remains unchanged. Healthy-history compatibility is checked
against the previously retained original execution, not another healthy rerun.

This does not establish lost voting/publication ACKs, complete joining process
deaths, cancellation/expiry during multi-content transfer, arbitrary partitions,
all seven membership profiles or complete Phase 3 acceptance. Those obligations
remain required. Production Java, workflows, POMs and frozen inputs are unchanged.
