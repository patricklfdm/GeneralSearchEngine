package io.github.patricklfdm.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.patricklfdm.generalsearch.analysis.Analyzer;
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

    private record Article(String body) {}
}
