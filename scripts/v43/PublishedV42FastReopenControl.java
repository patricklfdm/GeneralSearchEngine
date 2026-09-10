import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Exact published-4.2 forced-rebuild control for the V4.3 evidence lane. */
public final class PublishedV42FastReopenControl {
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

    private PublishedV42FastReopenControl() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException(
                    "expected profile, absent store and absent properties file");
        }
        Profile profile = Profile.named(arguments[0]);
        Path store = Path.of(arguments[1]).toAbsolutePath().normalize();
        Path output = Path.of(arguments[2]).toAbsolutePath().normalize();
        if (Files.exists(store) || Files.exists(output)
                || output.getParent() == null
                || !Files.isDirectory(output.getParent())) {
            throw new IllegalArgumentException("control output paths must be absent");
        }
        DurableStorageConfig<Integer, Document> storage =
                DurableStorageConfig.builder(store, CODEC)
                        .storageIdentity("v43-fast-reopen-store-v1")
                        .schemaIdentity("v43-fast-reopen-schema-v1")
                        .maxDocuments(profile.documents() * 2)
                        .maxBulkElements(1_000)
                        .checkpointWalBytes(256L * 1024 * 1024)
                        .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                        .build();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(storage)) {
            for (int start = 0; start < profile.documents(); start += profile.batch()) {
                List<Document> batch = new ArrayList<>();
                for (int id = start; id < Math.min(
                        profile.documents(), start + profile.batch()); id++) {
                    batch.add(document(id));
                }
                engine.addAll(batch).join();
            }
            engine.checkpoint().join();
        }
        long[] samples = new long[profile.samples()];
        String checksum = null;
        for (int sample = 0; sample < samples.length; sample++) {
            long started = System.nanoTime();
            try (DurableSearchEngine<Integer, Document> engine = builder()
                    .buildDurable(storage)) {
                samples[sample] = Math.max(1L, System.nanoTime() - started);
                String actual = checksum(engine, profile.documents());
                if (checksum != null && !checksum.equals(actual)) {
                    throw new IllegalStateException("published control checksum differs");
                }
                checksum = actual;
            }
        }
        long[] ordered = samples.clone();
        Arrays.sort(ordered);
        Map<String, String> values = new TreeMap<>();
        values.put("schemaVersion", "gse-v43-published-v42-properties-v1");
        values.put("status", "PASS");
        values.put("profile", profile.name());
        values.put("publishedVersion", "4.2.0");
        values.put("documents", Integer.toString(profile.documents()));
        values.put("tokensPerDocument", "16");
        values.put("samples", Integer.toString(profile.samples()));
        values.put("open.samplesNanos", csv(samples));
        values.put("open.medianNanos", Long.toString(ordered[ordered.length / 2]));
        values.put("open.minNanos", Long.toString(ordered[0]));
        values.put("open.maxNanos", Long.toString(ordered[ordered.length - 1]));
        values.put("oracleChecksum", checksum);
        values.put("pageCacheState", "uncontrolled-os-cache");
        write(output, values);
        System.out.printf("v43PublishedV42Control=PASS profile=%s documents=%d "
                + "medianNanos=%d%n", profile.name(), profile.documents(),
                ordered[ordered.length / 2]);
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE).textField(TEXT)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(TEXT));
    }

    private static String checksum(
            DurableSearchEngine<Integer, Document> engine,
            int documents
    ) {
        MessageDigest digest = sha256();
        for (int id = 0; id < documents; id++) {
            Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("published control lost document");
            }
            byte[] value = CODEC.encodeDocument(document);
            digest.update(ByteBuffer.allocate(8).putInt(id)
                    .putInt(value.length).array());
            digest.update(value);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static Document document(int id) {
        return new Document(id, "category-" + (id % 32), id % 10_000,
                "title-" + (id % 2_048),
                "document id" + id + " revision0 bucket" + (id % 97)
                        + " alpha beta gamma delta epsilon zeta eta theta iota"
                        + " kappa lambda mu");
    }

    private static String csv(long[] values) {
        return Arrays.stream(values).mapToObj(Long::toString)
                .reduce((left, right) -> left + "," + right).orElseThrow();
    }

    private static void write(Path output, Map<String, String> values)
            throws IOException {
        StringBuilder content = new StringBuilder();
        for (Map.Entry<String, String> entry : values.entrySet()) {
            content.append(entry.getKey()).append('=').append(entry.getValue())
                    .append('\n');
        }
        Files.writeString(output, content, StandardCharsets.US_ASCII,
                StandardOpenOption.CREATE_NEW);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private record Profile(
            String name,
            int documents,
            int batch,
            int samples
    ) {
        private static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(name, 1_000, 100, 3);
                case "production" -> new Profile(name, 100_000, 1_000, 5);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
    }

    private record Document(
            int id,
            String category,
            int price,
            String title,
            String body
    ) {
    }

    private static final class Codec implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v43-fast-reopen-codec-v1";
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
        public Integer decodeKey(byte[] encoded) {
            if (encoded.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid key");
            }
            return ByteBuffer.wrap(encoded).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
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

        @Override
        public Document decodeDocument(byte[] encoded) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(encoded))) {
                Document value = new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF(), input.readUTF());
                if (input.read() != -1) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return value;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document", failure);
            }
        }
    }
}
