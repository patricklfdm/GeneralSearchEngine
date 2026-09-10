package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.durability.DurableDerivedStateStatus;
import io.github.patricklfdm.generalsearch.durability.DurableReopenOutcome;
import io.github.patricklfdm.generalsearch.durability.DurableReopenRejection;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexRegistry;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.equality.EqualityIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.range.RangeIndexSnapshot;
import io.github.patricklfdm.generalsearch.internal.index.ImmutableOverlayMap;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;

/** Production V4.3 structured-image codec, deliberately separate from inspection. */
final class DurableStructuredDerivedState {
    static final String CATALOG_FILE = "gse-derived-manifest";
    static final String CATALOG_STAGING_FILE = CATALOG_FILE + ".staging";
    static final Pattern COMPONENT_FILE = Pattern.compile(
            "gse-derived-index-([0-9]{20})-([0-9]{5})-([a-f0-9]{32})\\.idx");
    static final Pattern COMPONENT_STAGING_FILE = Pattern.compile(
            COMPONENT_FILE.pattern() + "\\.staging");

    private static final long CATALOG_MAGIC = 0x4753454443415431L;
    private static final long COMPONENT_MAGIC = 0x4753454449445831L;
    private static final short ENCODING_MAJOR = 1;
    private static final short ENCODING_MINOR = 0;
    private static final String GENERATOR_ID = "gse-derived-generator-v1";
    private static final int GENERATOR_VERSION = 1;
    private static final byte[] CATALOG_DOMAIN = ascii(
            "gse-derived-catalog-content-v1\0");
    private static final byte[] COMPONENT_DOMAIN = ascii(
            "gse-derived-component-content-v1\0");
    private static final int MAX_CATALOG_BYTES = 16 * 1024 * 1024;
    private static final long MAX_COMPONENT_BYTES = 2L * 1024 * 1024 * 1024;
    private static final int MAX_COMPONENTS = 100_000;
    private static final int MAX_COUNT = 100_000_000;
    private static final int MAX_STRING_BYTES = 1024 * 1024;

    private DurableStructuredDerivedState() {
    }

    static <K, T> LoadResult<T> load(
            DurableStorageOwner storage,
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            DurableCheckpoint.Manifest manifest,
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) {
        long inspectionStarted = System.nanoTime();
        Authority authority;
        try {
            authority = authority(storage, config, manifest, checkpoint);
        } catch (IOException failure) {
            return rebuildAll(checkpoint, schema,
                    DurableDerivedStateStatus.CORRUPT,
                    List.of(), elapsed(inspectionStarted), Duration.ZERO, 0L);
        }
        Path catalogPath = storage.directory().resolve(CATALOG_FILE);
        if (!Files.isRegularFile(catalogPath, LinkOption.NOFOLLOW_LINKS)
                || Files.isSymbolicLink(catalogPath)) {
            return rebuildAll(checkpoint, schema,
                    DurableDerivedStateStatus.ABSENT,
                    List.of(), elapsed(inspectionStarted), Duration.ZERO, 0L);
        }

        Catalog catalog;
        long bytesRead = 0L;
        try {
            byte[] encoded = readBounded(catalogPath, MAX_CATALOG_BYTES);
            bytesRead = encoded.length;
            catalog = parseCatalog(encoded, authority);
        } catch (DerivedFailure failure) {
            return rebuildAll(checkpoint, schema, failure.status(),
                    List.of(), elapsed(inspectionStarted), Duration.ZERO, bytesRead);
        } catch (IOException | RuntimeException failure) {
            return rebuildAll(checkpoint, schema,
                    DurableDerivedStateStatus.CORRUPT,
                    List.of(), elapsed(inspectionStarted), Duration.ZERO, bytesRead);
        }
        Duration inspectionDuration = elapsed(inspectionStarted);
        long loadStarted = System.nanoTime();
        List<IndexSnapshot<T>> snapshots = new ArrayList<>(catalog.entries().size());
        List<DurableReopenRejection> rejections = new ArrayList<>();
        boolean componentFailure = false;
        int loaded = 0;
        for (CatalogEntry entry : catalog.entries()) {
            DurableIndexDescriptor descriptor = checkpoint.indexes().get(entry.ordinal());
            Path component = storage.directory().resolve(entry.filename());
            try {
                byte[] encoded = readBounded(component, MAX_COMPONENT_BYTES);
                bytesRead = Math.addExact(bytesRead, encoded.length);
                requireWholeMember(entry, encoded);
                IndexSnapshot<T> parsed = parseStructuredComponent(
                        encoded, authority, entry, checkpoint, schema);
                snapshots.add(parsed);
                if (descriptor.kind() == DurableIndexDescriptor.TEXT) {
                    rejections.add(new DurableReopenRejection(
                            entry.ordinal(), "TEXT_IMAGE_PHASE4_PENDING"));
                } else {
                    loaded++;
                }
            } catch (DerivedFailure failure) {
                snapshots.add(null);
                componentFailure = true;
                rejections.add(new DurableReopenRejection(
                        entry.ordinal(), failure.code()));
            } catch (IOException | RuntimeException failure) {
                snapshots.add(null);
                componentFailure = true;
                rejections.add(new DurableReopenRejection(
                        entry.ordinal(), "COMPONENT_CORRUPT"));
            }
        }
        Duration loadDuration = elapsed(loadStarted);
        DurableDerivedStateStatus status = componentFailure
                ? DurableDerivedStateStatus.PARTIAL
                : DurableDerivedStateStatus.VALID;
        return finishSnapshot(checkpoint, schema, snapshots, loaded, status,
                rejections, inspectionDuration, loadDuration, bytesRead);
    }

    static <K, T> RefreshResult refresh(
            DurableStorageOwner storage,
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            DurableCheckpoint.Manifest manifest,
            DurableCheckpoint.Capture<K, T> capture
    ) {
        long started = System.nanoTime();
        DurableCrashHooks.reach("v43-derived-before-refresh-v1");
        if (!storage.format().publicFormat().equals(
                io.github.patricklfdm.generalsearch.durability
                        .DurableStorageFormat.V1_2)
                || capture.indexes().stream().anyMatch(
                        index -> index.kind() == DurableIndexDescriptor.TEXT)) {
            DurableCrashHooks.reach("v43-derived-after-refresh-v1");
            return new RefreshResult(true, false, elapsed(started), 0L);
        }
        List<Path> staging = new ArrayList<>();
        try {
            Authority authority = authority(storage, config, manifest,
                    new DurableCheckpoint.Loaded<>(List.of(), Map.of(),
                            capture.nextDocId(), capture.sequence(), capture.indexes()),
                    capture.snapshot().activeDocuments().cardinality());
            String generation = UUID.randomUUID().toString().replace("-", "");
            List<EncodedComponent> encodedComponents = new ArrayList<>();
            long derivedBytes = 0L;
            for (int ordinal = 0; ordinal < capture.indexes().size(); ordinal++) {
                DurableIndexDescriptor descriptor = capture.indexes().get(ordinal);
                byte[] bytes = encodeComponent(
                        authority, ordinal, descriptor, capture.snapshot(), schema);
                if (bytes.length > MAX_COMPONENT_BYTES) {
                    throw new IOException("derived component exceeds its bound");
                }
                String filename = "gse-derived-index-%020d-%05d-%s.idx".formatted(
                        capture.sequence(), ordinal, generation);
                encodedComponents.add(new EncodedComponent(
                        ordinal, descriptor, filename, bytes,
                        trailingChecksum(bytes), sha256(bytes)));
                derivedBytes = Math.addExact(derivedBytes, bytes.length);
            }
            byte[] catalog = encodeCatalog(authority, encodedComponents);
            derivedBytes = Math.addExact(derivedBytes, catalog.length);
            if (catalog.length > MAX_CATALOG_BYTES
                    || derivedBytes > config.maxDerivedStateBytes()
                    || derivedBytes > config.maxRetainedBytes() - storage.retainedBytes()
                    || derivedBytes > Files.getFileStore(
                            storage.directory()).getUsableSpace()) {
                throw new IOException("derived generation exceeds available capacity");
            }

            for (EncodedComponent component : encodedComponents) {
                Path finalPath = storage.directory().resolve(component.filename());
                Path stagingPath = storage.directory().resolve(
                        component.filename() + ".staging");
                staging.add(stagingPath);
                DurableCrashHooks.reach("v43-derived-before-component-write-v1");
                writeForced(stagingPath, component.bytes(),
                        "v43-derived-during-component-write-v1");
                DurableCrashHooks.reach("v43-derived-after-component-force-v1");
                parseStructuredComponent(component.bytes(), authority,
                        new CatalogEntry(component.ordinal(),
                                component.descriptor().kind(),
                                component.descriptor().fieldName(),
                                component.descriptor().analyzerId(),
                                component.filename(), component.bytes().length,
                                component.checksum(), component.sha256()),
                        captureAsLoaded(capture), schema);
                DurableCrashHooks.reach(
                        "v43-derived-during-component-validation-v1");
                DurableCrashHooks.reach("v43-derived-before-component-rename-v1");
                moveAtomic(stagingPath, finalPath, false);
                DurableCrashHooks.reach("v43-derived-after-component-rename-v1");
                DurableStorageOwner.forceDirectory(storage.directory());
                DurableCrashHooks.reach(
                        "v43-derived-after-component-parent-force-v1");
            }

            Path catalogStaging = storage.directory().resolve(CATALOG_STAGING_FILE);
            staging.add(catalogStaging);
            Files.deleteIfExists(catalogStaging);
            DurableCrashHooks.reach("v43-derived-before-catalog-write-v1");
            writeForced(catalogStaging, catalog,
                    "v43-derived-during-catalog-write-v1");
            DurableCrashHooks.reach("v43-derived-after-catalog-force-v1");
            parseCatalog(catalog, authority);
            DurableCrashHooks.reach("v43-derived-before-catalog-publication-v1");
            moveAtomic(catalogStaging, storage.directory().resolve(CATALOG_FILE), true);
            DurableCrashHooks.reach("v43-derived-after-catalog-publication-v1");
            DurableStorageOwner.forceDirectory(storage.directory());
            DurableCrashHooks.reach("v43-derived-after-catalog-parent-force-v1");
            byte[] published = readBounded(
                    storage.directory().resolve(CATALOG_FILE), MAX_CATALOG_BYTES);
            Catalog validated = parseCatalog(published, authority);
            for (CatalogEntry entry : validated.entries()) {
                byte[] component = readBounded(
                        storage.directory().resolve(entry.filename()),
                        MAX_COMPONENT_BYTES);
                requireWholeMember(entry, component);
                parseStructuredComponent(component, authority, entry,
                        captureAsLoaded(capture), schema);
            }
            DurableCrashHooks.reach("v43-derived-during-published-reinspection-v1");
            DurableCrashHooks.reach("v43-derived-after-complete-generation-v1");
            DurableCrashHooks.reach("v43-derived-after-refresh-v1");
            return new RefreshResult(true, true, elapsed(started), derivedBytes);
        } catch (IOException | RuntimeException failure) {
            for (Path path : staging) {
                try {
                    Files.deleteIfExists(path);
                } catch (IOException ignored) {
                    // A staging remnant is non-authoritative and handled later.
                }
            }
            DurableCrashHooks.reach("v43-derived-after-refresh-v1");
            return new RefreshResult(true, false, elapsed(started), 0L);
        }
    }

    static boolean recognizedName(String name) {
        return CATALOG_FILE.equals(name) || CATALOG_STAGING_FILE.equals(name)
                || COMPONENT_FILE.matcher(name).matches()
                || COMPONENT_STAGING_FILE.matcher(name).matches();
    }

    private static <K, T> LoadResult<T> rebuildAll(
            DurableCheckpoint.Loaded<K, T> checkpoint,
            SearchSchema<T, K> schema,
            DurableDerivedStateStatus status,
            List<DurableReopenRejection> rejections,
            Duration inspectionDuration,
            Duration loadDuration,
            long bytesRead
    ) {
        return finishSnapshot(checkpoint, schema,
                java.util.Collections.nCopies(checkpoint.indexes().size(), null),
                0, status, rejections, inspectionDuration, loadDuration, bytesRead);
    }

    private static <K, T> LoadResult<T> finishSnapshot(
            DurableCheckpoint.Loaded<K, T> checkpoint,
            SearchSchema<T, K> schema,
            List<IndexSnapshot<T>> candidates,
            int loaded,
            DurableDerivedStateStatus status,
            List<DurableReopenRejection> initialRejections,
            Duration inspectionDuration,
            Duration loadDuration,
            long bytesRead
    ) {
        long rebuildStarted = System.nanoTime();
        DurableCrashHooks.reach("v43-derived-before-fallback-rebuild-v1");
        List<IndexSnapshot<T>> completed = new ArrayList<>(candidates);
        List<DurableReopenRejection> rejections = new ArrayList<>(initialRejections);
        for (int ordinal = 0; ordinal < completed.size(); ordinal++) {
            if (completed.get(ordinal) != null) {
                continue;
            }
            try {
                IndexDefinition<T> definition = checkpoint.indexes().get(ordinal)
                        .toDefinition(schema);
                IndexBuilder<T> builder = definition.createEmpty().toBuilder();
                for (int docId = 0; docId < checkpoint.slots().size(); docId++) {
                    T document = checkpoint.slots().get(docId);
                    if (document != null) {
                        builder.add(docId, document);
                    }
                }
                completed.set(ordinal, builder.build());
            } catch (RuntimeException failure) {
                throw new io.github.patricklfdm.generalsearch.durability
                        .DurabilityException(
                        io.github.patricklfdm.generalsearch.durability
                                .DurabilityException.Reason.INDEX_REBUILD_FAILURE,
                        "derived-index fallback rebuild failed during durable open",
                        failure);
            }
        }
        DurableCrashHooks.reach("v43-derived-after-fallback-rebuild-v1");
        SearchSnapshot<T> documents = documentSnapshot(checkpoint);
        SearchSnapshot<T> snapshot = documents.withIndexes(
                IndexRegistry.fromSnapshots(completed));
        int rebuilt = completed.size() - loaded;
        DurableReopenOutcome outcome = loaded == completed.size()
                ? DurableReopenOutcome.COMPLETE_WARM
                : loaded == 0
                        ? DurableReopenOutcome.FULL_FALLBACK
                        : DurableReopenOutcome.PARTIAL_FALLBACK;
        return new LoadResult<>(snapshot, status, outcome, loaded, rebuilt,
                List.copyOf(rejections), inspectionDuration, loadDuration,
                elapsed(rebuildStarted), bytesRead);
    }

    private static <K, T> SearchSnapshot<T> documentSnapshot(
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) {
        SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of()));
        for (int docId = 0; docId < checkpoint.slots().size(); docId++) {
            T document = checkpoint.slots().get(docId);
            if (document != null) {
                builder.add(docId, document);
            }
        }
        return builder.build();
    }

    private static <K, T> Authority authority(
            DurableStorageOwner storage,
            DurableStorageConfig<K, T> config,
            DurableCheckpoint.Manifest manifest,
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) throws IOException {
        return authority(storage, config, manifest, checkpoint,
                checkpoint.documentIds().size());
    }

    private static <K, T> Authority authority(
            DurableStorageOwner storage,
            DurableStorageConfig<K, T> config,
            DurableCheckpoint.Manifest manifest,
            DurableCheckpoint.Loaded<K, T> checkpoint,
            int liveDocuments
    ) throws IOException {
        Path checkpointPath = storage.directory().resolve(manifest.checkpointFile());
        return new Authority(storage.format(), storage.historyId(), manifest,
                sha256(checkpointPath), config.storageIdentity(),
                config.schemaIdentity(), config.codec().codecId(),
                config.codec().codecVersion(), checkpoint.nextDocId(),
                liveDocuments, checkpoint.indexes());
    }

    private static <K, T> DurableCheckpoint.Loaded<K, T> captureAsLoaded(
            DurableCheckpoint.Capture<K, T> capture
    ) {
        List<T> slots = new ArrayList<>(capture.nextDocId());
        for (int docId = 0; docId < capture.nextDocId(); docId++) {
            slots.add(capture.snapshot().get(docId));
        }
        return new DurableCheckpoint.Loaded<>(slots, capture.documentIds(),
                capture.nextDocId(), capture.sequence(), capture.indexes());
    }

    private static Catalog parseCatalog(byte[] encoded, Authority authority) {
        CheckedMember member = checked(encoded, CATALOG_DOMAIN, 256, "CATALOG");
        Cursor cursor = new Cursor(member.content());
        try {
            long magic = cursor.longValue();
            short encodingMajor = cursor.shortValue();
            short encodingMinor = cursor.shortValue();
            short liveMajor = cursor.shortValue();
            short liveMinor = cursor.shortValue();
            byte[] profile = cursor.bytes(32);
            UUID history = new UUID(cursor.longValue(), cursor.longValue());
            long sequence = cursor.longValue();
            String checkpointFile = cursor.string(256, false);
            long checkpointBytes = cursor.longValue();
            int checkpointChecksum = cursor.intValue();
            byte[] checkpointSha = cursor.bytes(32);
            String storage = cursor.string(128, false);
            String schema = cursor.string(128, false);
            String codec = cursor.string(128, false);
            int codecVersion = cursor.intValue();
            String generator = cursor.string(128, false);
            int generatorVersion = cursor.intValue();
            int nextDocId = cursor.intValue();
            int liveDocuments = cursor.intValue();
            int count = cursor.count(MAX_COMPONENTS);
            if (magic != CATALOG_MAGIC || encodingMajor != ENCODING_MAJOR
                    || encodingMinor != ENCODING_MINOR || liveMajor != 1
                    || liveMinor != 2) {
                throw incompatible("CATALOG_FORMAT");
            }
            if (!GENERATOR_ID.equals(generator)
                    || generatorVersion != GENERATOR_VERSION) {
                throw incompatible("CATALOG_GENERATOR");
            }
            List<CatalogEntry> entries = new ArrayList<>(count);
            Set<String> names = new HashSet<>();
            for (int ordinal = 0; ordinal < count; ordinal++) {
                int actualOrdinal = cursor.intValue();
                byte kind = cursor.byteValue();
                String field = cursor.string(MAX_STRING_BYTES, false);
                String analyzer = cursor.string(128, true);
                String filename = cursor.string(256, false);
                long bytes = cursor.longValue();
                int checksum = cursor.intValue();
                byte[] sha = cursor.bytes(32);
                Matcher matcher = COMPONENT_FILE.matcher(filename);
                if (actualOrdinal != ordinal || !validDescriptor(kind, field, analyzer)
                        || bytes < 128 || bytes > MAX_COMPONENT_BYTES
                        || !names.add(filename) || !matcher.matches()
                        || Long.parseLong(matcher.group(1)) != sequence
                        || Integer.parseInt(matcher.group(2)) != ordinal) {
                    throw corrupt("CATALOG_COMPONENT_DESCRIPTOR");
                }
                entries.add(new CatalogEntry(ordinal, kind, field, analyzer,
                        filename, bytes, checksum, sha));
            }
            cursor.requireExhausted();
            if (liveMajor != DurableFormatContext.MAJOR
                    || liveMinor != authority.format().minor()
                    || !Arrays.equals(profile, authority.format().profileDigest())
                    || !history.equals(authority.history())
                    || sequence != authority.manifest().checkpointSequence()
                    || !checkpointFile.equals(authority.manifest().checkpointFile())
                    || checkpointBytes != authority.manifest().checkpointBytes()
                    || checkpointChecksum != authority.manifest().checkpointChecksum()
                    || !Arrays.equals(checkpointSha, authority.checkpointSha256())
                    || !storage.equals(authority.storageIdentity())
                    || !schema.equals(authority.schemaIdentity())
                    || !codec.equals(authority.codecIdentity())
                    || codecVersion != authority.codecVersion()
                    || nextDocId != authority.nextDocId()
                    || liveDocuments != authority.liveDocuments()
                    || entries.size() != authority.descriptors().size()) {
                throw stale("CATALOG_CANONICAL_BINDING");
            }
            for (int ordinal = 0; ordinal < entries.size(); ordinal++) {
                CatalogEntry entry = entries.get(ordinal);
                DurableIndexDescriptor descriptor = authority.descriptors().get(ordinal);
                if (entry.kind() != descriptor.kind()
                        || !entry.field().equals(descriptor.fieldName())
                        || !entry.analyzer().equals(descriptor.analyzerId())) {
                    throw stale("CATALOG_DESCRIPTOR_SET");
                }
            }
            return new Catalog(entries);
        } catch (DerivedFailure failure) {
            throw failure;
        } catch (RuntimeException failure) {
            throw corrupt("CATALOG_STRUCTURE");
        }
    }

    private static <K, T> IndexSnapshot<T> parseStructuredComponent(
            byte[] encoded,
            Authority authority,
            CatalogEntry expected,
            DurableCheckpoint.Loaded<K, T> checkpoint,
            SearchSchema<T, K> schema
    ) {
        CheckedMember member = checked(encoded, COMPONENT_DOMAIN, 192, "COMPONENT");
        Cursor cursor = new Cursor(member.content());
        try {
            long magic = cursor.longValue();
            short encodingMajor = cursor.shortValue();
            short encodingMinor = cursor.shortValue();
            short liveMajor = cursor.shortValue();
            short liveMinor = cursor.shortValue();
            byte[] profile = cursor.bytes(32);
            UUID history = new UUID(cursor.longValue(), cursor.longValue());
            long sequence = cursor.longValue();
            byte[] checkpointSha = cursor.bytes(32);
            String storage = cursor.string(128, false);
            String schemaIdentity = cursor.string(128, false);
            String codec = cursor.string(128, false);
            int codecVersion = cursor.intValue();
            String generator = cursor.string(128, false);
            int generatorVersion = cursor.intValue();
            int ordinal = cursor.intValue();
            byte kind = cursor.byteValue();
            String field = cursor.string(MAX_STRING_BYTES, false);
            String analyzer = cursor.string(128, true);
            int nextDocId = cursor.intValue();
            int liveDocuments = cursor.intValue();
            if (magic != COMPONENT_MAGIC || encodingMajor != ENCODING_MAJOR
                    || encodingMinor != ENCODING_MINOR || liveMajor != 1
                    || liveMinor != 2) {
                throw incompatible("COMPONENT_FORMAT");
            }
            if (!GENERATOR_ID.equals(generator)
                    || generatorVersion != GENERATOR_VERSION) {
                throw incompatible("COMPONENT_GENERATOR");
            }
            if (!Arrays.equals(profile, authority.format().profileDigest())
                    || !history.equals(authority.history())
                    || sequence != authority.manifest().checkpointSequence()
                    || !Arrays.equals(checkpointSha, authority.checkpointSha256())
                    || !storage.equals(authority.storageIdentity())
                    || !schemaIdentity.equals(authority.schemaIdentity())
                    || !codec.equals(authority.codecIdentity())
                    || codecVersion != authority.codecVersion()
                    || nextDocId != authority.nextDocId()
                    || liveDocuments != authority.liveDocuments()) {
                throw stale("COMPONENT_CANONICAL_BINDING");
            }
            if (ordinal != expected.ordinal() || kind != expected.kind()
                    || !field.equals(expected.field())
                    || !analyzer.equals(expected.analyzer())) {
                throw stale("COMPONENT_DESCRIPTOR_BINDING");
            }
            IndexSnapshot<T> result = switch (kind) {
                case DurableIndexDescriptor.EQUALITY -> readEquality(
                        cursor, schema.requireField(field), checkpoint);
                case DurableIndexDescriptor.RANGE -> readRange(
                        cursor, schema.requireField(field), checkpoint);
                case DurableIndexDescriptor.PREFIX -> readPrefix(
                        cursor, schema.requireField(field, String.class), checkpoint);
                case DurableIndexDescriptor.TEXT -> {
                    readText(cursor, checkpoint, liveDocuments);
                    yield null;
                }
                default -> throw incompatible("COMPONENT_KIND");
            };
            cursor.requireExhausted();
            return result;
        } catch (DerivedFailure failure) {
            throw failure;
        } catch (RuntimeException failure) {
            throw corrupt("COMPONENT_STRUCTURE");
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static <K, T> IndexSnapshot<T> readEquality(
            Cursor cursor,
            Field<T, ?> field,
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) {
        int count = cursor.count(MAX_COUNT);
        Map<Object, ImmutableBitmap> values = new HashMap<>();
        Set<Integer> all = new HashSet<>();
        int indexed = 0;
        int previous = -1;
        for (int index = 0; index < count; index++) {
            int representative = cursor.intValue();
            if (representative <= previous) {
                throw corrupt("VALUE_GROUP_ORDER");
            }
            previous = representative;
            ImmutableBitmap bitmap = cursor.bitmap(checkpoint, all);
            if (!bitmap.get(representative)) {
                throw corrupt("VALUE_GROUP_REPRESENTATIVE");
            }
            Object value = field.valueOf(checkpoint.slots().get(representative));
            if (value == null || values.put(value, bitmap) != null) {
                throw corrupt("VALUE_GROUP_KEY");
            }
            indexed = Math.addExact(indexed, bitmap.cardinality());
        }
        ImmutableOverlayMap map = ImmutableOverlayMap.empty().withChanges(values, Set.of());
        return EqualityIndexSnapshot.fromValues((Field) field, map, indexed);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static <K, T> IndexSnapshot<T> readRange(
            Cursor cursor,
            Field<T, ?> field,
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) {
        int count = cursor.count(MAX_COUNT);
        PersistentAvlMap values = PersistentAvlMap.empty(
                value -> ((ImmutableBitmap) value).cardinality());
        Set<Integer> all = new HashSet<>();
        int indexed = 0;
        int previous = -1;
        for (int index = 0; index < count; index++) {
            int representative = cursor.intValue();
            if (representative <= previous) {
                throw corrupt("VALUE_GROUP_ORDER");
            }
            previous = representative;
            ImmutableBitmap bitmap = cursor.bitmap(checkpoint, all);
            if (!bitmap.get(representative)) {
                throw corrupt("VALUE_GROUP_REPRESENTATIVE");
            }
            Object value = field.valueOf(checkpoint.slots().get(representative));
            if (!(value instanceof Comparable comparable) || values.get(comparable) != null) {
                throw corrupt("VALUE_GROUP_KEY");
            }
            values = values.with(comparable, bitmap);
            indexed = Math.addExact(indexed, bitmap.cardinality());
        }
        return RangeIndexSnapshot.fromValues((Field) field, values, indexed);
    }

    private static <K, T> IndexSnapshot<T> readPrefix(
            Cursor cursor,
            Field<T, String> field,
            DurableCheckpoint.Loaded<K, T> checkpoint
    ) {
        int count = cursor.count(MAX_COUNT);
        PersistentAvlMap<String, ImmutableBitmap> values = PersistentAvlMap.empty(
                ImmutableBitmap::cardinality);
        Set<Integer> all = new HashSet<>();
        byte[] previous = null;
        int indexed = 0;
        for (int index = 0; index < count; index++) {
            byte[] encoded = cursor.stringBytes(MAX_STRING_BYTES, false);
            if (previous != null && Arrays.compareUnsigned(previous, encoded) >= 0) {
                throw corrupt("PREFIX_KEY_ORDER");
            }
            previous = encoded;
            String key = decodeUtf8(encoded);
            ImmutableBitmap bitmap = cursor.bitmap(checkpoint, all);
            values = values.with(key, bitmap);
            indexed = Math.addExact(indexed, bitmap.cardinality());
        }
        return PrefixIndexSnapshot.fromValues(field, values, indexed);
    }

    private static <K, T> void readText(
            Cursor cursor,
            DurableCheckpoint.Loaded<K, T> checkpoint,
            int liveDocuments
    ) {
        int documentCount = cursor.intValue();
        long totalFieldLength = cursor.longValue();
        if (documentCount < 0 || documentCount > liveDocuments
                || totalFieldLength < 0) {
            throw corrupt("TEXT_STATISTICS");
        }
        int lengths = cursor.count(MAX_COUNT);
        int previousDoc = -1;
        long summedLength = 0L;
        for (int index = 0; index < lengths; index++) {
            int docId = cursor.intValue();
            int length = cursor.intValue();
            if (docId <= previousDoc || docId < 0
                    || docId >= checkpoint.nextDocId()
                    || checkpoint.slots().get(docId) == null || length < 0) {
                throw corrupt("TEXT_FIELD_LENGTH_ORDER");
            }
            previousDoc = docId;
            summedLength = Math.addExact(summedLength, length);
        }
        if (lengths != documentCount || summedLength != totalFieldLength) {
            throw corrupt("TEXT_FIELD_LENGTH_TOTAL");
        }
        int terms = cursor.count(MAX_COUNT);
        byte[] previousTerm = null;
        for (int term = 0; term < terms; term++) {
            byte[] encoded = cursor.stringBytes(MAX_STRING_BYTES, false);
            if (previousTerm != null
                    && Arrays.compareUnsigned(previousTerm, encoded) >= 0) {
                throw corrupt("TEXT_TERM_ORDER");
            }
            previousTerm = encoded;
            decodeUtf8(encoded);
            int frequency = cursor.count(MAX_COUNT);
            int postings = cursor.count(MAX_COUNT);
            if (frequency != postings) {
                throw corrupt("TEXT_DOCUMENT_FREQUENCY");
            }
            previousDoc = -1;
            for (int posting = 0; posting < postings; posting++) {
                int docId = cursor.intValue();
                if (docId <= previousDoc || docId < 0
                        || docId >= checkpoint.nextDocId()
                        || checkpoint.slots().get(docId) == null) {
                    throw corrupt("TEXT_POSTING_ORDER");
                }
                previousDoc = docId;
                int positions = cursor.count(MAX_COUNT);
                int previousPosition = -1;
                for (int position = 0; position < positions; position++) {
                    int value = cursor.intValue();
                    if (value <= previousPosition || value < 0) {
                        throw corrupt("TEXT_POSITION_ORDER");
                    }
                    previousPosition = value;
                }
            }
        }
    }

    private static <K, T> byte[] encodeComponent(
            Authority authority,
            int ordinal,
            DurableIndexDescriptor descriptor,
            SearchSnapshot<T> snapshot,
            SearchSchema<T, K> schema
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            writeComponentHeader(output, authority, ordinal, descriptor);
            switch (descriptor.kind()) {
                case DurableIndexDescriptor.EQUALITY -> writeEquality(
                        output, schema.requireField(descriptor.fieldName()), snapshot);
                case DurableIndexDescriptor.RANGE -> writeRange(
                        output, schema.requireField(descriptor.fieldName()), snapshot);
                case DurableIndexDescriptor.PREFIX -> writePrefix(
                        output, schema.requireField(
                                descriptor.fieldName(), String.class), snapshot);
                default -> throw new IOException("text images belong to Phase 4");
            }
        }
        return finishMember(bytes.toByteArray(), COMPONENT_DOMAIN);
    }

    private static void writeComponentHeader(
            DataOutputStream output,
            Authority authority,
            int ordinal,
            DurableIndexDescriptor descriptor
    ) throws IOException {
        output.writeLong(COMPONENT_MAGIC);
        output.writeShort(ENCODING_MAJOR);
        output.writeShort(ENCODING_MINOR);
        output.writeShort(DurableFormatContext.MAJOR);
        output.writeShort(authority.format().minor());
        output.write(authority.format().profileDigest());
        output.writeLong(authority.history().getMostSignificantBits());
        output.writeLong(authority.history().getLeastSignificantBits());
        output.writeLong(authority.manifest().checkpointSequence());
        output.write(authority.checkpointSha256());
        writeString(output, authority.storageIdentity());
        writeString(output, authority.schemaIdentity());
        writeString(output, authority.codecIdentity());
        output.writeInt(authority.codecVersion());
        writeString(output, GENERATOR_ID);
        output.writeInt(GENERATOR_VERSION);
        output.writeInt(ordinal);
        output.writeByte(descriptor.kind());
        writeString(output, descriptor.fieldName());
        writeString(output, descriptor.analyzerId());
        output.writeInt(authority.nextDocId());
        output.writeInt(authority.liveDocuments());
    }

    private static <T> void writeEquality(
            DataOutputStream output,
            Field<T, ?> field,
            SearchSnapshot<T> snapshot
    ) throws IOException {
        Map<Object, Group> grouped = new HashMap<>();
        forEachDocument(snapshot, (docId, document) -> {
            Object value = field.valueOf(document);
            if (value != null) {
                grouped.computeIfAbsent(value, ignored -> new Group(docId)).add(docId);
            }
        });
        writeGroups(output, grouped.values());
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static <T> void writeRange(
            DataOutputStream output,
            Field<T, ?> field,
            SearchSnapshot<T> snapshot
    ) throws IOException {
        TreeMap<Comparable, Group> grouped = new TreeMap<>();
        forEachDocument(snapshot, (docId, document) -> {
            Object value = field.valueOf(document);
            if (value != null) {
                if (!(value instanceof Comparable comparable)) {
                    throw new IllegalArgumentException("range value is not comparable");
                }
                grouped.computeIfAbsent(comparable, ignored -> new Group(docId)).add(docId);
            }
        });
        writeGroups(output, grouped.values());
    }

    private static <T> void writePrefix(
            DataOutputStream output,
            Field<T, String> field,
            SearchSnapshot<T> snapshot
    ) throws IOException {
        TreeMap<byte[], PrefixGroup> grouped = new TreeMap<>(Arrays::compareUnsigned);
        forEachDocument(snapshot, (docId, document) -> {
            String value = field.valueOf(document);
            if (value != null) {
                byte[] encoded = strictUtf8(value);
                grouped.computeIfAbsent(encoded,
                        ignored -> new PrefixGroup(value)).add(docId);
            }
        });
        output.writeInt(grouped.size());
        for (PrefixGroup group : grouped.values()) {
            writeString(output, group.value());
            writeBitmap(output, group.bitmap());
        }
    }

    private static void writeGroups(
            DataOutputStream output,
            java.util.Collection<Group> groups
    ) throws IOException {
        List<Group> ordered = groups.stream()
                .sorted(Comparator.comparingInt(Group::representative)).toList();
        output.writeInt(ordered.size());
        for (Group group : ordered) {
            output.writeInt(group.representative());
            writeBitmap(output, group.bitmap());
        }
    }

    private static void writeBitmap(
            DataOutputStream output,
            ImmutableBitmapBuilder builder
    ) throws IOException {
        ImmutableBitmap bitmap = builder.build();
        output.writeInt(bitmap.cardinality());
        try {
            bitmap.forEachSetBit(value -> {
                try {
                    output.writeInt(value);
                } catch (IOException failure) {
                    throw new WriteFailure(failure);
                }
            });
        } catch (WriteFailure failure) {
            throw failure.ioFailure();
        }
    }

    private static <T> void forEachDocument(
            SearchSnapshot<T> snapshot,
            DocumentConsumer<T> consumer
    ) {
        snapshot.activeDocuments().forEachSetBit(
                docId -> consumer.accept(docId, snapshot.get(docId)));
    }

    private static byte[] encodeCatalog(
            Authority authority,
            List<EncodedComponent> components
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(CATALOG_MAGIC);
            output.writeShort(ENCODING_MAJOR);
            output.writeShort(ENCODING_MINOR);
            output.writeShort(DurableFormatContext.MAJOR);
            output.writeShort(authority.format().minor());
            output.write(authority.format().profileDigest());
            output.writeLong(authority.history().getMostSignificantBits());
            output.writeLong(authority.history().getLeastSignificantBits());
            output.writeLong(authority.manifest().checkpointSequence());
            writeString(output, authority.manifest().checkpointFile());
            output.writeLong(authority.manifest().checkpointBytes());
            output.writeInt(authority.manifest().checkpointChecksum());
            output.write(authority.checkpointSha256());
            writeString(output, authority.storageIdentity());
            writeString(output, authority.schemaIdentity());
            writeString(output, authority.codecIdentity());
            output.writeInt(authority.codecVersion());
            writeString(output, GENERATOR_ID);
            output.writeInt(GENERATOR_VERSION);
            output.writeInt(authority.nextDocId());
            output.writeInt(authority.liveDocuments());
            output.writeInt(components.size());
            for (EncodedComponent component : components) {
                output.writeInt(component.ordinal());
                output.writeByte(component.descriptor().kind());
                writeString(output, component.descriptor().fieldName());
                writeString(output, component.descriptor().analyzerId());
                writeString(output, component.filename());
                output.writeLong(component.bytes().length);
                output.writeInt(component.checksum());
                output.write(component.sha256());
            }
        }
        return finishMember(bytes.toByteArray(), CATALOG_DOMAIN);
    }

    private static byte[] finishMember(byte[] content, byte[] domain)
            throws IOException {
        ByteArrayOutputStream complete = new ByteArrayOutputStream(
                Math.addExact(content.length, 36));
        complete.write(content);
        MessageDigest digest = sha256();
        digest.update(domain);
        digest.update(content);
        complete.write(digest.digest());
        CRC32C checksum = new CRC32C();
        checksum.update(complete.toByteArray());
        try (DataOutputStream output = new DataOutputStream(complete)) {
            output.writeInt((int) checksum.getValue());
        }
        return complete.toByteArray();
    }

    private static CheckedMember checked(
            byte[] encoded,
            byte[] domain,
            int minimum,
            String member
    ) {
        if (encoded.length < minimum) {
            throw incomplete(member + "_TRUNCATED");
        }
        int contentLength = encoded.length - 36;
        int storedChecksum = ByteBuffer.wrap(encoded,
                encoded.length - 4, 4).order(ByteOrder.BIG_ENDIAN).getInt();
        CRC32C checksum = new CRC32C();
        checksum.update(encoded, 0, encoded.length - 4);
        if ((int) checksum.getValue() != storedChecksum) {
            throw corrupt(member + "_CRC32C");
        }
        MessageDigest digest = sha256();
        digest.update(domain);
        digest.update(encoded, 0, contentLength);
        if (!Arrays.equals(digest.digest(), Arrays.copyOfRange(
                encoded, contentLength, contentLength + 32))) {
            throw corrupt(member + "_IDENTITY");
        }
        return new CheckedMember(Arrays.copyOf(encoded, contentLength));
    }

    private static void requireWholeMember(CatalogEntry entry, byte[] encoded) {
        if (entry.bytes() != encoded.length
                || entry.checksum() != trailingChecksum(encoded)
                || !Arrays.equals(entry.sha256(), sha256(encoded))) {
            throw corrupt("COMPONENT_CATALOG_BINDING");
        }
    }

    private static byte[] readBounded(Path path, long maximum) throws IOException {
        if (Files.isSymbolicLink(path)
                || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("derived member is absent or not regular");
        }
        long size = Files.size(path);
        if (size < 0 || size > maximum || size > Integer.MAX_VALUE - 8L) {
            throw new IOException("derived member size is outside its bound");
        }
        return Files.readAllBytes(path);
    }

    private static void writeForced(
            Path path,
            byte[] encoded,
            String partialBarrier
    ) throws IOException {
        try (var channel = java.nio.channels.FileChannel.open(path,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            int split = Math.max(1, encoded.length / 2);
            writeFully(channel, ByteBuffer.wrap(encoded, 0, split));
            DurableCrashHooks.reach(partialBarrier);
            writeFully(channel, ByteBuffer.wrap(encoded, split,
                    encoded.length - split));
            channel.force(true);
        }
    }

    private static void writeFully(
            java.nio.channels.FileChannel channel,
            ByteBuffer bytes
    ) throws IOException {
        while (bytes.hasRemaining()) {
            if (DurableIoFaults.write(channel, bytes) <= 0) {
                throw new IOException("derived write made no progress");
            }
        }
    }

    private static void moveAtomic(Path source, Path target, boolean replace)
            throws IOException {
        try {
            if (replace) {
                Files.move(source, target, StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
            } else {
                Files.move(source, target, StandardCopyOption.ATOMIC_MOVE);
            }
        } catch (AtomicMoveNotSupportedException failure) {
            throw new IOException("derived publication requires atomic rename", failure);
        }
    }

    private static int trailingChecksum(byte[] encoded) {
        if (encoded.length < 4) {
            throw corrupt("COMPONENT_TRUNCATED");
        }
        return ByteBuffer.wrap(encoded, encoded.length - 4, 4)
                .order(ByteOrder.BIG_ENDIAN).getInt();
    }

    private static byte[] sha256(Path path) throws IOException {
        MessageDigest digest = sha256();
        try (var input = Files.newInputStream(path)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read > 0) {
                    digest.update(buffer, 0, read);
                }
            }
        }
        return digest.digest();
    }

    private static byte[] sha256(byte[] bytes) {
        return sha256().digest(bytes);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static byte[] ascii(String value) {
        return value.getBytes(StandardCharsets.US_ASCII);
    }

    private static byte[] strictUtf8(String value) {
        try {
            ByteBuffer encoded = StandardCharsets.UTF_8.newEncoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .encode(CharBuffer.wrap(value));
            byte[] result = new byte[encoded.remaining()];
            encoded.get(result);
            if (result.length > MAX_STRING_BYTES) {
                throw new IllegalArgumentException("UTF-8 value exceeds its bound");
            }
            return result;
        } catch (CharacterCodingException failure) {
            throw new IllegalArgumentException("value is not strict UTF-8", failure);
        }
    }

    private static String decodeUtf8(byte[] value) {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(value)).toString();
        } catch (CharacterCodingException failure) {
            throw corrupt("INVALID_UTF8");
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = strictUtf8(value);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private static boolean validDescriptor(byte kind, String field, String analyzer) {
        return kind >= DurableIndexDescriptor.EQUALITY
                && kind <= DurableIndexDescriptor.TEXT
                && !field.isEmpty()
                && ((kind == DurableIndexDescriptor.TEXT
                        && DurableIndexDescriptor.SIMPLE_ANALYZER.equals(analyzer))
                        || (kind != DurableIndexDescriptor.TEXT && analyzer.isEmpty()));
    }

    private static Duration elapsed(long started) {
        return Duration.ofNanos(Math.max(0L, System.nanoTime() - started));
    }

    private static DerivedFailure stale(String code) {
        return new DerivedFailure(DurableDerivedStateStatus.STALE, code);
    }

    private static DerivedFailure incompatible(String code) {
        return new DerivedFailure(DurableDerivedStateStatus.INCOMPATIBLE, code);
    }

    private static DerivedFailure incomplete(String code) {
        return new DerivedFailure(DurableDerivedStateStatus.INCOMPLETE, code);
    }

    private static DerivedFailure corrupt(String code) {
        return new DerivedFailure(DurableDerivedStateStatus.CORRUPT, code);
    }

    record LoadResult<T>(
            SearchSnapshot<T> checkpointSnapshot,
            DurableDerivedStateStatus status,
            DurableReopenOutcome outcome,
            int loadedComponents,
            int rebuiltComponents,
            List<DurableReopenRejection> rejections,
            Duration inspectionDuration,
            Duration loadDuration,
            Duration rebuildDuration,
            long bytesRead
    ) {
        LoadResult {
            Objects.requireNonNull(checkpointSnapshot, "checkpointSnapshot");
            Objects.requireNonNull(status, "status");
            Objects.requireNonNull(outcome, "outcome");
            rejections = List.copyOf(rejections);
        }
    }

    record RefreshResult(
            boolean attempted,
            boolean succeeded,
            Duration duration,
            long bytesWritten
    ) {
    }

    private record Authority(
            DurableFormatContext format,
            UUID history,
            DurableCheckpoint.Manifest manifest,
            byte[] checkpointSha256,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            int nextDocId,
            int liveDocuments,
            List<DurableIndexDescriptor> descriptors
    ) {
        private Authority {
            checkpointSha256 = checkpointSha256.clone();
            descriptors = List.copyOf(descriptors);
        }

        @Override
        public byte[] checkpointSha256() {
            return checkpointSha256.clone();
        }
    }

    private record Catalog(List<CatalogEntry> entries) {
        private Catalog {
            entries = List.copyOf(entries);
        }
    }

    private record CatalogEntry(
            int ordinal,
            byte kind,
            String field,
            String analyzer,
            String filename,
            long bytes,
            int checksum,
            byte[] sha256
    ) {
        private CatalogEntry {
            sha256 = sha256.clone();
        }

        @Override
        public byte[] sha256() {
            return sha256.clone();
        }
    }

    private record EncodedComponent(
            int ordinal,
            DurableIndexDescriptor descriptor,
            String filename,
            byte[] bytes,
            int checksum,
            byte[] sha256
    ) {
    }

    private record CheckedMember(byte[] content) {
    }

    private static final class Cursor {
        private final ByteBuffer bytes;

        private Cursor(byte[] bytes) {
            this.bytes = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        }

        private byte byteValue() {
            require(Byte.BYTES);
            return bytes.get();
        }

        private short shortValue() {
            require(Short.BYTES);
            return bytes.getShort();
        }

        private int intValue() {
            require(Integer.BYTES);
            return bytes.getInt();
        }

        private long longValue() {
            require(Long.BYTES);
            return bytes.getLong();
        }

        private int count(int maximum) {
            int value = intValue();
            if (value < 0 || value > maximum) {
                throw corrupt("COUNT_BOUND");
            }
            return value;
        }

        private byte[] bytes(int length) {
            require(length);
            byte[] value = new byte[length];
            bytes.get(value);
            return value;
        }

        private byte[] stringBytes(int maximum, boolean allowEmpty) {
            int length = intValue();
            if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
                throw corrupt("STRING_BOUND");
            }
            return bytes(length);
        }

        private String string(int maximum, boolean allowEmpty) {
            return decodeUtf8(stringBytes(maximum, allowEmpty));
        }

        private <K, T> ImmutableBitmap bitmap(
                DurableCheckpoint.Loaded<K, T> checkpoint,
                Set<Integer> all
        ) {
            int count = count(MAX_COUNT);
            ImmutableBitmapBuilder builder = new ImmutableBitmapBuilder(
                    ImmutableBitmap.empty());
            int previous = -1;
            for (int index = 0; index < count; index++) {
                int docId = intValue();
                if (docId <= previous || docId < 0
                        || docId >= checkpoint.nextDocId()
                        || checkpoint.slots().get(docId) == null
                        || !all.add(docId)) {
                    throw corrupt("BITMAP_ORDER");
                }
                previous = docId;
                builder.set(docId);
            }
            return builder.build();
        }

        private void requireExhausted() {
            if (bytes.hasRemaining()) {
                throw corrupt("TRAILING_BYTES");
            }
        }

        private void require(int length) {
            if (length < 0 || length > bytes.remaining()) {
                throw incomplete("MEMBER_TRUNCATED");
            }
        }
    }

    private static class Group {
        private final int representative;
        private final ImmutableBitmapBuilder bitmap = new ImmutableBitmapBuilder(
                ImmutableBitmap.empty());

        private Group(int representative) {
            this.representative = representative;
        }

        void add(int docId) {
            bitmap.set(docId);
        }

        private int representative() {
            return representative;
        }

        ImmutableBitmapBuilder bitmap() {
            return bitmap;
        }
    }

    private static final class PrefixGroup extends Group {
        private final String value;

        private PrefixGroup(String value) {
            super(Integer.MAX_VALUE);
            this.value = value;
        }

        private String value() {
            return value;
        }
    }

    private static final class DerivedFailure extends RuntimeException {
        private final DurableDerivedStateStatus status;
        private final String code;

        private DerivedFailure(DurableDerivedStateStatus status, String code) {
            this.status = status;
            this.code = code;
        }

        private DurableDerivedStateStatus status() {
            return status;
        }

        private String code() {
            return code;
        }
    }

    private static final class WriteFailure extends RuntimeException {
        private final IOException ioFailure;

        private WriteFailure(IOException ioFailure) {
            this.ioFailure = ioFailure;
        }

        private IOException ioFailure() {
            return ioFailure;
        }
    }

    @FunctionalInterface
    private interface DocumentConsumer<T> {
        void accept(int docId, T document);
    }
}
