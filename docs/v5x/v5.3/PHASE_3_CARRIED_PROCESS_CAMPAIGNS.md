# Phase 3 — carried-process campaign file prefixes

Phase 3 remains **OPEN**. This component extends the
[FLOOR and retirement process histories](PHASE_3_CARRIED_PROCESS_FLOORS.md) with
original allocator, grant, selection and selected-installation file inventories.
It targets the same INTENT/ACCEPT-rename halt and FINAL/PROOF-rename SIGKILL cases.
It does not qualify a crash during campaign preparation, later publication's
installation, all transient storage or the final hosted cohort.

## Original observations

The optional campaign mode of the bounded file recorder retains its own schemas
and `campaigns/life-1/`, `campaigns/life-2/` collections. The outer `maintenance/`
directory preserves the complete prior FLOOR/resource/retirement/history wrapper.
The same original callback indices, event digest, root, PID, terminal state and
resource owner identities bind all three file recorders. Existing optional modes
retain their original metadata formats and layouts.

The recorder observes allocator reservation through return, PROMISE through
complete source/BASIS capture, and SELECTED through the same owner's selected
installation. A returned SELECTED leaves that owner awaiting installation; it
cannot be closed as a complete capture or reused by another campaign. Installation
callbacks outside that interval belong to other operations, including publication,
and remain covered by their existing original-history prerequisites. They do not
earn campaign-prefix credit.

Each callback retains the complete replica inventory and content-addressed bytes,
including empty directories and files outside the current transaction. The same
2048-capture, 512-file, 64-MiB-per-file and 256-MiB-per-child bounds apply.
Original inventories before and after copying must match. CUT_PREFIX is the
observed prefix before process death; only actual successful successor closes
can produce CLOSED. These observations add test I/O, not performance evidence.

## Independent physical projection

The [reader](../../../scripts/v53/native_carried_campaign_prefixes.py) first
requires the full unchanged original process, snapshot, network, continuous
ledger, resource, retirement and FLOOR validation chain. Its
[transaction model](../../../scripts/v53/native_campaign_files.py) starts with
the independently derived post-maintenance files. The already validated original
grant extension, captured source and installed generation determine subsequent
bytes; none of the new captures supplies expected content.

The model distinguishes empty candidates, half-written source authority, packet,
image and BASIS prefixes, complete writes, forces, rename and directory force.
It preserves the old allocator and selector until their respective rename. The
source authority is the original selector plus PROMISE and BASIS and survives
until the BASIS is forced. SELECTED appends to the original journal. Every
generation member precedes selector publication. Selected-retention completion
occurs after INSTALL_PARENT_FORCED; the separate continuous ledger reader still
requires every original write, with the final ledger visible at
INSTALL_BEFORE_RETURN.

Every original campaign callback must bind exactly once to its independently
derived owner, kind, local event index and complete physical state. Ordinary
nonselected voters require their original grant but cannot borrow another owner's
selection or installation. No successful final snapshot substitutes for an
intermediate-file observation.

Qualification requires an unmodified complete original before any mutation.
Disposable sidecar mutations target process identity, schema, callback coverage,
object inventories, allocator publication, torn capture/source/BASIS prefixes,
selection persistence, generation members, selector rename, selected retention
and unrelated pending votes. Every rejection must have its exact declared reason;
the unchanged original inventory is checked again afterward.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedCampaignPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_campaign_prefixes \
  general-search-engine-replication/target/v53-native-carried-campaign-prefixes/run-<id> \
  --qualify
```

## Development evidence

The [development index](phase3-evidence/carried-process-campaign-prefixes.json)
binds the producer sources/classes, reader sources, original inventories and
validation logs. Both native JVM pairs complete without retries. All 1080 new
campaign inventories match independently derived states, composed with the same
originals' 2479 FLOOR and 1572 retirement inventories and complete prerequisite
chain. All 70 targeted mutations reject for their exact declared reasons.

| Original | First child | Successor child | Campaign prefixes |
| --- | --- | --- | --- |
| FINAL / PROOF rename / SIGKILL | 172, CUT_PREFIX | 285, CLOSED | 457 |
| INTENT / ACCEPT rename / halt | 172, CUT_PREFIX | 451, CLOSED | 623 |

Both complete originals also replay from relocated directories with Python
assertions disabled, producing identical receipts and leaving original storage
unchanged. The focused Java suites pass 15 tests; the native suite passes two.
Related Python suites pass 438 tests, including 68 boundary tests also run under
optimization. The 34 coverage tests pass. Earlier FLOOR and retirement receipts
remain identical with the optional campaign projection enabled; all 379 prior
evidence indexes retain their original hashes.

The focused Java fixture initially used the legacy journal entry, then a
misspelled capture entry; both failed development logs remain retained. The
corrected fixture uses the actual capturing entry. Neither failure caused a
native-process retry. An initial preparation file scan was stopped before any
native execution and replaced with tracked/nonignored source enumeration.

The coverage witness's prose now agrees with the actual existing catalogue:
12 hosted subsets, 552 histories, 246 execution groups and 486 archive units.
Only that description changed; selectors, conditions, acceptance-plan hash,
workload parameters and runtime limits remain unchanged.

Six other declared process cases, vote/application/ledger transient bytes,
publication installation, scratch, combined physical/accounting maxima,
application-ACK recovery and final-source cohort admission remain open.
Receipts remain **PARTIAL** with `transientCampaignBytesQualified=true`,
`fullTransientBytesQualified=false`, `postCutTailObserved=false`,
`wholeRuntimeResourcesQualified=false`, `cohortAdmitted=false` and
`phase3Complete=false`. No production Java, workflow or paid-cloud behavior
changes in this component.
