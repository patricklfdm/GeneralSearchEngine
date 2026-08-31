package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.FieldHighlight;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightSpan;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchHit;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

class HighlightedQueryEvidenceTest {
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
    void phraseSelectsLeastSlopBeforeEarliestSourceAndHandlesRepeatedTerms() {
        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(1, "", "alpha x beta alpha beta")).join();

            HighlightedSearchResult<Document> sloppy = highlighted(
                    engine,
                    SearchQueries.phrase(BODY_TEXT, "alpha beta", 1),
                    BODY_TEXT
            );
            assertCanonical(engine, sloppy, SearchQueries.phrase(
                    BODY_TEXT,
                    "alpha beta",
                    1
            ));
            assertSpans(sloppy, "body", new Range(13, 23));
        }

        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(1, "", "very very very")).join();
            HighlightedSearchResult<Document> repeated = highlighted(
                    engine,
                    SearchQueries.phrase(BODY_TEXT, "very very"),
                    BODY_TEXT
            );
            assertSpans(repeated, "body", new Range(0, 9));
        }
    }

    @Test
    void phraseUsesSamePositionAlternativesAndIncludesInterveningSource() {
        OffsetAnalyzer alternatives = text -> switch (text) {
            case "alternative-query" -> List.of(
                    new OffsetAnalyzedToken("usa", 1, 0, 11),
                    new OffsetAnalyzedToken("united_states", 0, 0, 11),
                    new OffsetAnalyzedToken("travel", 1, 12, 17)
            );
            case "USA travel" -> List.of(
                    new OffsetAnalyzedToken("usa", 1, 0, 3),
                    new OffsetAnalyzedToken("united_states", 0, 0, 3),
                    new OffsetAnalyzedToken("travel", 1, 4, 10)
            );
            default -> List.of();
        };
        TextField<Document> field = TextField.of(BODY, alternatives);
        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, field)) {
            engine.add(new Document(1, "", "USA travel")).join();
            HighlightedSearchResult<Document> result = highlighted(
                    engine,
                    SearchQueries.phrase(field, "alternative-query"),
                    field
            );
            assertSpans(result, "body", new Range(0, 10));
            assertEquals("USA travel", result.hits().getFirst().highlights()
                    .getFirst().fragments().getFirst().text());
        }
    }

    @Test
    void fuzzyHighlightsOnlyEveryOccurrenceOfScoringSelectedExpansion() {
        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(1, "", "museum museums museum")).join();

            HighlightedSearchResult<Document> exact = highlighted(
                    engine,
                    SearchQueries.fuzzy(BODY_TEXT, "museum"),
                    BODY_TEXT
            );
            assertSpans(exact, "body", new Range(0, 6), new Range(15, 21));

            HighlightedSearchResult<Document> typo = highlighted(
                    engine,
                    SearchQueries.fuzzy(BODY_TEXT, "musem"),
                    BODY_TEXT
            );
            assertSpans(typo, "body", new Range(0, 6), new Range(15, 21));
        }

        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(1, "", "bat cut")).join();
            HighlightedSearchResult<Document> tie = highlighted(
                    engine,
                    SearchQueries.fuzzy(BODY_TEXT, "cat"),
                    BODY_TEXT
            );
            assertSpans(tie, "body", new Range(0, 3));
        }
    }

    @Test
    void boolCollectsAllMatchingChildrenInRequestedFieldOrder() {
        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(
                    1,
                    "alpha",
                    "new york beta x gamma museum"
            )).join();
            SearchQuery<Document> query = SearchQueries.<Document>bool()
                    .must(SearchQueries.text(TITLE_TEXT, "alpha"))
                    .should(SearchQueries.phrase(BODY_TEXT, "new york"))
                    .should(SearchQueries.phrase(BODY_TEXT, "beta gamma"))
                    .should(SearchQueries.fuzzy(BODY_TEXT, "musem"))
                    .minimumShouldMatch(1)
                    .build();
            SearchRequest<Document> search = SearchRequest.of(query);
            HighlightedSearchRequest<Document> request =
                    HighlightedSearchRequest.<Document>builder(search)
                            .field(BODY_TEXT)
                            .field(TITLE_TEXT)
                            .contextCharacters(0)
                            .maxFragmentsPerField(10)
                            .build();

            HighlightedSearchResult<Document> result = engine.search(request);
            assertEquals(
                    engine.search(search).hits(),
                    result.hits().stream().map(HighlightedSearchHit::hit).toList()
            );
            assertEquals(
                    List.of("body", "title"),
                    result.hits().getFirst().highlights().stream()
                            .map(FieldHighlight::fieldName)
                            .toList()
            );
            assertSpans(result, "body", new Range(0, 8), new Range(22, 28));
            assertSpans(result, "title", new Range(0, 5));
        }
    }

    @Test
    void nestedBoostForwardsZeroScoreEvidenceAndOverlapsNormalize() {
        try (SearchEngine<Integer, Document> engine = engine(TITLE_TEXT, BODY_TEXT)) {
            engine.add(new Document(1, "", "new york alpha")).join();
            SearchQuery<Document> overlapping = SearchQueries.<Document>bool()
                    .should(SearchQueries.text(BODY_TEXT, "new"))
                    .should(SearchQueries.phrase(BODY_TEXT, "new york"))
                    .minimumShouldMatch(1)
                    .build();
            HighlightedSearchResult<Document> merged = highlighted(
                    engine,
                    overlapping,
                    BODY_TEXT
            );
            assertSpans(merged, "body", new Range(0, 8));

            SearchQuery<Document> underflow = SearchQueries
                    .text(BODY_TEXT, "alpha")
                    .boost(Double.MIN_VALUE)
                    .boost(Double.MIN_VALUE);
            HighlightedSearchResult<Document> zeroScore = highlighted(
                    engine,
                    underflow,
                    BODY_TEXT
            );
            assertEquals(0.0, zeroScore.hits().getFirst().hit().score());
            assertSpans(zeroScore, "body", new Range(9, 14));
        }
    }

    private static SearchEngine<Integer, Document> engine(
            TextField<Document> first,
            TextField<Document> second
    ) {
        SearchSchema<Document, Integer> schema = SearchSchema
                .builder(Document.class, ID)
                .textField(first)
                .textField(second)
                .build();
        return SearchEngine.builder(schema)
                .index(IndexDefinition.text(first))
                .index(IndexDefinition.text(second))
                .build();
    }

    private static HighlightedSearchResult<Document> highlighted(
            SearchEngine<Integer, Document> engine,
            SearchQuery<Document> query,
            TextField<Document> field
    ) {
        SearchRequest<Document> search = SearchRequest.of(query);
        HighlightedSearchResult<Document> result = engine.search(
                HighlightedSearchRequest.<Document>builder(search)
                        .field(field)
                        .contextCharacters(0)
                        .maxFragmentsPerField(10)
                        .build()
        );
        assertEquals(
                engine.search(search).hits(),
                result.hits().stream().map(HighlightedSearchHit::hit).toList()
        );
        return result;
    }

    private static void assertCanonical(
            SearchEngine<Integer, Document> engine,
            HighlightedSearchResult<Document> result,
            SearchQuery<Document> query
    ) {
        List<SearchHit<Document>> canonical = engine.search(
                SearchRequest.of(query)
        ).hits();
        assertEquals(
                canonical,
                result.hits().stream().map(HighlightedSearchHit::hit).toList()
        );
    }

    private static void assertSpans(
            HighlightedSearchResult<Document> result,
            String fieldName,
            Range... expected
    ) {
        FieldHighlight field = result.hits().getFirst().highlights().stream()
                .filter(highlight -> highlight.fieldName().equals(fieldName))
                .findFirst()
                .orElseThrow();
        List<Range> actual = field.fragments().stream()
                .map(HighlightFragment::spans)
                .flatMap(List::stream)
                .map(HighlightedQueryEvidenceTest::range)
                .toList();
        assertEquals(List.of(expected), actual);
    }

    private static Range range(HighlightSpan span) {
        return new Range(span.startOffset(), span.endOffset());
    }

    private record Document(int id, String title, String body) {
    }

    private record Range(int start, int end) {
    }
}
