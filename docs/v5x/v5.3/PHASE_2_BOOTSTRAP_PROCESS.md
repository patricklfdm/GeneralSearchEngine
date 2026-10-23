# Phase 2 — bootstrap transaction process recovery

Status: local process qualification complete; **Phase 2 remains OPEN**. This gate exercises
the [private all-voter transaction](PHASE_2_BOOTSTRAP_TRANSACTION.md) in separate
JVMs. It adds no public entry and changes no production behavior.

## Process boundaries

The **48-case matrix / 144 fresh JVMs** passed at 24 declared points, each exercised with `Runtime.halt` and an
external SIGKILL. They cover all four original decision prefixes/durable states,
new target and nested generation directories, original payload prefixes/forces,
local preparation prefixes, receipt candidate/rename/active force, and early/last
local seal publication. The last point is after complete force and before return.

Every case starts with its own retained original plan and three-voter EMPTY seed.
The first child stops at the declared point. A second fresh child resumes that
same plan/history and stops again while re-forcing node 1's original root. A third
fresh child completes. The parent then checks every initial payload, receipt and
seal through the private read-only verifier. No workload is rerun until it passes,
no new history is allocated during recovery, and no missing prepared authority is
reconstructed from arguments.

## Independent evidence

[Source/build/raw index](phase2-evidence/bootstrap-transaction-process.json) binds
the producer and unchanged production artifact to the retained cases. Each case
keeps the original plan/image, three process stdout/stderr pairs and the first,
second and final physical snapshots. The Python replay derives all payloads,
BOOTSTRAP decisions, preparation markers, receipt and seals from the original
plan/image and requires the exact force sequence and physical bytes at each stop.
The SIGKILL marker and final process receipt are also checked.

Negative mutations cover missing cases, changed original plan/image, altered first
and recovery traces, missing final result, stderr, every snapshot stage, scope,
unexpected early target and linked authority. The unmodified original must pass
before any mutation; normal and optimized Python and a relocated evidence copy
agree across all 13 exact-reason negative variants.

```bash
python3 -m scripts.v53.bootstrap_transaction_process_evidence <v53BootstrapTransactionProcessEvidence-directory>
python3 -O -m scripts.v53.bootstrap_transaction_process_evidence <v53BootstrapTransactionProcessEvidence-directory>
```

## Limits and next integration

Fresh process death tests do not emulate power loss, certify every filesystem or
establish recovery timing guarantees. This process matrix uses three EMPTY voters;
the earlier in-process transaction suite separately covers EMPTY and actual backup
at all 3/4/5 sizes. Typed source/configuration rechecks are a private fixture callback
here, not a completed public admission implementation. No synthetic historical
ownership is used to authorize an initial vote, and no voting/leadership/read claim
is made by the bootstrap receipt.

Public planning/apply/resume/result, complete local seal admission/accounting and
post-runtime result inspection remain required. Transferred-context lifetime,
maximal coordinated headroom and the full physical S/N closure map remain separate
Phase 2 obligations.
