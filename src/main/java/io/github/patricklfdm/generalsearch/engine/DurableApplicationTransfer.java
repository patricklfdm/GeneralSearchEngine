package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import io.github.patricklfdm.generalsearch.durability.DurableApplicationState;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;

/** Canonical offline transfer; never opens an engine, WAL or source writer. */
final class DurableApplicationTransfer {
    private static final Set<String> MEMBERS = Set.of(DurableBackupReader.MANIFEST_FILE,
            DurableBackupReader.METADATA_FILE, DurableBackupReader.CHECKPOINT_FILE);

    private DurableApplicationTransfer() { }

    static <K, T> DurableApplicationState<T> read(Path directory,
            DurableVerificationConfig<K, T> expected, long maximum,
            SearchSchema<T, K> schema, List<IndexDefinition<T>> startup) {
        Map<String, String> before = inventory(directory, maximum);
        if (io.github.patricklfdm.generalsearch.durability.DurableStorageOperations.inspectBackupFormat(directory)
                .structuralReport().status() == io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus.UNSUPPORTED) {
            throw failure(DurableOperationException.Reason.UNSUPPORTED_FORMAT, null);
        }
        var inspection = DurableSemanticOperations.inspect(directory, expected, schema, startup);
        if (!inspection.valid()) {
            throw failure(inspection.report().status() == DurableSemanticVerificationStatus.IDENTITY_MISMATCH
                    ? DurableOperationException.Reason.IDENTITY_MISMATCH
                    : DurableOperationException.Reason.BACKUP_INVALID, null);
        }
        if (!before.equals(inventory(directory, maximum))) {
            throw failure(DurableOperationException.Reason.BACKUP_INVALID, null);
        }
        // Canonical checkpoints can contain holes. Compact only the live slots, in order.
        List<T> documents = new ArrayList<>(inspection.loaded().documentIds().size());
        for (T document : inspection.loaded().slots()) {
            if (document != null) documents.add(document);
        }
        List<IndexDefinition<T>> indexes = inspection.loaded().indexes().stream()
                .map(index -> index.toDefinition(schema)).toList();
        return new DurableApplicationState<>(inspection.authority().history(),
                inspection.authority().sequence(), documents, indexes);
    }

    static <K, T> DurableBackupResult write(DurableApplicationState<T> state,
            DurableStorageConfig<K, T> config, DurableBackupRequest request, SearchSchema<T, K> schema) {
        validateAnchor(config.directory());
        validateAnchor(request.targetDirectory());
        DurableBackupWriter.validateTarget(config.directory(), request);
        if (state.documents().size() > config.maxDocuments() || state.indexes().size() > 100_000) {
            throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED, null);
        }
        List<DurableIndexDescriptor> indexes = new ArrayList<>();
        Set<String> fields = new HashSet<>();
        for (var definition : state.indexes()) {
            var descriptor = DurableIndexDescriptor.from(definition);
            if (schema.requireField(definition.field().name()) != definition.field()
                    || (definition instanceof TextIndexDefinition<T> text
                    && schema.requireTextField(text.textField().name()) != text.textField())
                    || !fields.add(descriptor.fieldName())) {
                throw new IllegalArgumentException("active indexes must use distinct canonical schema fields");
            }
            descriptor.toDefinition(schema);
            indexes.add(descriptor);
        }
        var snapshot = new SearchSnapshotBuilder<>(new SearchSnapshot<>(state.indexes()));
        Map<K, Integer> ids = new HashMap<>();
        for (T document : state.documents()) {
            schema.documentType().cast(document);
            K key = Objects.requireNonNull(schema.idOf(document), "document key");
            int id = ids.size();
            if (ids.putIfAbsent(key, id) != null) {
                throw new IllegalArgumentException("duplicate document key in application state");
            }
            snapshot.add(id, document);
        }
        String codecId = config.codec().codecId();
        int codecVersion = config.codec().codecVersion();
        long limit = Math.min(config.maxRetainedBytes(), request.maxBundleBytes());
        try {
            byte[] metadata = DurableStorageOwner.encodeMetadata(config, codecId, codecVersion,
                    indexes, state.history());
            var capture = new DurableCheckpoint.Capture<>(snapshot.build(), ids, ids.size(),
                    state.sequence(), indexes);
            byte[] checkpoint = DurableCheckpoint.encode(capture, config, schema,
                    DurableFormatContext.from(config.format()), state.history(), limit - metadata.length);
            return DurableBackupWriter.writeApplication(state.history(), state.sequence(), config,
                    codecId, codecVersion, request, metadata, checkpoint);
        } catch (IOException failure) {
            throw failure(DurableOperationException.Reason.IO_FAILURE, failure);
        } catch (DurabilityException failure) {
            if (failure.reason() == DurabilityException.Reason.CAPACITY_EXCEEDED) {
                throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED, failure);
            }
            throw failure;
        }
    }

    private static Map<String, String> inventory(Path requested, long maximum) {
        Path directory = requested.toAbsolutePath().normalize();
        validateAnchor(directory);
        Map<String, String> result = new HashMap<>();
        try (var members = Files.newDirectoryStream(directory)) {
            long total = 0;
            List<Path> paths = new ArrayList<>();
            for (Path member : members) {
                if (!MEMBERS.contains(member.getFileName().toString())
                        || !Files.isRegularFile(member, LinkOption.NOFOLLOW_LINKS)
                        || ((Number) Files.getAttribute(member, "unix:nlink", LinkOption.NOFOLLOW_LINKS)).longValue() != 1) {
                    throw failure(DurableOperationException.Reason.BACKUP_INVALID, null);
                }
                total = Math.addExact(total, Files.size(member));
                if (total > maximum) throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED, null);
                paths.add(member);
            }
            if (paths.size() != MEMBERS.size()) throw failure(DurableOperationException.Reason.BACKUP_INVALID, null);
            for (Path member : paths) {
                var digest = MessageDigest.getInstance("SHA-256");
                long size = 0;
                try (var input = Files.newInputStream(member)) {
                    byte[] buffer = new byte[64 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        size = Math.addExact(size, count);
                        if (size > maximum) throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED, null);
                        digest.update(buffer, 0, count);
                    }
                }
                result.put(member.getFileName().toString(), size + ":" + HexFormat.of().formatHex(digest.digest()));
            }
            return Map.copyOf(result);
        } catch (IOException failure) {
            throw failure(DurableOperationException.Reason.IO_FAILURE, failure);
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void validateAnchor(Path requested) {
        for (Path part = requested.toAbsolutePath().normalize(); part != null; part = part.getParent()) {
            if (Files.isSymbolicLink(part)) throw failure(DurableOperationException.Reason.TARGET_INVALID, null);
        }
    }

    private static DurableOperationException failure(DurableOperationException.Reason reason, Throwable cause) {
        return new DurableOperationException(reason, OptionalLong.empty(), cause);
    }
}
