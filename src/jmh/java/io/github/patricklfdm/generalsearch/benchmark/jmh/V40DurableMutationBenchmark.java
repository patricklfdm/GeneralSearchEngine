package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

/**
 * Separates the V4 in-memory compatibility path from force-backed durable mutation
 * completion. Production evidence runs this benchmark in sample-time mode with the
 * GC profiler so percentiles and allocation remain visible.
 */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V40DurableMutationBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Param("10000")
    public int documentCount;

    @Param("100")
    public int bulkSize;

    private final AtomicInteger inMemoryCursor = new AtomicInteger();
    private final AtomicInteger durableCursor = new AtomicInteger();
    private SearchEngine<Integer, Document> inMemory;
    private DurableSearchEngine<Integer, Document> durable;
    private Path durableDirectory;

    @Setup(Level.Trial)
    public void setUp() throws IOException {
        if (bulkSize <= 0 || bulkSize > documentCount) {
            throw new IllegalArgumentException(
                    "bulkSize must be between one and documentCount");
        }
        inMemory = SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .index(IndexDefinition.equality(BODY))
                .build();
        durableDirectory = Files.createTempDirectory("gse-v40-jmh-");
        durable = SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .index(IndexDefinition.equality(BODY))
                .buildDurable(DurableStorageConfig.builder(
                                durableDirectory, new DocumentCodec())
                        .storageIdentity("v40-performance-store-v1")
                        .schemaIdentity("v40-performance-schema-v1")
                        .checkpointWalBytes(256L * 1024 * 1024)
                        .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                        .build());
        List<Document> documents = documents(0, documentCount, 0);
        inMemory.addAll(documents).join();
        durable.addAll(documents).join();
    }

    @TearDown(Level.Trial)
    public void tearDown() throws IOException {
        RuntimeException primary = null;
        try {
            inMemory.close();
        } catch (RuntimeException failure) {
            primary = failure;
        }
        try {
            durable.close();
        } catch (RuntimeException failure) {
            if (primary == null) {
                primary = failure;
            } else {
                primary.addSuppressed(failure);
            }
        }
        deleteTree(durableDirectory);
        if (primary != null) {
            throw primary;
        }
    }

    @Benchmark
    public int inMemorySingleCompletion() {
        int cursor = inMemoryCursor.getAndIncrement();
        int id = Math.floorMod(cursor, documentCount);
        inMemory.update(new Document(id, body(id, cursor + 1))).join();
        return id;
    }

    @Benchmark
    public long durableSingleCompletion() {
        int cursor = durableCursor.getAndIncrement();
        int id = Math.floorMod(cursor, documentCount);
        durable.update(new Document(id, body(id, cursor + 1))).join();
        return durable.currentSequence();
    }

    @Benchmark
    public int inMemoryBulkCompletion() {
        int cursor = inMemoryCursor.getAndAdd(bulkSize);
        List<Document> batch = updateBatch(cursor);
        inMemory.updateAll(batch).join();
        return batch.getLast().id();
    }

    @Benchmark
    public long durableBulkCompletion() {
        int cursor = durableCursor.getAndAdd(bulkSize);
        durable.updateAll(updateBatch(cursor)).join();
        return durable.currentSequence();
    }

    private List<Document> updateBatch(int cursor) {
        List<Document> batch = new ArrayList<>(bulkSize);
        int start = Math.floorMod(cursor, documentCount);
        int revision = Math.floorDiv(cursor, documentCount) + 1;
        for (int offset = 0; offset < bulkSize; offset++) {
            int id = (start + offset) % documentCount;
            batch.add(new Document(id, body(id, revision)));
        }
        return batch;
    }

    private static List<Document> documents(int start, int count, int revision) {
        List<Document> documents = new ArrayList<>(count);
        for (int offset = 0; offset < count; offset++) {
            int id = start + offset;
            documents.add(new Document(id, body(id, revision)));
        }
        return documents;
    }

    private static String body(int id, int revision) {
        return "durable performance document " + id + " revision " + revision;
    }

    private static void deleteTree(Path root) throws IOException {
        if (root == null || !Files.exists(root)) {
            return;
        }
        try (var paths = Files.walk(root)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.delete(path);
            }
        }
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v40-performance-codec-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(Integer.BYTES).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid integer key");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeUTF(document.body());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new UncheckedIOException(impossible);
            }
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Document document = new Document(input.readInt(), input.readUTF());
                if (input.read() != -1) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return document;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
