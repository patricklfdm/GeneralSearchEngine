package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.FieldHighlight;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightSpan;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

class HighlightedSearchEngineTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> SUMMARY =
            Field.of("summary", String.class, Article::summary);
    private static final TextField<Article> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final TextField<Article> SUMMARY_TEXT =
            TextField.of(SUMMARY, Analyzer.simple());

    @Test
    void textHighlightPreservesCanonicalHitsAndSelectsEveryOccurrence() {
        try (SearchEngine<Long, Article> engine = engine(
                BODY_TEXT,
                List.of(BODY_TEXT, SUMMARY_TEXT)
        )) {
            Article first = new Article(1L, "alpha beta alpha", null);
            Article second = new Article(2L, "beta alpha", "unrelated");
            engine.addAll(List.of(first, second)).join();
            SearchRequest<Article> search = SearchRequest.of(
                    SearchQueries.text(BODY_TEXT, "alpha alpha")
            );
            HighlightedSearchRequest<Article> request =
                    HighlightedSearchRequest.<Article>builder(search)
                            .field(SUMMARY_TEXT)
                            .field(BODY_TEXT)
                            .contextCharacters(0)
                            .maxFragmentsPerField(3)
                            .build();

            HighlightedSearchResult<Article> actual = engine.search(request);
            assertEquals(
                    engine.search(search).hits(),
                    actual.hits().stream().map(hit -> hit.hit()).toList()
            );
            assertSame(first, actual.hits().getFirst().hit().document());
            assertEquals(1, actual.hits().getFirst().highlights().size());
            FieldHighlight field = actual.hits().getFirst()
                    .highlights().getFirst();
            assertEquals("body", field.fieldName());
            assertEquals(2, field.fragments().size());
            assertFragment(field.fragments().get(0), 0, 5, "alpha", 0, 5);
            assertFragment(field.fragments().get(1), 11, 16, "alpha", 11, 16);
            assertEquals(1, actual.hits().get(1)
                    .highlights().getFirst().fragments().size());
        }
    }

    @Test
    void contextCoalescesWindowsCapsFragmentsAndProtectsSurrogates() {
        try (SearchEngine<Long, Article> engine = engine(BODY_TEXT, List.of(BODY_TEXT))) {
            engine.addAll(List.of(
                    new Article(1L, "alpha beta alpha", ""),
                    new Article(2L, "😀a", "")
            )).join();
            HighlightedSearchResult<Article> merged = engine.search(request(
                    SearchQueries.text(BODY_TEXT, "alpha"),
                    BODY_TEXT,
                    6,
                    3
            ));
            HighlightFragment mergedFragment = merged.hits().getFirst()
                    .highlights().getFirst().fragments().getFirst();
            assertEquals(0, mergedFragment.startOffset());
            assertEquals(16, mergedFragment.endOffset());
            assertEquals(2, mergedFragment.spans().size());

            HighlightedSearchResult<Article> capped = engine.search(request(
                    SearchQueries.text(BODY_TEXT, "alpha"),
                    BODY_TEXT,
                    0,
                    1
            ));
            assertEquals(1, capped.hits().getFirst()
                    .highlights().getFirst().fragments().size());

            HighlightedSearchResult<Article> surrogate = engine.search(request(
                    SearchQueries.text(BODY_TEXT, "a"),
                    BODY_TEXT,
                    1,
                    3
            ));
            HighlightFragment fragment = surrogate.hits().stream()
                    .filter(hit -> hit.hit().document().id() == 2L)
                    .findFirst()
                    .orElseThrow()
                    .highlights().getFirst().fragments().getFirst();
            assertFragment(fragment, 0, 3, "😀a", 2, 3);
        }
    }

    @Test
    void nfkcTermsMapBackToExactOriginalSourceRange() {
        try (SearchEngine<Long, Article> engine = engine(BODY_TEXT, List.of(BODY_TEXT))) {
            engine.add(new Article(1L, "A½B", "")).join();

            HighlightFragment fragment = engine.search(request(
                    SearchQueries.text(BODY_TEXT, "a1"),
                    BODY_TEXT,
                    0,
                    3
            )).hits().getFirst().highlights().getFirst().fragments().getFirst();

            assertFragment(fragment, 0, 2, "A½", 0, 2);
        }
    }

    @Test
    void validatesCanonicalFieldsAndCapabilitiesBeforeCorpusDependentWork() {
        Analyzer legacy = text -> Analyzer.simple().analyze(text);
        TextField<Article> legacyText = TextField.of(BODY, legacy);
        try (SearchEngine<Long, Article> engine = engine(
                legacyText,
                List.of(legacyText)
        )) {
            HighlightedSearchRequest<Article> request = request(
                    SearchQueries.text(legacyText, "absent"),
                    legacyText,
                    0,
                    1
            );
            assertThrows(UnsupportedOperationException.class, () ->
                    engine.search(request));
        }

        try (SearchEngine<Long, Article> engine = engine(BODY_TEXT, List.of(BODY_TEXT))) {
            TextField<Article> impostor = TextField.of(BODY, Analyzer.simple());
            HighlightedSearchRequest<Article> noncanonical = request(
                    SearchQueries.text(BODY_TEXT, "absent"),
                    impostor,
                    0,
                    1
            );
            assertThrows(IllegalArgumentException.class, () ->
                    engine.search(noncanonical));
        }
    }

    @Test
    void preservesWrappedRequestValidationAndSupportsPhraseQueries() {
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(BODY_TEXT)
                .build();
        try (SearchEngine<Long, Article> noIndex = SearchEngine.builder(schema).build()) {
            assertThrows(IllegalStateException.class, () -> noIndex.search(request(
                    SearchQueries.text(BODY_TEXT, "alpha"),
                    BODY_TEXT,
                    0,
                    1
            )));
            assertEquals(0, noIndex.search(request(
                    SearchQueries.text(BODY_TEXT, "---"),
                    BODY_TEXT,
                    0,
                    1
            )).hits().size());
        }

        try (SearchEngine<Long, Article> engine = engine(BODY_TEXT, List.of(BODY_TEXT))) {
            engine.add(new Article(1L, "alpha beta", "")).join();
            HighlightFragment phrase = engine.search(request(
                    SearchQueries.phrase(BODY_TEXT, "alpha beta"),
                    BODY_TEXT,
                    0,
                    1
            )).hits().getFirst().highlights().getFirst().fragments().getFirst();
            assertFragment(phrase, 0, 10, "alpha beta", 0, 10);
        }
    }

    @Test
    void rejectsInvalidOffsetOutputWithFieldAndTokenContext() {
        OffsetAnalyzer malformed = new OffsetAnalyzer() {
            @Override
            public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
                return List.of(new OffsetAnalyzedToken("alpha", 1, 0, text.length() + 1));
            }

            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return Analyzer.simple().analyzeWithPositions(text);
            }
        };
        TextField<Article> field = TextField.of(BODY, malformed);
        try (SearchEngine<Long, Article> engine = engine(field, List.of(field))) {
            engine.add(new Article(1L, "alpha", "")).join();
            IllegalArgumentException failure = assertThrows(
                    IllegalArgumentException.class,
                    () -> engine.search(request(
                            SearchQueries.text(field, "alpha"),
                            field,
                            0,
                            1
                    ))
            );
            assertTrue(failure.getMessage().contains("text field 'body'"));
            assertTrue(failure.getMessage().contains("token 0"));
        }
    }

    @Test
    void propagatesRequestedFieldExtractorAndAnalyzerFailures() {
        AtomicBoolean failExtraction = new AtomicBoolean();
        Field<Article, String> extracted = Field.of(
                "extracted",
                String.class,
                article -> {
                    if (failExtraction.get()) {
                        throw new IllegalStateException("extractor failure");
                    }
                    return article.body();
                }
        );
        TextField<Article> extractedText = TextField.of(extracted, Analyzer.simple());
        try (SearchEngine<Long, Article> engine = engine(
                extractedText,
                List.of(extractedText)
        )) {
            engine.add(new Article(1L, "alpha", "")).join();
            HighlightedSearchRequest<Article> request = request(
                    SearchQueries.text(extractedText, "alpha"),
                    extractedText,
                    0,
                    1
            );
            failExtraction.set(true);
            IllegalStateException failure = assertThrows(
                    IllegalStateException.class,
                    () -> engine.search(request)
            );
            assertEquals("extractor failure", failure.getMessage());
        }

        OffsetAnalyzer throwing = new OffsetAnalyzer() {
            @Override
            public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
                throw new IllegalArgumentException("analyzer failure");
            }

            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return Analyzer.simple().analyzeWithPositions(text);
            }
        };
        TextField<Article> throwingText = TextField.of(BODY, throwing);
        try (SearchEngine<Long, Article> engine = engine(
                throwingText,
                List.of(throwingText)
        )) {
            engine.add(new Article(1L, "alpha", "")).join();
            IllegalArgumentException failure = assertThrows(
                    IllegalArgumentException.class,
                    () -> engine.search(request(
                            SearchQueries.text(throwingText, "alpha"),
                            throwingText,
                            0,
                            1
                    ))
            );
            assertEquals("analyzer failure", failure.getMessage());
        }
    }

    @Test
    void followsDynamicTextIndexPublicationAndDrop() {
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(BODY_TEXT)
                .build();
        HighlightedSearchRequest<Article> request = request(
                SearchQueries.text(BODY_TEXT, "alpha"),
                BODY_TEXT,
                0,
                1
        );
        try (SearchEngine<Long, Article> engine = SearchEngine.builder(schema).build()) {
            engine.add(new Article(1L, "alpha", "")).join();
            assertThrows(IllegalStateException.class, () -> engine.search(request));

            engine.createIndex(IndexDefinition.text(BODY_TEXT)).join();
            assertEquals(1, engine.search(request).hits().size());

            engine.dropIndex(BODY.name()).join();
            assertThrows(IllegalStateException.class, () -> engine.search(request));
        }
    }

    @Test
    void rejectsCallsStartedAfterClose() {
        SearchEngine<Long, Article> engine = engine(BODY_TEXT, List.of(BODY_TEXT));
        HighlightedSearchRequest<Article> request = request(
                SearchQueries.text(BODY_TEXT, "alpha"),
                BODY_TEXT,
                0,
                1
        );
        engine.close();

        EngineRejectedExecutionException failure = assertThrows(
                EngineRejectedExecutionException.class,
                () -> engine.search(request)
        );
        assertEquals(EngineRejectedExecutionException.Reason.CLOSED, failure.reason());
    }

    @Test
    void keepsHitsAndSourceFromOneSnapshotDuringConcurrentMutation() throws Exception {
        CountDownLatch offsetEntered = new CountDownLatch(1);
        CountDownLatch releaseOffset = new CountDownLatch(1);
        AtomicBoolean block = new AtomicBoolean();
        OffsetAnalyzer blocking = new OffsetAnalyzer() {
            @Override
            public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
                if (block.get()) {
                    offsetEntered.countDown();
                    try {
                        if (!releaseOffset.await(5, TimeUnit.SECONDS)) {
                            throw new AssertionError("timed out releasing offset analysis");
                        }
                    } catch (InterruptedException failure) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError("offset analysis interrupted", failure);
                    }
                }
                return ((OffsetAnalyzer) Analyzer.simple()).analyzeWithOffsets(text);
            }

            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return Analyzer.simple().analyzeWithPositions(text);
            }
        };
        TextField<Article> field = TextField.of(BODY, blocking);
        Article original = new Article(1L, "alpha old", "");
        Article replacement = new Article(1L, "replacement", "");

        try (SearchEngine<Long, Article> engine = engine(field, List.of(field))) {
            engine.add(original).join();
            HighlightedSearchRequest<Article> request = request(
                    SearchQueries.text(field, "alpha"),
                    field,
                    0,
                    1
            );
            block.set(true);
            CompletableFuture<HighlightedSearchResult<Article>> pending =
                    CompletableFuture.supplyAsync(() -> engine.search(request));

            assertTrue(offsetEntered.await(5, TimeUnit.SECONDS));
            engine.update(replacement).join();
            releaseOffset.countDown();

            HighlightedSearchResult<Article> captured = pending.get(5, TimeUnit.SECONDS);
            assertSame(original, captured.hits().getFirst().hit().document());
            assertEquals("alpha", captured.hits().getFirst().highlights().getFirst()
                    .fragments().getFirst().text());
            assertEquals(0, engine.search(request).hits().size());
        } finally {
            releaseOffset.countDown();
        }
    }

    private static SearchEngine<Long, Article> engine(
            TextField<Article> indexed,
            List<TextField<Article>> configured
    ) {
        SearchSchema.Builder<Article, Long> schema =
                SearchSchema.builder(Article.class, ID);
        configured.forEach(schema::textField);
        return SearchEngine.builder(schema.build())
                .index(IndexDefinition.text(indexed))
                .build();
    }

    private static HighlightedSearchRequest<Article> request(
            io.github.patricklfdm.generalsearch.search.SearchQuery<Article> query,
            TextField<Article> field,
            int context,
            int maxFragments
    ) {
        return HighlightedSearchRequest.<Article>builder(SearchRequest.of(query))
                .field(field)
                .contextCharacters(context)
                .maxFragmentsPerField(maxFragments)
                .build();
    }

    private static void assertFragment(
            HighlightFragment fragment,
            int start,
            int end,
            String text,
            int spanStart,
            int spanEnd
    ) {
        assertEquals(start, fragment.startOffset());
        assertEquals(end, fragment.endOffset());
        assertEquals(text, fragment.text());
        assertEquals(1, fragment.spans().size());
        HighlightSpan span = fragment.spans().getFirst();
        assertEquals(spanStart, span.startOffset());
        assertEquals(spanEnd, span.endOffset());
    }

    private record Article(long id, String body, String summary) {
    }
}
