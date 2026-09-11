# GeneralSearchEngine V4.4 Phase 2 local matrix baseline

- **Entry:** Phase 1 protected-master acceptance `a984086`
- **Scope:** Complete local correctness, crash, authority and compatibility analysis
- **Production changes:** None
- **Paid cloud execution:** None
- **Finding result:** No admitted V4.4 product correction

## Outcome

Phase 2 binds every case in the frozen ten-family, twenty-case V4.4 matrix to
executable local gates. The gates exercise the complete inherited V4.0 recovery,
checkpoint and lifecycle suites; V4.1 backup, restore and cleanup suites; V4.2
format and transform migration suites; V4.3 derived-state reopen and lifecycle
suites; the paired published-4.3 control; and new targeted all-format, authority,
replacement-host and permission-denial cases.

All negative cases are expected published boundaries. They fail closed, fall back,
or reject before canonical mutation as frozen. No unexpected finding was reproduced,
so Phase 2 admits no `CONTRACT_VIOLATION` or `MEASURED_REGRESSION` and makes no
`src/main` change. A zero-production-change Phase 3 is therefore the expected next
decision unless protected review finds contradictory evidence.

## New targeted coverage

The Phase 2 JUnit matrix proves:

- live formats `(1,0)`, `(1,1)` and `(1,2)` each complete checkpoint/WAL reopen,
  continued mutation, second checkpoint and second reopen;
- a renamed `(1,2)` WAL generation fails codec-free verification and open without
  mutating the member;
- a canonical hard link is classified as aliased authority and retained;
- unreadable canonical bytes fail closed and a failed open releases storage ownership.

The local replacement probe uses separate producer and recovery JVMs. It deletes the
source and first restore directories, recovers from the immutable backup into a new
target, continues sequence `3`, and separately proves permission denial cannot
publish a target. Exact cleanup is mandatory.

## Executable evidence

[`phase2-execution.json`](phase2-execution.json) is the machine-readable case-to-gate
map. `scripts/v44/local_matrix.py` validates that every frozen case and every gate is
bound exactly, records one strict receipt per successful gate, and writes a
checksummed `gse-v44-final-durable-evidence-v1` bundle. Missing, extra, malformed or
tampered receipts fail closed.

The complete local gate is:

```bash
scripts/verify-v44-phase2-matrix.sh
```

It provisions no GCP resources and invokes no workflow. Failure workspaces are
retained for diagnosis; successful workspaces are removed.

## Classification

The result is `PASS_NO_ADMITTED_FINDINGS`. Passing cases have no finding
classification. Frozen negative cases are classified `EXPECTED_BOUNDARY`. The
remaining classification vocabulary stays available for later evidence but is not
used to manufacture a change.
