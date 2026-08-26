package io.github.patricklfdm.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class TextQueryTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void termUsesCanonicalAnalyzedText() {
        TermQuery<Article> query = Query.term(TEXT, "ＪＡＶＡ");

        assertEquals("java", query.term());
        assertTrue(query.matches(new Article("Java search")));
        assertFalse(query.matches(new Article("JavaScript")));
        assertFalse(query.matches(new Article(null)));
        assertThrows(IllegalArgumentException.class, () -> Query.term(TEXT, "!!!"));
        assertThrows(IllegalArgumentException.class,
                () -> Query.term(TEXT, "java search"));
        assertEquals("java", Query.term(TEXT, "java JAVA").term());
    }

    @Test
    void anyAndAllDeduplicateTermsAndZeroTokensMatchNothing() {
        AnyTermsQuery<Article> any = Query.anyTerms(TEXT, "JAVA java engine");
        AllTermsQuery<Article> all = Query.allTerms(TEXT, "JAVA java engine");

        assertEquals(java.util.List.of("java", "engine"), any.terms());
        assertTrue(any.matches(new Article("engine internals")));
        assertTrue(all.matches(new Article("An ENGINE for Java")));
        assertFalse(all.matches(new Article("Java only")));
        assertFalse(Query.anyTerms(TEXT, "---").matches(new Article("anything")));
        assertFalse(Query.allTerms(TEXT, "---").matches(new Article("anything")));
        assertThrows(NullPointerException.class, () -> Query.anyTerms(TEXT, null));
    }

    @Test
    void queryAndDocumentMatchingUseNativePositionedAnalysis() {
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of(new Token("legacy"));
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return switch (text) {
                    case "query" -> List.of(new AnalyzedToken("target", 3));
                    case "both" -> List.of(
                            new AnalyzedToken("target", 1),
                            new AnalyzedToken("alternative", 0));
                    case "matching" -> List.of(
                            new AnalyzedToken("target", 2),
                            new AnalyzedToken("alternative", 0));
                    default -> List.of(new AnalyzedToken("other", 1));
                };
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article matching = new Article("matching");

        assertEquals("target", Query.term(text, "query").term());
        assertTrue(Query.term(text, "query").matches(matching));
        assertEquals(List.of("target", "alternative"),
                Query.anyTerms(text, "both").terms());
        assertTrue(Query.allTerms(text, "both").matches(matching));
        assertEquals(List.of(new Token("legacy")), text.analyzeDocument(matching));
    }

    @Test
    void rejectsMalformedPositionedQueryOutputWithFieldContext() {
        assertInvalidPositionedAnalysis(null, "null token list");
        assertInvalidPositionedAnalysis(
                Arrays.asList((AnalyzedToken) null), "null token at index 0");
        assertInvalidPositionedAnalysis(
                List.of(new AnalyzedToken("zero", 0)),
                "non-positive first position increment");
        assertInvalidPositionedAnalysis(List.of(
                new AnalyzedToken("large", Integer.MAX_VALUE),
                new AnalyzedToken("overflow", 2)), "overflowed logical position");
    }

    private static void assertInvalidPositionedAnalysis(
            List<AnalyzedToken> output,
            String expectedDetail
    ) {
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return output;
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);

        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> Query.term(text, "query"));
        assertTrue(failure.getMessage().contains("text field 'body'"));
        assertTrue(failure.getMessage().contains(expectedDetail));
    }

    private record Article(String body) {}
}
