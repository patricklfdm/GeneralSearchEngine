package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.equality.EqualityIndexDefinition;
import io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition;
import io.github.patricklfdm.generalsearch.index.range.RangeIndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/** Private preparation plus atomic publication; neither engine opens a V4 WAL. */
final class ReplicaApplication<K, T> implements AutoCloseable {
    private final SearchSchema<T, K> schema;
    private final SearchEngineConfiguration<K, T> captured;
    private final DurableStorageConfig<K, T> configuration;
    private final DurableCodec<K, T> codec;
    private final ReplicationBounds bounds;
    private final int maximumPayload;
    private final AtomicReference<Published<K, T>> published;
    private Slot<K, T> working;
    private Operation<T, K> catchup, prepared;
    private volatile boolean closed;
    private final String indexDigest;
    private final List<IndexDefinition<T>> initialIndexes;
    private final java.util.TreeMap<String, String> registered = new java.util.TreeMap<>();

    private static final class Slot<K, T> {
        final SearchEngine<K, T> engine;
        final AtomicInteger readers = new AtomicInteger(Integer.MIN_VALUE);
        Slot(SearchEngine<K, T> engine) { this.engine = engine; }
    }
    private record Published<K, T>(Slot<K, T> slot, long index, long sequence) { }
    private record Operation<T, K>(String type, List<T> documents, List<K> keys, IndexDefinition<T> index, String field) { }

    ReplicaApplication(SearchSchema<T, K> schema, List<IndexDefinition<T>> indexes,
                       DurableStorageConfig<K, T> configuration, ReplicationBounds bounds) {
        this(SearchEngine.builder(schema).indexes(indexes).configuration(), configuration, bounds);
    }

    ReplicaApplication(SearchEngineConfiguration<K, T> captured, DurableStorageConfig<K, T> configuration, ReplicationBounds bounds) {
        this.captured = captured;
        var schema = captured.schema(); var indexes = captured.indexes();
        this.schema = schema; this.configuration = configuration; this.codec = configuration.codec(); this.bounds = bounds;
        this.initialIndexes = List.copyOf(indexes);
        for (var index : indexes) registered.put(index.field().name(), descriptor(index));
        require(bounds.maxFrameBytes() >= 4096, CAPACITY_EXCEEDED, "leader runtime requires at least a 4096-byte frame bound");
        maximumPayload = (bounds.maxFrameBytes() - 2048) / 4 * 3 - 197;
        var descriptions = indexes.stream().map(ReplicaApplication::descriptor).sorted().toList();
        require(descriptions.stream().distinct().count() == descriptions.size(), PROTOCOL_MISMATCH, "duplicate initial indexes");
        indexDigest = configurationDigest(indexes);
        Slot<K, T> first = new Slot<>(captured.newBuilder().build());
        try { working = new Slot<>(captured.newBuilder().build()); }
        catch (RuntimeException | Error error) { first.engine.close(); throw error; }
        first.readers.set(0);
        published = new AtomicReference<>(new Published<>(first, 0, 0));
    }

    void validateManifest(ReplicaManifest manifest) {
        require(manifest.codecId().equals(codec.codecId()) && manifest.codecVersion() == codec.codecVersion()
                        && manifest.schemaId().equals(configuration.schemaIdentity()) && manifest.schemaVersion() == 1
                        && manifest.indexConfigurationDigest().equals(indexDigest),
                PROTOCOL_MISMATCH, "application codec/schema/index identity mismatch");
    }
    String indexDigest() { return indexDigest; }
    long appliedIndex() { return published.get().index(); }
    long sequence() { return published.get().sequence(); }

    /** Writer-only check: a pending private operation must be discarded before resuming. */
    boolean canResumeAt(long index) { return !closed && prepared == null && appliedIndex() == index; }

    byte[] emptySnapshot() {
        try (var empty = new ReplicaApplication<>(captured, configuration, bounds)) { return empty.snapshot(); }
    }

    byte[] snapshot() {
        require(prepared == null, CONFLICTING_HISTORY, "cannot snapshot an unresolved application operation");
        int maximum = ReplicaSnapshot.maximum(bounds);
        return read(engine -> body(out -> {
            out.writeShort(1); out.writeInt(registered.size());
            for (String descriptor : registered.values()) {
                require((long) out.size() + 4 + descriptor.length() + HEADER_BYTES <= maximum, CAPACITY_EXCEEDED, "snapshot indexes exceed bound");
                text(out, descriptor);
            }
            var documents = engine.search(document -> true);
            out.writeInt(documents.size());
            for (T document : documents) {
                ReplicaSnapshot.blob(out, canonicalKey(schema.idOf(document)), maximum);
                ReplicaSnapshot.blob(out, canonicalDocument(document), maximum);
            }
            require(out.size() <= maximum - HEADER_BYTES, CAPACITY_EXCEEDED, "application snapshot exceeds bound");
        }));
    }

    /** Rebuilds privately; the caller publishes only after authority installation succeeds. */
    ReplicaApplication<K, T> rebuild(ReplicaRecoveryImage image) {
        var rebuilt = new ReplicaApplication<>(captured, configuration, bounds);
        try {
            var snapshot = image.snapshot();
            var in = input(snapshot.application());
            require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported application snapshot version");
            int count = in.readInt();
            require(count >= 0 && count <= 10_000 && count <= in.available() / 4, CAPACITY_EXCEEDED, "snapshot index count exceeds bound");
            var definitions = new ArrayList<IndexDefinition<T>>();
            var fields = new java.util.HashSet<String>();
            for (int i = 0; i < count; i++) {
                String descriptor = text(in, 8192); var definition = definition(descriptor);
                require(descriptor(definition).equals(descriptor) && fields.add(definition.field().name()),
                        INTEGRITY_FAILURE, "noncanonical or duplicate snapshot index");
                definitions.add(definition);
            }
            for (var index : initialIndexes) {
                rebuilt.published.get().slot().engine.dropIndex(index.field().name()).join();
                rebuilt.working.engine.dropIndex(index.field().name()).join();
            }
            rebuilt.registered.clear();
            for (var definition : definitions) {
                rebuilt.published.get().slot().engine.createIndex(definition).join();
                rebuilt.working.engine.createIndex(definition).join();
                rebuilt.registered.put(definition.field().name(), descriptor(definition));
            }
            count = in.readInt();
            require(count >= 0 && count <= configuration.maxDocuments() && count <= in.available() / 8,
                    CAPACITY_EXCEEDED, "snapshot document count exceeds bound");
            var batch = new ArrayList<T>();
            for (int i = 0; i < count; i++) {
                byte[] key = ReplicaSnapshot.blob(in, configuration.maxEncodedKeyBytes());
                byte[] bytes = ReplicaSnapshot.blob(in, configuration.maxEncodedDocumentBytes());
                T document = codec.decodeDocument(bytes.clone());
                require(Arrays.equals(key, canonicalKey(schema.idOf(document))) && Arrays.equals(bytes, canonicalDocument(document)),
                        INTEGRITY_FAILURE, "snapshot codec/key mismatch");
                batch.add(document);
                if (batch.size() == configuration.maxBulkElements() || i == count - 1) {
                    rebuilt.published.get().slot().engine.addAll(batch).join(); rebuilt.working.engine.addAll(batch).join(); batch.clear();
                }
            }
            end(in);
            rebuilt.published.set(new Published<>(rebuilt.published.get().slot(), snapshot.index(), snapshot.sequence()));
            require(Arrays.equals(snapshot.application(), rebuilt.snapshot()), INTEGRITY_FAILURE, "noncanonical application snapshot");
            for (var entry : image.entries()) { rebuilt.prepare(entry); rebuilt.publish(entry.index()); }
            return rebuilt;
        } catch (IOException | RuntimeException | Error error) {
            rebuilt.close();
            if (error instanceof IOException) throw failure(INTEGRITY_FAILURE, "invalid application snapshot", error);
            if (error instanceof RuntimeException runtime) throw runtime;
            throw (Error) error;
        }
    }

    void replaceWith(ReplicaApplication<K, T> rebuilt) {
        require(!closed && !rebuilt.closed, CLOSED, "application closed during recovery");
        var old = published.getAndSet(rebuilt.published.get());
        var oldWorking = working;
        working = rebuilt.working; catchup = rebuilt.catchup; prepared = rebuilt.prepared;
        registered.clear(); registered.putAll(rebuilt.registered);
        rebuilt.closed = true; // ownership of both engines moved to this application
        old.slot().readers.getAndUpdate(readers -> readers | Integer.MIN_VALUE);
        old.slot().engine.close(); oldWorking.engine.close();
    }

    <R> R read(Function<SearchEngine<K, T>, R> action) {
        while (true) {
            require(!closed, CLOSED, "application closed");
            var view = published.get();
            int leases = view.slot().readers.get();
            if (leases < 0 || !view.slot().readers.compareAndSet(leases, leases + 1)) continue;
            try {
                if (published.get() == view) return action.apply(view.slot().engine);
            } finally { view.slot().readers.decrementAndGet(); }
        }
    }

    byte[] documents(String operation, Collection<? extends T> documents) {
        require(List.of("ADD", "UPDATE", "ADD_ALL", "UPDATE_ALL").contains(operation), PROTOCOL_MISMATCH, "not a document operation");
        return encodeItems(operation, documents, true);
    }
    byte[] keys(String operation, Collection<? extends K> keys) {
        require(List.of("REMOVE", "REMOVE_ALL").contains(operation), PROTOCOL_MISMATCH, "not a key operation");
        return encodeItems(operation, keys, false);
    }
    byte[] index(IndexDefinition<T> definition) {
        java.util.Objects.requireNonNull(definition, "definition");
        if (schema.requireField(definition.field().name()) != definition.field())
            throw new IllegalArgumentException("dynamic indexes require the canonical schema field: " + definition.field().name());
        if (definition instanceof TextIndexDefinition<?> text && schema.requireTextField(text.textField().name()) != text.textField())
            throw new IllegalArgumentException("dynamic text indexes require the canonical TextField: " + text.textField().name());
        return bounded(out -> { out.writeShort(1); text(out, descriptor(definition)); });
    }
    byte[] dropIndex(String field) {
        schema.requireField(field);
        return bounded(out -> { out.writeShort(1); text(out, field); });
    }

    @SuppressWarnings("unchecked")
    private byte[] encodeItems(String operation, Collection<?> items, boolean documents) {
        java.util.Objects.requireNonNull(items, "items");
        require(items.size() <= configuration.maxBulkElements(), CAPACITY_EXCEEDED, "bulk count exceeds bound");
        require(operation.endsWith("_ALL") || items.size() == 1, PROTOCOL_MISMATCH, "single operation requires one item");
        return bounded(out -> {
            out.writeShort(1); out.writeInt(items.size());
            int count = 0;
            for (Object item : items) {
                require(++count <= items.size(), CAPACITY_EXCEEDED, "collection changed while encoding");
                K key = documents ? schema.idOf((T) item) : (K) java.util.Objects.requireNonNull(item);
                byte[] encodedKey = canonicalKey(key);
                blob(out, encodedKey);
                if (documents) {
                    byte[] bytes = canonicalDocument((T) item);
                    T decoded = codec.decodeDocument(bytes.clone());
                    require(Arrays.equals(encodedKey, canonicalKey(schema.idOf(decoded))), INTEGRITY_FAILURE, "document codec changes key");
                    blob(out, bytes);
                }
            }
            require(count == items.size(), PROTOCOL_MISMATCH, "collection changed while encoding");
        });
    }
    private byte[] canonicalKey(K key) {
        byte[] bytes = java.util.Objects.requireNonNull(codec.encodeKey(key)).clone();
        require(bytes.length <= configuration.maxEncodedKeyBytes(), CAPACITY_EXCEEDED, "encoded key exceeds bound");
        require(Arrays.equals(bytes, codec.encodeKey(key)) && Arrays.equals(bytes, codec.encodeKey(codec.decodeKey(bytes.clone()))),
                INTEGRITY_FAILURE, "key codec is not canonical");
        return bytes;
    }
    private byte[] canonicalDocument(T document) {
        byte[] bytes = java.util.Objects.requireNonNull(codec.encodeDocument(document)).clone();
        require(bytes.length <= configuration.maxEncodedDocumentBytes(), CAPACITY_EXCEEDED, "encoded document exceeds bound");
        require(Arrays.equals(bytes, codec.encodeDocument(document))
                        && Arrays.equals(bytes, codec.encodeDocument(codec.decodeDocument(bytes.clone()))),
                INTEGRITY_FAILURE, "document codec is not canonical");
        return bytes;
    }
    private byte[] bounded(Encoder encoder) {
        byte[] result = body(encoder);
        require(result.length <= maximumPayload, CAPACITY_EXCEEDED, "application payload exceeds wire/storage bound");
        return result;
    }
    private void blob(DataOutputStream out, byte[] bytes) throws IOException {
        require((long) out.size() + 4 + bytes.length <= maximumPayload, CAPACITY_EXCEEDED, "application payload exceeds bound");
        out.writeInt(bytes.length); out.write(bytes);
    }
    private byte[] blob(DataInputStream in, int max) throws IOException {
        int length = in.readInt();
        require(length >= 0 && length <= max && length <= in.available(), INTEGRITY_FAILURE, "invalid application field length");
        return in.readNBytes(length);
    }

    /** Prepares only private state. Rejected atomic operations leave it unchanged. */
    void prepare(ReplicaEntry entry) {
        require(!closed && prepared == null, CLOSED, "application has an unresolved prepared operation");
        if (catchup != null) {
            long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            while (working.readers.get() != Integer.MIN_VALUE) {
                require(!closed && System.nanoTime() < deadline, QUORUM_UNAVAILABLE, "retired readers did not drain");
                java.util.concurrent.locks.LockSupport.parkNanos(100_000);
            }
            apply(working.engine, catchup); catchup = null;
        }
        require(control(entry.operation()) || sequence() < Long.MAX_VALUE, CAPACITY_EXCEEDED, "application sequence exhausted");
        Operation<T, K> operation = decode(entry);
        if (operation.type().equals("INDEX_CREATE")) {
            String existing = registered.get(operation.index().field().name());
            require(existing == null || existing.equals(descriptor(operation.index())), PROTOCOL_MISMATCH,
                    "replica snapshots allow one index per field; drop the existing index first");
            require(registered.size() < 10_000, CAPACITY_EXCEEDED, "snapshot index count exceeds bound");
        }
        if (operation.type().equals("ADD") || operation.type().equals("ADD_ALL"))
            require((long) working.engine.metrics().documentCount() + operation.documents().size() <= configuration.maxDocuments(),
                    CAPACITY_EXCEEDED, "application document count exceeds bound");
        apply(working.engine, operation);
        prepared = operation;
    }

    /** Atomically publishes the prepared search state and its index/sequence after proof quorum. */
    void publish(long index) {
        require(!closed && prepared != null && index == appliedIndex() + 1, CONFLICTING_HISTORY, "application publication is not contiguous");
        var old = published.get();
        if (prepared.type().equals("INDEX_CREATE")) registered.put(prepared.index().field().name(), descriptor(prepared.index()));
        if (prepared.type().equals("INDEX_DROP")) registered.remove(prepared.field());
        boolean application = !control(prepared.type());
        if (application) {
            working.readers.set(0);
            published.set(new Published<>(working, index, Math.addExact(old.sequence(), 1)));
            old.slot().readers.getAndUpdate(readers -> readers | Integer.MIN_VALUE);
            working = old.slot();
            catchup = prepared;
        } else published.set(new Published<>(old.slot(), index, old.sequence()));
        prepared = null;
    }

    private Operation<T, K> decode(ReplicaEntry entry) {
        if (control(entry.operation())) {
            require(entry.payload().length == 0, INTEGRITY_FAILURE, "NO_OP payload must be empty");
            return new Operation<>(entry.operation(), List.of(), List.of(), null, null);
        }
        require(entry.payload().length <= maximumPayload, CAPACITY_EXCEEDED, "application payload exceeds bound");
        try {
            var in = input(entry.payload());
            require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported application payload version");
            var docs = new ArrayList<T>(); var keys = new ArrayList<K>();
            IndexDefinition<T> index = null; String field = null;
            if (List.of("ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL", "REMOVE_ALL").contains(entry.operation())) {
                int count = in.readInt();
                require(count >= 0 && count <= configuration.maxBulkElements() && count <= in.available() / 4,
                        CAPACITY_EXCEEDED, "invalid bulk count");
                require(entry.operation().endsWith("_ALL") || count == 1, INTEGRITY_FAILURE, "single operation count mismatch");
                for (int i = 0; i < count; i++) {
                    byte[] bytes = blob(in, configuration.maxEncodedKeyBytes());
                    K key = codec.decodeKey(bytes.clone());
                    require(Arrays.equals(bytes, canonicalKey(key)), INTEGRITY_FAILURE, "noncanonical key payload");
                    keys.add(key);
                    if (!entry.operation().startsWith("REMOVE")) {
                        byte[] document = blob(in, configuration.maxEncodedDocumentBytes());
                        T decoded = codec.decodeDocument(document.clone());
                        require(Arrays.equals(document, canonicalDocument(decoded))
                                        && Arrays.equals(bytes, canonicalKey(schema.idOf(decoded))), INTEGRITY_FAILURE, "noncanonical document payload");
                        docs.add(decoded);
                    }
                }
            } else if (entry.operation().equals("INDEX_CREATE")) index = definition(text(in, 8192));
            else if (entry.operation().equals("INDEX_DROP")) { field = text(in, 1024); schema.requireField(field); }
            else throw new ReplicationException(PROTOCOL_MISMATCH, "application operation is not enabled in Phase 3");
            end(in);
            return new Operation<>(entry.operation(), docs, keys, index, field);
        } catch (IOException error) { throw failure(INTEGRITY_FAILURE, "invalid application payload", error); }
    }

    private void apply(SearchEngine<K, T> engine, Operation<T, K> operation) {
        switch (operation.type()) {
            case "NO_OP", "SNAPSHOT_MARKER" -> { }
            case "ADD" -> engine.add(operation.documents().getFirst()).join();
            case "UPDATE" -> engine.update(operation.documents().getFirst()).join();
            case "REMOVE" -> engine.remove(operation.keys().getFirst()).join();
            case "ADD_ALL" -> engine.addAll(operation.documents()).join();
            case "UPDATE_ALL" -> engine.updateAll(operation.documents()).join();
            case "REMOVE_ALL" -> engine.removeAll(operation.keys()).join();
            case "INDEX_CREATE" -> engine.createIndex(operation.index()).join();
            case "INDEX_DROP" -> engine.dropIndex(operation.field()).join();
            default -> throw new ReplicationException(PROTOCOL_MISMATCH, "unsupported application operation");
        }
    }

    static boolean control(String operation) { return operation.equals("NO_OP") || operation.equals("SNAPSHOT_MARKER"); }
    static String configurationDigest(List<? extends IndexDefinition<?>> indexes) {
        return sha256(ReplicaJson.encode(indexes.stream().map(ReplicaApplication::descriptor).sorted().toList(), MAX_METADATA_BYTES));
    }
    io.github.patricklfdm.generalsearch.durability.DurableBackupResult backup(java.util.UUID history,
            io.github.patricklfdm.generalsearch.durability.DurableBackupRequest request) {
        // V4 metadata binds descriptor order. Preserve captured field order, then append newly indexed fields canonically.
        var active = new java.util.LinkedHashMap<String, IndexDefinition<T>>();
        for (var initial : initialIndexes) {
            String descriptor = registered.get(initial.field().name());
            if (descriptor != null) active.put(initial.field().name(), definition(descriptor));
        }
        for (var entry : registered.entrySet()) active.putIfAbsent(entry.getKey(), definition(entry.getValue()));
        var definitions = List.copyOf(active.values());
        var state = new io.github.patricklfdm.generalsearch.durability.DurableApplicationState<T>(history, sequence(),
                read(engine -> engine.search(document -> true)), definitions);
        return captured.newBuilder().writeDurableBackup(state, configuration, request);
    }

    static String descriptor(IndexDefinition<?> definition) {
        String field = definition.field().name();
        require(field.getBytes(java.nio.charset.StandardCharsets.UTF_8).length <= 1024,
                PROTOCOL_MISMATCH, "index field exceeds durable bound");
        String kind;
        if (definition instanceof EqualityIndexDefinition<?, ?>) kind = "equality";
        else if (definition instanceof RangeIndexDefinition<?, ?>) kind = "range";
        else if (definition instanceof PrefixIndexDefinition<?>) kind = "prefix";
        else if (definition instanceof TextIndexDefinition<?> text && text.textField().analyzer() == SimpleAnalyzer.INSTANCE) kind = "text";
        else throw new ReplicationException(PROTOCOL_MISMATCH, "only built-in durable indexes/simple analyzer are supported");
        return new String(ReplicaJson.encode(Map.of("kind", kind, "field", field,
                "analyzer", kind.equals("text") ? "gse-simple-v1" : ""), 8192), java.nio.charset.StandardCharsets.US_ASCII);
    }
    @SuppressWarnings({"rawtypes", "unchecked"})
    private IndexDefinition<T> definition(String descriptor) {
        var parsed = ReplicaWire.object(ReplicaJson.decode(descriptor.getBytes(java.nio.charset.StandardCharsets.US_ASCII), 8192));
        require(parsed.keySet().equals(java.util.Set.of("kind", "field", "analyzer")), PROTOCOL_MISMATCH, "invalid index descriptor fields");
        String kind = ReplicaWire.string(parsed, "kind"), name = ReplicaWire.string(parsed, "field");
        require(ReplicaWire.string(parsed, "analyzer").equals(kind.equals("text") ? "gse-simple-v1" : ""), PROTOCOL_MISMATCH, "index analyzer mismatch");
        Field<T, ?> field = schema.requireField(name);
        return switch (kind) {
            case "equality" -> IndexDefinition.equality((Field) field);
            case "range" -> IndexDefinition.range((Field) field);
            case "prefix" -> IndexDefinition.prefix(schema.requireField(name, String.class));
            case "text" -> {
                var text = schema.requireTextField(name);
                require(text.analyzer() == SimpleAnalyzer.INSTANCE, PROTOCOL_MISMATCH, "text analyzer mismatch");
                yield IndexDefinition.text(text);
            }
            default -> throw new ReplicationException(PROTOCOL_MISMATCH, "unknown index descriptor");
        };
    }
    @Override public void close() {
        if (closed) return;
        closed = true;
        published.get().slot().engine.close();
        working.engine.close();
    }
}
