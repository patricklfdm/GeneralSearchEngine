# Phase 3 — CURRENT ownership across original histories

After the [initial voter open correction](PHASE_3_INITIAL_CURRENT.md), four
disposable REPLACE variants still passed the complete prior reader: removing the
first joining owner's `CURRENT_FILES_FORCED`, adding an unknown CURRENT callback
after the history, adding a complete extra open for an unused voter, and adding
a claimed-force field to the cold owner's callback. The unchanged originals,
altered observations and prior successful results are retained. These demonstrate
reader omissions; they do not show that the native runtime skipped durability.

## Ownership contract

`current_lifecycle_evidence` complements the existing independently derived
physical, wire, writer-order and lifecycle readers. It accounts for every
`CURRENT_` observation in the same complete history:

- Original voters open before retention recovery. The process history additionally
  has the prescribed interrupted and resumed proposer's opens, whose exact child
  prefixes and snapshots are checked by the original process lifecycle reader.
- The joining node has five distinct prescribed owners: initial takeover,
  retention, repeated-basis read, continuation and cold reopen. Initial takeover
  lies between its original ownership transfer and active-vote recovery; the
  later opens precede their original joining-retention recovery.
- Original SELECTED records and CERTIFICATE proofs derive each node's ordered
  generation changes. Reused SELECTED records do not create another install.
  An interrupted installation does not invent a publication. A joining owner
  omitted from the final publishing cohort needs its independently verified
  newer-prefix adoption; an optional same-view recovery adds its actual selected
  owners afterward.
- Each derived installation/publication/adoption owns exactly five CURRENT
  callbacks between its original installation parent force and operation return.
  No additional generation may be justified merely by adding observations.
- Capture callbacks belong to original grant owners/scopes, plus the prescribed
  repeated-basis read that does not append another grant. Existing grant readers
  still bind their original bytes and causal intervals.

Every consumed row has exact node/event/scope shape. A callback can belong to
only one interval. At completion, the consumed indices must equal the entire
CURRENT-prefixed observation set, including unused voters and callbacks outside
otherwise valid intervals. Unknown callbacks, extra whole opens and detached
forces therefore cannot disappear between component checks.

The shared complement runs in ADD/REPLACE, REMOVE and the verified merged
process trace. Process observations must still project exactly to the retained
parent and child streams before normalization. New process mutations update
both parent projections while preserving child streams byte-for-byte.

## Qualification

The [receipt](phase3-evidence/current-ownership.json) records actual results,
reader/input hashes and extracted-archive replay. Ten focused reader tests cover
derived generation sequences, all five joining scopes, exact intervals, duplicate
consumption, unsupported extra histories, captures, process opens and independent
node interleaving. A process mutation regression checks exact projections and
unchanged child output.

Six common and six joining-specific observation negatives are integrated into
the persistent qualification drivers. All profile/process tests keep their
original-first precondition; unchanged physical inputs are required before using
the focused observation replay. Original result shapes and existing rejection
ordering remain unchanged. Prior failed diagnostic setup is retained separately
from executed reader results and cannot count as a negative rejection.

Measured validation: all 1,786 Python tests passed. The complete retained REPLACE,
4-REMOVE, 5-REMOVE and SIGKILL/reopen compositions passed, together with historical
ADD compatibility. The four previously accepted diagnostic copies now fail the
complete corrected REPLACE composition for the exact expected reasons.

| Original | CURRENT callbacks | Opens/reloads | Captures/reads |
| --- | ---: | ---: | ---: |
| 3-REPLACE | 245 | 45 | 20 |
| 4-REMOVE | 108 | 20 | 8 |
| 5-REMOVE | 124 | 23 | 9 |
| 4-REMOVE SIGKILL/reopen | 136 | 25 | 11 |
| Historical ADD | 250 | 46 | 20 |

The focused final-source pass rejects 12 new REPLACE mutations and six for each
REMOVE/process original: 30 exact rejections. Existing complete negative matrices
are retained from their earlier batches; this increment did not repeat all of them.
The 41,670,046-byte archive contains 27,297 files and
5,161 directories. All five extracted originals replay with
optimized Python and exactly match the original results; source and input
inventories remain unchanged. No native workload was rerun.

## Scope and remaining closure

The observations belong to historical native originals replayed with the current
reader. This qualifies this CURRENT callback family for those complete histories,
not every storage family or the final-source native profile/process matrix.
Interruptions *inside* a CURRENT open need their own original process recovery
derivation; the retained retirement SIGKILL history interrupted a different stage.

The frozen S/N mapping, remaining whole-history/profile/fault cohorts and combined
resource qualification remain open. Phase 3 is not closed. Java, persisted bytes,
POMs, workflows and cloud behavior are unchanged. Rollback removes this reader
increment while preserving the four reproduced omissions and their evidence.
