package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import io.github.patricklfdm.generalsearch.schema.Field;

class V40DurableOperationalProbeTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    @Test
    void preloadsCorporaLargerThanTheAtomicBulkLimitInBoundedBatches() {
        int limit = SnapshotEngineConfig.DEFAULT.maxBatchSize();
        List<Document> corpus = new ArrayList<>();
        for (int id = 0; id < limit * 2 + 501; id++) {
            corpus.add(new Document(id));
        }

        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .build()) {
            V40DurableOperationalProbe.addInBatches(engine, corpus, limit);

            assertEquals(limit * 2 + 501, engine.metrics().documentCount());
            assertNotNull(engine.get(0));
            assertNotNull(engine.get(limit * 2 + 500));
        }
    }

    @Test
    void rejectsPreloadBatchesOutsideTheEngineAtomicBulkLimit() {
        int limit = SnapshotEngineConfig.DEFAULT.maxBatchSize();
        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .build()) {
            assertThrows(IllegalArgumentException.class, () ->
                    V40DurableOperationalProbe.addInBatches(
                            engine, List.of(new Document(1)), 0));
            assertThrows(IllegalArgumentException.class, () ->
                    V40DurableOperationalProbe.addInBatches(
                            engine, List.of(new Document(1)), limit + 1));
        }
    }

    private record Document(int id) {
    }
}
