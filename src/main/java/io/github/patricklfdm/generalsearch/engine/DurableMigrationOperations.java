package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationException;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationIndexChange;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationSourceMember;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationStage;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;

/** Internal Phase 3 format-only migration planner and publisher. */
final class DurableMigrationOperations {
    private static final byte[] SOURCE_DOMAIN =
            "gse-migration-source-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] DESCRIPTOR_DOMAIN =
            "gse-migration-descriptor-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] PROJECTION_DOMAIN =
            "gse-migration-projection-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] PLAN_DOMAIN =
            "gse-migration-plan-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final long WAL_GENERATION = 2L;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");

    private DurableMigrationOperations() {
    }

    static <SK, ST, TK, TT> DurableMigrationPlan plan(
            SearchSchema<ST, SK> sourceSchema,
            List<IndexDefinition<ST>> sourceDefinitions,
            SearchSchema<TT, TK> targetSchema,
            List<IndexDefinition<TT>> targetDefinitions,
            DurableMigrationRequest<SK, ST, TK, TT> request
    ) {
        UUID targetHistory = freshHistory(null);
        try (Observation<SK, ST, TK, TT> observation = observe(
                sourceSchema, sourceDefinitions, targetSchema,
                targetDefinitions, request, targetHistory)) {
            return observation.plan();
        }
    }

    static <SK, ST, TK, TT> DurableMigrationResult apply(
            SearchSchema<ST, SK> sourceSchema,
            List<IndexDefinition<ST>> sourceDefinitions,
            SearchSchema<TT, TK> targetSchema,
            List<IndexDefinition<TT>> targetDefinitions,
            SnapshotEngineConfig engineConfig,
            DurableMigrationRequest<SK, ST, TK, TT> request,
            DurableMigrationPlan plan
    ) {
        Objects.requireNonNull(plan, "plan");
        try (Observation<SK, ST, TK, TT> observation = observe(
                sourceSchema, sourceDefinitions, targetSchema,
                targetDefinitions, request, plan.targetHistory())) {
            DurableMigrationPlan current = observation.plan();
            if (!current.equals(plan)) {
                DurableMigrationException.Reason reason =
                        otherwiseEqualExceptProjection(current, plan)
                                ? DurableMigrationException.Reason
                                        .TRANSFORM_NONDETERMINISTIC
                                : DurableMigrationException.Reason.PLAN_STALE;
                throw failure(reason, DurableMigrationStage.VERIFY_SOURCE,
                        OptionalLong.of(observation.sequence()), null);
            }
            return publish(observation, targetSchema, targetDefinitions,
                    engineConfig, request, plan);
        }
    }

    private static <SK, ST, TK, TT> Observation<SK, ST, TK, TT> observe(
            SearchSchema<ST, SK> sourceSchema,
            List<IndexDefinition<ST>> sourceDefinitions,
            SearchSchema<TT, TK> targetSchema,
            List<IndexDefinition<TT>> targetDefinitions,
            DurableMigrationRequest<SK, ST, TK, TT> request,
            UUID targetHistory
    ) {
        Objects.requireNonNull(sourceSchema, "sourceSchema");
        Objects.requireNonNull(sourceDefinitions, "sourceDefinitions");
        Objects.requireNonNull(targetSchema, "targetSchema");
        Objects.requireNonNull(targetDefinitions, "targetDefinitions");
        Objects.requireNonNull(request, "request");
        Path source = request.sourceDirectory();
        Target target = validatePaths(source, request.targetConfig().directory());
        validateEdge(request);

        DurableVerificationReport structural;
        try {
            structural = DurableStorageOperations.verifyStore(source);
        } catch (DurableOperationException problem) {
            DurableMigrationException.Reason reason = problem.reason()
                    == DurableOperationException.Reason.STORAGE_IN_USE
                    ? DurableMigrationException.Reason.STORAGE_IN_USE
                    : DurableMigrationException.Reason.SOURCE_INVALID;
            throw failure(reason, DurableMigrationStage.ACQUIRE_SOURCE,
                    problem.sequence(), problem);
        }
        if (structural.status() != DurableVerificationStatus.VALID) {
            throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                    DurableMigrationStage.VERIFY_SOURCE,
                    structural.sequence(), null);
        }
        if (structural.authoritativeBytes()
                > request.maxSourceAuthoritativeBytes()) {
            throw failure(DurableMigrationException.Reason.CAPACITY_EXCEEDED,
                    DurableMigrationStage.VALIDATE_CAPACITY,
                    structural.sequence(), null);
        }

        DurableStorageOwner.Metadata metadata;
        try {
            metadata = DurableStorageOwner.readMetadata(
                    source.resolve(DurableStorageOwner.METADATA_FILE));
        } catch (IOException | RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                    DurableMigrationStage.VERIFY_SOURCE,
                    structural.sequence(), problem);
        }
        List<DurableIndexDescriptor> sourceIndexes = descriptors(sourceDefinitions);
        List<DurableIndexDescriptor> targetIndexes = descriptors(targetDefinitions);
        validateFormatOnlyIdentities(metadata, sourceIndexes, targetIndexes,
                request);
        DurableStorageConfig<SK, ST> sourceStorage = sourceStorage(
                source, metadata, request);

        DurableStorageOwner.OpenResult opened;
        try {
            opened = DurableStorageOwner.open(sourceStorage,
                    metadata.codecId(), metadata.codecVersion(), sourceIndexes);
        } catch (DurabilityException problem) {
            DurableMigrationException.Reason reason = problem.reason()
                    == DurabilityException.Reason.STORAGE_IN_USE
                    ? DurableMigrationException.Reason.STORAGE_IN_USE
                    : DurableMigrationException.Reason.SOURCE_INVALID;
            throw failure(reason, DurableMigrationStage.ACQUIRE_SOURCE,
                    structural.sequence(), problem);
        }

        boolean success = false;
        try {
            DurableCheckpoint.Manifest manifest = opened.manifest();
            DurableWal wal = opened.owner().wal();
            if (opened.fresh() || manifest == null
                    || opened.wals().size() != 1
                    || opened.truncatedBytes() != 0
                    || wal.records() != 0
                    || wal.position() != metadata.format().walHeaderBytes()
                    || wal.firstSequence() != manifest.walFirstSequence()
                    || manifest.checkpointSequence() == Long.MAX_VALUE) {
                throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                        DurableMigrationStage.VERIFY_SOURCE,
                        structural.sequence(), null);
            }
            DurableCheckpoint.Loaded<SK, ST> loaded = DurableCheckpoint.read(
                    source.resolve(manifest.checkpointFile()), sourceStorage,
                    sourceSchema, metadata.format(), metadata.historyId(), manifest);
            if (loaded.sequence() != manifest.checkpointSequence()
                    || loaded.indexes().equals(sourceIndexes) == false) {
                throw failure(DurableMigrationException.Reason.IDENTITY_MISMATCH,
                        DurableMigrationStage.VERIFY_SOURCE,
                        OptionalLong.of(loaded.sequence()), null);
            }
            List<DurableMigrationSourceMember> members = sourceMembers(
                    source, metadata, wal.generation());
            long sourceBytes = members.stream()
                    .mapToLong(DurableMigrationSourceMember::size)
                    .reduce(0L, Math::addExact);
            if (sourceBytes != structural.authoritativeBytes()
                    || sourceBytes > request.maxSourceAuthoritativeBytes()) {
                throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                        DurableMigrationStage.VERIFY_SOURCE,
                        OptionalLong.of(loaded.sequence()), null);
            }
            String sourceIdentity = sourceAuthorityIdentity(
                    metadata, loaded, members);
            Projection<TK, TT> projection = project(
                    loaded, sourceStorage, sourceSchema, targetSchema,
                    request.targetConfig(), targetDefinitions, request,
                    targetHistory);
            long targetBytes = targetAuthoritativeBytes(
                    projection, targetSchema, targetIndexes,
                    request.targetConfig(), targetHistory, loaded.sequence());
            long peakBytes = Math.addExact(
                    targetBytes, request.capacitySafetyReserveBytes());
            if (targetBytes > request.maxTargetAuthoritativeBytes()
                    || targetBytes > request.targetConfig().maxRetainedBytes()
                    || peakBytes > Files.getFileStore(target.parent()).getUsableSpace()) {
                throw failure(DurableMigrationException.Reason.CAPACITY_EXCEEDED,
                        DurableMigrationStage.VALIDATE_CAPACITY,
                        OptionalLong.of(loaded.sequence()), null);
            }
            String sourceDescriptor = descriptorDigest(
                    metadata.format().publicFormat(), metadata.storageIdentity(),
                    metadata.schemaIdentity(), metadata.codecId(),
                    metadata.codecVersion(), metadata.maxKeyBytes(),
                    metadata.maxDocumentBytes(), metadata.maxDocuments(), sourceIndexes);
            String targetDescriptor = descriptorDigest(
                    request.targetConfig().format(),
                    request.targetConfig().storageIdentity(),
                    request.targetConfig().schemaIdentity(),
                    request.targetConfig().codec().codecId(),
                    request.targetConfig().codec().codecVersion(),
                    request.targetConfig().maxEncodedKeyBytes(),
                    request.targetConfig().maxEncodedDocumentBytes(),
                    request.targetConfig().maxDocuments(), targetIndexes);
            List<String> retained = indexStrings(sourceIndexes).stream()
                    .sorted().toList();
            DurableMigrationIndexChange change =
                    new DurableMigrationIndexChange(List.of(), List.of(), retained);
            String planDigest = planDigest(
                    source, target.target(), metadata, targetHistory,
                    loaded, members, sourceIdentity, sourceDescriptor,
                    targetDescriptor, request, targetIndexes, change,
                    targetBytes, peakBytes, projection.digest());
            DurableMigrationPlan result = new DurableMigrationPlan(
                    1, source, target.target(), metadata.format().publicFormat(),
                    request.targetConfig().format(), metadata.historyId(),
                    targetHistory, loaded.sequence(), loaded.nextDocId(), members,
                    sourceIdentity, sourceDescriptor, targetDescriptor,
                    request.transformDescriptor(), loaded.documentIds().size(),
                    sourceIndexes.size(), targetIndexes.size(), change,
                    targetBytes, peakBytes, request.capacitySafetyReserveBytes(),
                    projection.digest(), planDigest);
            success = true;
            return new Observation<>(opened.owner(), metadata, loaded,
                    projection, result, target);
        } catch (DurableMigrationException problem) {
            throw problem;
        } catch (IOException | RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                    DurableMigrationStage.VERIFY_SOURCE,
                    structural.sequence(), problem);
        } finally {
            if (!success) {
                opened.owner().close();
            }
        }
    }

    private static void validateEdge(DurableMigrationRequest<?, ?, ?, ?> request) {
        DurableStorageFormat target = request.targetConfig().format();
        if (!target.equals(DurableStorageFormat.V1_1)) {
            throw failure(DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
        if (!request.transformDescriptor().identifier().equals("identity-format-v1")
                || request.transformDescriptor().version() != 1) {
            throw failure(DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
    }

    private static <SK, ST, TK, TT> void validateFormatOnlyIdentities(
            DurableStorageOwner.Metadata metadata,
            List<DurableIndexDescriptor> sourceIndexes,
            List<DurableIndexDescriptor> targetIndexes,
            DurableMigrationRequest<SK, ST, TK, TT> request
    ) {
        DurableStorageConfig<TK, TT> target = request.targetConfig();
        String sourceCodec;
        int sourceCodecVersion;
        String targetCodec;
        int targetCodecVersion;
        try {
            sourceCodec = request.sourceConfig().codec().codecId();
            sourceCodecVersion = request.sourceConfig().codec().codecVersion();
            targetCodec = target.codec().codecId();
            targetCodecVersion = target.codec().codecVersion();
        } catch (RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.IDENTITY_MISMATCH,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), problem);
        }
        if (!metadata.format().publicFormat().equals(DurableStorageFormat.V1_0)) {
            DurableMigrationException.Reason reason = metadata.format()
                    .publicFormat().equals(DurableStorageFormat.V1_1)
                    ? DurableMigrationException.Reason.MIGRATION_NOT_REQUIRED
                    : DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED;
            throw failure(reason, DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
        if (!metadata.storageIdentity().equals(request.sourceConfig().storageIdentity())
                || !metadata.schemaIdentity().equals(request.sourceConfig().schemaIdentity())
                || !metadata.codecId().equals(sourceCodec)
                || metadata.codecVersion() != request.sourceConfig().codecVersion()
                || sourceCodecVersion != request.sourceConfig().codecVersion()
                || metadata.maxKeyBytes()
                        != request.sourceConfig().maxEncodedKeyBytes()
                || metadata.maxDocumentBytes()
                        != request.sourceConfig().maxEncodedDocumentBytes()
                || metadata.maxDocuments() != request.sourceConfig().maxDocuments()
                || !metadata.storageIdentity().equals(target.storageIdentity())
                || !metadata.schemaIdentity().equals(target.schemaIdentity())
                || !metadata.codecId().equals(targetCodec)
                || metadata.codecVersion() != targetCodecVersion
                || metadata.maxKeyBytes() != target.maxEncodedKeyBytes()
                || metadata.maxDocumentBytes() != target.maxEncodedDocumentBytes()
                || metadata.maxDocuments() != target.maxDocuments()
                || !metadata.indexes().equals(sourceIndexes)
                || !sourceIndexes.equals(targetIndexes)) {
            throw failure(DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
    }

    private static <SK, ST, TK, TT> Projection<TK, TT> project(
            DurableCheckpoint.Loaded<SK, ST> loaded,
            DurableStorageConfig<SK, ST> sourceConfig,
            SearchSchema<ST, SK> sourceSchema,
            SearchSchema<TT, TK> targetSchema,
            DurableStorageConfig<TK, TT> targetConfig,
            List<IndexDefinition<TT>> targetDefinitions,
            DurableMigrationRequest<SK, ST, TK, TT> request,
            UUID targetHistory
    ) {
        if (loaded.documentIds().size() > request.maxCollisionEntries()) {
            throw failure(DurableMigrationException.Reason.CAPACITY_EXCEEDED,
                    DurableMigrationStage.PROJECT_TARGET,
                    OptionalLong.of(loaded.sequence()), null);
        }
        ArrayList<TT> slots = new ArrayList<>(loaded.nextDocId());
        HashMap<TK, Integer> ids = new HashMap<>();
        HashSet<String> encodedKeys = new HashSet<>();
        ArrayList<EncodedRecord> encoded = new ArrayList<>();
        MessageDigest digest = digest(PROJECTION_DOMAIN);
        update(digest, targetHistory);
        update(digest, loaded.sequence());
        update(digest, loaded.nextDocId());
        for (int slot = 0; slot < loaded.nextDocId(); slot++) {
            ST sourceDocument = loaded.slots().get(slot);
            if (sourceDocument == null) {
                slots.add(null);
                update(digest, slot);
                update(digest, 0);
                continue;
            }
            SK sourceKey;
            DurableMigrationRecord<TK, TT> transformed;
            try {
                sourceKey = sourceSchema.idOf(sourceDocument);
                transformed = Objects.requireNonNull(
                        request.transform().transform(sourceKey, sourceDocument));
            } catch (RuntimeException problem) {
                throw failure(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                        DurableMigrationStage.PROJECT_TARGET,
                        OptionalLong.of(loaded.sequence()), problem);
            }
            TK key = transformed.key();
            TT document = transformed.document();
            byte[] sourceKeyBytes = canonicalKey(sourceConfig, sourceKey);
            byte[] sourceDocumentBytes = canonicalDocument(
                    sourceConfig, sourceSchema, sourceKey, sourceDocument);
            byte[] targetKeyBytes = canonicalKey(targetConfig, key);
            byte[] targetDocumentBytes = canonicalDocument(
                    targetConfig, targetSchema, key, document);
            if (!Arrays.equals(sourceKeyBytes, targetKeyBytes)
                    || !Arrays.equals(sourceDocumentBytes, targetDocumentBytes)) {
                throw failure(
                        DurableMigrationException.Reason.MIGRATION_PATH_UNSUPPORTED,
                        DurableMigrationStage.PROJECT_TARGET,
                        OptionalLong.of(loaded.sequence()), null);
            }
            String keyDigest = HexFormat.of().formatHex(
                    digestBytes(targetKeyBytes));
            if (ids.put(key, slot) != null || !encodedKeys.add(keyDigest)) {
                throw failure(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                        DurableMigrationStage.PROJECT_TARGET,
                        OptionalLong.of(loaded.sequence()), null);
            }
            slots.add(document);
            encoded.add(new EncodedRecord(slot, targetKeyBytes, targetDocumentBytes));
            update(digest, slot);
            update(digest, 1);
            update(digest, targetKeyBytes);
            update(digest, targetDocumentBytes);
        }
        if (ids.size() != loaded.documentIds().size()) {
            throw failure(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                    DurableMigrationStage.PROJECT_TARGET,
                    OptionalLong.of(loaded.sequence()), null);
        }
        return new Projection<>(java.util.Collections.unmodifiableList(slots), Map.copyOf(ids),
                List.copyOf(encoded),
                "gse-migration-projection-v1-"
                        + HexFormat.of().formatHex(digest.digest()));
    }

    private static <K, T> DurableMigrationResult publish(
            Observation<?, ?, K, T> observation,
            SearchSchema<T, K> schema,
            List<IndexDefinition<T>> targetDefinitions,
            SnapshotEngineConfig engineConfig,
            DurableMigrationRequest<?, ?, K, T> request,
            DurableMigrationPlan plan
    ) {
        Path target = plan.targetDirectory();
        Path parent = target.getParent();
        String compact = UUID.randomUUID().toString().replace("-", "");
        Path staging = parent.resolve(".gse-v42-migration-" + compact + ".staging");
        Path marker = parent.resolve(".gse-v42-migration-" + compact + ".operation");
        boolean published = false;
        boolean markerCreated = false;
        boolean stagingCreated = false;
        Throwable primary = null;
        try {
            if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
                throw failure(DurableMigrationException.Reason.TARGET_EXISTS,
                        DurableMigrationStage.PREPARE_TARGET,
                        OptionalLong.of(plan.sourceSequence()), null);
            }
            try (FileChannel channel = FileChannel.open(marker,
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
                 FileLock ignored = acquireMarker(channel, plan.sourceSequence())) {
                markerCreated = true;
                writeFully(channel, ByteBuffer.wrap(plan.planDigest()
                        .getBytes(StandardCharsets.US_ASCII)));
                channel.force(true);
                DurableStorageOwner.forceDirectory(parent);
                DurableCrashHooks.reach("v42-migration-after-marker-force-v1");

                Files.createDirectory(staging);
                stagingCreated = true;
                DurableStorageOwner.forceDirectory(parent);
                createLock(staging.resolve(DurableStorageOwner.LOCK_FILE));
                writeTarget(staging, observation, schema, targetDefinitions,
                        request.targetConfig(), plan);
                DurableCrashHooks.reach("v42-migration-before-final-rename-v1");
                if (!sourceMembers(plan.sourceDirectory(), observation.metadata(),
                        observation.owner().wal().generation())
                        .equals(plan.sourceMembers())) {
                    throw failure(DurableMigrationException.Reason.PLAN_STALE,
                            DurableMigrationStage.VERIFY_SOURCE_PRESERVED,
                            OptionalLong.of(plan.sourceSequence()), null);
                }
                Files.move(staging, target, StandardCopyOption.ATOMIC_MOVE);
                published = true;
                DurableCrashHooks.reach("v42-migration-after-final-rename-v1");
                DurableStorageOwner.forceDirectory(parent);
                DurableCrashHooks.reach("v42-migration-after-parent-force-v1");
            }
            DurableVerificationReport completed = requireTarget(
                    target, plan.sourceSequence());
            validateTarget(target, schema, targetDefinitions,
                    request.targetConfig(), plan, observation.projection());
            try (DurableCommitCoordinator<K, T> ignored =
                         DurableCommitCoordinator.open(request.targetConfig(),
                                 engineConfig, schema, targetDefinitions)) {
                // A normal production open/close is part of successful completion.
            }
            if (!sourceMembers(plan.sourceDirectory(), observation.metadata(),
                    observation.owner().wal().generation())
                    .equals(plan.sourceMembers())) {
                throw failure(DurableMigrationException.Reason.PLAN_STALE,
                        DurableMigrationStage.VERIFY_SOURCE_PRESERVED,
                        OptionalLong.of(plan.sourceSequence()), null);
            }
            Files.delete(marker);
            markerCreated = false;
            DurableStorageOwner.forceDirectory(parent);
            return new DurableMigrationResult(
                    plan.sourceDirectory(), target, plan.sourceFormat(),
                    plan.targetFormat(), plan.sourceHistory(), plan.targetHistory(),
                    plan.sourceSequence(), plan.nextDocId(), plan.documentCount(),
                    plan.sourceAuthorityIdentity(), plan.projectionDigest(),
                    plan.planDigest(), completed.authoritativeBytes());
        } catch (DurableMigrationException problem) {
            primary = problem;
            if (published && problem.reason()
                    != DurableMigrationException.Reason.PLAN_STALE) {
                throw failure(
                        DurableMigrationException.Reason.PUBLICATION_INDETERMINATE,
                        DurableMigrationStage.VERIFY_TARGET,
                        OptionalLong.of(plan.sourceSequence()), problem);
            }
            throw problem;
        } catch (AtomicMoveNotSupportedException problem) {
            primary = problem;
            throw failure(DurableMigrationException.Reason.UNSUPPORTED_FILESYSTEM,
                    DurableMigrationStage.PUBLISH_TARGET,
                    OptionalLong.of(plan.sourceSequence()), problem);
        } catch (FileAlreadyExistsException problem) {
            primary = problem;
            throw failure(DurableMigrationException.Reason.TARGET_EXISTS,
                    DurableMigrationStage.PREPARE_TARGET,
                    OptionalLong.of(plan.sourceSequence()), problem);
        } catch (IOException | RuntimeException problem) {
            primary = problem;
            DurableMigrationException.Reason reason = published
                    ? DurableMigrationException.Reason.PUBLICATION_INDETERMINATE
                    : DurableMigrationException.Reason.IO_FAILURE;
            throw failure(reason, published
                            ? DurableMigrationStage.VERIFY_TARGET
                            : DurableMigrationStage.PREPARE_TARGET,
                    OptionalLong.of(plan.sourceSequence()), problem);
        } finally {
            if (!published) {
                cleanup(staging, marker, stagingCreated, markerCreated, primary);
            }
        }
    }

    private static <K, T> void writeTarget(
            Path staging,
            Observation<?, ?, K, T> observation,
            SearchSchema<T, K> schema,
            List<IndexDefinition<T>> definitions,
            DurableStorageConfig<K, T> config,
            DurableMigrationPlan plan
    ) throws IOException {
        List<DurableIndexDescriptor> indexes = descriptors(definitions);
        String codecId = config.codec().codecId();
        int codecVersion = config.codec().codecVersion();
        byte[] metadata = DurableStorageOwner.encodeMetadata(
                config, codecId, codecVersion, indexes, plan.targetHistory());
        DurableStorageOwner.writeMetadata(staging, metadata);
        DurableCrashHooks.reach("v42-migration-after-metadata-force-v1");

        SearchSnapshot<T> empty = new SearchSnapshot<>(definitions);
        SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(empty);
        for (int slot = 0; slot < observation.projection().slots().size(); slot++) {
            T document = observation.projection().slots().get(slot);
            if (document != null) {
                builder.add(slot, document);
            }
        }
        SearchSnapshot<T> snapshot = builder.build();
        DurableCheckpoint.Capture<K, T> capture = new DurableCheckpoint.Capture<>(
                snapshot, observation.projection().ids(),
                Math.toIntExact(plan.nextDocId()),
                plan.sourceSequence(), indexes);
        String checkpointFile = DurableCheckpoint.newCheckpointFile(
                plan.sourceSequence());
        Path checkpointStaging = staging.resolve(checkpointFile + ".staging");
        DurableCheckpoint.Written written = DurableCheckpoint.write(
                checkpointStaging, capture, config, schema,
                DurableFormatContext.V1_1, plan.targetHistory(),
                config.maxRetainedBytes());
        Files.move(checkpointStaging, staging.resolve(checkpointFile),
                StandardCopyOption.ATOMIC_MOVE);
        DurableCrashHooks.reach("v42-migration-after-checkpoint-rename-v1");

        long firstSequence = Math.addExact(plan.sourceSequence(), 1L);
        String walName = DurableStorageOwner.walFile(WAL_GENERATION);
        try (DurableWal ignored = DurableWal.create(staging.resolve(walName),
                DurableFormatContext.V1_1, plan.targetHistory(), WAL_GENERATION,
                firstSequence)) {
            // Header creation is forced by DurableWal.create.
        }
        DurableCrashHooks.reach("v42-migration-after-wal-force-v1");

        DurableCheckpoint.Manifest manifest = new DurableCheckpoint.Manifest(
                plan.sourceSequence(), checkpointFile, written.bytes(),
                written.checksum(), WAL_GENERATION, firstSequence);
        Path manifestStaging = staging.resolve(
                DurableCheckpoint.MANIFEST_STAGING_FILE);
        try (FileChannel channel = FileChannel.open(manifestStaging,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            writeFully(channel, ByteBuffer.wrap(DurableCheckpoint.encodeManifest(
                    manifest, DurableFormatContext.V1_1, plan.targetHistory())));
            channel.force(true);
        }
        Files.move(manifestStaging,
                staging.resolve(DurableCheckpoint.MANIFEST_FILE),
                StandardCopyOption.ATOMIC_MOVE);
        DurableStorageOwner.forceDirectory(staging);
        DurableCrashHooks.reach("v42-migration-after-manifest-rename-v1");
        DurableVerificationReport report = requireTarget(
                staging, plan.sourceSequence());
        if (report.authoritativeBytes() != plan.targetAuthoritativeBytes()) {
            throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                    DurableMigrationStage.VERIFY_STAGING,
                    OptionalLong.of(plan.sourceSequence()), null);
        }
        validateTarget(staging, schema, definitions, config, plan,
                observation.projection());
    }

    private static <K, T> void validateTarget(
            Path directory,
            SearchSchema<T, K> schema,
            List<IndexDefinition<T>> definitions,
            DurableStorageConfig<K, T> config,
            DurableMigrationPlan plan,
            Projection<K, T> projection
    ) throws IOException {
        List<DurableIndexDescriptor> indexes = descriptors(definitions);
        DurableStorageOwner.Metadata metadata = DurableStorageOwner.readMetadata(
                directory.resolve(DurableStorageOwner.METADATA_FILE));
        DurableStorageOwner.validateMetadata(metadata, config,
                config.codec().codecId(), config.codec().codecVersion(), indexes);
        DurableCheckpoint.Manifest manifest = DurableCheckpoint.readManifest(
                directory.resolve(DurableCheckpoint.MANIFEST_FILE),
                metadata.format(), plan.targetHistory());
        DurableCheckpoint.Loaded<K, T> loaded = DurableCheckpoint.read(
                directory.resolve(manifest.checkpointFile()), config, schema,
                metadata.format(), plan.targetHistory(), manifest);
        if (loaded.sequence() != plan.sourceSequence()
                || loaded.nextDocId() != plan.nextDocId()
                || !loaded.documentIds().equals(projection.ids())
                || loaded.documentIds().size() != plan.documentCount()
                || !loaded.slots().equals(projection.slots())) {
            throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                    DurableMigrationStage.VERIFY_TARGET,
                    OptionalLong.of(plan.sourceSequence()), null);
        }
        DurableWal.Header wal = DurableWal.inspectHeader(directory.resolve(
                DurableStorageOwner.walFile(WAL_GENERATION)), metadata.format(),
                plan.targetHistory());
        if (wal.firstSequence() != Math.addExact(plan.sourceSequence(), 1L)) {
            throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                    DurableMigrationStage.VERIFY_TARGET,
                    OptionalLong.of(plan.sourceSequence()), null);
        }
    }

    private static DurableVerificationReport requireTarget(Path directory,
                                                            long sequence) {
        DurableVerificationReport report = DurableStorageOperations.verifyStore(directory);
        if (report.status() != DurableVerificationStatus.VALID
                || report.sequence().isEmpty()
                || report.sequence().getAsLong() != sequence) {
            throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                    DurableMigrationStage.VERIFY_TARGET,
                    OptionalLong.of(sequence), null);
        }
        return report;
    }

    private static <SK, ST, TK, TT> DurableStorageConfig<SK, ST> sourceStorage(
            Path source, DurableStorageOwner.Metadata metadata,
            DurableMigrationRequest<SK, ST, TK, TT> request) {
        return DurableStorageConfig.builder(source, request.sourceConfig().codec())
                .format(metadata.format().publicFormat())
                .storageIdentity(metadata.storageIdentity())
                .schemaIdentity(metadata.schemaIdentity())
                .maxEncodedKeyBytes(metadata.maxKeyBytes())
                .maxEncodedDocumentBytes(metadata.maxDocumentBytes())
                .maxBulkElements(metadata.maxBulkElements())
                .maxDocuments(metadata.maxDocuments())
                .checkpointWalBytes(metadata.checkpointWalBytes())
                .maxRetainedBytes(metadata.maxRetainedBytes())
                .build();
    }

    private static Target validatePaths(Path source, Path configuredTarget) {
        Path target = Objects.requireNonNull(configuredTarget, "targetDirectory")
                .toAbsolutePath().normalize();
        if (!Files.isDirectory(source, LinkOption.NOFOLLOW_LINKS)
                || Files.isSymbolicLink(source)) {
            throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            throw failure(DurableMigrationException.Reason.TARGET_EXISTS,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
        Path requestedParent = target.getParent();
        if (requestedParent == null
                || !Files.isDirectory(requestedParent, LinkOption.NOFOLLOW_LINKS)
                || Files.isSymbolicLink(requestedParent)
                || target.startsWith(source) || source.startsWith(target)) {
            throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), null);
        }
        try {
            Path realSource = source.toRealPath(LinkOption.NOFOLLOW_LINKS);
            Path realParent = requestedParent.toRealPath(LinkOption.NOFOLLOW_LINKS);
            Path resolved = realParent.resolve(target.getFileName()).normalize();
            if (!realSource.equals(source) || !resolved.equals(target)
                    || resolved.startsWith(realSource)
                    || realSource.startsWith(resolved)) {
                throw failure(DurableMigrationException.Reason.TARGET_INVALID,
                        DurableMigrationStage.VALIDATE_REQUEST,
                        OptionalLong.empty(), null);
            }
            validateFileSystem(realParent);
            return new Target(realParent, resolved);
        } catch (DurableMigrationException problem) {
            throw problem;
        } catch (IOException problem) {
            throw failure(DurableMigrationException.Reason.IO_FAILURE,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), problem);
        }
    }

    private static List<DurableMigrationSourceMember> sourceMembers(
            Path source, DurableStorageOwner.Metadata metadata,
            long walGeneration) throws IOException {
        DurableCheckpoint.Manifest manifest = DurableCheckpoint.readManifest(
                source.resolve(DurableCheckpoint.MANIFEST_FILE),
                metadata.format(), metadata.historyId());
        Set<String> expected = Set.of(
                DurableStorageOwner.LOCK_FILE,
                DurableStorageOwner.METADATA_FILE,
                DurableCheckpoint.MANIFEST_FILE,
                manifest.checkpointFile(),
                DurableStorageOwner.walFile(walGeneration));
        List<Path> entries;
        try (var stream = Files.list(source)) {
            entries = stream.toList();
        }
        Set<String> actual = entries.stream()
                .map(path -> path.getFileName().toString())
                .collect(java.util.stream.Collectors.toSet());
        if (!actual.equals(expected)) {
            throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                    DurableMigrationStage.VERIFY_SOURCE,
                    OptionalLong.of(manifest.checkpointSequence()), null);
        }
        ArrayList<DurableMigrationSourceMember> result = new ArrayList<>();
        for (Path entry : entries) {
            String name = entry.getFileName().toString();
            if (name.equals(DurableStorageOwner.LOCK_FILE)) {
                continue;
            }
            if (Files.isSymbolicLink(entry)
                    || !Files.isRegularFile(entry, LinkOption.NOFOLLOW_LINKS)) {
                throw failure(DurableMigrationException.Reason.SOURCE_INVALID,
                        DurableMigrationStage.VERIFY_SOURCE,
                        OptionalLong.of(manifest.checkpointSequence()), null);
            }
            result.add(new DurableMigrationSourceMember(name, Files.size(entry),
                    HexFormat.of().formatHex(fileDigest(entry))));
        }
        result.sort(Comparator.comparing(DurableMigrationSourceMember::name));
        return List.copyOf(result);
    }

    private static String sourceAuthorityIdentity(
            DurableStorageOwner.Metadata metadata,
            DurableCheckpoint.Loaded<?, ?> loaded,
            List<DurableMigrationSourceMember> members) {
        MessageDigest digest = digest(SOURCE_DOMAIN);
        update(digest, metadata.format().publicFormat().family());
        update(digest, metadata.format().publicFormat().major());
        update(digest, metadata.format().publicFormat().minor());
        update(digest, metadata.historyId());
        update(digest, loaded.sequence());
        update(digest, loaded.nextDocId());
        for (DurableMigrationSourceMember member : members) {
            update(digest, member.name());
            update(digest, member.size());
            update(digest, member.sha256());
        }
        return "gse-migration-source-v1-"
                + HexFormat.of().formatHex(digest.digest());
    }

    private static String descriptorDigest(
            DurableStorageFormat format, String storage, String schema,
            String codec, int codecVersion, int maxKey, int maxDocument,
            int maxDocuments, List<DurableIndexDescriptor> indexes) {
        MessageDigest digest = digest(DESCRIPTOR_DOMAIN);
        update(digest, format.family());
        update(digest, format.major());
        update(digest, format.minor());
        update(digest, storage);
        update(digest, schema);
        update(digest, codec);
        update(digest, codecVersion);
        update(digest, maxKey);
        update(digest, maxDocument);
        update(digest, maxDocuments);
        indexStrings(indexes).forEach(value -> update(digest, value));
        return "gse-migration-descriptor-v1-"
                + HexFormat.of().formatHex(digest.digest());
    }

    private static String planDigest(
            Path source, Path target, DurableStorageOwner.Metadata metadata,
            UUID targetHistory, DurableCheckpoint.Loaded<?, ?> loaded,
            List<DurableMigrationSourceMember> members,
            String sourceIdentity, String sourceDescriptor,
            String targetDescriptor, DurableMigrationRequest<?, ?, ?, ?> request,
            List<DurableIndexDescriptor> targetIndexes,
            DurableMigrationIndexChange change, long targetBytes,
            long peakBytes, String projection) {
        MessageDigest digest = digest(PLAN_DOMAIN);
        update(digest, 1);
        update(digest, source.toString());
        update(digest, target.toString());
        update(digest, metadata.format().publicFormat().toString());
        update(digest, request.targetConfig().format().toString());
        update(digest, metadata.historyId());
        update(digest, targetHistory);
        update(digest, loaded.sequence());
        update(digest, loaded.nextDocId());
        for (DurableMigrationSourceMember member : members) {
            update(digest, member.name());
            update(digest, member.size());
            update(digest, member.sha256());
        }
        update(digest, sourceIdentity);
        update(digest, sourceDescriptor);
        update(digest, targetDescriptor);
        update(digest, request.transformDescriptor().identifier());
        update(digest, request.transformDescriptor().version());
        update(digest, loaded.documentIds().size());
        update(digest, metadata.indexes().size());
        update(digest, targetIndexes.size());
        change.added().forEach(value -> update(digest, "+" + value));
        change.removed().forEach(value -> update(digest, "-" + value));
        change.retained().forEach(value -> update(digest, "=" + value));
        update(digest, targetBytes);
        update(digest, peakBytes);
        update(digest, request.capacitySafetyReserveBytes());
        update(digest, projection);
        return "gse-migration-plan-v1-"
                + HexFormat.of().formatHex(digest.digest());
    }

    private static <K, T> long targetAuthoritativeBytes(
            Projection<K, T> projection,
            SearchSchema<T, K> schema,
            List<DurableIndexDescriptor> indexes,
            DurableStorageConfig<K, T> config,
            UUID history,
            long sequence) throws IOException {
        byte[] metadata = DurableStorageOwner.encodeMetadata(config,
                config.codec().codecId(), config.codec().codecVersion(), indexes,
                history);
        long checkpoint = 8 + 2 + 2 + 16 + 32 + 8 + 4 + 4 + 4;
        for (DurableIndexDescriptor index : indexes) {
            checkpoint = Math.addExact(checkpoint,
                    1L + 4 + utf8(index.fieldName()).length
                            + 4 + utf8(index.analyzerId()).length);
        }
        checkpoint = Math.addExact(checkpoint, 4L + projection.slots().size() + 4L);
        for (EncodedRecord record : projection.encoded()) {
            checkpoint = Math.addExact(checkpoint,
                    4L + record.key().length + 4L + record.document().length);
        }
        String filename = "gse-checkpoint-%020d-%s.chk".formatted(sequence,
                "00000000000000000000000000000000");
        DurableCheckpoint.Manifest manifest = new DurableCheckpoint.Manifest(
                sequence, filename, checkpoint, 0, WAL_GENERATION,
                Math.addExact(sequence, 1L));
        long manifestBytes = DurableCheckpoint.encodeManifest(
                manifest, DurableFormatContext.V1_1, history).length;
        return Math.addExact(Math.addExact(metadata.length, checkpoint),
                Math.addExact(manifestBytes,
                        DurableFormatContext.V1_1.walHeaderBytes()));
    }

    private static List<String> indexStrings(List<DurableIndexDescriptor> indexes) {
        return indexes.stream().map(index -> Byte.toUnsignedInt(index.kind())
                + ":" + index.fieldName() + ":" + index.analyzerId()).toList();
    }

    private static <T> List<DurableIndexDescriptor> descriptors(
            List<IndexDefinition<T>> definitions) {
        try {
            List<DurableIndexDescriptor> result = definitions.stream()
                    .map(DurableIndexDescriptor::from).toList();
            if (new HashSet<>(result).size() != result.size()) {
                throw new IllegalArgumentException("duplicate durable index");
            }
            return result;
        } catch (RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.IDENTITY_MISMATCH,
                    DurableMigrationStage.VALIDATE_REQUEST,
                    OptionalLong.empty(), problem);
        }
    }

    private static <K, T> byte[] canonicalKey(
            DurableStorageConfig<K, T> config, K key) {
        try {
            byte[] encoded = Objects.requireNonNull(
                    config.codec().encodeKey(key)).clone();
            K decoded = Objects.requireNonNull(
                    config.codec().decodeKey(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(
                    config.codec().encodeKey(decoded)).clone();
            if (encoded.length > config.maxEncodedKeyBytes()
                    || !key.equals(decoded) || !Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("non-canonical key");
            }
            return encoded;
        } catch (RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                    DurableMigrationStage.PROJECT_TARGET,
                    OptionalLong.empty(), problem);
        }
    }

    private static <K, T> byte[] canonicalDocument(
            DurableStorageConfig<K, T> config, SearchSchema<T, K> schema,
            K key, T document) {
        try {
            if (!key.equals(schema.idOf(document))) {
                throw new IllegalArgumentException("document key mismatch");
            }
            byte[] encoded = Objects.requireNonNull(
                    config.codec().encodeDocument(document)).clone();
            T decoded = Objects.requireNonNull(
                    config.codec().decodeDocument(encoded.clone()));
            byte[] roundTrip = Objects.requireNonNull(
                    config.codec().encodeDocument(decoded)).clone();
            if (encoded.length > config.maxEncodedDocumentBytes()
                    || !document.equals(decoded)
                    || !key.equals(schema.idOf(decoded))
                    || !Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("non-canonical document");
            }
            return encoded;
        } catch (RuntimeException problem) {
            throw failure(DurableMigrationException.Reason.TRANSFORM_FAILURE,
                    DurableMigrationStage.PROJECT_TARGET,
                    OptionalLong.empty(), problem);
        }
    }

    private static boolean otherwiseEqualExceptProjection(
            DurableMigrationPlan left, DurableMigrationPlan right) {
        return !left.projectionDigest().equals(right.projectionDigest())
                && left.schemaVersion() == right.schemaVersion()
                && left.sourceDirectory().equals(right.sourceDirectory())
                && left.targetDirectory().equals(right.targetDirectory())
                && left.sourceFormat().equals(right.sourceFormat())
                && left.targetFormat().equals(right.targetFormat())
                && left.sourceHistory().equals(right.sourceHistory())
                && left.targetHistory().equals(right.targetHistory())
                && left.sourceSequence() == right.sourceSequence()
                && left.nextDocId() == right.nextDocId()
                && left.sourceMembers().equals(right.sourceMembers())
                && left.sourceAuthorityIdentity().equals(right.sourceAuthorityIdentity())
                && left.sourceDescriptorDigest().equals(right.sourceDescriptorDigest())
                && left.targetDescriptorDigest().equals(right.targetDescriptorDigest())
                && left.transformDescriptor().equals(right.transformDescriptor())
                && left.documentCount() == right.documentCount()
                && left.sourceIndexCount() == right.sourceIndexCount()
                && left.targetIndexCount() == right.targetIndexCount()
                && left.indexChange().equals(right.indexChange())
                && left.targetAuthoritativeBytes() == right.targetAuthoritativeBytes()
                && left.peakTargetBytes() == right.peakTargetBytes()
                && left.capacitySafetyReserveBytes()
                        == right.capacitySafetyReserveBytes();
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String marker : UNSUPPORTED_FILE_SYSTEM_MARKERS) {
            if (type.contains(marker)) {
                throw failure(
                        DurableMigrationException.Reason.UNSUPPORTED_FILESYSTEM,
                        DurableMigrationStage.VALIDATE_REQUEST,
                        OptionalLong.empty(), null);
            }
        }
    }

    private static UUID freshHistory(UUID source) {
        UUID result;
        do {
            result = UUID.randomUUID();
        } while (result.equals(new UUID(0, 0)) || result.equals(source));
        return result;
    }

    private static void createLock(Path path) throws IOException {
        try (FileChannel channel = FileChannel.open(path,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.READ,
                StandardOpenOption.WRITE)) {
            channel.force(true);
        }
    }

    private static FileLock acquireMarker(FileChannel channel, long sequence)
            throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw failure(DurableMigrationException.Reason.STORAGE_IN_USE,
                        DurableMigrationStage.PREPARE_TARGET,
                        OptionalLong.of(sequence), null);
            }
            return lock;
        } catch (OverlappingFileLockException problem) {
            throw failure(DurableMigrationException.Reason.STORAGE_IN_USE,
                    DurableMigrationStage.PREPARE_TARGET,
                    OptionalLong.of(sequence), problem);
        }
    }

    private static void cleanup(Path staging, Path marker,
                                boolean stagingCreated, boolean markerCreated,
                                Throwable primary) {
        try {
            if (stagingCreated && Files.isDirectory(staging,
                    LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(staging)) {
                try (var stream = Files.list(staging)) {
                    for (Path member : stream.toList()) {
                        Files.deleteIfExists(member);
                    }
                }
                Files.deleteIfExists(staging);
            }
            if (markerCreated) {
                Files.deleteIfExists(marker);
            }
            if (stagingCreated || markerCreated) {
                DurableStorageOwner.forceDirectory(marker.getParent());
            }
        } catch (IOException | RuntimeException cleanup) {
            if (primary != null) {
                primary.addSuppressed(cleanup);
            }
        }
    }

    private static void writeFully(FileChannel channel, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            if (channel.write(bytes) <= 0) {
                throw new IOException("migration write made no progress");
            }
        }
    }

    private static byte[] fileDigest(Path path) throws IOException {
        MessageDigest digest = digest(null);
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

    private static byte[] digestBytes(byte[] bytes) {
        MessageDigest digest = digest(null);
        digest.update(bytes);
        return digest.digest();
    }

    private static MessageDigest digest(byte[] domain) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            if (domain != null) {
                digest.update(domain);
            }
            return digest;
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void update(MessageDigest digest, UUID value) {
        update(digest, value.toString());
    }

    private static void update(MessageDigest digest, long value) {
        update(digest, Long.toString(value));
    }

    private static void update(MessageDigest digest, int value) {
        update(digest, Integer.toString(value));
    }

    private static void update(MessageDigest digest, String value) {
        update(digest, utf8(value));
    }

    private static void update(MessageDigest digest, byte[] value) {
        digest.update((byte) (value.length >>> 24));
        digest.update((byte) (value.length >>> 16));
        digest.update((byte) (value.length >>> 8));
        digest.update((byte) value.length);
        digest.update(value);
    }

    private static byte[] utf8(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private static DurableMigrationException failure(
            DurableMigrationException.Reason reason,
            DurableMigrationStage stage,
            OptionalLong sequence,
            Throwable cause) {
        return new DurableMigrationException(reason, stage, sequence, cause);
    }

    private record Target(Path parent, Path target) {
    }

    private record EncodedRecord(int slot, byte[] key, byte[] document) {
        private EncodedRecord {
            key = key.clone();
            document = document.clone();
        }
    }

    private record Projection<K, T>(
            List<T> slots,
            Map<K, Integer> ids,
            List<EncodedRecord> encoded,
            String digest
    ) {
        private Projection {
            slots = java.util.Collections.unmodifiableList(new ArrayList<>(slots));
            ids = Map.copyOf(ids);
            encoded = List.copyOf(encoded);
        }
    }

    private record Observation<SK, ST, TK, TT>(
            DurableStorageOwner owner,
            DurableStorageOwner.Metadata metadata,
            DurableCheckpoint.Loaded<SK, ST> loaded,
            Projection<TK, TT> projection,
            DurableMigrationPlan plan,
            Target target
    ) implements AutoCloseable {
        long sequence() {
            return loaded.sequence();
        }

        @Override
        public void close() {
            owner.close();
        }
    }
}
