# V5.2 Phase 6C advancing independent query replay

**Status:** local untimed query replay verified. Actual measured replicas, the full
execution freeze and hosted/cloud qualification remain pending. This extends the
[program foundation](PHASE_6_MEASUREMENT_PROGRAM.md) alongside the
[lossless observation foundation](PHASE_6_MEASUREMENT_TRACE.md).

## Query truth without a JVM for every captured cut

`measurement_oracle.py` accepts only the declared 64-document corpus, an exact
prefix of M01's update stream, and frozen query descriptors at valid application
sequences. It creates a canonical identity from **both** sequence and descriptor.
Duplicate requests for that exact pair may share computation; different sequences
cannot. The caller's original offered/completed operation ledger is separate and
must retain every call, outcome and timing sample.

`V52MeasurementOracle` runs one actual durable core, applies the ordered updates
once and executes the requested queries in application-sequence order. It records
each query identity, sequence, full result and hash of the actual core documents
and sequence. Python reconstructs those states independently and rejects borrowed
states, changed query identities, missing/duplicate/reordered/extra responses and
incomplete lines. Ranking, highlights and explanations remain actual published
core results rather than a hand-written approximation of search behavior.

This module supports M01's closed update program. Fault-cell mutation schedules
need their own frozen admission before reuse; it is not a generic command runner.
The future physical checker must prove each requested sequence from the original
captured publication and chosen history. A matching query result alone does not
prove a token's lower bound, a strong barrier, quorum or response ordering.

## Bounded inputs and local validation

Admission permits at most 4,096 requested cuts, 180 updates, 1 MiB input,
64 KiB per response row and 32 MiB total responses. These are validation safety
limits, not altered workload counts. The future complete execution plan must bind
them together with the source/control/class identities and evidence budgets.

The existing foundation check now compiles this consumer separately against
published V4.4 and the candidate core. Both execute 180 actual updates and all 138
distinct query descriptors at each of five application states. Each advancing
replay's 690 answers matches its separately executed direct-query foundation, and
the two cores agree exactly. Actual loaded JAR paths and compiled class hashes
are retained. Evidence: `target/v52-measurement-oracle/development-1`.

Five new Python tests cover exact reuse, mutation order, undeclared queries,
invalid sequences, output state/order/completeness and input bounds. All 71 V5.2
Python tests pass. The first test draft expected all fifteen offered descriptors
in a slice to be distinct; ranked/highlight repeat, leaving eleven per state.
That assertion was corrected to 55 across five states; the failed test log is
retained. No runtime or workload acceptance was relaxed.

This remains an untimed foundation check in the existing required job, with the
same always-retained evidence artifact. It establishes no performance comparison.
Next implement and qualify the actual V5.1/candidate public consumers, tie compact
trace observations to independent physical and query checks, and commit the
complete machine execution plan before M01–M04 measurements.
