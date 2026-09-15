package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.index.text.TextIndexDefinition;

/** Complete canonical application/local configuration descriptor, independent of JVM object identity. */
final class AdmissionConfiguration {
    private AdmissionConfiguration() { }

    static Map<String, Object> application(SearchEngineConfiguration<?, ?> config) {
        var schema = config.schema();
        var indexes = config.indexes().stream().map(ReplicaApplication::descriptor).toList();
        var fields = new HashSet<String>();
        require(indexes.size() <= 10_000, CAPACITY_EXCEEDED, "too many genesis indexes");
        for (var definition : config.indexes()) {
            require(fields.add(definition.field().name()) && schema.requireField(definition.field().name()) == definition.field(),
                    PROTOCOL_MISMATCH, "genesis indexes must use distinct canonical fields");
            if (definition instanceof TextIndexDefinition<?> text) require(schema.requireTextField(text.textField().name()) == text.textField(),
                    PROTOCOL_MISMATCH, "genesis text index is not canonical");
        }
        for (var text : schema.textFields().values()) require(text.analyzer() == SimpleAnalyzer.INSTANCE,
                PROTOCOL_MISMATCH, "only the durable simple analyzer is supported");
        var snapshot = config.config();
        return Map.of("documentType", schema.documentType().getName(), "idField", schema.idField().name(),
                "fields", schema.fields().values().stream().sorted(java.util.Comparator.comparing(f -> f.name()))
                        .map(f -> Map.of("name", f.name(), "type", f.valueType().getName())).toList(),
                "textFields", schema.textFields().values().stream().sorted(java.util.Comparator.comparing(f -> f.name()))
                        .map(f -> Map.of("field", f.name(), "analyzer", "gse-simple-v1")).toList(),
                "indexes", indexes, "snapshot", Map.of("queueCapacity", snapshot.queueCapacity(), "maxBatchSize", snapshot.maxBatchSize(),
                        "maxBatchWaitSeconds", snapshot.maxBatchWait().getSeconds(), "maxBatchWaitNanos", snapshot.maxBatchWait().getNano()),
                "planner", config.plannerConfig().rangePlanningMode().name());
    }

    static Map<String, Object> local(ReplicationGroupConfig<?, ?> config) throws IOException {
        var core = config.materialization(); var bounds = config.bounds();
        require(core.codec().codecVersion() > 0, PROTOCOL_MISMATCH, "replication codec version must be positive");
        return Map.of("node", config.localNodeId().value(), "target", AdmissionPaths.binding(config.replicaDirectory()),
                "materialization", Map.of("directory", AdmissionPaths.binding(core.directory()),
                        "format", Map.of("family", core.format().family(), "major", core.format().major(), "minor", core.format().minor()),
                        "storageIdentity", core.storageIdentity(), "schemaIdentity", core.schemaIdentity(),
                        "codecId", core.codec().codecId(), "codecVersion", core.codec().codecVersion(),
                        "bounds", Map.of("maxEncodedKeyBytes", core.maxEncodedKeyBytes(), "maxEncodedDocumentBytes", core.maxEncodedDocumentBytes(),
                                "maxBulkElements", core.maxBulkElements(), "maxDocuments", core.maxDocuments(),
                                "checkpointWalBytes", core.checkpointWalBytes(), "maxRetainedBytes", core.maxRetainedBytes(),
                                "maxDerivedStateBytes", core.maxDerivedStateBytes())),
                "replicationBounds", Map.of("maxFrameBytes", bounds.maxFrameBytes(), "maxEntriesPerAppend", bounds.maxEntriesPerAppend(),
                        "maxInFlightPerPeer", bounds.maxInFlightPerPeer(), "maxPendingClientOperations", bounds.maxPendingClientOperations(),
                        "maxRetryAttempts", bounds.maxRetryAttempts(), "requestTimeoutMillis", bounds.requestTimeoutMillis(),
                        "retryBackoffMillis", bounds.retryBackoffMillis(), "snapshotChunkBytes", bounds.snapshotChunkBytes(),
                        "maxRetainedLogBytes", bounds.maxRetainedLogBytes(), "maxSnapshotStagingBytes", bounds.maxSnapshotStagingBytes()));
    }

    static Map<String, Object> object(Object value) {
        require(value instanceof Map<?, ?>, INTEGRITY_FAILURE, "expected descriptor object");
        @SuppressWarnings("unchecked") var result = (Map<String, Object>) value;
        return result;
    }

    static List<?> array(Object value) {
        require(value instanceof List<?>, INTEGRITY_FAILURE, "expected descriptor array"); return (List<?>) value;
    }

    static String string(Map<String, Object> object, String key) {
        Object value = object.get(key);
        require(value instanceof String && !((String) value).isEmpty(), INTEGRITY_FAILURE, "missing descriptor string: " + key);
        return (String) value;
    }

    static long number(Map<String, Object> object, String key, long minimum, long maximum) {
        Object value = object.get(key);
        require(value instanceof Integer || value instanceof Long, INTEGRITY_FAILURE, "invalid descriptor number: " + key);
        long number = ((Number) value).longValue();
        require(number >= minimum && number <= maximum, CAPACITY_EXCEEDED, "descriptor number outside bound: " + key);
        return number;
    }

    static void keys(Map<String, Object> object, String... keys) {
        require(object.keySet().equals(Set.of(keys)), INTEGRITY_FAILURE, "unexpected descriptor keys");
    }

    static Path path(Object value) {
        var binding = object(value);
        keys(binding, "path", "parentRealPath", "fileStoreName", "fileStoreType", "parentFileKey");
        for (String key : binding.keySet()) require(string(binding, key).getBytes(StandardCharsets.UTF_8).length <= 4096,
                CAPACITY_EXCEEDED, "path binding exceeds bound");
        Path path = Path.of(string(binding, "path"));
        require(path.isAbsolute() && path.normalize().equals(path) && path.getParent() != null
                        && path.getParent().toString().equals(string(binding, "parentRealPath")),
                INTEGRITY_FAILURE, "noncanonical path binding");
        return path;
    }

    static void validateLocal(Map<String, Object> local, AdmissionFormat.Manifest manifest) {
        keys(local, "node", "target", "materialization", "replicationBounds"); path(local.get("target"));
        require(manifest.group().contains(new ReplicationNodeId(string(local, "node"))), PROTOCOL_MISMATCH, "foreign local node");
        var core = object(local.get("materialization"));
        keys(core, "directory", "format", "storageIdentity", "schemaIdentity", "codecId", "codecVersion", "bounds"); path(core.get("directory"));
        require(string(core, "storageIdentity").matches("[a-z0-9][a-z0-9._-]{0,127}")
                        && string(core, "schemaIdentity").equals(manifest.group().schemaId())
                        && string(core, "codecId").equals(manifest.group().codecId())
                        && number(core, "codecVersion", 1, Integer.MAX_VALUE) == manifest.group().codecVersion(), PROTOCOL_MISMATCH, "local identity mismatch");
        var format = object(core.get("format")); keys(format, "family", "major", "minor");
        require(string(format, "family").equals("gse-durable") && number(format, "major", 0, Integer.MAX_VALUE) == 1, PROTOCOL_MISMATCH, "unsupported materialization family");
        long minor = number(format, "minor", 0, Integer.MAX_VALUE);
        require(minor <= 2, PROTOCOL_MISMATCH, "unsupported materialization version");
        var b = object(core.get("bounds"));
        keys(b, "maxEncodedKeyBytes", "maxEncodedDocumentBytes", "maxBulkElements", "maxDocuments", "checkpointWalBytes", "maxRetainedBytes", "maxDerivedStateBytes");
        number(b, "maxEncodedKeyBytes", 1, 64 << 20); number(b, "maxEncodedDocumentBytes", 1, 256 << 20);
        number(b, "maxBulkElements", 1, 1_000_000); number(b, "maxDocuments", 1, 100_000_000);
        long wal = number(b, "checkpointWalBytes", 1, 1L << 40), retained = number(b, "maxRetainedBytes", 1, 16L << 40);
        long derived = number(b, "maxDerivedStateBytes", 1, 8L << 40);
        require(retained > wal && (minor != 2 || derived <= retained), CAPACITY_EXCEEDED, "invalid local core budgets");
        var r = object(local.get("replicationBounds"));
        keys(r, "maxFrameBytes", "maxEntriesPerAppend", "maxInFlightPerPeer", "maxPendingClientOperations", "maxRetryAttempts",
                "requestTimeoutMillis", "retryBackoffMillis", "snapshotChunkBytes", "maxRetainedLogBytes", "maxSnapshotStagingBytes");
        number(r, "maxFrameBytes", 1, 64 << 20); number(r, "maxEntriesPerAppend", 1, 10_000);
        number(r, "maxInFlightPerPeer", 1, 4096); number(r, "maxPendingClientOperations", 1, 100_000);
        number(r, "maxRetryAttempts", 1, 100); number(r, "requestTimeoutMillis", 1, 300_000);
        number(r, "retryBackoffMillis", 1, 60_000); number(r, "snapshotChunkBytes", 1, 64 << 20);
        number(r, "maxRetainedLogBytes", 1, 1L << 40); number(r, "maxSnapshotStagingBytes", 1, 1L << 40);
    }
}
