package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;
import java.util.OptionalLong;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationFinding;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/** Internal one-pass typed inspection shared by verification and restore. */
final class DurableSemanticOperations {
    private DurableSemanticOperations() {
    }

    static <K, T> Inspection<K, T> inspect(
            Path backupDirectory,
            DurableVerificationConfig<K, T> expected,
            SearchSchema<T, K> schema,
            List<IndexDefinition<T>> startupDefinitions
    ) {
        Path directory = Objects.requireNonNull(backupDirectory, "backupDirectory")
                .toAbsolutePath().normalize();
        Objects.requireNonNull(expected, "expectedConfig");
        Objects.requireNonNull(schema, "schema");
        Objects.requireNonNull(startupDefinitions, "startupDefinitions");

        DurableVerificationReport structural =
                DurableStorageOperations.verifyBackup(directory);
        if (structural.status() != DurableVerificationStatus.VALID) {
            throw operation(DurableOperationException.Reason.BACKUP_INVALID,
                    structural.sequence(), null);
        }
        DurableBackupReader.Authority authority = DurableBackupReader.read(directory);
        DurableStorageOwner.Metadata metadata;
        try {
            metadata = DurableStorageOwner.readMetadata(
                    directory.resolve(DurableBackupReader.METADATA_FILE));
        } catch (IOException | DurabilityException failure) {
            throw operation(DurableOperationException.Reason.BACKUP_INVALID,
                    structural.sequence(), failure);
        }

        String codecIdentity;
        int actualCodecVersion;
        try {
            codecIdentity = Objects.requireNonNull(expected.codec().codecId());
            actualCodecVersion = expected.codec().codecVersion();
        } catch (RuntimeException failure) {
            return mismatch(structural, "CODEC_IDENTITY_LOOKUP",
                    "configured codec identity could not be established");
        }
        List<DurableIndexDescriptor> startupIndexes;
        try {
            startupIndexes = startupDefinitions.stream()
                    .map(DurableIndexDescriptor::from).toList();
        } catch (RuntimeException failure) {
            return mismatch(structural, "INDEX_IDENTITY_MISMATCH",
                    "builder startup indexes are not durable-compatible");
        }
        if (!authority.storageIdentity().equals(expected.storageIdentity())
                || !authority.schemaIdentity().equals(expected.schemaIdentity())
                || !authority.codecIdentity().equals(codecIdentity)
                || authority.codecVersion() != expected.codecVersion()
                || actualCodecVersion != expected.codecVersion()
                || metadata.maxKeyBytes() != expected.maxEncodedKeyBytes()
                || metadata.maxDocumentBytes()
                        != expected.maxEncodedDocumentBytes()
                || metadata.maxDocuments() != expected.maxDocuments()
                || !metadata.indexes().equals(startupIndexes)) {
            return mismatch(structural, "SEMANTIC_IDENTITY_MISMATCH",
                    "expected typed identities, bounds, or startup indexes differ");
        }

        DurableStorageConfig<K, T> decodeConfig;
        try {
            decodeConfig = DurableStorageConfig.builder(directory, expected.codec())
                    .storageIdentity(metadata.storageIdentity())
                    .schemaIdentity(metadata.schemaIdentity())
                    .maxEncodedKeyBytes(metadata.maxKeyBytes())
                    .maxEncodedDocumentBytes(metadata.maxDocumentBytes())
                    .maxBulkElements(metadata.maxBulkElements())
                    .maxDocuments(metadata.maxDocuments())
                    .checkpointWalBytes(metadata.checkpointWalBytes())
                    .maxRetainedBytes(metadata.maxRetainedBytes())
                    .build();
        } catch (RuntimeException failure) {
            return mismatch(structural, "SEMANTIC_CONFIG_MISMATCH",
                    "persisted safety bounds cannot form the expected typed config");
        }

        DurableCheckpoint.Loaded<K, T> loaded;
        DurableRecovery.Result<K, T> recovered;
        try {
            loaded = DurableCheckpoint.read(
                    directory.resolve(DurableBackupReader.CHECKPOINT_FILE),
                    decodeConfig, schema, authority.history(), null);
            if (loaded.sequence() != authority.sequence()
                    || loaded.nextDocId() != loaded.slots().size()
                    || loaded.documentIds().size() > expected.maxDocuments()) {
                return stateMismatch(structural);
            }
            recovered = DurableRecovery.replay(decodeConfig, schema,
                    startupIndexes, loaded, List.of(), false);
            if (recovered.sequence() != authority.sequence()
                    || recovered.nextDocId() != loaded.nextDocId()
                    || !recovered.documentIds().equals(loaded.documentIds())
                    || !recovered.indexes().equals(loaded.indexes())
                    || recovered.snapshot().activeDocuments().cardinality()
                            != loaded.documentIds().size()) {
                return stateMismatch(structural);
            }
        } catch (DurabilityException failure) {
            if (failure.reason() == DurabilityException.Reason.CODEC_FAILURE) {
                return decodeFailure(structural);
            }
            return stateMismatch(structural);
        } catch (IOException | RuntimeException failure) {
            return stateMismatch(structural);
        }

        DurableVerificationReport after =
                DurableStorageOperations.verifyBackup(directory);
        if (!after.equals(structural)) {
            throw operation(DurableOperationException.Reason.BACKUP_INVALID,
                    structural.sequence(), null);
        }
        DurableSemanticVerificationReport report =
                new DurableSemanticVerificationReport(structural,
                        DurableSemanticVerificationStatus.SEMANTICALLY_VALID,
                        List.of(), loaded.documentIds().size());
        return new Inspection<>(report, authority, metadata, loaded, recovered);
    }

    private static <K, T> Inspection<K, T> mismatch(
            DurableVerificationReport structural, String code, String detail) {
        return failed(structural,
                DurableSemanticVerificationStatus.IDENTITY_MISMATCH,
                code, DurableBackupReader.MANIFEST_FILE, detail);
    }

    private static <K, T> Inspection<K, T> decodeFailure(
            DurableVerificationReport structural) {
        return failed(structural,
                DurableSemanticVerificationStatus.DECODE_FAILURE,
                "BACKUP_DECODE_FAILURE", DurableBackupReader.CHECKPOINT_FILE,
                "a canonical key or document did not decode under the expected codec");
    }

    private static <K, T> Inspection<K, T> stateMismatch(
            DurableVerificationReport structural) {
        return failed(structural,
                DurableSemanticVerificationStatus.STATE_MISMATCH,
                "BACKUP_STATE_MISMATCH", DurableBackupReader.CHECKPOINT_FILE,
                "decoded state or derived index reconstruction is inconsistent");
    }

    private static <K, T> Inspection<K, T> failed(
            DurableVerificationReport structural,
            DurableSemanticVerificationStatus status,
            String code,
            String member,
            String detail
    ) {
        DurableVerificationFinding finding =
                new DurableVerificationFinding(code, member, detail);
        return new Inspection<>(new DurableSemanticVerificationReport(
                structural, status, List.of(finding), 0),
                null, null, null, null);
    }

    private static DurableOperationException operation(
            DurableOperationException.Reason reason,
            OptionalLong sequence,
            Throwable cause
    ) {
        return new DurableOperationException(reason, sequence, cause);
    }

    record Inspection<K, T>(
            DurableSemanticVerificationReport report,
            DurableBackupReader.Authority authority,
            DurableStorageOwner.Metadata metadata,
            DurableCheckpoint.Loaded<K, T> loaded,
            DurableRecovery.Result<K, T> recovered
    ) {
        boolean valid() {
            return report.status()
                    == DurableSemanticVerificationStatus.SEMANTICALLY_VALID;
        }
    }
}
