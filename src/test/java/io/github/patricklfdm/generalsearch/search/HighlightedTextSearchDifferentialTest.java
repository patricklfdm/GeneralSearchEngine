package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class HighlightedTextSearchDifferentialTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final List<String> VOCABULARY = List.of(
            "alpha", "beta", "gamma", "delta", "river", "museum"
    );

    @Test
    void randomizedTextHighlightingEqualsCanonicalHitsAndIndependentFragments() {
        long seed = 0x32D1FF3L;
        Random random = new Random(seed);
        List<Document> documents = new ArrayList<>();
        for (int id = 0; id < 80; id++) {
            documents.add(new Document(id, randomSource(random)));
        }

        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build()) {
            engine.addAll(documents).join();
            for (int trial = 0; trial < 300; trial++) {
                String queryText = randomQuery(random);
                int context = random.nextInt(5);
                int cap = 1 + random.nextInt(4);
                int limit = 1 + random.nextInt(12);
                SearchRequest.Builder<Document> searchBuilder = SearchRequest
                        .<Document>builder()
                        .query(SearchQueries.text(BODY_TEXT, queryText))
                        .limit(limit);
                if (random.nextBoolean()) {
                    int lower = random.nextInt(80);
                    int upper = lower + random.nextInt(80 - lower);
                    searchBuilder.filter(Query.between(ID, lower, upper));
                }
                SearchRequest<Document> search = searchBuilder.build();
                HighlightedSearchRequest<Document> highlighted =
                        HighlightedSearchRequest.<Document>builder(search)
                                .field(BODY_TEXT)
                                .contextCharacters(context)
                                .maxFragmentsPerField(cap)
                                .build();
                SearchResult<Document> canonical = engine.search(search);
                HighlightedSearchResult<Document> actual = engine.search(highlighted);
                String replay = "seed=" + seed
                        + " trial=" + trial
                        + " query=" + queryText
                        + " context=" + context
                        + " cap=" + cap
                        + " limit=" + limit;

                assertEquals(
                        canonical.hits(),
                        actual.hits().stream().map(hit -> hit.hit()).toList(),
                        replay
                );
                Set<String> terms = new HashSet<>(List.of(queryText.split(" ")));
                for (HighlightedSearchHit<Document> hit : actual.hits()) {
                    List<V32TestReference.Fragment> expected =
                            V32TestReference.fragments(
                                    hit.hit().document().body(),
                                    matchingRanges(hit.hit().document().body(), terms),
                                    context,
                                    cap
                            );
                    FieldHighlight field = hit.highlights().getFirst();
                    assertEquals("body", field.fieldName(), replay);
                    assertFragments(expected, field.fragments(), replay);
                }
            }
        }
    }

    private static String randomSource(Random random) {
        int count = 2 + random.nextInt(14);
        StringBuilder source = new StringBuilder();
        for (int index = 0; index < count; index++) {
            if (index > 0) {
                source.append(switch (random.nextInt(4)) {
                    case 0 -> " ";
                    case 1 -> ", ";
                    case 2 -> "...";
                    default -> "-";
                });
            }
            source.append(VOCABULARY.get(random.nextInt(VOCABULARY.size())));
        }
        return source.toString();
    }

    private static String randomQuery(Random random) {
        int count = 1 + random.nextInt(4);
        List<String> terms = new ArrayList<>();
        for (int index = 0; index < count; index++) {
            terms.add(VOCABULARY.get(random.nextInt(VOCABULARY.size())));
        }
        return String.join(" ", terms);
    }

    private static List<V32TestReference.Range> matchingRanges(
            String source,
            Set<String> terms
    ) {
        List<V32TestReference.Range> ranges = new ArrayList<>();
        int start = -1;
        for (int index = 0; index <= source.length(); index++) {
            boolean termCharacter = index < source.length()
                    && Character.isLetterOrDigit(source.charAt(index));
            if (termCharacter && start < 0) {
                start = index;
            } else if (!termCharacter && start >= 0) {
                if (terms.contains(source.substring(start, index))) {
                    ranges.add(new V32TestReference.Range(start, index));
                }
                start = -1;
            }
        }
        return ranges;
    }

    private static void assertFragments(
            List<V32TestReference.Fragment> expected,
            List<HighlightFragment> actual,
            String replay
    ) {
        assertEquals(expected.size(), actual.size(), replay);
        for (int index = 0; index < expected.size(); index++) {
            V32TestReference.Fragment left = expected.get(index);
            HighlightFragment right = actual.get(index);
            assertEquals(left.window().start(), right.startOffset(), replay);
            assertEquals(left.window().end(), right.endOffset(), replay);
            assertEquals(left.text(), right.text(), replay);
            assertEquals(
                    left.spans(),
                    right.spans().stream()
                            .map(span -> new V32TestReference.Range(
                                    span.startOffset(),
                                    span.endOffset()
                            ))
                            .toList(),
                    replay
            );
        }
    }

    private record Document(int id, String body) {
    }
}
