# Phase 2C2 — selected local generation installation

Status: **locally complete for selected local installation**. Phase 2 remains **OPEN**.
This private transaction returns a local installation receipt; it neither sends a
network ACK nor enables the public runtime. Historical remote ownership inputs
are still conditional fixtures.

## Transaction and recovery

The same exclusive `MembershipGrantJournal` owner verifies the retained original
local source and recomputes the exact persisted SELECTED decision. A different
source set, basis, cut or carried entry cannot replace that decision. The plan
preserves the selected longest capsule/catalog/application and the original
highest applicable next-slot ACCEPT/ENTRY/payload, including when that tail comes
from another selected source. Entries covered by the longer certified prefix do
not become an owned next-slot tail.

Before staging, the installer verifies the complete candidate capsule, local
eligibility, tail binding and every retained original parent. Compacted parents
require authenticated CHECKPOINT/ACK ancestry, retained with the generation and
verified again on reopen. Missing authenticated evidence fails before selector
or staging writes. Shared reservations include both generations and their image
copies; this batch does not relax the two-generation or seven-image limits.

The transaction writes the inactive a/b slot, preserving the previous generation:

1. Reserve complete metadata and image capacity; refuse an occupied old slot.
2. Write/force the exact manifest and every packet, grant, selection, tail,
   ancestry and image file. Verify disk bytes against the frozen manifest hashes.
3. Force the candidate generation and generations directories.
4. Write/force `selector.pending.gsr`, atomically replace `selector.gsr`, then
   force its parent directory.
5. Reopen and validate the new current generation under the same owner before
   returning. Recheck the root-wide ballot fence at write/return boundaries.

| Interruption | Explicit recovery |
| --- | --- |
| Before any staging bytes | Revalidate the same durable choice and restart installation |
| Exact prefix of candidate manifest/member/pending selector | Resume only the identical recomputed plan; new grants remain blocked while this installation is incomplete |
| Different prefix, unexpected file, replaced owner/current inode | Refuse without repairing, truncating or deleting authority |
| Selector already names the complete new generation | Force/validate on reopen; exact duplicate returns the original manifest without another installation |
| Both slots occupied after successful installation | Retain both; a later installation requires governing-floor retirement, which is a separate Phase 2 obligation |

The original journal/source bytes remain available after installation. A new
ballot freezes a new BASIS from the newly selected generation. No inactive source
is promoted by scanning for a convenient valid manifest. Publication requires the
exact selector and its selected journal record.

## Qualification

[Exact hashes and result index](phase2-evidence/generation-install.json) bind parent
`ba0818f` plus the dirty local implementation. All 109 focused Java tests, 65
Python/build-contract tests and 49 optimized-Python tests passed. The final matrix
passed in 433.547 seconds. Current-generation regression passed 90 cases / 360
JVMs / 13 negatives in 162.516 seconds; durable-selection regression passed 54
cases / 270 JVMs / 11 negatives in 174.115 seconds. All three portable replays and
complete raw receipt inventories/hashes passed.

The fresh-process matrix has 174 cases / 696 JVMs: sizes 3/4/5, tail/no-tail,
clean installation and halt/SIGKILL at 14 force/publication boundary categories.
Member/image hooks cut the first occurrence in the sorted file sequence; this is
not a claim of power-loss coverage or every possible per-file interruption.

The independent Python reader reconstructs candidate bytes from the retained
original inputs. It checks every snapshot, original source/old-generation
preservation, actual sorted write order, selector state, duplicate receipt and
the next grant's new source. Twelve original-first exact-reason negatives reject
forged receipts, network-ACK relabeling, missing forces, lost old authority,
wrong selectors/tails/packets/references, duplicate writes and capture drift.

Java regressions also cover compacted ancestry, semantic verification before any
write, different-source carried tails, all-boundary higher observations, changed
input buffers/selector inodes, bounded shared capacity, partial prefixes and an
installation recovery interrupted a second time.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_generation_install_evidence \
  scripts.v53.test_durable_selection_evidence scripts.v53.test_current_generation_evidence \
  scripts.v53.test_basis_sources_evidence scripts.v53.test_grant_evidence \
  scripts.v53.test_allocator_evidence scripts.test_ci_v51_bundle
python3 -m scripts.v53.generation_install_qualification \
  "target/v53-phase2-generation-install/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use a new output directory. Raw results remain under
`target/v53-phase2-generation-install/`, with final installation evidence in
`qualified-v4`. Earlier failures remain retained: the red semantic-verification
regression, a capacity-test message mismatch, two stale-JAR precheck refusals after
a comment-only Java edit, and a JVM performance-file warning caused by concurrent
PID namespaces. The corrected probe disables optional `hsperfdata` files and keeps
strict JSON output checks. Repackaging retained the old JAR and did not repeat the
already passing Java suite. The original Java implementation stayed fixed through
the regressions and final matrix; the final Python change only controls that
probe's optional monitoring file. These development corrections are not workload
measurement retries.

Public offline initialization, real application mutation,
cross-view adoption, ACCEPT/PROOF/certificate ownership, floor/retirement, bounded
journal rotation and complete old/joint/new physical qualification remain in the
[Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md). No frozen format,
legacy runtime, workflow, POM or V5.2 cloud resource is changed by this batch.
