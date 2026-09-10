import java.nio.ByteBuffer;
import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Reopens an unchanged default-format V4.3-development store using published 4.2.0. */
public final class PublishedV42RollbackProbe {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, Integer> VALUE =
            Field.of("value", Integer.class, Document::value);
    private static final Field<Document, String> TEXT =
            Field.of("text", String.class, Document::text);
    private static final TextField<Document> ANALYZED =
            TextField.of(TEXT, SimpleAnalyzer.INSTANCE);

    private PublishedV42RollbackProbe() {
    }

    public static void main(String[] arguments) {
        if (arguments.length != 1) throw new IllegalArgumentException("expected directory");
        Path directory = Path.of(arguments[0]).toAbsolutePath().normalize();
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(VALUE).textField(ANALYZED)
                .index(IndexDefinition.equality(VALUE))
                .index(IndexDefinition.range(VALUE))
                .index(IndexDefinition.prefix(TEXT))
                .index(IndexDefinition.text(ANALYZED))
                .buildDurable(config(directory))) {
            if (engine.currentSequence() != 2
                    || !new Document(1, 11, "alpha search").equals(engine.get(1))
                    || !new Document(2, 22, "beta durable").equals(engine.get(2))) {
                throw new IllegalStateException("published 4.2 rollback state differs");
            }
        }
        System.out.println("publishedV42Rollback=PASS sequence=2 format=1.0");
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new Codec())
                .storageIdentity("v43-published-v42-rollback-v1")
                .schemaIdentity("v43-published-v42-rollback-schema-v1")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024).build();
    }

    private record Document(int id, int value, String text) { }

    private static final class Codec implements DurableCodec<Integer, Document> {
        @Override public String codecId() { return "v43-rollback-codec-v1"; }
        @Override public int codecVersion() { return 1; }
        @Override public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }
        @Override public Integer decodeKey(byte[] encoded) {
            return ByteBuffer.wrap(encoded).getInt();
        }
        @Override public byte[] encodeDocument(Document document) {
            byte[] text = document.text().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            return ByteBuffer.allocate(12 + text.length).putInt(document.id())
                    .putInt(document.value()).putInt(text.length).put(text).array();
        }
        @Override public Document decodeDocument(byte[] encoded) {
            ByteBuffer input = ByteBuffer.wrap(encoded);
            int id = input.getInt();
            int value = input.getInt();
            int length = input.getInt();
            if (length < 0 || length != input.remaining()) {
                throw new IllegalArgumentException("invalid document");
            }
            byte[] text = new byte[length];
            input.get(text);
            return new Document(id, value,
                    new String(text, java.nio.charset.StandardCharsets.UTF_8));
        }
    }
}
