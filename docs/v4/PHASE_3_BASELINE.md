# V4.0 Phase 3 local recovery baseline

## Source boundary

Phase 3 is developed on branch `feat/v4.0-phase3-recovery` from protected-master
commit `7056a5ad00d1f38757f984c51ad21d83ee922443`, the merge of Phase 2 PR #79.
Exact-master Phase 2 CI run `33583721019` completed successfully. No paid cloud
resources are required for this phase.

## Implemented evidence

The production reader supports generation-1 WAL-only bootstrap and repeated reopen.
Focused tests restore sparse canonical slots, `nextDocId`, sequence, startup and
dynamic indexes, queries and continued writes. They reject checksum, short invalid
tail, sequence, complete-payload, metadata/history/configuration, codec, logical replay
and index-rebuild failures under stable categories.

An uninterrupted in-memory oracle and a separately recovered durable engine execute a
mixed history containing single and bulk mutations, successful no-ops, and equality,
prefix, text and range index transitions. Comparison includes structured truth,
text/ranked membership and exact score bits, canonical order, SearchRequest, first
page, exact totals, Explain and restart cursor invalidation.

The Phase 3 verifier exercises all ten inherited writer barriers, all three recovery
barriers, external kill after force, external kill after replay, three independent
Python corruption/tail fixtures and a fake-cloud failure drill. Every successful crash
artifact passes the existing checksummed evidence validator. The fake lane explicitly
selects `phase3-recovery`; it does not claim a paid persistent-disk run.

## Current local results

- focused Phase 3 recovery and differential tests: PASS;
- independent Phase 3 Python fixtures: 3 tests, PASS;
- production process-crash matrix: PASS;
- fake-cloud `failure-drill` evidence and artifact validation: PASS; and
- full reactor: 409 core and 5 processor tests, zero failures.

Published 1.0.0 through 3.4.0 compatibility, all three independent consumers, strict
release/Javadoc artifacts, six-JAR integrity, JMH smoke and two-build reproducibility
also pass locally. Required PR, protected merge and exact-master CI remain acceptance
gates.
