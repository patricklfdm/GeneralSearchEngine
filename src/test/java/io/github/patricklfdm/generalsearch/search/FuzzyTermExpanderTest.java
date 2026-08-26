package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class FuzzyTermExpanderTest {
    private static final long SEED = 0x46555a5a595f5633L;
    private static final int[] ALPHABET = {
            'a', 'b', 'c', 'd', 'e', 0x00e9, 0xe000, 0x10000, 0x1f600
    };
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Analyzer WHOLE_VALUE = text -> text.isEmpty()
            ? List.of()
            : List.of(new Token(text));
    private static final TextField<Document> TEXT =
            TextField.of(BODY, WHOLE_VALUE);
    private static final FuzzyTermExpander EXPANDER =
            new VocabularyScanningFuzzyTermExpander();

    @Test
    void expandsTheExactFrozenSetWithDistanceAndSimilarity() {
        TextIndexSnapshot<Document> index = indexOf(List.of(
                "restaurant",
                "restaurants",
                "restarant",
                "restorant",
                "restaurante",
                "resort"
        ));

        List<FuzzyExpansion> expansions = EXPANDER.expand(
                index,
                "restaurant",
                2
        );

        assertEquals(
                List.of(
                        "restaurant",
                        "restarant",
                        "restaurante",
                        "restaurants",
                        "restorant"
                ),
                expansions.stream().map(FuzzyExpansion::term).toList()
        );
        assertEquals(
                List.of(0, 1, 1, 1, 2),
                expansions.stream().map(FuzzyExpansion::editDistance).toList()
        );
        assertEquals(1.0, expansions.getFirst().similarity());
        assertEquals(0.9, expansions.get(1).similarity());
        assertEquals(1.0 - 1.0 / 11.0, expansions.get(2).similarity());
        assertEquals(0.8, expansions.getLast().similarity());
        expansions.forEach(expansion -> {
            assertSame(index.posting(expansion.term()), expansion.posting());
            assertEquals(1, expansion.posting().documentFrequency());
        });
        assertThrows(UnsupportedOperationException.class, expansions::clear);
    }

    @Test
    void sortsEqualDistanceTermsByNumericCodePointsNotAvlUtf16Order() {
        String privateUse = "ab\ue000";
        String supplementary = "ab\ud800\udc00";
        TextIndexSnapshot<Document> index = indexOf(List.of(
                supplementary,
                privateUse,
                "abc"
        ));

        assertEquals(
                List.of("abc", privateUse, supplementary),
                EXPANDER.expand(index, "abc", 1).stream()
                        .map(FuzzyExpansion::term)
                        .toList()
        );
    }

    @Test
    void returnsEmptyForNoExpansionAndValidatesInputs() {
        TextIndexSnapshot<Document> index = indexOf(List.of("alpha", "beta"));
        assertTrue(EXPANDER.expand(index, "restaurant", 2).isEmpty());
        assertThrows(
                NullPointerException.class,
                () -> EXPANDER.expand(null, "alpha", 1)
        );
        assertThrows(
                NullPointerException.class,
                () -> EXPANDER.expand(index, null, 1)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> EXPANDER.expand(index, "", 0)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> EXPANDER.expand(index, "alpha", 3)
        );
    }

    @Test
    void randomizedExpansionMatchesBruteForceReferenceSetAndOrder() {
        Random random = new Random(SEED);
        for (int iteration = 0; iteration < 400; iteration++) {
            Set<String> vocabulary = new LinkedHashSet<>();
            int vocabularySize = 1 + random.nextInt(30);
            while (vocabulary.size() < vocabularySize) {
                vocabulary.add(randomTerm(random, 1 + random.nextInt(8)));
            }
            String query = randomTerm(random, 1 + random.nextInt(8));
            int maxEdits = BoundedOptimalStringAlignment.autoMaxEdits(query);

            List<ExpectedExpansion> expected = new ArrayList<>();
            for (String term : vocabulary) {
                int distance = FuzzyTestReference.optimalStringAlignmentDistance(
                        query,
                        term
                );
                if (distance <= maxEdits) {
                    expected.add(new ExpectedExpansion(term, distance));
                }
            }
            expected.sort(Comparator
                    .comparingInt(ExpectedExpansion::distance)
                    .thenComparing(
                            ExpectedExpansion::term,
                            FuzzyTestReference::compareCodePoints
                    ));

            List<FuzzyExpansion> actual = EXPANDER.expand(
                    indexOf(List.copyOf(vocabulary)),
                    query,
                    maxEdits
            );
            String context = "seed=" + SEED + ", iteration=" + iteration
                    + ", query=" + query;
            assertEquals(
                    expected.stream().map(ExpectedExpansion::term).toList(),
                    actual.stream().map(FuzzyExpansion::term).toList(),
                    context
            );
            assertEquals(
                    expected.stream().map(ExpectedExpansion::distance).toList(),
                    actual.stream().map(FuzzyExpansion::editDistance).toList(),
                    context
            );
        }
    }

    private static TextIndexSnapshot<Document> indexOf(List<String> terms) {
        TextIndexSnapshot<Document> index = TextIndexSnapshot.empty(TEXT);
        IndexBuilder<Document> builder = index.toBuilder();
        for (int docId = 0; docId < terms.size(); docId++) {
            builder.add(docId, new Document(terms.get(docId)));
        }
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<Document> built =
                (TextIndexSnapshot<Document>) builder.build();
        return built;
    }

    private static String randomTerm(Random random, int length) {
        StringBuilder term = new StringBuilder();
        for (int index = 0; index < length; index++) {
            term.appendCodePoint(ALPHABET[random.nextInt(ALPHABET.length)]);
        }
        return term.toString();
    }

    private record Document(String body) {
    }

    private record ExpectedExpansion(String term, int distance) {
    }
}
