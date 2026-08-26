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

    private record Document(String body) {
    }
}
