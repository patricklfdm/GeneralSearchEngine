# Phase 3 — original ancestry through native transitions

Status: **locally qualified correction**, 2026-10-28. Full [Phase 3](PHASE_3_ENTRY_PLAN.md)
remains open. This batch preserves independently authenticated original history;
it does not give an old acknowledgement new voting authority.

## Observed failures and correction

Three retained native transition failures exposed separate omissions:

1. At INTENT publication, an original retained stable parent was omitted from the
   new generation. Publication now preserves required authenticated bridges outside
   the range being extended. An endpoint inside an enlarged range still needs a
   fresh exact renewal; an old acknowledgement cannot endorse that new endpoint.
2. A selected receiver can own an older grant that the proposer never owned. Its
   exact local ancestry now supplements installation of the already chosen source.
   Selection bytes, source order, carried choice and original acceptance are
   unchanged. Missing, foreign, duplicate or altered proofs still reject.
3. Projecting a pending certificate into an unchanged native prefix dropped
   authenticated historical keys outside the indexed packet. This projection now
   preserves those exact keys. Merely adding certificate/vote records to the
   inventory does not authenticate them; native capability checks remain required.

No wire or persistent format, quorum, resource bound, request timeout or retry
limit changes. The original failing histories and the initially incorrect fixture
that supplied observations from future slots remain retained.

## Qualification and its limits

The [receipt](phase3-evidence/publication-ancestry.json) binds an immutable build
from `c7ba71d0` with only five production classes and two regression test classes
changed. All 49 focused Java tests pass, including ten new ancestry tests. This
isolated build excludes the pending automatic transition-round implementation.

Separately, that pending round implementation plus this correction passes the
actual TCP submitted-SEAL test: three activations, BARRIER/SEAL/INTENT/FINAL and
new-stable BARRIER at indices 4–8. The test takes 597 seconds and retains its raw
history and 6,025 diagnostic rows. Its source manifest is separate from the
isolated correction. **Independent physical/lifecycle replay for this distinct
submitted-SEAL profile remains pending**; Java success is not that qualification.
The archived original data is not rewritten to fit the earlier sealed-start reader.

Departing selected proposers/followers still require an explicit nonvoting FINAL
completion path. Real learner ADD/REPLACE, all seven transition profiles,
automatic discovery/election/adoption and complete process/network fault coverage
remain required. No public runtime, protected CI, paid cloud or whole Phase 3
acceptance is claimed.
