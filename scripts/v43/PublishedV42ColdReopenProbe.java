import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Published-4.2-only forced canonical rebuild diagnostic for V4.3 calibration. */
public final class PublishedV42ColdReopenProbe {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, SimpleAnalyzer.INSTANCE);
    private static final Codec CODEC = new Codec();

    private PublishedV42ColdReopenProbe() {
    }

    public static void main(String[] arguments) {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("expected directory and document count");
        }
        Path directory = Path.of(arguments[0]).toAbsolutePath().normalize();
        int documents = Integer.parseInt(arguments[1]);
        if (documents < 1_000 || documents > 100_000) {
            throw new IllegalArgumentException("document count out of diagnostic bounds");
        }
        DurableStorageConfig<Integer, Document> config = config(directory, documents);
        try (DurableSearchEngine<Integer, Document> writer = builder().buildDurable(config)) {
            for (int start = 0; start < documents; start += 1_000) {
                List<Document> batch = new ArrayList<>();
                for (int id = start; id < Math.min(documents, start + 1_000); id++) {
                    batch.add(document(id));
                }
                writer.addAll(batch).join();
            }
            writer.checkpoint().join();
        }

        long[] samples = new long[5];
        long checksum = 0;
        for (int sample = 0; sample < samples.length; sample++) {
            long started = System.nanoTime();
            try (DurableSearchEngine<Integer, Document> reopened =
                         builder().buildDurable(config)) {
                samples[sample] = System.nanoTime() - started;
                checksum ^= reopened.currentSequence();
                checksum ^= reopened.get(sample * (documents / samples.length)).id();
            }
        }
        long[] ordered = samples.clone();
        Arrays.sort(ordered);
        System.out.printf(
                "publishedV42ColdReopen=PASS documents=%d indexes=4 samples=%d "
                        + "medianNanos=%d minNanos=%d maxNanos=%d checksum=%d%n",
                documents, samples.length, ordered[2], ordered[0], ordered[4], checksum);
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE).textField(TEXT)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(TEXT));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory, int documents) {
        return DurableStorageConfig.builder(directory, CODEC)
                .storageIdentity("v43-published-v42-cold-control-v1")
                .schemaIdentity("v43-fast-reopen-schema-v1")
                .maxDocuments(documents * 2)
                .maxBulkElements(1_000)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static Document document(int id) {
        String body = "java search durable reopen token" + (id % 97)
                + " alpha beta gamma delta epsilon zeta eta theta iota kappa";
        return new Document(id, "category-" + (id % 32), id % 10_000,
                "title-" + (id % 2_048), body);
    }

    private record Document(int id, String category, int price, String title, String body) {
    }

    private static final class Codec implements DurableCodec<Integer, Document> {
        @Override public String codecId() { return "v43-published-v42-control-codec-v1"; }
        @Override public int codecVersion() { return 1; }
        @Override public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }
        @Override public Integer decodeKey(byte[] encoded) {
            if (encoded.length != 4) throw new IllegalArgumentException("invalid key");
            return ByteBuffer.wrap(encoded).getInt();
        }
        @Override public byte[] encodeDocument(Document document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeUTF(document.category());
                    output.writeInt(document.price());
                    output.writeUTF(document.title());
                    output.writeUTF(document.body());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new UncheckedIOException(impossible);
            }
        }
        @Override public Document decodeDocument(byte[] encoded) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(encoded))) {
                Document value = new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF(), input.readUTF());
                if (input.read() != -1) throw new IllegalArgumentException("trailing bytes");
                return value;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document", failure);
            }
        }
    }
}
