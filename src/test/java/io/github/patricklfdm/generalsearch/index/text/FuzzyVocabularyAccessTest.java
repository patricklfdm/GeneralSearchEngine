package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.ArrayList;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class FuzzyVocabularyAccessTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void visitsEveryNormalizedVocabularyTermSynchronouslyAndOnce() {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        IndexBuilder<Document> builder = index.toBuilder();
        builder.add(0, new Document("gamma alpha"));
        builder.add(1, new Document("beta alpha"));
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<Document> built =
                (TextIndexSnapshot<Document>) builder.build();
        List<String> visited = new ArrayList<>();

        FuzzyVocabularyAccess.forEachTerm(built, visited::add);

        assertEquals(List.of("alpha", "beta", "gamma"), visited);
    }

    @Test
    void validatesArgumentsAndPropagatesConsumerFailureUnchanged() {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        assertThrows(
                NullPointerException.class,
                () -> FuzzyVocabularyAccess.forEachTerm(null, ignored -> { })
        );
        assertThrows(
                NullPointerException.class,
                () -> FuzzyVocabularyAccess.forEachTerm(index, null)
        );

        IndexBuilder<Document> builder = index.toBuilder();
        builder.add(0, new Document("alpha"));
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<Document> built =
                (TextIndexSnapshot<Document>) builder.build();
        IllegalStateException expected = new IllegalStateException("stop");
        IllegalStateException actual = assertThrows(
                IllegalStateException.class,
                () -> FuzzyVocabularyAccess.forEachTerm(
                        built,
                        ignored -> { throw expected; }
                )
        );
        assertSame(expected, actual);
    }

    @Test
    void visitsBoundedOsaMatchesInNumericCodePointTraversalOrder() {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        IndexBuilder<Document> builder = index.toBuilder();
        builder.add(0, new Document("tea ten the alpha"));
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<Document> built =
                (TextIndexSnapshot<Document>) builder.build();
        List<String> visited = new ArrayList<>();

        FuzzyVocabularyAccess.forEachWithinEditDistance(
                built,
                "teh",
                1,
                (term, distance) -> visited.add(term + ":" + distance)
        );

        assertEquals(List.of("tea:1", "ten:1", "the:1"), visited);
    }

    @Test
    void boundedVisitorValidatesInputsAndPropagatesConsumerFailure() {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        assertThrows(
                NullPointerException.class,
                () -> FuzzyVocabularyAccess.forEachWithinEditDistance(
                        null, "alpha", 1, (term, distance) -> { })
        );
        assertThrows(
                NullPointerException.class,
                () -> FuzzyVocabularyAccess.forEachWithinEditDistance(
                        index, null, 1, (term, distance) -> { })
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> FuzzyVocabularyAccess.forEachWithinEditDistance(
                        index, "", 1, (term, distance) -> { })
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> FuzzyVocabularyAccess.forEachWithinEditDistance(
                        index, "alpha", 3, (term, distance) -> { })
        );

        TextIndexSnapshot<Document> built = indexOf("alpha");
        IllegalStateException expected = new IllegalStateException("stop");
        IllegalStateException actual = assertThrows(
                IllegalStateException.class,
                () -> FuzzyVocabularyAccess.forEachWithinEditDistance(
                        built,
                        "alpha",
                        0,
                        (term, distance) -> { throw expected; }
                )
        );
        assertSame(expected, actual);
    }

    private static TextIndexSnapshot<Document> indexOf(String term) {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        IndexBuilder<Document> builder = index.toBuilder();
        builder.add(0, new Document(term));
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<Document> built =
                (TextIndexSnapshot<Document>) builder.build();
        return built;
    }

    private record Document(String body) {
    }
}
