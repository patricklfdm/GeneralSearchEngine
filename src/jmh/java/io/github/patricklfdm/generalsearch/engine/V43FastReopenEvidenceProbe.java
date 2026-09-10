package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableReopenOutcome;
import io.github.patricklfdm.generalsearch.durability.DurableReopenReport;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Benchmark-only V4.3 fast-reopen and replacement-host evidence probe. */
public final class V43FastReopenEvidenceProbe {
    private static final String PROPERTY_SCHEMA =
            "gse-v43-fast-reopen-properties-v1";
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

    private V43FastReopenEvidenceProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length == 0) {
            usage();
        }
        switch (arguments[0]) {
            case "source" -> source(arguments);
            case "replacement" -> replacement(arguments);
            default -> usage();
        }
    }

    private static void source(String[] arguments) throws Exception {
        if (arguments.length != 5) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path primary = realDirectory(arguments[2], "primary root");
        Path target = realDirectory(arguments[3], "target root");
        Path output = absentFile(arguments[4]);
        Path store = absent(primary.resolve("current-store"));
        Path backup = absent(primary.resolve("canonical-backup"));
        Path migrationSource = absent(primary.resolve("migration-source"));
        Path restored = absent(target.resolve("restored-target"));
        Path migrated = absent(target.resolve("migrated-target"));
        Map<String, String> values = base("source", profile);
        long stageStarted = System.nanoTime();

        long loadStarted = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            addDocuments(engine, profile);
            engine.checkpoint().join();
            values.put("source.sequence", Long.toString(engine.currentSequence()));
            values.put("source.initialChecksum", checksum(engine, profile.documents()));
        }
        values.put("source.loadCheckpointNanos", elapsed(loadStarted));
        requireValid(store);

        long backupStarted = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            var result = engine.backup(new DurableBackupRequest(
                    backup, 8L * 1024 * 1024 * 1024)).join();
            values.put("backup.sequence", Long.toString(result.sequence()));
            values.put("backup.contentIdentity", result.contentIdentity());
            values.put("backup.totalBytes", Long.toString(result.totalBytes()));
        }
        values.put("backup.elapsedNanos", elapsed(backupStarted));
        if (DurableStorageOperations.verifyBackup(backup).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("canonical backup verification failed");
        }

        long[] forced = new long[profile.samples()];
        long[] ready = new long[profile.samples()];
        long[] refresh = new long[profile.samples()];
        long[] warm = new long[profile.samples()];
        long[] warmRead = new long[profile.samples()];
        for (int sample = 0; sample < profile.samples(); sample++) {
            removeDerived(store);
            OpenResult cold = measureOpen(store, profile,
                    DurableReopenOutcome.FULL_FALLBACK, 0);
            forced[sample] = cold.elapsedNanos();
            refresh[sample] = Math.max(1L,
                    cold.report().refreshDuration().toNanos());
            ready[sample] = Math.max(1L, cold.report().totalOpenDuration().toNanos()
                    - cold.report().refreshDuration().toNanos());
            OpenResult hot = measureOpen(store, profile,
                    DurableReopenOutcome.COMPLETE_WARM, 0);
            warm[sample] = hot.elapsedNanos();
            warmRead[sample] = hot.report().derivedBytesRead();
        }
        values.put("forced.samplesNanos", csv(forced));
        values.put("forced.medianNanos", Long.toString(median(forced)));
        values.put("forced.recoveryReadyMedianNanos", Long.toString(median(ready)));
        values.put("forced.refreshMedianNanos", Long.toString(median(refresh)));
        values.put("forced.checksum", values.get("source.initialChecksum"));
        values.put("warm.samplesNanos", csv(warm));
        values.put("warm.medianNanos", Long.toString(median(warm)));
        values.put("warm.derivedReadMedianBytes", Long.toString(median(warmRead)));
        values.put("warm.checksum", values.get("source.initialChecksum"));
        values.put("warm.ratioMicros", Long.toString(Math.round(
                median(warm) * 1_000_000.0 / median(forced))));
        requireDerivedValid(store, "paired measurement");

        builder().restoreDurableBackup(backup,
                config(restored, DurableStorageFormat.V1_2, profile));
        OpenResult restoredCold = measureOpen(restored, profile,
                DurableReopenOutcome.FULL_FALLBACK, 0);
        OpenResult restoredWarm = measureOpen(restored, profile,
                DurableReopenOutcome.COMPLETE_WARM, 0);
        values.put("restore.coldOpenNanos",
                Long.toString(restoredCold.elapsedNanos()));
        values.put("restore.warmOpenNanos",
                Long.toString(restoredWarm.elapsedNanos()));
        values.put("restore.checksum", restoredWarm.checksum());
        values.put("restore.coldOutcome", restoredCold.report().outcome().name());
        values.put("restore.warmOutcome", restoredWarm.report().outcome().name());
        deleteTree(restored);

        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(migrationSource,
                        DurableStorageFormat.V1_1, profile))) {
            addDocuments(engine, profile);
            engine.checkpoint().join();
        }
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                migration(migrationSource, migrated, profile);
        long planStarted = System.nanoTime();
        DurableMigrationPlan plan = builder().planDurableMigration(
                builder(), request);
        values.put("migration.planNanos", elapsed(planStarted));
        values.put("migration.planDigest", plan.planDigest());
        values.put("migration.targetHistory", plan.targetHistory().toString());
        long applyStarted = System.nanoTime();
        builder().applyDurableMigration(builder(), request, plan);
        values.put("migration.applyNanos", elapsed(applyStarted));
        OpenResult migratedCold = measureOpen(migrated, profile,
                DurableReopenOutcome.FULL_FALLBACK, 0);
        values.put("migration.coldOpenNanos",
                Long.toString(migratedCold.elapsedNanos()));
        values.put("migration.coldOutcome", migratedCold.report().outcome().name());
        values.put("migration.checksum", migratedCold.checksum());
        requireDerivedValid(store, "migration");

        values.put("source.canonicalBytes", Long.toString(canonicalBytes(store)));
        values.put("source.derivedBytes", Long.toString(derivedBytes(store)));
        values.put("source.directoryBytes", Long.toString(directoryBytes(store)));
        values.put("source.temporaryPeakBytes", Long.toString(Math.max(
                directoryBytes(store) + directoryBytes(backup),
                directoryBytes(migrationSource) + directoryBytes(migrated))));
        values.put("source.heapUsedBytes", Long.toString(heapUsedBytes()));
        values.put("source.gcCount", Long.toString(gcCount()));
        values.put("source.gcTimeMillis", Long.toString(gcTimeMillis()));
        values.put("source.totalNanos", elapsed(stageStarted));
        values.put("pageCacheState", "uncontrolled-os-cache");
        values.put("status", "PASS");
        writeProperties(output, values);
        System.out.printf("v43FastReopenSource=PASS profile=%s documents=%d "
                        + "ratioMicros=%s%n", profile.name(), profile.documents(),
                values.get("warm.ratioMicros"));
    }

    private static void replacement(String[] arguments) throws Exception {
        if (arguments.length != 7) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path primary = realDirectory(arguments[2], "primary root");
        Path target = realDirectory(arguments[3], "target root");
        Map<String, String> source = readProperties(Path.of(arguments[4]));
        Path output = absentFile(arguments[5]);
        long seconds = positive(arguments[6], "measurement seconds");
        validateSource(source, profile);
        Path store = existing(primary.resolve("current-store"));
        Path migrated = existing(target.resolve("migrated-target"));
        Map<String, String> values = base("replacement", profile);

        OpenResult primaryWarm = measureOpen(store, profile,
                DurableReopenOutcome.COMPLETE_WARM, 0);
        values.put("replacement.primaryWarmNanos",
                Long.toString(primaryWarm.elapsedNanos()));
        values.put("replacement.primaryChecksum", primaryWarm.checksum());
        OpenResult migratedWarm = measureOpen(migrated, profile,
                DurableReopenOutcome.COMPLETE_WARM, 0);
        values.put("replacement.migratedWarmNanos",
                Long.toString(migratedWarm.elapsedNanos()));
        values.put("replacement.migratedChecksum", migratedWarm.checksum());

        corrupt(component(store, 0));
        OpenResult structured = measureOpen(store, profile,
                DurableReopenOutcome.PARTIAL_FALLBACK, 0);
        values.put("fallback.structuredOpenNanos",
                Long.toString(structured.elapsedNanos()));
        values.put("fallback.structuredChecksum", structured.checksum());
        values.put("fallback.structuredLoaded",
                Integer.toString(structured.report().loadedComponentCount()));
        values.put("fallback.structuredRebuilt",
                Integer.toString(structured.report().rebuiltComponentCount()));
        cleanup(store);

        corrupt(component(store, 3));
        OpenResult text = measureOpen(store, profile,
                DurableReopenOutcome.PARTIAL_FALLBACK, 0);
        values.put("fallback.textOpenNanos", Long.toString(text.elapsedNanos()));
        values.put("fallback.textChecksum", text.checksum());
        values.put("fallback.textLoaded",
                Integer.toString(text.report().loadedComponentCount()));
        values.put("fallback.textRebuilt",
                Integer.toString(text.report().rebuiltComponentCount()));
        cleanup(store);

        corrupt(store.resolve("gse-derived-manifest"));
        OpenResult catalog = measureOpen(store, profile,
                DurableReopenOutcome.FULL_FALLBACK, 0);
        values.put("fallback.catalogOpenNanos",
                Long.toString(catalog.elapsedNanos()));
        values.put("fallback.catalogChecksum", catalog.checksum());
        values.put("fallback.catalogRebuilt",
                Integer.toString(catalog.report().rebuiltComponentCount()));
        cleanup(store);

        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            engine.checkpoint().join();
            updateDocuments(engine, profile);
        }
        OpenResult wal = measureOpen(store, profile,
                DurableReopenOutcome.COMPLETE_WARM, profile.mutations());
        values.put("wal.openNanos", Long.toString(wal.elapsedNanos()));
        values.put("wal.checksum", wal.checksum());
        values.put("wal.replayCreatedIndexes",
                Integer.toString(wal.report().replayCreatedIndexCount()));
        values.put("wal.recoveredSequence",
                Long.toString(wal.report().recoveredSequence()));

        long lifecycleStarted = System.nanoTime();
        long finalSequence;
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            engine.dropIndex(BODY.name()).join();
            engine.createIndex(IndexDefinition.text(TEXT)).join();
            engine.checkpoint().join();
            finalSequence = engine.currentSequence();
        }
        cleanup(store);
        OpenResult lifecycle = measureOpen(store, profile,
                DurableReopenOutcome.COMPLETE_WARM, profile.mutations());
        values.put("lifecycle.elapsedNanos", elapsed(lifecycleStarted));
        values.put("lifecycle.reopenNanos",
                Long.toString(lifecycle.elapsedNanos()));
        values.put("lifecycle.checksum", lifecycle.checksum());
        values.put("lifecycle.sequence", Long.toString(finalSequence));

        long cpuStart = processCpuNanos();
        long readsStart = processIo("read_bytes");
        long writesStart = processIo("write_bytes");
        long gcCountStart = gcCount();
        long gcTimeStart = gcTimeMillis();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            measureReads(engine, profile, seconds, values);
        }
        values.put("measurement.processCpuNanos",
                Long.toString(Math.max(0L, processCpuNanos() - cpuStart)));
        values.put("measurement.readBytes",
                Long.toString(delta(processIo("read_bytes"), readsStart)));
        values.put("measurement.writeBytes",
                Long.toString(delta(processIo("write_bytes"), writesStart)));
        values.put("measurement.gcCount",
                Long.toString(delta(gcCount(), gcCountStart)));
        values.put("measurement.gcTimeMillis",
                Long.toString(delta(gcTimeMillis(), gcTimeStart)));
        values.put("replacement.heapUsedBytes", Long.toString(heapUsedBytes()));
        values.put("replacement.canonicalBytes",
                Long.toString(canonicalBytes(store)));
        values.put("replacement.derivedBytes", Long.toString(derivedBytes(store)));
        values.put("replacement.directoryBytes",
                Long.toString(directoryBytes(store)));
        values.put("pageCacheState", "uncontrolled-os-cache");
        values.put("measurementSeconds", Long.toString(seconds));
        values.put("status", "PASS");
        writeProperties(output, values);
        System.out.printf("v43FastReopenReplacement=PASS profile=%s "
                + "sequence=%d%n", profile.name(), finalSequence);
    }

    private static OpenResult measureOpen(
            Path store,
            Profile profile,
            DurableReopenOutcome outcome,
            int revised
    ) {
        long started = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, DurableStorageFormat.V1_2, profile))) {
            long elapsed = Math.max(1L, System.nanoTime() - started);
            DurableReopenReport report = engine.lastReopenReport().orElseThrow();
            boolean fallback = outcome == DurableReopenOutcome.PARTIAL_FALLBACK
                    || outcome == DurableReopenOutcome.FULL_FALLBACK;
            if (report.outcome() != outcome
                    || fallback && (!report.refreshAttempted()
                            || !report.refreshSucceeded())
                    || !fallback && report.refreshAttempted()) {
                throw new IllegalStateException("unexpected reopen report: " + report);
            }
            String checksum = checksum(engine, profile.documents());
            if (!checksum.equals(expectedChecksum(profile, revised))) {
                throw new IllegalStateException("reopen checksum differs");
            }
            assertRetrieval(engine, profile, revised);
            return new OpenResult(elapsed, checksum, report);
        }
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            migration(Path source, Path target, Profile profile) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v43-fast-reopen-store-v1", "v43-fast-reopen-schema-v1",
                        CODEC, 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        profile.documents() * 2),
                config(target, DurableStorageFormat.V1_2, profile),
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                8L * 1024 * 1024 * 1024, 8L * 1024 * 1024 * 1024,
                1024L * 1024 * 1024, profile.documents(), 1_000, 64 * 1024);
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
            Path path,
            DurableStorageFormat format,
            Profile profile
    ) {
        DurableStorageConfig.Builder<Integer, Document> builder =
                DurableStorageConfig.builder(path, CODEC)
                        .format(format)
                        .storageIdentity("v43-fast-reopen-store-v1")
                        .schemaIdentity("v43-fast-reopen-schema-v1")
                        .maxDocuments(profile.documents() * 2)
                        .maxBulkElements(1_000)
                        .checkpointWalBytes(256L * 1024 * 1024)
                        .maxRetainedBytes(8L * 1024 * 1024 * 1024);
        if (format.equals(DurableStorageFormat.V1_2)) {
            builder.maxDerivedStateBytes(4L * 1024 * 1024 * 1024);
        }
        return builder.build();
    }

    private static void addDocuments(
            DurableSearchEngine<Integer, Document> engine,
            Profile profile
    ) {
        for (int start = 0; start < profile.documents(); start += profile.batch()) {
            List<Document> batch = new ArrayList<>();
            for (int id = start; id < Math.min(
                    profile.documents(), start + profile.batch()); id++) {
                batch.add(document(id, 0));
            }
            engine.addAll(batch).join();
        }
    }

    private static void updateDocuments(
            DurableSearchEngine<Integer, Document> engine,
            Profile profile
    ) {
        for (int start = 0; start < profile.mutations(); start += profile.batch()) {
            List<Document> batch = new ArrayList<>();
            for (int id = start; id < Math.min(
                    profile.mutations(), start + profile.batch()); id++) {
                batch.add(document(id, 1));
            }
            engine.updateAll(batch).join();
        }
    }

    private static void assertRetrieval(
            DurableSearchEngine<Integer, Document> engine,
            Profile profile,
            int revised
    ) {
        int id = profile.documents() - 1;
        Document expected = document(id, id < revised ? 1 : 0);
        if (!expected.equals(engine.get(id))
                || !engine.search(Query.eq(CATEGORY, expected.category()))
                        .contains(expected)
                || !engine.search(Query.between(PRICE, expected.price(),
                        expected.price())).contains(expected)
                || !engine.search(Query.prefix(TITLE, expected.title()))
                        .contains(expected)
                || !engine.search(Query.term(TEXT, "bucket" + (id % 97)))
                        .contains(expected)) {
            throw new IllegalStateException("retrieval oracle differs");
        }
    }

    private static void measureReads(
            DurableSearchEngine<Integer, Document> engine,
            Profile profile,
            long seconds,
            Map<String, String> values
    ) throws InterruptedException {
        AtomicLong reads = new AtomicLong();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        long started = System.nanoTime();
        long deadline = started + TimeUnit.SECONDS.toNanos(seconds);
        List<Thread> workers = new ArrayList<>();
        for (int worker = 0; worker < profile.readers(); worker++) {
            int offset = worker;
            Thread thread = new Thread(() -> {
                try {
                    while (System.nanoTime() < deadline && failure.get() == null) {
                        long operation = reads.getAndIncrement();
                        int id = (int) ((operation + offset) % profile.documents());
                        if (engine.get(id) == null) {
                            throw new IllegalStateException("measurement lost data");
                        }
                    }
                } catch (Throwable caught) {
                    failure.compareAndSet(null, caught);
                }
            }, "v43-fast-reopen-reader-" + worker);
            workers.add(thread);
            thread.start();
        }
        for (Thread worker : workers) {
            worker.join(TimeUnit.SECONDS.toMillis(seconds + 30));
            if (worker.isAlive()) {
                worker.interrupt();
                throw new IllegalStateException("measurement worker did not stop");
            }
        }
        if (failure.get() != null || reads.get() == 0) {
            throw new IllegalStateException("measurement failed", failure.get());
        }
        long duration = Math.max(1L, System.nanoTime() - started);
        values.put("measurement.reads", Long.toString(reads.get()));
        values.put("measurement.durationNanos", Long.toString(duration));
        values.put("measurement.readsPerSecondMicros", Long.toString(Math.round(
                reads.get() * 1_000_000_000_000_000.0 / duration)));
    }

    private static String checksum(
            DurableSearchEngine<Integer, Document> engine,
            int documents
    ) {
        MessageDigest digest = sha256();
        for (int id = 0; id < documents; id++) {
            Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing document " + id);
            }
            digestRecord(digest, id, CODEC.encodeDocument(document));
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String expectedChecksum(Profile profile, int revised) {
        MessageDigest digest = sha256();
        for (int id = 0; id < profile.documents(); id++) {
            digestRecord(digest, id, CODEC.encodeDocument(
                    document(id, id < revised ? 1 : 0)));
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void digestRecord(MessageDigest digest, int id, byte[] value) {
        digest.update(ByteBuffer.allocate(8).putInt(id).putInt(value.length).array());
        digest.update(value);
    }

    private static Document document(int id, int revision) {
        return new Document(id, "category-" + (id % 32), id % 10_000,
                "title-" + (id % 2_048),
                "document id" + id + " revision" + revision
                        + " bucket" + (id % 97)
                        + " alpha beta gamma delta epsilon zeta eta theta iota"
                        + " kappa lambda mu");
    }

    private static void requireValid(Path store) {
        if (DurableStorageOperations.verifyStore(store).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("store verification failed");
        }
    }

    private static void requireDerivedValid(Path store, String stage) {
        var report = DurableStorageOperations.inspectDerivedState(store);
        if (report.status() != DurableDerivedStateStatus.VALID) {
            throw new IllegalStateException(
                    "derived state changed after " + stage + ": " + report);
        }
    }

    private static void cleanup(Path store) {
        var request = new DurableCleanupRequest(
                store, DurableCleanupScope.LIVE_STORE);
        DurableStorageOperations.applyCleanup(
                DurableStorageOperations.planCleanup(request));
        requireValid(store);
    }

    private static void removeDerived(Path store) throws IOException {
        try (var paths = Files.list(store)) {
            for (Path path : paths.filter(candidate -> candidate.getFileName()
                    .toString().startsWith("gse-derived-")).toList()) {
                Files.delete(path);
            }
        }
    }

    private static Path component(Path store, int ordinal) throws IOException {
        String marker = "-%05d-".formatted(ordinal);
        try (var paths = Files.list(store)) {
            return paths.filter(path -> path.getFileName().toString()
                            .startsWith("gse-derived-index-"))
                    .filter(path -> path.getFileName().toString().contains(marker))
                    .filter(path -> path.getFileName().toString().endsWith(".idx"))
                    .min(Comparator.comparing(path -> path.getFileName().toString()))
                    .orElseThrow();
        }
    }

    private static void corrupt(Path path) throws IOException {
        byte[] bytes = Files.readAllBytes(path);
        bytes[bytes.length / 2] ^= 1;
        Files.write(path, bytes);
    }

    private static long canonicalBytes(Path store) throws IOException {
        return bytesMatching(store, false);
    }

    private static long derivedBytes(Path store) throws IOException {
        return bytesMatching(store, true);
    }

    private static long bytesMatching(Path store, boolean derived)
            throws IOException {
        long result = 0L;
        try (var paths = Files.walk(store)) {
            for (Path path : paths.filter(Files::isRegularFile).toList()) {
                boolean member = path.getFileName().toString()
                        .startsWith("gse-derived-");
                if (member == derived) {
                    result = Math.addExact(result, Files.size(path));
                }
            }
        }
        return result;
    }

    private static long directoryBytes(Path directory) throws IOException {
        long result = 0L;
        try (var paths = Files.walk(directory)) {
            for (Path path : paths.filter(Files::isRegularFile).toList()) {
                result = Math.addExact(result, Files.size(path));
            }
        }
        return result;
    }

    private static void deleteTree(Path directory) throws IOException {
        try (var paths = Files.walk(directory)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.delete(path);
            }
        }
    }

    private static Map<String, String> base(String stage, Profile profile) {
        Map<String, String> values = new TreeMap<>();
        values.put("schemaVersion", PROPERTY_SCHEMA);
        values.put("status", "RUNNING");
        values.put("stage", stage);
        values.put("profile", profile.name());
        values.put("documents", Integer.toString(profile.documents()));
        values.put("tokensPerDocument", "16");
        values.put("mutations", Integer.toString(profile.mutations()));
        values.put("samples", Integer.toString(profile.samples()));
        values.put("processCpuNanosAtStart", Long.toString(processCpuNanos()));
        return values;
    }

    private static void validateSource(
            Map<String, String> values,
            Profile profile
    ) {
        if (!PROPERTY_SCHEMA.equals(values.get("schemaVersion"))
                || !"PASS".equals(values.get("status"))
                || !"source".equals(values.get("stage"))
                || !profile.name().equals(values.get("profile"))
                || !Integer.toString(profile.documents())
                        .equals(values.get("documents"))) {
            throw new IllegalArgumentException("source properties differ");
        }
    }

    private static Map<String, String> readProperties(Path path) throws IOException {
        Map<String, String> result = new TreeMap<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            int separator = line.indexOf('=');
            if (separator <= 0 || separator == line.length() - 1
                    || result.put(line.substring(0, separator),
                    line.substring(separator + 1)) != null) {
                throw new IllegalArgumentException("invalid evidence properties");
            }
        }
        return result;
    }

    private static void writeProperties(Path path, Map<String, String> values)
            throws IOException {
        values.put("processCpuNanosAtEnd", Long.toString(processCpuNanos()));
        StringBuilder content = new StringBuilder();
        for (Map.Entry<String, String> entry : values.entrySet()) {
            if (!entry.getKey().matches("[A-Za-z0-9.]+")
                    || entry.getValue().isBlank()
                    || entry.getValue().contains("\n")
                    || entry.getValue().contains("\r")
                    || entry.getValue().contains("=")) {
                throw new IllegalArgumentException("invalid evidence property");
            }
            content.append(entry.getKey()).append('=').append(entry.getValue())
                    .append('\n');
        }
        Files.writeString(path, content, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
    }

    private static Path realDirectory(String value, String label)
            throws IOException {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.isSymbolicLink(path) || !Files.isDirectory(path)) {
            throw new IllegalArgumentException(label + " is not a real directory");
        }
        return path.toRealPath();
    }

    private static Path absent(Path path) {
        Path value = path.toAbsolutePath().normalize();
        if (Files.exists(value)) {
            throw new IllegalArgumentException("path already exists: " + value);
        }
        return value;
    }

    private static Path existing(Path path) {
        Path value = path.toAbsolutePath().normalize();
        if (!Files.isDirectory(value) || Files.isSymbolicLink(value)) {
            throw new IllegalArgumentException("directory is absent: " + value);
        }
        return value;
    }

    private static Path absentFile(String value) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.exists(path) || path.getParent() == null
                || !Files.isDirectory(path.getParent())) {
            throw new IllegalArgumentException("output file must be absent");
        }
        return path;
    }

    private static long positive(String value, String label) {
        try {
            long parsed = Long.parseLong(value);
            if (parsed <= 0) {
                throw new NumberFormatException();
            }
            return parsed;
        } catch (NumberFormatException failure) {
            throw new IllegalArgumentException(label + " must be positive", failure);
        }
    }

    private static String csv(long[] values) {
        return Arrays.stream(values).mapToObj(Long::toString)
                .reduce((left, right) -> left + "," + right).orElseThrow();
    }

    private static long median(long[] values) {
        long[] copy = values.clone();
        Arrays.sort(copy);
        return copy[copy.length / 2];
    }

    private static long heapUsedBytes() {
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    private static long gcCount() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount)
                .filter(value -> value > 0).sum();
    }

    private static long gcTimeMillis() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionTime)
                .filter(value -> value > 0).sum();
    }

    private static long processCpuNanos() {
        var bean = ManagementFactory.getOperatingSystemMXBean();
        if (bean instanceof com.sun.management.OperatingSystemMXBean sun) {
            return Math.max(0L, sun.getProcessCpuTime());
        }
        return 0L;
    }

    private static long processIo(String key) {
        Path io = Path.of("/proc/self/io");
        if (!Files.isRegularFile(io)) {
            return 0L;
        }
        try {
            for (String line : Files.readAllLines(io, StandardCharsets.US_ASCII)) {
                if (line.startsWith(key + ":")) {
                    return Long.parseLong(line.substring(line.indexOf(':') + 1)
                            .trim());
                }
            }
            return 0L;
        } catch (IOException | NumberFormatException ignored) {
            return 0L;
        }
    }

    private static long delta(long after, long before) {
        return Math.max(0L, after - before);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static String elapsed(long started) {
        return Long.toString(Math.max(1L, System.nanoTime() - started));
    }

    private static void usage() {
        throw new IllegalArgumentException(
                "usage: V43FastReopenEvidenceProbe source <profile> <primary-root> "
                        + "<target-root> <properties> | replacement <profile> "
                        + "<primary-root> <target-root> <source-properties> "
                        + "<properties> <measurement-seconds>");
    }

    private record OpenResult(
            long elapsedNanos,
            String checksum,
            DurableReopenReport report
    ) {
    }

    private record Document(
            int id,
            String category,
            int price,
            String title,
            String body
    ) {
    }

    private record Profile(
            String name,
            int documents,
            int mutations,
            int batch,
            int samples,
            int readers
    ) {
        private static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(name, 1_000, 100, 100, 3, 2);
                case "production" ->
                        new Profile(name, 100_000, 10_000, 1_000, 5, 8);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
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
