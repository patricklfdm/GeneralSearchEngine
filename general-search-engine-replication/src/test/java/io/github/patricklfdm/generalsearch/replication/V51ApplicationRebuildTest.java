package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletionException;
import java.util.stream.IntStream;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.engine.exception.BulkMutationException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class V51ApplicationRebuildTest {
    @TempDir Path temporary;

    private ReplicaApplication<Integer, Document> application(int engineBatch, int durableBatch) {
        var captured = SearchEngine.builder(SCHEMA).indexes(INDEXES)
                .config(new SnapshotEngineConfig(64, engineBatch, Duration.ofMillis(1))).configuration();
        var storage = DurableStorageConfig.builder(temporary, new Codec()).storageIdentity("fixture-storage")
                .schemaIdentity("fixture-schema").maxDocuments(1000).maxBulkElements(durableBatch).build();
        return new ReplicaApplication<>(captured, storage, BOUNDS);
    }
    private static void apply(ReplicaApplication<Integer, Document> app, String kind, byte[] payload) {
        app.prepare(kind, payload); app.publish(app.appliedIndex() + 1);
    }

    @ParameterizedTest
    @CsvSource({"16,100,18", "100,2,7", "2,2,7", "1,100,3"})
    void privatelyRebuildsAcrossBothBatchBoundsAndPreservesApplicationCut(int engineBatch, int durableBatch, int count) {
        try (var source = application(engineBatch, durableBatch)) {
            var documents = IntStream.range(0, count).mapToObj(i -> new Document(i, "value-" + i)).toList();
            for (var document : documents) apply(source, "ADD", source.documents("ADD", List.of(document)));
            apply(source, "INDEX_DROP", source.dropIndex(VALUE.name()));
            apply(source, "INDEX_CREATE", source.index(IndexDefinition.equality(ID)));
            apply(source, "NO_OP", new byte[0]);
            byte[] snapshot = source.snapshot();
            try (var rebuilt = source.rebuildApplication(snapshot, source.appliedIndex(), source.sequence())) {
                assertArrayEquals(snapshot, rebuilt.snapshot());
                assertEquals(count + 3, rebuilt.appliedIndex());
                assertEquals(count + 2, rebuilt.sequence());
                assertEquals(documents, rebuilt.read(engine -> engine.search(document -> true)));
                // Exercise both rebuilt engines, including deferred catchup, after publication.
                for (int i = 0; i < 2; i++) {
                    var extra = new Document(count + i, "later-" + i);
                    apply(rebuilt, "ADD", rebuilt.documents("ADD", List.of(extra)));
                    assertEquals(extra, rebuilt.read(engine -> engine.get(extra.id())));
                    assertEquals(count + i + 1, rebuilt.read(engine -> engine.search(document -> true)).size());
                }
                assertArrayEquals(snapshot, source.snapshot());
            }
        }
    }

    @Test
    void userAtomicBulkStillRejectsEngineLimitWithoutPartialPublication() {
        try (var source = application(2, 100)) {
            var documents = List.of(new Document(1, "one"), new Document(2, "two"), new Document(3, "three"));
            byte[] before = source.snapshot();
            var failure = assertThrows(CompletionException.class,
                    () -> source.prepare("ADD_ALL", source.documents("ADD_ALL", documents)));
            assertInstanceOf(BulkMutationException.class, failure.getCause());
            assertArrayEquals(before, source.snapshot());
            assertEquals(0, source.appliedIndex());
            apply(source, "ADD", source.documents("ADD", documents.subList(0, 1)));
            assertEquals(documents.subList(0, 1), source.read(engine -> engine.search(document -> true)));
        }
    }
}
