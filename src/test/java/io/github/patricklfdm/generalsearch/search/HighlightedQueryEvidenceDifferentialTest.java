package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.function.Function;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class HighlightedQueryEvidenceDifferentialTest {
    private static final long PHRASE_SEED = 0x32_04_5001L;
    private static final long FUZZY_SEED = 0x32_04_5002L;
    private static final long BOOL_SEED = 0x32_04_5003L;
    private static final List<String> TERMS = List.of(
            "alpha", "beta", "gamma", "delta", "echo"
    );
    private static final List<String> FUZZY_TERMS = List.of(
            "cat", "bat", "cut", "cot", "cart", "coat", "dog"
    );
    private static final List<String> FUZZY_QUERIES = List.of(
            "cat", "cta", "cet", "crt", "coat", "dat", "dog"
    );
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void randomizedPhraseWitnessMatchesExhaustiveOffsetOracle() {
        Random random = new Random(PHRASE_SEED);
        List<Document> documents = randomDocuments(random, TERMS, 60);
        try (SearchEngine<Integer, Document> engine = engine(documents)) {
            for (int trial = 0; trial < 240; trial++) {
                List<String> queryTerms = randomTerms(random, TERMS, 1, 4);
                int slop = random.nextInt(5);
                SearchQuery<Document> query = SearchQueries.phrase(
                        BODY_TEXT,
                        String.join(" ", queryTerms),
                        slop
                );
                SearchRequest<Document> search = SearchRequest.<Document>builder()
                        .query(query)
                        .limit(20)
                        .build();
                HighlightedSearchResult<Document> result = highlighted(
                        engine,
                        search,
                        List.of(BODY_TEXT)
                );
                String replay = "seed=" + PHRASE_SEED
                        + " trial=" + trial
                        + " query=" + queryTerms
                        + " slop=" + slop;
                assertCanonical(engine, search, result, replay);

                List<V32TestReference.PhraseSlot> slots = new ArrayList<>();
                for (int index = 0; index < queryTerms.size(); index++) {
                    slots.add(new V32TestReference.PhraseSlot(
                            index,
                            List.of(queryTerms.get(index))
                    ));
                }
                for (HighlightedSearchHit<Document> hit : result.hits()) {
                    List<V32TestReference.Occurrence> occurrences = occurrences(
                            hit.hit().document().body()
                    ).stream().map(token -> new V32TestReference.Occurrence(
                            token.term(),
                            token.position(),
                            token.range()
                    )).toList();
                    V32TestReference.PhraseWitness expected =
                            V32TestReference.phraseWitness(slots, occurrences)
                                    .orElseThrow();
                    assertTrue(expected.consumedSlop() <= slop, replay);
                    assertEquals(
                            List.of(expected.range()),
                            ranges(hit, "body"),
                            replay
                    );
                }
            }
        }
    }

    @Test
    void randomizedPhraseOffsetsCoverLogicalGapsAndSamePositionAlternatives() {
        Random random = new Random(PHRASE_SEED ^ 0xA17E2L);
        Map<String, List<OffsetAnalyzedToken>> analyses = new HashMap<>();
        OffsetAnalyzer analyzer = text -> {
            List<OffsetAnalyzedToken> tokens = analyses.get(text);
            if (tokens == null) {
                throw new AssertionError("missing synthetic analysis for " + text);
            }
            return tokens;
        };
        TextField<Document> field = TextField.of(BODY, analyzer);
        List<Document> documents = new ArrayList<>();
        for (int id = 0; id < 30; id++) {
            String source = "document-" + id + "-" + "x".repeat(96);
            analyses.put(source, randomOffsetAnalysis(random, 1, 8));
            documents.add(new Document(id, "", source));
        }

        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(field))
                .build()) {
            engine.addAll(documents).join();
            for (int trial = 0; trial < 180; trial++) {
                String querySource = "query-" + trial + "-" + "q".repeat(96);
                List<OffsetAnalyzedToken> queryAnalysis = randomOffsetAnalysis(
                        random,
                        1,
                        4
                );
                analyses.put(querySource, queryAnalysis);
                List<V32TestReference.PhraseSlot> slots = slots(queryAnalysis);
                int slop = random.nextInt(7);
                SearchRequest<Document> search = SearchRequest.<Document>builder()
                        .query(SearchQueries.phrase(field, querySource, slop))
                        .limit(100)
                        .build();
                HighlightedSearchResult<Document> result = highlighted(
                        engine,
                        search,
                        List.of(field)
                );
                String replay = "gap/alternative seed="
                        + (PHRASE_SEED ^ 0xA17E2L)
                        + " trial=" + trial
                        + " slop=" + slop;
                assertCanonical(engine, search, result, replay);

                Set<Integer> expectedIds = new LinkedHashSet<>();
                Map<Integer, V32TestReference.PhraseWitness> expectedById =
                        new HashMap<>();
                for (Document document : documents) {
                    V32TestReference.phraseWitness(
                            slots,
                            offsetOccurrences(analyses.get(document.body()))
                    ).filter(witness -> witness.consumedSlop() <= slop)
                            .ifPresent(witness -> {
                                expectedIds.add(document.id());
                                expectedById.put(document.id(), witness);
                            });
                }
                assertEquals(
                        expectedIds,
                        result.hits().stream()
                                .map(hit -> hit.hit().document().id())
                                .collect(java.util.stream.Collectors.toCollection(
                                        LinkedHashSet::new
                                )),
                        replay
                );
                for (HighlightedSearchHit<Document> hit : result.hits()) {
                    assertEquals(
                            List.of(expectedById.get(
                                    hit.hit().document().id()
                            ).range()),
                            ranges(hit, "body"),
                            replay
                    );
                }
            }
        }
    }

    @Test
    void randomizedFuzzySelectionMatchesFullScanBm25Oracle() {
        Random random = new Random(FUZZY_SEED);
        List<Document> documents = randomDocuments(random, FUZZY_TERMS, 50);
        double averageLength = documents.stream()
                .mapToInt(document -> occurrences(document.body()).size())
                .average()
                .orElseThrow();
        try (SearchEngine<Integer, Document> engine = engine(documents)) {
            for (int trial = 0; trial < 180; trial++) {
                String queryTerm = FUZZY_QUERIES.get(
                        random.nextInt(FUZZY_QUERIES.size())
                );
                SearchRequest<Document> search = SearchRequest.of(
                        SearchQueries.fuzzy(BODY_TEXT, queryTerm)
                );
                HighlightedSearchResult<Document> result = highlighted(
                        engine,
                        search,
                        List.of(BODY_TEXT)
                );
                String replay = "seed=" + FUZZY_SEED
                        + " trial=" + trial
                        + " query=" + queryTerm;
                assertCanonical(engine, search, result, replay);

                for (HighlightedSearchHit<Document> hit : result.hits()) {
                    List<TokenOccurrence> documentTerms = occurrences(
                            hit.hit().document().body()
                    );
                    List<V32TestReference.ScoredTerm> scored = scoredTerms(
                            documents,
                            documentTerms,
                            averageLength,
                            search.bm25()
                    );
                    V32TestReference.FuzzySelection expected =
                            V32TestReference.selectFuzzy(
                                    queryTerm,
                                    BoundedOptimalStringAlignment.autoMaxEdits(
                                            queryTerm
                                    ),
                                    scored
                            ).orElseThrow();
                    assertEquals(expected.occurrences(), ranges(hit, "body"), replay);
                }
            }
        }
    }

    @Test
    void randomizedNestedBoolBoostEvidenceMatchesIndependentTreeOracle() {
        Random random = new Random(BOOL_SEED);
        List<Document> documents = randomDocuments(random, TERMS, 45);
        try (SearchEngine<Integer, Document> engine = engine(documents)) {
            for (int trial = 0; trial < 220; trial++) {
                Generated generated = generated(random, 3);
                SearchRequest<Document> search = SearchRequest.<Document>builder()
                        .query(generated.query())
                        .limit(20)
                        .build();
                HighlightedSearchResult<Document> result = highlighted(
                        engine,
                        search,
                        List.of(BODY_TEXT, TITLE_TEXT)
                );
                String replay = "seed=" + BOOL_SEED + " trial=" + trial;
                assertCanonical(engine, search, result, replay);

                for (HighlightedSearchHit<Document> hit : result.hits()) {
                    V32TestReference.EvidenceEvaluation expected =
                            V32TestReference.evaluate(
                                    generated.evidence().apply(hit.hit().document())
                            );
                    assertTrue(expected.matched(), replay);
                    assertEquals(
                            expectedRanges(expected, "body"),
                            ranges(hit, "body"),
                            replay
                    );
                    assertEquals(
                            expectedRanges(expected, "title"),
                            ranges(hit, "title"),
                            replay
                    );
                    List<String> expectedFields = List.of("body", "title").stream()
                            .filter(field -> !expectedRanges(expected, field).isEmpty())
                            .toList();
                    assertEquals(
                            expectedFields,
                            hit.highlights().stream()
                                    .map(FieldHighlight::fieldName)
                                    .toList(),
                            replay
                    );
                }
            }
        }
    }

    private static Generated generated(Random random, int depth) {
        if (depth == 0 || random.nextInt(4) == 0) {
            return leaf(random);
        }
        if (random.nextInt(4) == 0) {
            Generated child = generated(random, depth - 1);
            return new Generated(
                    child.query().boost(random.nextBoolean() ? 0.5 : 2.0),
                    document -> new V32TestReference.BoostEvidence(
                            child.evidence().apply(document)
                    )
            );
        }

        int mustCount = random.nextInt(3);
        int shouldCount = 1 + random.nextInt(3);
        List<Generated> must = new ArrayList<>();
        List<Generated> should = new ArrayList<>();
        SearchQueries.BoolBuilder<Document> builder = SearchQueries.bool();
        for (int index = 0; index < mustCount; index++) {
            Generated child = generated(random, depth - 1);
            must.add(child);
            builder.must(child.query());
        }
        for (int index = 0; index < shouldCount; index++) {
            Generated child = generated(random, depth - 1);
            should.add(child);
            builder.should(child.query());
        }
        int minimum = must.isEmpty()
                ? 1 + random.nextInt(should.size())
                : random.nextInt(should.size() + 1);
        builder.minimumShouldMatch(minimum);
        SearchQuery<Document> query = builder.build();
        return new Generated(
                query,
                document -> new V32TestReference.BoolEvidence(
                        must.stream()
                                .map(child -> child.evidence().apply(document))
                                .toList(),
                        should.stream()
                                .map(child -> child.evidence().apply(document))
                                .toList(),
                        minimum
                )
        );
    }

    private static Generated leaf(Random random) {
        boolean body = random.nextBoolean();
        TextField<Document> field = body ? BODY_TEXT : TITLE_TEXT;
        String fieldName = field.name();
        String term = TERMS.get(random.nextInt(TERMS.size()));
        return new Generated(
                SearchQueries.text(field, term),
                document -> {
                    String source = body ? document.body() : document.title();
                    List<V32TestReference.FieldRange> ranges = occurrences(source)
                            .stream()
                            .filter(token -> token.term().equals(term))
                            .map(token -> new V32TestReference.FieldRange(
                                    fieldName,
                                    token.range()
                            ))
                            .toList();
                    return new V32TestReference.LeafEvidence(
                            !ranges.isEmpty(),
                            ranges
                    );
                }
        );
    }

    private static List<V32TestReference.Range> expectedRanges(
            V32TestReference.EvidenceEvaluation evaluation,
            String fieldName
    ) {
        return V32TestReference.normalizeRanges(evaluation.ranges().stream()
                .filter(range -> range.fieldName().equals(fieldName))
                .map(V32TestReference.FieldRange::range)
                .toList());
    }

    private static List<V32TestReference.ScoredTerm> scoredTerms(
            List<Document> corpus,
            List<TokenOccurrence> documentTerms,
            double averageLength,
            Bm25Config config
    ) {
        Set<String> terms = new LinkedHashSet<>();
        documentTerms.forEach(token -> terms.add(token.term()));
        List<V32TestReference.ScoredTerm> scored = new ArrayList<>();
        for (String term : terms) {
            List<V32TestReference.Range> ranges = documentTerms.stream()
                    .filter(token -> token.term().equals(term))
                    .map(TokenOccurrence::range)
                    .toList();
            int documentFrequency = (int) corpus.stream()
                    .filter(document -> occurrences(document.body()).stream()
                            .anyMatch(token -> token.term().equals(term)))
                    .count();
            double inverseDocumentFrequency = Math.log1p(
                    (corpus.size() - documentFrequency + 0.5)
                            / (documentFrequency + 0.5)
            );
            int frequency = ranges.size();
            double normalization = config.k1() * (
                    1.0 - config.b()
                            + config.b() * documentTerms.size() / averageLength
            );
            double score = inverseDocumentFrequency
                    * frequency * (config.k1() + 1.0)
                    / (frequency + normalization);
            scored.add(new V32TestReference.ScoredTerm(term, score, ranges));
        }
        return List.copyOf(scored);
    }

    private static List<OffsetAnalyzedToken> randomOffsetAnalysis(
            Random random,
            int minimumPositions,
            int maximumPositions
    ) {
        int positions = minimumPositions
                + random.nextInt(maximumPositions - minimumPositions + 1);
        List<OffsetAnalyzedToken> tokens = new ArrayList<>();
        for (int position = 0; position < positions; position++) {
            int increment = 1 + random.nextInt(3);
            Set<String> alternatives = new LinkedHashSet<>();
            int alternativeCount = 1 + random.nextInt(2);
            while (alternatives.size() < alternativeCount) {
                alternatives.add(TERMS.get(random.nextInt(TERMS.size())));
            }
            int start = position * 2;
            boolean first = true;
            for (String term : alternatives) {
                tokens.add(new OffsetAnalyzedToken(
                        term,
                        first ? increment : 0,
                        start,
                        start + 1
                ));
                first = false;
            }
        }
        return List.copyOf(tokens);
    }

    private static List<V32TestReference.PhraseSlot> slots(
            List<OffsetAnalyzedToken> tokens
    ) {
        List<V32TestReference.PhraseSlot> slots = new ArrayList<>();
        int logicalPosition = -1;
        int firstPosition = -1;
        int currentPosition = -1;
        List<String> alternatives = new ArrayList<>();
        for (OffsetAnalyzedToken token : tokens) {
            logicalPosition += token.positionIncrement();
            if (firstPosition < 0) {
                firstPosition = logicalPosition;
            }
            if (currentPosition >= 0 && logicalPosition != currentPosition) {
                slots.add(new V32TestReference.PhraseSlot(
                        currentPosition - firstPosition,
                        alternatives
                ));
                alternatives = new ArrayList<>();
            }
            currentPosition = logicalPosition;
            alternatives.add(token.term());
        }
        slots.add(new V32TestReference.PhraseSlot(
                currentPosition - firstPosition,
                alternatives
        ));
        return List.copyOf(slots);
    }

    private static List<V32TestReference.Occurrence> offsetOccurrences(
            List<OffsetAnalyzedToken> tokens
    ) {
        List<V32TestReference.Occurrence> occurrences = new ArrayList<>();
        int logicalPosition = -1;
        for (OffsetAnalyzedToken token : tokens) {
            logicalPosition += token.positionIncrement();
            occurrences.add(new V32TestReference.Occurrence(
                    token.term(),
                    logicalPosition,
                    new V32TestReference.Range(
                            token.startOffset(),
                            token.endOffset()
                    )
            ));
        }
        return List.copyOf(occurrences);
    }

    private static HighlightedSearchResult<Document> highlighted(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> search,
            List<TextField<Document>> fields
    ) {
        HighlightedSearchRequest.Builder<Document> builder =
                HighlightedSearchRequest.<Document>builder(search)
                        .contextCharacters(0)
                        .maxFragmentsPerField(50);
        fields.forEach(builder::field);
        return engine.search(builder.build());
    }

    private static void assertCanonical(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> search,
            HighlightedSearchResult<Document> highlighted,
            String replay
    ) {
        assertEquals(
                engine.search(search).hits(),
                highlighted.hits().stream().map(HighlightedSearchHit::hit).toList(),
                replay
        );
    }

    private static List<V32TestReference.Range> ranges(
            HighlightedSearchHit<Document> hit,
            String fieldName
    ) {
        return hit.highlights().stream()
                .filter(field -> field.fieldName().equals(fieldName))
                .findFirst()
                .stream()
                .map(FieldHighlight::fragments)
                .flatMap(List::stream)
                .map(HighlightFragment::spans)
                .flatMap(List::stream)
                .map(span -> new V32TestReference.Range(
                        span.startOffset(),
                        span.endOffset()
                ))
                .toList();
    }

    private static SearchEngine<Integer, Document> engine(
            List<Document> documents
    ) {
        SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(TITLE_TEXT))
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
        engine.addAll(documents).join();
        return engine;
    }

    private static List<Document> randomDocuments(
            Random random,
            List<String> vocabulary,
            int count
    ) {
        List<Document> documents = new ArrayList<>(count);
        for (int id = 0; id < count; id++) {
            documents.add(new Document(
                    id,
                    String.join(" ", randomTerms(random, vocabulary, 1, 5)),
                    String.join(" ", randomTerms(random, vocabulary, 2, 10))
            ));
        }
        return List.copyOf(documents);
    }

    private static List<String> randomTerms(
            Random random,
            List<String> vocabulary,
            int minimum,
            int maximum
    ) {
        int count = minimum + random.nextInt(maximum - minimum + 1);
        List<String> terms = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            terms.add(vocabulary.get(random.nextInt(vocabulary.size())));
        }
        return List.copyOf(terms);
    }

    private static List<TokenOccurrence> occurrences(String source) {
        List<TokenOccurrence> occurrences = new ArrayList<>();
        int position = 0;
        int start = 0;
        while (start < source.length()) {
            int end = source.indexOf(' ', start);
            if (end < 0) {
                end = source.length();
            }
            occurrences.add(new TokenOccurrence(
                    source.substring(start, end),
                    position++,
                    new V32TestReference.Range(start, end)
            ));
            start = end + 1;
        }
        return List.copyOf(occurrences);
    }

    private record Generated(
            SearchQuery<Document> query,
            Function<Document, V32TestReference.EvidenceNode> evidence
    ) {
    }

    private record TokenOccurrence(
            String term,
            int position,
            V32TestReference.Range range
    ) {
    }

    private record Document(int id, String title, String body) {
    }
}
