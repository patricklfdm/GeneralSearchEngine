package io.github.patricklfdm.generalsearch.engine;

import java.util.Collection;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;

/**
 * Thread-safe in-memory search engine over documents identified by a business key.
 *
 * <p>Reads observe immutable snapshots. Mutations and index lifecycle operations are
 * asynchronous; successful completion means the resulting snapshot is visible to new
 * reads. Accepted documents must be treated as immutable.</p>
 *
 * @param <K> business ID type
 * @param <T> document type
 */
public interface SearchEngine<K, T> extends AutoCloseable {
    /** Starts a builder from an immutable, complete schema. */
    static <K, T> SearchEngineBuilder<K, T> builder(SearchSchema<T, K> schema) {
        return new SearchEngineBuilder<>(schema);
    }

    /** Starts a builder that will assemble a manual schema around the ID field. */
    static <K, T> SearchEngineBuilder<K, T> builder(
            Class<T> documentType,
            Field<T, K> idField
    ) {
        return new SearchEngineBuilder<>(documentType, idField);
    }

    /** Generates an annotated schema and returns a configurable engine builder. */
    static <K, T> SearchEngineBuilder<K, T> annotatedBuilder(
            Class<T> documentType,
            Class<K> idType
    ) {
        return SearchEngineBuilder.annotated(documentType, idType);
    }

    /** Generates an annotated schema and immediately builds an engine. */
    static <K, T> SearchEngine<K, T> fromAnnotatedClass(
            Class<T> documentType,
            Class<K> idType
    ) {
        return annotatedBuilder(documentType, idType).build();
    }

    /**
     * Adds a document reference; duplicate business IDs fail with
     * DocumentAlreadyExistsException. Accepted documents must be treated as immutable.
     */
    CompletableFuture<Void> add(T document);

    /**
     * Replaces an active document reference; missing IDs fail with
     * DocumentNotFoundException. A business ID cannot be changed by an update.
     */
    CompletableFuture<Void> update(T document);

    /** Removes a document by business ID; removing a missing ID is idempotent. */
    CompletableFuture<Void> remove(K id);

    /**
     * Atomically adds an explicit collection when this implementation supports bulk
     * mutation. The collection's iteration order defines internal document-ID order.
     */
    default CompletableFuture<Void> addAll(Collection<? extends T> documents) {
        Objects.requireNonNull(documents, "documents");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support bulk mutation");
    }

    /** Atomically updates an explicit collection in its iteration order. */
    default CompletableFuture<Void> updateAll(Collection<? extends T> documents) {
        Objects.requireNonNull(documents, "documents");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support bulk mutation");
    }

    /** Atomically removes an explicit collection of business IDs. */
    default CompletableFuture<Void> removeAll(Collection<? extends K> ids) {
        Objects.requireNonNull(ids, "ids");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support bulk mutation");
    }

    /**
     * Builds and atomically publishes an index without blocking readers or mutations.
     * Completion means the index is visible to new searches.
     */
    CompletableFuture<Void> createIndex(IndexDefinition<T> definition);

    /**
     * Removes every index registered for a canonical schema field name.
     * Dropping a known field without indexes is idempotent.
     */
    CompletableFuture<Void> dropIndex(String fieldName);

    /** Returns the retained document reference, or null when the ID is not active. */
    T get(K id);

    /** Returns retained document references in ascending internal document-ID order. */
    List<T> search(Query<T> query);

    /**
     * Returns BM25-ranked hits when this implementation supports ranked retrieval.
     * Existing third-party v1 implementations remain binary-compatible and reject the
     * additive capability until they override it.
     */
    default List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request) {
        Objects.requireNonNull(request, "request");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support ranked retrieval");
    }

    /**
     * Returns V3 ranked-search results when this implementation supports the additive
     * request capability.
     *
     * @param request non-null ranked-search request
     * @return immutable ranked-search result from the snapshot captured by this
     *         invocation, ordered by score descending and deterministic tie-break
     * @throws NullPointerException when {@code request} is null
     * @throws UnsupportedOperationException when the implementation does not support
     *         V3 search requests
     */
    default SearchResult<T> search(SearchRequest<T> request) {
        Objects.requireNonNull(request, "request");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support search requests");
    }

    /**
     * Explains one document when this implementation supports the additive capability.
     *
     * @param request non-null ranked-search request
     * @param id non-null business ID
     * @return explanation for an existing document in the snapshot captured by this
     *         invocation, or empty when the ID is missing; an existing non-match is
     *         represented with {@code matched == false} and score zero
     * @throws NullPointerException when either argument is null
     * @throws UnsupportedOperationException when the implementation does not support
     *         search explanations
     *
     * <p>An explanation is independent of request limit and top-K membership. Each
     * invocation observes its own current snapshot and does not reuse the snapshot of
     * an earlier search.</p>
     */
    default Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id) {
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(id, "id");
        throw new UnsupportedOperationException(
                "this SearchEngine implementation does not support search explanations");
    }

    /** Returns the canonical schema whose fields should be used by queries and indexes. */
    SearchSchema<T, K> schema();

    /**
     * Returns a canonical schema field by name.
     *
     * @param name field name
     * @return the field registered under {@code name}
     * @throws IllegalArgumentException when the field is unknown
     */
    default Field<T, ?> field(String name) {
        return schema().requireField(name);
    }

    /**
     * Returns a canonical schema field by name and validates its value type.
     *
     * @param name field name
     * @param valueType expected boxed value type
     * @param <V> field value type
     * @return the typed field registered under {@code name}
     * @throws IllegalArgumentException when the field is unknown or has another type
     */
    default <V> Field<T, V> field(String name, Class<V> valueType) {
        return schema().requireField(name, valueType);
    }

    /**
     * Returns the canonical analyzed-text configuration for a field.
     *
     * @param name text field name
     * @return the analyzed-text field registered under {@code name}
     * @throws IllegalArgumentException when no text configuration is registered
     */
    default TextField<T> textField(String name) {
        return schema().requireTextField(name);
    }

    /** Returns a lock-free, immutable operational snapshot of this engine. */
    SearchEngineMetrics metrics();

    @Override
    void close();
}
