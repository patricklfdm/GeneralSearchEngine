import java.nio.ByteBuffer;
import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Reopens an untouched V4.2 migration source using only published 4.1.0. */
public final class PublishedV41RollbackProbe {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    private PublishedV41RollbackProbe() {
    }

    public static void main(String[] arguments) {
        if (arguments.length != 1) {
            throw new IllegalArgumentException("expected source directory");
        }
        Path source = Path.of(arguments[0]).toAbsolutePath().normalize();
        DurableStorageConfig<Integer, Document> config =
                DurableStorageConfig.builder(source, new DocumentCodec())
                        .storageIdentity("v42-rollback-store")
                        .schemaIdentity("v42-rollback-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024)
                        .build();
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).buildDurable(config)) {
            if (engine.get(1) != null
                    || !new Document(2, 22).equals(engine.get(2))
                    || engine.get(3) != null
                    || engine.currentSequence() != 3L) {
                throw new IllegalStateException("rollback source state mismatch");
            }
        }
        System.out.println("publishedV41Rollback=PASS sequence=3");
    }

    private record Document(int id, int value) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-rollback-codec";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] encoded) {
            return ByteBuffer.wrap(encoded).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            return ByteBuffer.allocate(8)
                    .putInt(document.id()).putInt(document.value()).array();
        }

        @Override
        public Document decodeDocument(byte[] encoded) {
            ByteBuffer value = ByteBuffer.wrap(encoded);
            return new Document(value.getInt(), value.getInt());
        }
    }
}
