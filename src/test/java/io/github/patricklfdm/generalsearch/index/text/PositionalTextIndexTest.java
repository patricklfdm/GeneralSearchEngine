package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class PositionalTextIndexTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);

    @Test
    void retainsRepeatedTermsGapsAlternativesAndInitialGaps() {
        TextField<Article> text = TextField.of(BODY, fixtureAnalyzer());
        TextIndexBuilder<Article> builder = new TextIndexBuilder<>(
                TextIndexSnapshot.empty(text));
        builder.add(0, new Article("repeat"));
        builder.add(1, new Article("gaps"));
        builder.add(2, new Article("alternatives"));
        builder.add(3, new Article("duplicate-position"));
        builder.add(4, new Article("initial-gap"));

        TextIndexSnapshot<Article> index = snapshot(builder);

        assertEquals(List.of(0, 1), positions(index, "very", 0));
        assertEquals(List.of(2), positions(index, "good", 0));
        assertEquals(List.of(0), positions(index, "quick", 1));
        assertEquals(List.of(2), positions(index, "brown", 1));
        assertEquals(List.of(3), positions(index, "fox", 1));
        assertEquals(List.of(0), positions(index, "usa", 2));
        assertEquals(List.of(0), positions(index, "united_states", 2));
        assertEquals(List.of(1), positions(index, "travel", 2));
        assertEquals(List.of(0), positions(index, "echo", 3));
        assertEquals(1, index.posting("echo").termFrequency(3));
        assertEquals(2, index.documentLength(3));
        assertEquals(List.of(2), positions(index, "start", 4));
        assertEquals(1, index.documentLength(4));
        assertEquals(12, index.totalDocumentLength());
    }

    @Test
    void updatesOnReorderingAndKeepsOldSnapshotIsolated() {
        TextField<Article> text = TextField.of(BODY, fixtureAnalyzer());
        TextIndexBuilder<Article> initial = new TextIndexBuilder<>(
                TextIndexSnapshot.empty(text));
        initial.add(0, new Article("old-order"));
        TextIndexSnapshot<Article> base = snapshot(initial);

        TextIndexBuilder<Article> changes = new TextIndexBuilder<>(base);
        changes.update(0, new Article("old-order"), new Article("new-order"));
        TextIndexSnapshot<Article> updated = snapshot(changes);

        assertEquals(List.of(0), positions(base, "java", 0));
        assertEquals(List.of(1), positions(base, "search", 0));
        assertEquals(List.of(1), positions(updated, "java", 0));
        assertEquals(List.of(0), positions(updated, "search", 0));
        assertEquals(1, updated.posting("java").termFrequency(0));
        assertEquals(2, updated.documentLength(0));

        TextIndexBuilder<Article> noOp = new TextIndexBuilder<>(updated);
        noOp.update(0, new Article("new-order"), new Article("new-order"));
        assertSame(updated, noOp.build());
    }

    @Test
    void publishesTokenCountOnlyChangesWithoutRepublishingEqualPositions() {
        TextField<Article> text = TextField.of(BODY, fixtureAnalyzer());
        TextIndexBuilder<Article> initial = new TextIndexBuilder<>(
                TextIndexSnapshot.empty(text));
        initial.add(0, new Article("duplicate-position"));
        TextIndexSnapshot<Article> base = snapshot(initial);
        PostingList basePosting = base.posting("echo");

        TextIndexBuilder<Article> changes = new TextIndexBuilder<>(base);
        changes.update(
                0,
                new Article("duplicate-position"),
                new Article("single-position")
        );
        TextIndexSnapshot<Article> updated = snapshot(changes);

        assertSame(basePosting, updated.posting("echo"));
        assertEquals(List.of(0), positions(updated, "echo", 0));
        assertEquals(2, base.documentLength(0));
        assertEquals(1, updated.documentLength(0));
        assertEquals(1, updated.totalDocumentLength());
    }

    @Test
    void preservesLegacyPostingListMethodsOverPositionStorage() {
        PostingList empty = PostingList.empty();
        PostingList posting = empty.withTermFrequency(7, 3);

        assertEquals(1, posting.documentFrequency());
        assertTrue(posting.documents().get(7));
        assertEquals(3, posting.termFrequency(7));
        assertEquals(List.of(0, 1, 2), positions(posting, 7));
        assertSame(posting, posting.withTermFrequency(7, 3));
        assertEquals(0, posting.termFrequency(-1));

        PostingList changed = posting.withTermFrequency(7, 2);
        assertEquals(List.of(0, 1), positions(changed, 7));
        PostingList removed = changed.without(7);
        assertEquals(0, removed.documentFrequency());
        assertEquals(0, removed.termFrequency(7));
        assertFalse(removed.documents().get(7));

        assertThrows(IllegalArgumentException.class,
                () -> empty.withTermFrequency(-1, 1));
        assertThrows(IllegalArgumentException.class,
                () -> empty.withTermFrequency(0, 0));
        assertThrows(IllegalArgumentException.class,
                () -> empty.withTermFrequency(0, -1));
        assertThrows(IllegalArgumentException.class, () -> empty.without(-1));
    }

    @Test
    void rejectsMalformedPositionedOutputBeforeMutatingBuilder() {
        TextField<Article> text = TextField.of(BODY, malformedAnalyzer());
        TextIndexBuilder<Article> builder = new TextIndexBuilder<>(
                TextIndexSnapshot.empty(text));

        IllegalArgumentException nullList = assertThrows(
                IllegalArgumentException.class,
                () -> builder.add(0, new Article("null-list"))
        );
        assertTrue(nullList.getMessage().contains("'body'"));
        assertTrue(nullList.getMessage().contains("null token list"));

        IllegalArgumentException nullToken = assertThrows(
                IllegalArgumentException.class,
                () -> builder.add(0, new Article("null-token"))
        );
        assertTrue(nullToken.getMessage().contains("index 1"));

        IllegalArgumentException firstZero = assertThrows(
                IllegalArgumentException.class,
                () -> builder.add(0, new Article("first-zero"))
        );
        assertTrue(firstZero.getMessage().contains("first position increment"));

        IllegalArgumentException overflow = assertThrows(
                IllegalArgumentException.class,
                () -> builder.add(0, new Article("overflow"))
        );
        assertTrue(overflow.getMessage().contains("token index 1"));
        assertTrue(overflow.getCause() instanceof ArithmeticException);

        builder.add(0, new Article("valid"));
        TextIndexSnapshot<Article> index = snapshot(builder);
        assertEquals(List.of(0), positions(index, "valid", 0));
        assertEquals(1, index.documentLength(0));
    }

    @Test
    void propagatesAnalyzerFailureUnchanged() {
        RuntimeException failure = new RuntimeException("synthetic failure");
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                throw failure;
            }
        };
        TextIndexBuilder<Article> builder = new TextIndexBuilder<>(
                TextIndexSnapshot.empty(TextField.of(BODY, analyzer)));

        RuntimeException thrown = assertThrows(
                RuntimeException.class,
                () -> builder.add(0, new Article("ignored"))
        );

        assertSame(failure, thrown);
    }

    private static Analyzer fixtureAnalyzer() {
        return analyzer(text -> switch (text) {
            case "repeat" -> List.of(
                    new AnalyzedToken("very", 1),
                    new AnalyzedToken("very", 1),
                    new AnalyzedToken("good", 1));
            case "gaps" -> List.of(
                    new AnalyzedToken("quick", 1),
                    new AnalyzedToken("brown", 2),
                    new AnalyzedToken("fox", 1));
            case "alternatives" -> List.of(
                    new AnalyzedToken("usa", 1),
                    new AnalyzedToken("united_states", 0),
                    new AnalyzedToken("travel", 1));
            case "duplicate-position" -> List.of(
                    new AnalyzedToken("echo", 1),
                    new AnalyzedToken("echo", 0));
            case "single-position" -> List.of(new AnalyzedToken("echo", 1));
            case "initial-gap" -> List.of(new AnalyzedToken("start", 3));
            case "old-order" -> List.of(
                    new AnalyzedToken("java", 1),
                    new AnalyzedToken("search", 1));
            case "new-order" -> List.of(
                    new AnalyzedToken("search", 1),
                    new AnalyzedToken("java", 1));
            default -> List.of();
        });
    }

    private static Analyzer malformedAnalyzer() {
        return analyzer(text -> switch (text) {
            case "null-list" -> null;
            case "null-token" -> Arrays.asList(
                    new AnalyzedToken("first", 1), null);
            case "first-zero" -> List.of(new AnalyzedToken("first", 0));
            case "overflow" -> List.of(
                    new AnalyzedToken("first", Integer.MAX_VALUE),
                    new AnalyzedToken("second", 2));
            case "valid" -> List.of(new AnalyzedToken("valid", 1));
            default -> List.of();
        });
    }

    private static Analyzer analyzer(PositionedTokens tokens) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                List<AnalyzedToken> positioned = tokens.analyze(text);
                if (positioned == null) {
                    return List.of();
                }
                return positioned.stream()
                        .filter(java.util.Objects::nonNull)
                        .map(token -> new Token(token.term()))
                        .toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return tokens.analyze(text);
            }
        };
    }

    private static TextIndexSnapshot<Article> snapshot(
            IndexBuilder<Article> builder
    ) {
        return (TextIndexSnapshot<Article>) builder.build();
    }

    private static List<Integer> positions(
            TextIndexSnapshot<Article> index,
            String term,
            int docId
    ) {
        return positions(index.posting(term), docId);
    }

    private static List<Integer> positions(PostingList posting, int docId) {
        IntPositions positions = posting.positions(docId);
        List<Integer> values = new ArrayList<>(positions.size());
        for (int index = 0; index < positions.size(); index++) {
            values.add(positions.get(index));
        }
        return List.copyOf(values);
    }

    private record Article(String body) {}

    @FunctionalInterface
    private interface PositionedTokens {
        List<AnalyzedToken> analyze(String text);
    }
}
