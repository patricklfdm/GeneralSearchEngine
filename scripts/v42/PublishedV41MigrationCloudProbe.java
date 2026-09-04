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
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Published-4.1-only rollback verifier for V4.2 cloud evidence. */
public final class PublishedV41MigrationCloudProbe {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final DocumentCodec CODEC = new DocumentCodec();

    private PublishedV41MigrationCloudProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException(
                    "expected profile, source directory and source properties");
        }
        Profile profile = Profile.named(arguments[0]);
        Path source = Path.of(arguments[1]).toAbsolutePath().normalize();
        Map<String, String> properties = readProperties(Path.of(arguments[2]));
        if (!"PASS".equals(properties.get("status"))
                || !profile.name().equals(properties.get("profile"))) {
            throw new IllegalArgumentException("source evidence is not compatible");
        }
        long expectedSequence = Long.parseLong(properties.get("source.sequence"));
        String expectedChecksum = properties.get("source.oracleChecksum");
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .index(IndexDefinition.equality(BODY))
                .buildDurable(config(source, profile))) {
            if (engine.currentSequence() != expectedSequence
                    || !checksum(engine, profile.documents())
                    .equals(expectedChecksum)) {
                throw new IllegalStateException(
                        "published 4.1 rollback source differs");
            }
        }
        System.out.printf(
                "publishedV41MigrationRollback=PASS profile=%s sequence=%d%n",
                profile.name(), expectedSequence);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            Profile profile
    ) {
        return DurableStorageConfig.builder(directory, CODEC)
                .storageIdentity("v42-migration-source-v1")
                .schemaIdentity("v42-migration-source-schema-v1")
                .maxDocuments(profile.documents() * 2)
                .maxBulkElements(1_000)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static String checksum(
            DurableSearchEngine<Integer, Document> engine,
            int count
    ) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
        for (int id = 0; id < count; id++) {
            Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing source document " + id);
            }
            byte[] encoded = CODEC.encodeDocument(document);
            digest.update(ByteBuffer.allocate(8)
                    .putInt(id).putInt(encoded.length).array());
            digest.update(encoded);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static Map<String, String> readProperties(Path path) throws IOException {
        Map<String, String> result = new TreeMap<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            int separator = line.indexOf('=');
            if (separator <= 0 || separator == line.length() - 1
                    || result.put(line.substring(0, separator),
                    line.substring(separator + 1)) != null) {
                throw new IllegalArgumentException("invalid source properties");
            }
        }
        return result;
    }

    private record Document(int id, String body) {
    }

    private record Profile(String name, int documents) {
        private static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(name, 1_000);
                case "production" -> new Profile(name, 100_000);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-migration-source-codec-v1";
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
            if (encoded.length != 4) {
                throw new IllegalArgumentException("invalid source key");
            }
            return ByteBuffer.wrap(encoded).getInt();
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
        public Document decodeDocument(byte[] encoded) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(encoded))) {
                Document result = new Document(input.readInt(), input.readUTF());
                if (input.read() != -1) {
                    throw new IllegalArgumentException("trailing source bytes");
                }
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid source bytes", failure);
            }
        }
    }
}
