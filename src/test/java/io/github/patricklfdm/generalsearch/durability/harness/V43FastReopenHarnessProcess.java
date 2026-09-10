package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.stream.Stream;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableReopenOutcome;
import io.github.patricklfdm.generalsearch.durability.DurableReopenReport;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Separate-JVM scaffold for V4.3 barriers before production images exist. */
public final class V43FastReopenHarnessProcess {
    private static final Pattern BARRIER_ID =
            Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V43FastReopenHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3 || !BARRIER_ID.matcher(arguments[2]).matches()) {
            throw new IllegalArgumentException("expected mode, store and barrier ID");
        }
        String mode = arguments[0];
        Path store = Path.of(arguments[1]).toAbsolutePath().normalize();
        String barrier = arguments[2];
        switch (mode) {
            case "child-halt" -> child(store, barrier, true);
            case "child-wait" -> child(store, barrier, false);
            case "verify" -> verify(store, barrier);
            case "phase3-crash" -> phase3Crash(store);
            case "phase3-inspect" -> phase3Inspect(store, barrier);
            case "phase3-verify" -> phase3Verify(store, barrier);
            case "phase4-crash" -> phase4Crash(store);
            case "phase4-inspect" -> phase3Inspect(store, barrier);
            case "phase4-verify" -> phase4Verify(store, barrier);
            case "phase5-cleanup-crash" -> phase5CleanupCrash(store);
            case "phase5-cleanup-inspect" -> phase3Inspect(store, barrier);
            case "phase5-cleanup-verify" -> phase5CleanupVerify(store, barrier);
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void child(Path store, String barrier, boolean halt) throws Exception {
        Files.createDirectories(store);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(store.resolve("graceful-close.marker"), "ran\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // Presence is the only parent-visible signal.
            }
        }, "v43-fast-reopen-shutdown-marker"));
        Files.writeString(store.resolve("v43-phase1-canonical.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\ncanonicalAuthority=VALID\nformat=PHASE2_PENDING"
                        + "\nproductionDerivedState=false\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V43_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrier + "\",\"pid\":"
                + ProcessHandle.current().pid()
                + ",\"canonicalAuthority\":\"VALID\","
                + "\"derivedMembersCreated\":false}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(89);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void verify(Path store, String barrier) throws Exception {
        String value = Files.readString(store.resolve("v43-phase1-canonical.properties"),
                StandardCharsets.UTF_8);
        boolean derived;
        try (Stream<Path> members = Files.list(store)) {
            derived = members.anyMatch(path -> {
                String name = path.getFileName().toString();
                return name.startsWith("gse-derived-")
                        || name.equals("gse-derived-catalog");
            });
        }
        if (!value.contains("barrierId=" + barrier + "\n")
                || !value.contains("canonicalAuthority=VALID\n")
                || !value.contains("format=PHASE2_PENDING\n")
                || !value.contains("productionDerivedState=false\n")
                || Files.exists(store.resolve("graceful-close.marker")) || derived) {
            throw new IllegalStateException("V4.3 Phase 1 scaffold state mismatch");
        }
        System.out.println("GSE_V43_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"ABSENT\",\"productionDerivedState\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static void phase3Crash(Path store) {
        installShutdownMarker(store.resolve("graceful-close.marker"));
        String barrier = System.getProperty("gse.v4.crashBarrier");
        String action = System.getProperty("gse.v4.crashAction", "halt");
        if (barrier == null) {
            throw new IllegalArgumentException("missing production crash barrier");
        }
        System.clearProperty("gse.v4.crashBarrier");
        DurableSearchEngine<Integer, Document> engine = openEngine(store);
        engine.addAll(List.of(
                new Document(1, "book", 10, "alpha"),
                new Document(2, "music", 20, "alpine"),
                new Document(3, "book", 30, "beta"))).join();
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", action);
        engine.checkpoint().join();
        throw new IllegalStateException(
                "configured V4.3 derived-state barrier was not reached");
    }

    private static void phase3Verify(Path store, String barrier) {
        if (Files.exists(store.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        DurableReopenReport report;
        try (DurableSearchEngine<Integer, Document> engine = openEngine(store)) {
            report = engine.lastReopenReport().orElseThrow();
            if (engine.currentSequence() != 1
                    || engine.get(1) == null || engine.get(2) == null
                    || engine.get(3) == null
                    || !engine.search(Query.eq(CATEGORY, "book")).stream()
                            .map(Document::id).toList().equals(List.of(1, 3))
                    || !engine.search(Query.between(PRICE, 15, 30)).stream()
                            .map(Document::id).toList().equals(List.of(2, 3))
                    || !engine.search(Query.prefix(TITLE, "al")).stream()
                            .map(Document::id).toList().equals(List.of(1, 2))) {
                throw new IllegalStateException(
                        "V4.3 replacement-JVM query result mismatch");
            }
        }
        DurableDerivedStateStatus finalStatus =
                DurableStorageOperations.inspectDerivedState(store).status();
        if (finalStatus != DurableDerivedStateStatus.VALID) {
            throw new IllegalStateException(
                    "replacement JVM did not leave a valid derived generation");
        }
        System.out.println("GSE_V43_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"" + finalStatus + "\","
                + "\"reopenOutcome\":\"" + report.outcome() + "\","
                + "\"refreshAttempted\":" + report.refreshAttempted() + ","
                + "\"refreshSucceeded\":" + report.refreshSucceeded() + ","
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static void phase3Inspect(Path store, String barrier) {
        var canonical = DurableStorageOperations.verifyStore(store);
        var derived = DurableStorageOperations.inspectDerivedState(store);
        if (canonical.status() != DurableVerificationStatus.VALID
                || derived.status() == DurableDerivedStateStatus.NOT_APPLICABLE
                || derived.status() == DurableDerivedStateStatus.INCOMPATIBLE) {
            throw new IllegalStateException(
                    "independent pre-open inspection rejected crash state");
        }
        System.out.println("GSE_V43_INSPECTION_RESULT={\"schemaVersion\":1,"
                + "\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"" + derived.status() + "\","
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static DurableSearchEngine<Integer, Document> openEngine(Path store) {
        DurableStorageConfig<Integer, Document> storage =
                DurableStorageConfig.builder(store, new DocumentCodec())
                        .format(DurableStorageFormat.V1_2)
                        .storageIdentity("v43-phase3-crash-store")
                        .schemaIdentity("v43-phase3-crash-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024)
                        .maxDerivedStateBytes(16L * 1024 * 1024)
                        .build();
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .buildDurable(storage);
    }

    private static void phase4Crash(Path store) {
        installShutdownMarker(store.resolve("graceful-close.marker"));
        String barrier = System.getProperty("gse.v4.crashBarrier");
        String action = System.getProperty("gse.v4.crashAction", "halt");
        if (barrier == null) {
            throw new IllegalArgumentException("missing production crash barrier");
        }
        System.clearProperty("gse.v4.crashBarrier");
        DurableSearchEngine<Integer, Phase4Document> engine = openPhase4Engine(store);
        engine.addAll(List.of(
                new Phase4Document(1, "book", 10, "alpha",
                        "java search search"),
                new Phase4Document(2, "music", 20, "alpine",
                        "java memory model"),
                new Phase4Document(3, "book", 30, "beta",
                        "search engine design"))).join();
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", action);
        engine.checkpoint().join();
        throw new IllegalStateException(
                "configured V4.3 text-image barrier was not reached");
    }

    private static void phase4Verify(Path store, String barrier) {
        if (Files.exists(store.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        DurableReopenReport report;
        try (DurableSearchEngine<Integer, Phase4Document> engine =
                     openPhase4Engine(store)) {
            report = engine.lastReopenReport().orElseThrow();
            if (engine.currentSequence() != 1
                    || !engine.search(Query.eq(PHASE4_CATEGORY, "book")).stream()
                            .map(Phase4Document::id).toList().equals(List.of(1, 3))
                    || !engine.search(Query.between(PHASE4_PRICE, 15, 30)).stream()
                            .map(Phase4Document::id).toList().equals(List.of(2, 3))
                    || !engine.search(Query.prefix(PHASE4_TITLE, "al")).stream()
                            .map(Phase4Document::id).toList().equals(List.of(1, 2))
                    || !engine.search(Query.term(PHASE4_TEXT, "java")).stream()
                            .map(Phase4Document::id).toList().equals(List.of(1, 2))
                    || !engine.search(Query.allTerms(
                            PHASE4_TEXT, "java search")).stream()
                            .map(Phase4Document::id).toList().equals(List.of(1))) {
                throw new IllegalStateException(
                        "V4.3 Phase 4 replacement-JVM query result mismatch");
            }
        }
        DurableDerivedStateStatus finalStatus =
                DurableStorageOperations.inspectDerivedState(store).status();
        if (finalStatus != DurableDerivedStateStatus.VALID) {
            throw new IllegalStateException(
                    "replacement JVM did not leave a valid mixed generation");
        }
        System.out.println("GSE_V43_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"" + finalStatus + "\","
                + "\"reopenOutcome\":\"" + report.outcome() + "\","
                + "\"refreshAttempted\":" + report.refreshAttempted() + ","
                + "\"refreshSucceeded\":" + report.refreshSucceeded() + ","
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static DurableSearchEngine<Integer, Phase4Document> openPhase4Engine(
            Path store
    ) {
        DurableStorageConfig<Integer, Phase4Document> storage =
                DurableStorageConfig.builder(store, new Phase4DocumentCodec())
                        .format(DurableStorageFormat.V1_2)
                        .storageIdentity("v43-phase4-crash-store")
                        .schemaIdentity("v43-phase4-crash-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024)
                        .maxDerivedStateBytes(16L * 1024 * 1024)
                        .build();
        return SearchEngine.builder(Phase4Document.class, PHASE4_ID)
                .field(PHASE4_CATEGORY).field(PHASE4_PRICE)
                .field(PHASE4_TITLE).field(PHASE4_BODY)
                .textField(PHASE4_TEXT)
                .index(IndexDefinition.equality(PHASE4_CATEGORY))
                .index(IndexDefinition.range(PHASE4_PRICE))
                .index(IndexDefinition.prefix(PHASE4_TITLE))
                .index(IndexDefinition.text(PHASE4_TEXT))
                .buildDurable(storage);
    }

    private static void phase5CleanupCrash(Path store) throws IOException {
        installShutdownMarker(store.resolve("graceful-close.marker"));
        String barrier = System.getProperty("gse.v4.crashBarrier");
        String action = System.getProperty("gse.v4.crashAction", "halt");
        if (barrier == null) {
            throw new IllegalArgumentException("missing production cleanup barrier");
        }
        System.clearProperty("gse.v4.crashBarrier");
        try (DurableSearchEngine<Integer, Phase4Document> engine =
                     openPhase4Engine(store)) {
            engine.addAll(List.of(
                    new Phase4Document(1, "book", 10, "alpha",
                            "java search search"),
                    new Phase4Document(2, "music", 20, "alpine",
                            "java memory model"),
                    new Phase4Document(3, "book", 30, "beta",
                            "search engine design"))).join();
            engine.checkpoint().join();
            engine.add(new Phase4Document(4, "book", 40, "delta",
                    "continued search lifecycle")).join();
            engine.checkpoint().join();
        }
        Files.writeString(store.resolve("gse-derived-manifest.staging"),
                "abandoned catalog staging", StandardCharsets.UTF_8);
        var plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(store, DurableCleanupScope.LIVE_STORE));
        if (plan.deleteSet().size() < 5) {
            throw new IllegalStateException(
                    "superseded derived cleanup fixture is incomplete");
        }
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", action);
        DurableStorageOperations.applyCleanup(plan);
        throw new IllegalStateException(
                "configured V4.3 cleanup barrier was not reached");
    }

    private static void phase5CleanupVerify(Path store, String barrier) {
        if (Files.exists(store.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        var request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        var recoveryPlan = DurableStorageOperations.planCleanup(request);
        DurableStorageOperations.applyCleanup(recoveryPlan);
        var cleaned = DurableStorageOperations.inspectDerivedState(store);
        if (cleaned.status() != DurableDerivedStateStatus.VALID
                || cleaned.stagingBytes() != 0
                || cleaned.unreferencedBytes() != 0) {
            throw new IllegalStateException(
                    "replacement cleanup did not converge to one valid generation");
        }

        DurableReopenReport first;
        try (DurableSearchEngine<Integer, Phase4Document> engine =
                     openPhase4Engine(store)) {
            first = engine.lastReopenReport().orElseThrow();
            if (!engine.search(Query.term(PHASE4_TEXT, "search")).stream()
                    .map(Phase4Document::id).toList()
                    .equals(List.of(1, 3, 4))) {
                throw new IllegalStateException(
                        "cleanup replacement-JVM query result mismatch");
            }
            engine.add(new Phase4Document(5, "music", 50, "epsilon",
                    "post cleanup mutation")).join();
            engine.checkpoint().join();
        }
        DurableStorageOperations.applyCleanup(
                DurableStorageOperations.planCleanup(request));
        DurableReopenReport second;
        long continuedSequence;
        try (DurableSearchEngine<Integer, Phase4Document> reopened =
                     openPhase4Engine(store)) {
            second = reopened.lastReopenReport().orElseThrow();
            continuedSequence = reopened.currentSequence();
            if (reopened.get(5) == null
                    || !reopened.search(Query.term(PHASE4_TEXT, "mutation"))
                            .stream().map(Phase4Document::id).toList()
                            .equals(List.of(5))) {
                throw new IllegalStateException(
                        "post-cleanup continuation did not survive second reopen");
            }
        }
        var finalState = DurableStorageOperations.inspectDerivedState(store);
        if (first.outcome() != DurableReopenOutcome.COMPLETE_WARM
                || second.outcome() != DurableReopenOutcome.COMPLETE_WARM
                || finalState.status() != DurableDerivedStateStatus.VALID
                || finalState.unreferencedBytes() != 0) {
            throw new IllegalStateException(
                    "cleanup lifecycle did not remain completely warm");
        }
        System.out.println("GSE_V43_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"VALID\","
                + "\"reopenOutcome\":\"" + second.outcome() + "\","
                + "\"refreshAttempted\":" + second.refreshAttempted() + ","
                + "\"refreshSucceeded\":" + second.refreshSucceeded() + ","
                + "\"continuedSequence\":" + continuedSequence + ","
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static void installShutdownMarker(Path marker) {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(marker, "shutdown-hook-ran\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // The verifier treats marker presence as a non-abrupt termination.
            }
        }, "v43-derived-shutdown-marker"));
    }

    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);

    private static final Field<Phase4Document, Integer> PHASE4_ID =
            Field.of("id", Integer.class, Phase4Document::id);
    private static final Field<Phase4Document, String> PHASE4_CATEGORY =
            Field.of("category", String.class, Phase4Document::category);
    private static final Field<Phase4Document, Integer> PHASE4_PRICE =
            Field.of("price", Integer.class, Phase4Document::price);
    private static final Field<Phase4Document, String> PHASE4_TITLE =
            Field.of("title", String.class, Phase4Document::title);
    private static final Field<Phase4Document, String> PHASE4_BODY =
            Field.of("body", String.class, Phase4Document::body);
    private static final TextField<Phase4Document> PHASE4_TEXT =
            TextField.of(PHASE4_BODY, Analyzer.simple());

    private record Document(int id, String category, int price, String title) {
    }

    private record Phase4Document(
            int id,
            String category,
            int price,
            String title,
            String body
    ) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v43-phase3-crash-codec";
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
            return ByteBuffer.wrap(bytes).getInt();
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
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Document result = new Document(input.readInt(), input.readUTF(),
                        input.readInt(), input.readUTF());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }

    private static final class Phase4DocumentCodec
            implements DurableCodec<Integer, Phase4Document> {
        @Override
        public String codecId() {
            return "v43-phase4-crash-codec";
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
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Phase4Document document) {
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
                throw new AssertionError(impossible);
            }
        }

        @Override
        public Phase4Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Phase4Document result = new Phase4Document(
                        input.readInt(), input.readUTF(), input.readInt(),
                        input.readUTF(), input.readUTF());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException(
                        "invalid Phase 4 document bytes", failure);
            }
        }
    }
}
