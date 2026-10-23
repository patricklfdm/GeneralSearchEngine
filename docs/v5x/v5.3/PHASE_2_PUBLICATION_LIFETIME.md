# Repeated publication and original-source maintenance

Status: local private Phase 2 integration. The full Phase 2 gate remains **OPEN**.

## Installation must preserve more than the new selected set

A repeated fresh ballot can select three equally advanced sources while an older
local BASIS remains retained. The older BASIS endpoint may be hidden inside the
new compacted RANGE. The selection algorithm correctly rejects that bridge as
unused for the new selected voters, but generation installation still needs it
until authorized source retirement finishes. A single ancestry argument for both
operations prevented the second repeated publication cycle from progressing.

The private journal now accepts a separate list of retained installation bridges.
The existing overload still supplies no extras. Selection is calculated and
checked using only its original source proofs; supplemental proofs cannot change
the selected set, longest cut or carried entry. Installation combines those proofs
with exactly the missing endpoints required by current, floor and retained local
sources. Missing, duplicate, conflicting, unused or unauthenticated proofs reject
before generation writes. Both the supplied bridge observations and the retained
capsule verifier must authenticate the endpoints. The existing six-group/96 KiB
bound remains unchanged.

All combined bytes enter the ordinary manifest and exact installation transaction.
An interrupted candidate cannot be replaced with a different valid endorsement
representation. Original SELECTED/BASIS bytes remain unchanged. Higher observed
ballots still fence installation; no supplemental proof creates a new ballot.
This is a private storage overload, with no frozen public API or wire change.

An exact completed installation retry also retains its manifest's already verified
ancestry after the obsolete source is safely retired. Recomputing that receipt
solely from the remaining live source references would incorrectly reject a late
retry. The stored original endpoints only participate when the exact selection is
already installed; they do not admit unrelated proofs into a new installation.

## Bounded clean lifetime

The three-node test starts with one real DATA publication, then executes twelve
fresh ballots and twelve real BARRIER publications. Each cycle:

1. Captures complete original sources under the new ballot and fixes the selection.
2. Installs the new selected generation, preserving the old source's hidden parent.
3. Establishes a governing floor from the exact local and one other complete copy.
4. Retires the inactive generation and obsolete original source under that floor,
   then releases the floor and compacts the journal.
5. Obtains actual ACCEPT/PROOF/certificate observations from all three local owners,
   applies the BARRIER and forces the new end/parent acknowledgements.
6. Publishes the exact generation, clears covered work, retires the old generation
   under another complete floor, and releases that floor.

At each settled round there is exactly one generation, one original source, two
physical images and one PROMISE/BASIS/SELECTED group per node. The original selected
cut advances each round; subsequent publications contain one parent bridge.
No renewed ancestor groups accumulate. Reservation high-water values are observed
at storage callbacks; reservations stay distinct from physical-file counts.

The separate Python snapshot audit checks all 39 round/node inventories, original
grant/selection bindings, captured previous publication, exact BARRIER catalog
projection, two image hashes and absence of obsolete sources/floors. It rejects
damaged snapshots and false scope, then replays after relocation. It does not
independently reconstruct every intermediate force or reservation peak.

## Validation and limits

The [local source/build/evidence index](phase2-evidence/publication-lifetime.json)
records the initial second-cycle failure, corrected executions, focused rejection
and repeated-install recovery tests, retained snapshots and independent audit.
It also retains the regression that rejected an exact completed installation
after source retirement, and the correction preserving that original receipt.
The final source passed seven focused Java methods: all four lifetime/retry tests,
two existing installation tests and the distinct-source ancestor test. All 39
snapshots passed independent audit and relocation, including six rejection cases,
both normally and with Python assertions disabled. The producer observed at most
seven application reservations and 268,449,712 staging bytes; each settled journal
was 2,053–2,055 bytes. These small-image measurements do not replace maximal-size
qualification.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53PublicationLifetimeTest -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.publication_lifetime_evidence <printed-v53PublicationLifetimeEvidence>
```

Historical bootstrap remains a conditional fixture. These are repeated local
owner opens within a test JVM, with separate I/O interruption tests; they are not
a fresh-process lifetime crash matrix, same-ballot continuation, public runtime,
network quorum or power-loss result. Maximal image/journal pressure, cross-view
lifetimes and interruption across the entire coordinated maintenance sequence
remain required by the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
