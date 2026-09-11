import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Published-4.3/current paired Phase 1 diagnostic compiled against published API. */
public final class PairedPublishedV43Probe {
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

    private PairedPublishedV43Probe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException("expected label, directory and documents");
        }
        String label = arguments[0];
        Path directory = Path.of(arguments[1]).toAbsolutePath().normalize();
        int documents = Integer.parseInt(arguments[2]);
        if (!label.matches("[a-z0-9-]{1,32}") || documents < 1_000
                || documents > 100_000) {
            throw new IllegalArgumentException("diagnostic input is out of bounds");
        }
        DurableStorageConfig<Integer, Document> config = config(directory, documents);
        long writeStarted = System.nanoTime();
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
        long writeNanos = System.nanoTime() - writeStarted;

        long[] reopen = new long[3];
        String digest = null;
        for (int sample = 0; sample < reopen.length; sample++) {
            long started = System.nanoTime();
            try (DurableSearchEngine<Integer, Document> engine =
                         builder().buildDurable(config)) {
                reopen[sample] = System.nanoTime() - started;
                String observed = semanticDigest(engine, documents);
                if (digest != null && !digest.equals(observed)) {
                    throw new IllegalStateException("reopen semantics changed");
                }
                digest = observed;
            }
        }
        Arrays.sort(reopen);
        System.out.printf("v44PairedControl=PASS label=%s documents=%d indexes=4 "
                        + "writeNanos=%d reopenMedianNanos=%d semanticDigest=%s%n",
                label, documents, writeNanos, reopen[1], digest);
    }

    private static String semanticDigest(DurableSearchEngine<Integer, Document> engine,
                                         int documents) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (int id = 0; id < documents; id++) {
            Document value = engine.get(id);
            if (!document(id).equals(value)) {
                throw new IllegalStateException("document differs: " + id);
            }
            digest.update(ByteBuffer.allocate(8).putInt(id).putInt(value.price()).array());
        }
        List<Integer> equality = engine.search(Query.eq(CATEGORY, "category-7"))
                .stream().map(Document::id).toList();
        List<Integer> range = engine.search(Query.between(PRICE, 100, 200))
                .stream().map(Document::id).toList();
        List<Integer> prefix = engine.search(Query.prefix(TITLE, "title-10"))
                .stream().map(Document::id).toList();
        for (List<Integer> result : List.of(equality, range, prefix)) {
            for (int id : result) {
                digest.update(ByteBuffer.allocate(4).putInt(id).array());
            }
            digest.update((byte) 0xff);
        }
        digest.update(Long.toString(engine.currentSequence())
                .getBytes(StandardCharsets.US_ASCII));
        return HexFormat.of().formatHex(digest.digest());
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
                .storageIdentity("v44-paired-published-v43-control-v1")
                .schemaIdentity("v44-final-hardening-schema-v1")
                .maxDocuments(documents * 2)
                .maxBulkElements(1_000)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static Document document(int id) {
        return new Document(id, "category-" + (id % 32), id % 10_000,
                "title-" + (id % 2_048),
                "java search durable final hardening token" + (id % 97));
    }

    private record Document(int id, String category, int price, String title,
                            String body) {
    }

    private static final class Codec implements DurableCodec<Integer, Document> {
        @Override public String codecId() { return "v44-paired-control-codec-v1"; }
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
