# V3.2 validation contract

## Independent oracles

V3.2 requires representation-free test oracles that do not call production offset
mapping, match-evidence, range-merging, or fragment code:

- offset oracle returns expected normalized terms, logical positions, and original
  UTF-16 ranges from explicit fixtures;
- highlighted-search oracle exhaustively evaluates the source document and normalized
  query tree, then applies the frozen leaf and composition rules;
- phrase oracle enumerates every valid witness and orders them by consumed slop and
  source-offset tuple;
- fuzzy oracle uses complete vocabulary scan and existing bounded OSA reference logic
  to select the same per-document expansion;
- fragment oracle unions explicit intervals and applies the frozen window algorithm;
  and
- snapshot oracle compares an integrated highlighted call with ordinary search and
  document values captured from one controlled immutable state.

A production helper cannot serve as its own oracle. Randomized failures report seed,
source, analyzer output, query shape, expected ranges, and actual ranges.

## Public compatibility fixtures

Reflection and source fixtures prove:

- `Analyzer` remains a functional interface with one abstract method;
- `AnalyzedToken` retains exactly two record components in the same order;
- `OffsetAnalyzer` has the frozen abstract/default method shape;
- `OffsetAnalyzedToken` has exactly four frozen record components;
- all highlighted request/result classes are final and expose only authorized methods;
- `SearchEngine` gains only the additive default highlighted-search overload;
- existing query/request/result/explanation descriptors are unchanged; and
- no offset, evidence, plan, posting, snapshot, or internal-ID implementation type
  becomes supported API.

Japicmp runs against published `1.0.0`, `2.0.0`, `2.1.0`, pinned `3.0.0`, and pinned
`3.1.0` in normal clean-home and fresh-isolated repositories.

## Offset validation matrix

Focused fixtures include:

| Shape | Required observation |
|---|---|
| ASCII and whitespace | exact half-open source ranges and unchanged terms/positions |
| supplementary code point | boundaries never split a surrogate pair |
| composed/decomposed form | normalized term is unchanged from legacy analysis; range maps to original contributors |
| NFKC expansion/contraction | normalized length may differ while source range remains valid |
| NFKC source-range/multi-token expansion | successive positions may reuse or monotonically overlap source ranges |
| punctuation and unpaired surrogate | delimiter behavior and source ranges are deterministic |
| duplicate term | occurrences retain distinct ordered ranges |
| same-position alternatives | alternatives share one exact source range |
| stop-word/internal gap fixture | logical gap and character gap remain independent |
| initial position gap | existing validation/normalization remains unchanged |
| empty/null built-in input | empty immutable output |
| invalid list/element/term | field-specific deterministic failure |
| negative/zero-width/reversed/out-of-bounds range | construction or sequence validation fails |
| split-surrogate boundary | validation fails before fragment construction |
| decreasing later-position boundary | sequence validation fails; monotonic overlap remains valid |
| logical-position overflow | existing overflow failure remains |

For randomized Unicode strings, the built-in analyzer's term and positioned projections
must equal the published ordinary outputs bit-for-bit while every emitted range safely
slices the original string.

## Highlight request/result matrix

Builder fixtures cover null search request/field, missing field, duplicate logical
name, field insertion order, zero/negative context, positive/non-positive fragment cap,
builder reuse, immutable snapshots, null result elements, and constructor range
validation.

Engine fixtures cover canonical versus equal-looking noncanonical fields, offset-capable
versus legacy analyzers, unsupported third-party engines, missing indexes, closed
engines, empty corpora, zero-term queries, null/empty document fields, extractor
failure, analyzer failure, and malformed offset output.

Capability and canonical-field failures must not depend on whether the corpus happens
to contain a hit.

## Query-semantic matrix

| Query shape | Required highlight observation |
|---|---|
| TEXT | all matched normalized-term occurrences; query duplicates do not duplicate ranges |
| exact PHRASE | earliest minimum-slop witness range includes intervening source text |
| sloppy PHRASE | least consumed slop wins before source position |
| repeated-term PHRASE | distinct ordered occurrences form the witness |
| same-position PHRASE alternatives | selected alternative uses its shared source range |
| FUZZY exact | exact selected expansion occurrences are highlighted |
| FUZZY typo/tie | selected expansion and tie order equal search/Explain |
| BOOL MUST/SHOULD | all matching evaluated children contribute ranges |
| `minimumShouldMatch` | reaching the threshold does not stop range collection |
| matched zero-score child | may highlight even with zero score |
| nested BOOL/BOOST | recursive union; boost adds no new range |
| duplicate/overlapping leaves | score occurrence semantics remain; visible intervals deduplicate/merge |
| structured filter | changes eligibility only, never creates a range |
| requested unrelated field | hit remains with no field highlight |

For every fixture, highlighted hits must match ordinary search in document reference,
score bits, order, and cardinality. Search and Explain match/score facts remain equal.

## Fragment matrix

Focused interval fixtures cover:

- context zero and positive context;
- source start/end clipping;
- high/low surrogate adjustment at both window boundaries;
- exact duplicates, containment, overlap, adjacency, and separated spans;
- phrase covering ranges versus adjacent term ranges;
- overlapping proposed windows and stable coalescing;
- earliest-fragment truncation at the configured cap;
- multiple fields with request-order output;
- fragment text equal to the exact source substring; and
- every absolute span contained in exactly one emitted fragment.

Randomized interval tests compare the complete fragment structure with the independent
oracle and assert strictly increasing, non-overlapping fragment windows.

## Mutation, snapshot, and lifecycle matrix

Deterministic concurrency fixtures pause after snapshot capture and publish add,
update, remove, bulk mutation, dynamic text-index installation, or index drop before
highlight assembly resumes. Every hit and source fragment must come entirely from the
captured old or new snapshot, never a mixture.

Additional fixtures cover:

- repeated highlighted reads during one writer's publications;
- document update changing both matched terms and source offsets;
- removal/re-add with a different retained source string;
- dynamic-index build with journal replay;
- failed analysis and failed bulk mutation publishing nothing;
- drop/create races and canonical-field stability;
- close before invocation and close during an admitted read; and
- no retained analyzer list, evidence object, or snapshot after completion.

Accepted test documents remain immutable; mutation of a retained document reference is
not a supported oracle case.

## Differential and fuzzing requirements

Randomized generators vary Unicode source, term normalization, token count, logical
gaps, same-position alternatives, repeated terms, query-tree depth, phrase slop, fuzzy
distance, BOOL threshold, boosts, filters, requested fields, top-K, context, fragment
cap, and mutation history.

The differential suite compares full hit and highlight structures and independently
checks interval safety. Bounded exhaustive small-alphabet suites cover phrase and fuzzy
selection. Tests use fixed seed sets in normal CI and print a replayable seed for every
failure.

## Consumers, artifacts, and documentation

The V3 consumer and travel example execute a supported highlighted search using only
public types. V1/V2 consumers compile unchanged. Strict Javadocs cover offset coordinate
rules, half-open ranges, snapshot behavior, exceptions, and immutability.

Release packaging, service-entry inspection, reproducibility, API fixture, and remote
published-consumer gates remain mandatory. Documentation examples must never imply
HTML safety, stored offsets, phrase-all-witness output, or support from a legacy
analyzer.

## Performance correctness guards

Benchmarks consume hit IDs, score checksums, fragment counts, and span checksums outside
the timed path where JMH permits. Setup validates every benchmark result against the
independent oracle. Ordinary search/index cells run with highlighting disabled and
assert no offset-result allocation path is entered.
