# Protected context covered by a published majority

Status: local owner qualification **PASS**. Phase 2 remains **OPEN**.

An admitted lagging voter retained its original vote in `pending.context` after
the original generation and predecessor source were retired. A majority published
that slot, but the lagging voter could only select another same-parent carried
entry. The retained run1 reproduces this refusal. The first correction passed
installation; extending it through maintenance in run3 exposed a second issue:
the old governing floor still pinned original vote bytes absent from the majority's
new packet. Both failed attempts remain intact.

The private storage owner now permits a newer stable-view selection covering that
slot. It reconstructs the exact original context, retains its frozen local source,
checks the selected source reference and preserves the authenticated original and
backing parent endpoints. A numeric index alone cannot authorize cleanup. Derived
application/replay work remains excluded from this path.

The covering generation keeps the original and intermediate ACCEPT/ENTRY/payload
bytes that are still pinned by the old floor. Each copied byte is rechecked against
the immutable selected local source. They carry no selection or owned-tail authority
and consume the existing bounded source packet and generation reservation. An exact
installation retry preserves the already forced extras and checks them against the
same source, including after explicit floor maintenance.

Only after forcing the new selector can the owner replace the old pending vote with
the exact EMPTY frame. It forces the empty vote and parent directory before deleting
the context and forcing that deletion. Reopen validates the same installed decision,
governing floor, original context and intermediate generation, then resumes only the
exact empty candidate. A newer volatile observation still prevents an old installation
receipt. No old ACCEPT, PROOF or application ACK is emitted by this cleanup.

Floor release remains explicit and still requires prior inactive-generation
retirement. The existing above-floor original-byte checks are unchanged. After that
release, an independently established new floor reclaims old sources, a fresh ballot
installs, and a BARRIER publishes while the original DATA remains applied once.

## Qualification and limits

The clean gate uses actual public offline bootstrap for all six 3/4/5-voter
EMPTY/verified-backup profiles with original certificates, plus three-voter ACCEPT
and PROOF variants. Its 50 node publications include recovery, ordinary maintenance
and continuation. Four/five-voter saved states reach but do not exceed seven physical
images. Eleven boundaries are interrupted twice through generation installation,
empty-vote persistence and context deletion.

The independent reader derives admitted bootstrap, phased votes, source capture,
context metadata, floor copies, original retirement, majority publication, advanced
selection, the retained extra objects and subsequent maintenance/publication. It
checks exact intermediate inventories and force ordering before trying seventeen
specified evidence mutations. Typed application semantics remain Java checks;
the Python reader does not independently execute the DATA operation.

The completed gate has 37 Java tests and 27 Python tests. Normal, optimized and
relocated replay agree. The [retained evidence index](phase2-evidence/covered-context.json)
binds source/build hashes, all measured results and the original failed attempts.

This is small-image local owner and exception-interruption qualification. The
[dedicated process gate](PHASE_2_COVERED_CONTEXT_PROCESS.md) additionally covers
22 repeated-death cases and 66 fresh workers on the same production classes.
Mixed-original-ballot covered completion, complete cross-view storage, maximal
capacity/lifetime and the final S/N mapping remain open. Public
membership runtime, frozen formats/limits, workflows and V5.2 are unchanged. See the
[closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).

## Reproduction

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53CoveredContextTest -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_covered_context
python3 -m scripts.v53.covered_context_evidence \
  "$PROFILES" "$INTERRUPTIONS" "$ACCEPT" "$PROOF"
```

Use the producer's printed locations from the same build; do not combine old failed
profiles with a later runtime. The retained index records the exact qualified roots.
