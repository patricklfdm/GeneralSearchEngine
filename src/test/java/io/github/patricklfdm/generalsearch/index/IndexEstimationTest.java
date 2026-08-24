package io.github.patricklfdm.generalsearch.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Optional;
import java.util.Random;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;

class IndexEstimationTest {
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> SCORE =
            Field.of("score", Integer.class, Document::score);
    private static final Field<Document, String> NAME =
            Field.of("name", String.class, Document::name);
    private static final Field<Document, String> UNINDEXED =
            Field.of("unindexed", String.class, Document::name);

    @Test
    void maintainsImmutableStatisticsAcrossMutationsAndSnapshots() {
        IndexRegistry<Document> empty = registry();
        assertStatistics(empty, CATEGORY, 0, 0);
        assertStatistics(empty, SCORE, 0, 0);
        assertStatistics(empty, NAME, 0, 0);

        Document alpha = new Document("book", 10, "Alpha");
        Document alphabet = new Document("book", 20, "Alphabet");
        Document nullable = new Document(null, 30, null);
        IndexRegistryBuilder<Document> initial = empty.toBuilder();
        initial.add(0, alpha);
        initial.add(2, alphabet);
        initial.add(5, nullable);
        IndexRegistry<Document> first = initial.build();

        assertStatistics(first, CATEGORY, 2, 1);
        assertStatistics(first, SCORE, 3, 3);
        assertStatistics(first, NAME, 2, 2);
        assertEstimate(first, CATEGORY, Query.eq(CATEGORY, "book"),
                2, 1, CandidateAccuracy.EXACT);
        assertTrue(index(first, CATEGORY)
                .estimateCandidates(Query.eq(CATEGORY, null)).isEmpty());
        assertEstimate(first, SCORE, Query.eq(SCORE, 10),
                1, 1, CandidateAccuracy.SUPERSET);
        assertEstimate(first, SCORE, Query.between(SCORE, 10, 20),
                2, 2, CandidateAccuracy.EXACT);
        assertEstimate(first, SCORE, Query.between(SCORE, 20, 10),
                0, 0, CandidateAccuracy.EXACT);
        assertEstimate(first, NAME, Query.prefix(NAME, "Al"),
                2, 2, CandidateAccuracy.EXACT);
        assertEstimate(first, NAME, Query.prefix(NAME, ""),
                2, 2, CandidateAccuracy.EXACT);
        assertEstimate(first, NAME, Query.eq(NAME, "Alpha"),
                1, 1, CandidateAccuracy.EXACT);
        assertTrue(index(first, NAME)
                .estimateCandidates(Query.eq(NAME, null)).isEmpty());
        assertTrue(index(first, NAME)
                .estimateCandidates(Query.eq(UNINDEXED, "Alpha")).isEmpty());

        Document beta = new Document("electronics", 20, "Beta");
        Document book = new Document("book", null, "Book");
        IndexRegistryBuilder<Document> mutation = first.toBuilder();
        mutation.update(0, alpha, beta);
        mutation.remove(2, alphabet);
        mutation.add(8, book);
        IndexRegistry<Document> second = mutation.build();

        assertStatistics(first, CATEGORY, 2, 1);
        assertStatistics(first, SCORE, 3, 3);
        assertStatistics(first, NAME, 2, 2);
        assertStatistics(second, CATEGORY, 2, 2);
        assertStatistics(second, SCORE, 2, 2);
        assertStatistics(second, NAME, 2, 2);
        assertEstimate(second, CATEGORY, Query.eq(CATEGORY, "book"),
                1, 1, CandidateAccuracy.EXACT);
        assertEstimate(second, SCORE, Query.between(SCORE, 20, 30),
                2, 2, CandidateAccuracy.EXACT);
        assertEstimate(second, NAME, Query.prefix(NAME, "Al"),
                0, 0, CandidateAccuracy.EXACT);
    }

    @Test
    void randomizedExactEstimatesMatchMaterializedCandidateCardinality() {
        Random random = new Random(0x51A71571L);
        IndexRegistryBuilder<Document> builder = registry().toBuilder();
        for (int docId = 0; docId < 2_000; docId++) {
            String category = docId % 17 == 0 ? null : "c" + random.nextInt(13);
            Integer score = docId % 19 == 0 ? null : random.nextInt(500);
            String name = docId % 23 == 0
                    ? null
                    : "prefix-" + random.nextInt(80) + "-" + docId;
            builder.add(docId * 2, new Document(category, score, name));
        }
        IndexRegistry<Document> indexes = builder.build();

        for (int iteration = 0; iteration < 500; iteration++) {
            assertEstimateMatchesCandidates(
                    index(indexes, CATEGORY),
                    Query.eq(CATEGORY, "c" + random.nextInt(16)));

            int first = random.nextInt(600) - 50;
            int second = random.nextInt(600) - 50;
            assertEstimateMatchesCandidates(
                    index(indexes, SCORE),
                    Query.between(SCORE, first, second));
            assertEstimateMatchesCandidates(
                    index(indexes, SCORE),
                    Query.eq(SCORE, random.nextInt(550)));

            String prefix = switch (random.nextInt(4)) {
                case 0 -> "";
                case 1 -> "prefix-" + random.nextInt(80);
                case 2 -> "prefix-" + random.nextInt(80) + "-";
                default -> "missing-";
            };
            assertEstimateMatchesCandidates(
                    index(indexes, NAME),
                    Query.prefix(NAME, prefix));
        }
    }

    @Test
    void legacyIndexSnapshotRemainsUsableWithoutEstimationCapability() {
        ImmutableBitmap candidates = ImmutableBitmap.empty().withSet(7);
        IndexSnapshot<Document> legacy = new LegacyIndexSnapshot(CATEGORY, candidates);
        IndexRegistry<Document> registry = IndexRegistry.fromSnapshots(List.of(legacy));

        assertFalse(legacy instanceof EstimatingIndexSnapshot<?>);
        CandidateResult result = registry.candidates(Query.eq(CATEGORY, "book"))
                .orElseThrow();
        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertTrue(result.bitmap().get(7));
    }

    private static IndexRegistry<Document> registry() {
        return IndexRegistry.create(List.of(
                IndexDefinition.equality(CATEGORY),
                IndexDefinition.range(SCORE),
                IndexDefinition.prefix(NAME)
        ));
    }

    private static void assertStatistics(
            IndexRegistry<Document> indexes,
            Field<Document, ?> field,
            int indexedDocumentCount,
            int distinctKeyCount
    ) {
        assertEquals(
                new IndexStatistics(indexedDocumentCount, distinctKeyCount),
                index(indexes, field).statistics()
        );
    }

    private static void assertEstimate(
            IndexRegistry<Document> indexes,
            Field<Document, ?> field,
            Query<Document> query,
            int cardinality,
            int sourceCount,
            CandidateAccuracy accuracy
    ) {
        CandidateEstimate estimate = index(indexes, field)
                .estimateCandidates(query)
                .orElseThrow();
        assertEquals(cardinality, estimate.estimatedCandidateCardinality());
        assertEquals(sourceCount, estimate.estimatedSourceCount());
        assertEquals(EstimateQuality.EXACT, estimate.quality());
        assertEquals(accuracy, estimate.accuracy());
    }

    private static void assertEstimateMatchesCandidates(
            EstimatingIndexSnapshot<Document> index,
            Query<Document> query
    ) {
        CandidateEstimate estimate = index.estimateCandidates(query).orElseThrow();
        CandidateResult candidates = index.candidates(query).orElseThrow();
        assertEquals(
                candidates.bitmap().cardinality(),
                estimate.estimatedCandidateCardinality()
        );
        assertEquals(candidates.accuracy(), estimate.accuracy());
        assertEquals(EstimateQuality.EXACT, estimate.quality());
    }

    @SuppressWarnings("unchecked")
    private static EstimatingIndexSnapshot<Document> index(
            IndexRegistry<Document> indexes,
            Field<Document, ?> field
    ) {
        IndexSnapshot<Document> snapshot = indexes.indexes().stream()
                .filter(candidate -> candidate.field() == field)
                .findFirst()
                .orElseThrow();
        return (EstimatingIndexSnapshot<Document>) assertInstanceOf(
                EstimatingIndexSnapshot.class,
                snapshot
        );
    }

    private record Document(String category, Integer score, String name) {}

    private record LegacyIndexSnapshot(
            Field<Document, ?> field,
            ImmutableBitmap candidates
    ) implements IndexSnapshot<Document> {
        @Override
        public Optional<CandidateResult> candidates(Query<Document> query) {
            return Optional.of(new CandidateResult(
                    candidates,
                    CandidateAccuracy.EXACT
            ));
        }

        @Override
        public IndexBuilder<Document> toBuilder() {
            throw new UnsupportedOperationException("not needed by this fixture");
        }
    }
}
