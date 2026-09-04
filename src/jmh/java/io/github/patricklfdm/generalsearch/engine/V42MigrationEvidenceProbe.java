package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.management.ManagementFactory;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Benchmark-only V4.2 scale, migration and replacement-host evidence probe. */
public final class V42MigrationEvidenceProbe {
    private static final String PROPERTY_SCHEMA =
            "gse-v42-migration-properties-v1";
    private static final Field<SourceDocument, Integer> SOURCE_ID =
            Field.of("id", Integer.class, SourceDocument::id);
    private static final Field<SourceDocument, String> SOURCE_BODY =
            Field.of("body", String.class, SourceDocument::body);
    private static final Field<TargetDocument, String> TARGET_ID =
            Field.of("sku", String.class, TargetDocument::sku);
    private static final Field<TargetDocument, Long> TARGET_VALUE =
            Field.of("value", Long.class, TargetDocument::value);
    private static final Field<TargetDocument, String> TARGET_BODY =
            Field.of("body", String.class, TargetDocument::body);
    private static final SourceCodec SOURCE_CODEC = new SourceCodec();
    private static final TargetCodec TARGET_CODEC = new TargetCodec();

    private V42MigrationEvidenceProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length == 0) {
            usage();
        }
        switch (arguments[0]) {
            case "source" -> source(arguments);
            case "migrate" -> migrate(arguments);
            case "target" -> target(arguments);
            default -> usage();
        }
    }

    private static void source(String[] arguments) throws Exception {
        if (arguments.length != 6) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path store = absent(arguments[2], "source store");
        Path backup = absent(arguments[3], "backup");
        Path output = absentFile(arguments[4], "source properties");
        positive(arguments[5], "measurement seconds");
        Map<String, String> values = base("source", profile);
        long started = System.nanoTime();
        try (DurableSearchEngine<Integer, SourceDocument> engine = sourceBuilder()
                .buildDurable(sourceConfig(store, profile))) {
            long load = System.nanoTime();
            addSource(engine, profile);
            values.put("source.loadNanos", elapsed(load));
            long mutations = System.nanoTime();
            updateSource(engine, profile.preMigrationMutations(), 1,
                    profile.batchSize());
            values.put("source.mutationNanos", elapsed(mutations));
            long checkpoint = System.nanoTime();
            engine.checkpoint().join();
            values.put("source.checkpointNanos", elapsed(checkpoint));
            values.put("source.sequence", Long.toString(engine.currentSequence()));
            values.put("source.oracleChecksum",
                    sourceChecksum(engine, profile.documents()));
            long backupStarted = System.nanoTime();
            var result = engine.backup(new DurableBackupRequest(
                    backup, 8L * 1024 * 1024 * 1024)).join();
            values.put("backup.elapsedNanos", elapsed(backupStarted));
            values.put("backup.sequence", Long.toString(result.sequence()));
            values.put("backup.contentIdentity", result.contentIdentity());
            values.put("backup.totalBytes", Long.toString(result.totalBytes()));
            values.put("source.retainedBytes",
                    Long.toString(engine.durabilityMetrics().retainedBytes()));
            values.put("source.heapUsedBytes", Long.toString(heapUsedBytes()));
        }
        if (DurableStorageOperations.verifyStore(store).status()
                != DurableVerificationStatus.VALID
                || DurableStorageOperations.verifyBackup(backup).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("source or backup verification failed");
        }
        values.put("source.directorySha256", directoryDigest(store));
        values.put("source.directoryBytes", Long.toString(directoryBytes(store)));
        values.put("source.totalNanos", elapsed(started));
        values.put("status", "PASS");
        writeProperties(output, values);
        System.out.printf("v42MigrationSource=PASS profile=%s documents=%d%n",
                profile.name(), profile.documents());
    }

    private static void migrate(String[] arguments) throws Exception {
        if (arguments.length != 6) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path source = existing(arguments[2], "source store");
        Path target = absent(arguments[3], "target store");
        Map<String, String> sourceValues = readProperties(
                Path.of(arguments[4]));
        Path output = absentFile(arguments[5], "migration properties");
        validateSource(sourceValues, profile);
        if (!directoryDigest(source).equals(
                sourceValues.get("source.directorySha256"))) {
            throw new IllegalStateException("source bytes changed before migration");
        }
        Map<String, String> values = base("migration", profile);
        DurableMigrationRequest<Integer, SourceDocument,
                String, TargetDocument> request = request(source, target, profile);
        long planStarted = System.nanoTime();
        DurableMigrationPlan plan = targetBuilder().planDurableMigration(
                sourceBuilder(), request);
        values.put("migration.planNanos", elapsed(planStarted));
        values.put("migration.planDigest", plan.planDigest());
        values.put("migration.projectionDigest", plan.projectionDigest());
        values.put("migration.sourceAuthorityIdentity",
                plan.sourceAuthorityIdentity());
        values.put("migration.predictedTargetBytes",
                Long.toString(plan.targetAuthoritativeBytes()));
        values.put("migration.peakTargetBytes",
                Long.toString(plan.peakTargetBytes()));
        values.put("migration.sourceSequence",
                Long.toString(plan.sourceSequence()));
        values.put("migration.sourceHistory", plan.sourceHistory().toString());
        values.put("migration.targetHistory", plan.targetHistory().toString());
        long applyStarted = System.nanoTime();
        DurableMigrationResult result = targetBuilder().applyDurableMigration(
                sourceBuilder(), request, plan);
        values.put("migration.applyNanos", elapsed(applyStarted));
        values.put("migration.authoritativeBytes",
                Long.toString(result.authoritativeBytes()));
        values.put("migration.sourceDirectorySha256After", directoryDigest(source));
        if (!values.get("migration.sourceDirectorySha256After").equals(
                sourceValues.get("source.directorySha256"))) {
            throw new IllegalStateException("migration changed source bytes");
        }
        if (DurableStorageOperations.verifyStore(target).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("target structural verification failed");
        }
        try (DurableSearchEngine<String, TargetDocument> engine = targetBuilder()
                .buildDurable(targetConfig(target, profile))) {
            String expected = expectedTargetChecksum(profile, false);
            String actual = targetChecksum(engine, profile.documents());
            if (!actual.equals(expected)
                    || engine.currentSequence() != plan.sourceSequence()) {
                throw new IllegalStateException("initial target oracle differs");
            }
            values.put("target.initialChecksum", actual);
            values.put("target.initialSequence",
                    Long.toString(engine.currentSequence()));
        }
        values.put("target.directoryBytes", Long.toString(directoryBytes(target)));
        values.put("target.directorySha256", directoryDigest(target));
        values.put("migration.heapUsedBytes", Long.toString(heapUsedBytes()));
        values.put("status", "PASS");
        writeProperties(output, values);
        System.out.printf("v42MigrationApply=PASS profile=%s plan=%s%n",
                profile.name(), plan.planDigest());
    }

    private static void target(String[] arguments) throws Exception {
        if (arguments.length != 6) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path target = existing(arguments[2], "target store");
        Map<String, String> migration = readProperties(Path.of(arguments[3]));
        Path output = absentFile(arguments[4], "target properties");
        long measurementSeconds = positive(
                arguments[5], "measurement seconds");
        if (!"PASS".equals(migration.get("status"))
                || !profile.name().equals(migration.get("profile"))
                || !directoryDigest(target).equals(
                migration.get("target.directorySha256"))) {
            throw new IllegalArgumentException("migration evidence differs");
        }
        Map<String, String> values = base("target", profile);
        long firstOpen = System.nanoTime();
        long finalSequence;
        String finalChecksum;
        try (DurableSearchEngine<String, TargetDocument> engine = targetBuilder()
                .buildDurable(targetConfig(target, profile))) {
            values.put("target.firstOpenNanos", elapsed(firstOpen));
            if (!targetChecksum(engine, profile.documents()).equals(
                    migration.get("target.initialChecksum"))) {
                throw new IllegalStateException("replacement target oracle differs");
            }
            assertTargetRetrieval(engine, profile);
            long continued = System.nanoTime();
            updateTarget(engine, profile.continuedTargetMutations(), 2,
                    profile.batchSize());
            values.put("target.continuedMutationNanos", elapsed(continued));
            long checkpoint = System.nanoTime();
            engine.checkpoint().join();
            values.put("target.checkpointNanos", elapsed(checkpoint));
            finalSequence = engine.currentSequence();
            finalChecksum = targetChecksum(engine, profile.documents());
            if (!finalChecksum.equals(expectedTargetChecksum(profile, true))) {
                throw new IllegalStateException(
                        "continued target oracle differs");
            }
            values.put("target.retainedBytes",
                    Long.toString(engine.durabilityMetrics().retainedBytes()));
            values.put("target.heapUsedBytes", Long.toString(heapUsedBytes()));
        }
        long secondOpen = System.nanoTime();
        try (DurableSearchEngine<String, TargetDocument> engine = targetBuilder()
                .buildDurable(targetConfig(target, profile))) {
            values.put("target.secondOpenNanos", elapsed(secondOpen));
            if (engine.currentSequence() != finalSequence
                    || !targetChecksum(engine, profile.documents())
                    .equals(finalChecksum)) {
                throw new IllegalStateException("continued target reopen differs");
            }
            assertTargetRetrieval(engine, profile);
            measureReads(engine, profile, measurementSeconds, values);
        }
        values.put("target.finalSequence", Long.toString(finalSequence));
        values.put("target.finalChecksum", finalChecksum);
        values.put("target.finalDirectoryBytes",
                Long.toString(directoryBytes(target)));
        values.put("target.finalDirectorySha256", directoryDigest(target));
        values.put("measurementSeconds", Long.toString(measurementSeconds));
        values.put("status", "PASS");
        writeProperties(output, values);
        System.out.printf("v42MigrationTarget=PASS profile=%s sequence=%d%n",
                profile.name(), finalSequence);
    }

    private static DurableMigrationRequest<Integer, SourceDocument,
            String, TargetDocument> request(
            Path source,
            Path target,
            Profile profile
    ) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v42-migration-source-v1",
                        "v42-migration-source-schema-v1", SOURCE_CODEC, 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        profile.documents() * 2),
                targetConfig(target, profile),
                new DurableMigrationTransformDescriptor(
                        "catalog-schema-key-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(sku(key),
                        new TargetDocument(sku(key), document.id() * 10L,
                                document.body())),
                8L * 1024 * 1024 * 1024,
                8L * 1024 * 1024 * 1024,
                1024L * 1024 * 1024,
                profile.documents(), 1024, 64 * 1024);
    }

    private static SearchEngineBuilder<Integer, SourceDocument> sourceBuilder() {
        return SearchEngine.builder(SourceDocument.class, SOURCE_ID)
                .field(SOURCE_BODY)
                .index(IndexDefinition.equality(SOURCE_BODY));
    }

    private static SearchEngineBuilder<String, TargetDocument> targetBuilder() {
        return SearchEngine.builder(TargetDocument.class, TARGET_ID)
                .field(TARGET_VALUE).field(TARGET_BODY)
                .index(IndexDefinition.range(TARGET_VALUE))
                .index(IndexDefinition.prefix(TARGET_BODY));
    }

    private static DurableStorageConfig<Integer, SourceDocument> sourceConfig(
            Path path,
            Profile profile
    ) {
        return DurableStorageConfig.builder(path, SOURCE_CODEC)
                .format(DurableStorageFormat.V1_0)
                .storageIdentity("v42-migration-source-v1")
                .schemaIdentity("v42-migration-source-schema-v1")
                .maxBulkElements(1_000)
                .maxDocuments(profile.documents() * 2)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static DurableStorageConfig<String, TargetDocument> targetConfig(
            Path path,
            Profile profile
    ) {
        return DurableStorageConfig.builder(path, TARGET_CODEC)
                .format(DurableStorageFormat.V1_1)
                .storageIdentity("v42-migration-target-v1")
                .schemaIdentity("v42-migration-target-schema-v1")
                .maxBulkElements(1_000)
                .maxDocuments(profile.documents() * 2)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static void addSource(
            DurableSearchEngine<Integer, SourceDocument> engine,
            Profile profile
    ) {
        for (int start = 0; start < profile.documents();
                start += profile.batchSize()) {
            List<SourceDocument> values = new ArrayList<>();
            for (int id = start; id < Math.min(
                    start + profile.batchSize(), profile.documents()); id++) {
                values.add(sourceDocument(id, 0));
            }
            engine.addAll(values).join();
        }
    }

    private static void updateSource(
            DurableSearchEngine<Integer, SourceDocument> engine,
            int count,
            int revision,
            int batch
    ) {
        for (int start = 0; start < count; start += batch) {
            List<SourceDocument> values = new ArrayList<>();
            for (int id = start; id < Math.min(start + batch, count); id++) {
                values.add(sourceDocument(id, revision));
            }
            engine.updateAll(values).join();
        }
    }

    private static void updateTarget(
            DurableSearchEngine<String, TargetDocument> engine,
            int count,
            int revision,
            int batch
    ) {
        for (int start = 0; start < count; start += batch) {
            List<TargetDocument> values = new ArrayList<>();
            for (int id = start; id < Math.min(start + batch, count); id++) {
                values.add(new TargetDocument(sku(id), id * 10L, body(id, revision)));
            }
            engine.updateAll(values).join();
        }
    }

    private static void assertTargetRetrieval(
            DurableSearchEngine<String, TargetDocument> engine,
            Profile profile
    ) {
        int id = profile.documents() - 1;
        TargetDocument expected = new TargetDocument(
                sku(id), id * 10L, body(id, 0));
        if (!expected.equals(engine.get(expected.sku()))
                || !engine.search(Query.between(
                        TARGET_VALUE, expected.value(), expected.value()))
                .equals(List.of(expected))) {
            throw new IllegalStateException("target retrieval oracle differs");
        }
    }

    private static void measureReads(
            DurableSearchEngine<String, TargetDocument> engine,
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
                        if (engine.get(sku(id)) == null) {
                            throw new IllegalStateException("target read lost data");
                        }
                    }
                } catch (Throwable caught) {
                    failure.compareAndSet(null, caught);
                }
            }, "v42-target-reader-" + worker);
            workers.add(thread);
            thread.start();
        }
        for (Thread worker : workers) {
            worker.join(TimeUnit.SECONDS.toMillis(seconds + 30));
            if (worker.isAlive()) {
                worker.interrupt();
                throw new IllegalStateException("target reader did not stop");
            }
        }
        if (failure.get() != null || reads.get() == 0) {
            throw new IllegalStateException("target measurement failed", failure.get());
        }
        long duration = Math.max(1L, System.nanoTime() - started);
        values.put("measurement.reads", Long.toString(reads.get()));
        values.put("measurement.durationNanos", Long.toString(duration));
        values.put("measurement.readsPerSecondMicros", Long.toString(Math.round(
                reads.get() * 1_000_000_000_000_000.0 / duration)));
    }

    private static String sourceChecksum(
            DurableSearchEngine<Integer, SourceDocument> engine,
            int count
    ) {
        MessageDigest digest = sha256Digest();
        for (int id = 0; id < count; id++) {
            SourceDocument document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing source document " + id);
            }
            digestRecord(digest, id, SOURCE_CODEC.encodeDocument(document));
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String targetChecksum(
            DurableSearchEngine<String, TargetDocument> engine,
            int count
    ) {
        MessageDigest digest = sha256Digest();
        for (int id = 0; id < count; id++) {
            TargetDocument document = engine.get(sku(id));
            if (document == null) {
                throw new IllegalStateException("missing target document " + id);
            }
            byte[] key = TARGET_CODEC.encodeKey(document.sku());
            byte[] value = TARGET_CODEC.encodeDocument(document);
            digest.update(ByteBuffer.allocate(8)
                    .putInt(key.length).putInt(value.length).array());
            digest.update(key);
            digest.update(value);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String expectedTargetChecksum(
            Profile profile,
            boolean continued
    ) {
        MessageDigest digest = sha256Digest();
        for (int id = 0; id < profile.documents(); id++) {
            int actualRevision = continued
                    && id < profile.continuedTargetMutations() ? 2
                    : id < profile.preMigrationMutations() ? 1 : 0;
            TargetDocument document = new TargetDocument(
                    sku(id), id * 10L, body(id, actualRevision));
            byte[] key = TARGET_CODEC.encodeKey(document.sku());
            byte[] value = TARGET_CODEC.encodeDocument(document);
            digest.update(ByteBuffer.allocate(8)
                    .putInt(key.length).putInt(value.length).array());
            digest.update(key);
            digest.update(value);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void digestRecord(MessageDigest digest, int id, byte[] value) {
        digest.update(ByteBuffer.allocate(8)
                .putInt(id).putInt(value.length).array());
        digest.update(value);
    }

    private static String directoryDigest(Path directory) throws IOException {
        MessageDigest digest = sha256Digest();
        try (var files = Files.walk(directory)) {
            for (Path file : files.filter(Files::isRegularFile)
                    .sorted(Comparator.comparing(path ->
                            directory.relativize(path).toString())).toList()) {
                byte[] name = directory.relativize(file).toString()
                        .getBytes(StandardCharsets.UTF_8);
                byte[] content = Files.readAllBytes(file);
                digest.update(ByteBuffer.allocate(8)
                        .putInt(name.length).putInt(content.length).array());
                digest.update(name);
                digest.update(content);
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static long directoryBytes(Path directory) throws IOException {
        try (var files = Files.walk(directory)) {
            long total = 0L;
            for (Path file : files.filter(Files::isRegularFile).toList()) {
                total = Math.addExact(total, Files.size(file));
            }
            return total;
        }
    }

    private static SourceDocument sourceDocument(int id, int revision) {
        return new SourceDocument(id, body(id, revision));
    }

    private static String body(int id, int revision) {
        return "document id" + id + " revision" + revision
                + " alpha beta gamma delta epsilon zeta eta theta iota kappa"
                + " lambda mu nu";
    }

    private static String sku(int id) {
        return "sku-%08d".formatted(id);
    }

    private static Map<String, String> base(String stage, Profile profile) {
        Map<String, String> values = new TreeMap<>();
        values.put("schemaVersion", PROPERTY_SCHEMA);
        values.put("status", "RUNNING");
        values.put("stage", stage);
        values.put("profile", profile.name());
        values.put("documents", Integer.toString(profile.documents()));
        values.put("tokensPerDocument", "16");
        values.put("preMigrationMutations",
                Integer.toString(profile.preMigrationMutations()));
        values.put("continuedTargetMutations",
                Integer.toString(profile.continuedTargetMutations()));
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
                || !profile.name().equals(values.get("profile"))) {
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

    private static Path absent(String value, String label) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.exists(path)) {
            throw new IllegalArgumentException(label + " already exists");
        }
        return path;
    }

    private static Path existing(String value, String label) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (!Files.isDirectory(path) || Files.isSymbolicLink(path)) {
            throw new IllegalArgumentException(label + " is not a real directory");
        }
        return path;
    }

    private static Path absentFile(String value, String label) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.exists(path) || path.getParent() == null
                || !Files.isDirectory(path.getParent())) {
            throw new IllegalArgumentException(label + " is not absent");
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

    private static MessageDigest sha256Digest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static long heapUsedBytes() {
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    private static long processCpuNanos() {
        var bean = ManagementFactory.getOperatingSystemMXBean();
        if (bean instanceof com.sun.management.OperatingSystemMXBean sun) {
            return Math.max(0L, sun.getProcessCpuTime());
        }
        return 0L;
    }

    private static String elapsed(long started) {
        return Long.toString(Math.max(1L, System.nanoTime() - started));
    }

    private static void usage() {
        throw new IllegalArgumentException(
                "usage: V42MigrationEvidenceProbe source <profile> <source> "
                        + "<backup> <properties> <seconds> | migrate <profile> "
                        + "<source> <target> <source-properties> <properties> | "
                        + "target <profile> <target> <migration-properties> "
                        + "<properties> <seconds>");
    }

    private record SourceDocument(int id, String body) {
    }

    private record TargetDocument(String sku, long value, String body) {
    }

    private record Profile(
            String name,
            int documents,
            int preMigrationMutations,
            int continuedTargetMutations,
            int batchSize,
            int readers
    ) {
        private static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(name, 1_000, 100, 20, 100, 2);
                case "production" ->
                        new Profile(name, 100_000, 10_000, 1_000, 1_000, 8);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
    }

    private static final class SourceCodec
            implements DurableCodec<Integer, SourceDocument> {
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
        public byte[] encodeDocument(SourceDocument document) {
            return write(output -> {
                output.writeInt(document.id());
                output.writeUTF(document.body());
            });
        }

        @Override
        public SourceDocument decodeDocument(byte[] encoded) {
            return read(encoded, input -> new SourceDocument(
                    input.readInt(), input.readUTF()));
        }
    }

    private static final class TargetCodec
            implements DurableCodec<String, TargetDocument> {
        @Override
        public String codecId() {
            return "v42-migration-target-codec-v1";
        }

        @Override
        public int codecVersion() {
            return 2;
        }

        @Override
        public byte[] encodeKey(String key) {
            return write(output -> output.writeUTF(key));
        }

        @Override
        public String decodeKey(byte[] encoded) {
            return read(encoded, input -> input.readUTF());
        }

        @Override
        public byte[] encodeDocument(TargetDocument document) {
            return write(output -> {
                output.writeUTF(document.sku());
                output.writeLong(document.value());
                output.writeUTF(document.body());
            });
        }

        @Override
        public TargetDocument decodeDocument(byte[] encoded) {
            return read(encoded, input -> new TargetDocument(
                    input.readUTF(), input.readLong(), input.readUTF()));
        }
    }

    private static byte[] write(Writer writer) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                writer.write(output);
            }
            return bytes.toByteArray();
        } catch (IOException impossible) {
            throw new UncheckedIOException(impossible);
        }
    }

    private static <T> T read(byte[] encoded, Reader<T> reader) {
        try (DataInputStream input = new DataInputStream(
                new ByteArrayInputStream(encoded))) {
            T result = reader.read(input);
            if (input.read() != -1) {
                throw new IllegalArgumentException("trailing codec bytes");
            }
            return result;
        } catch (IOException failure) {
            throw new IllegalArgumentException("invalid codec bytes", failure);
        }
    }

    @FunctionalInterface
    private interface Writer {
        void write(DataOutputStream output) throws IOException;
    }

    @FunctionalInterface
    private interface Reader<T> {
        T read(DataInputStream input) throws IOException;
    }
}
