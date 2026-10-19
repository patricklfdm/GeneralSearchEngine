package io.github.patricklfdm.generalsearch.replication;

import java.util.List;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchResult;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;

/**
 * Read-only view of one committed publication, valid only on its active callback
 * thread. No pagination, mutation, maintenance or escaping snapshot ownership.
 * Returning the wrapper does not extend its lifetime.
 */
public interface ReplicaReadView<K, T> {
    T get(K id);
    List<T> search(Query<T> query);
    List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request);
    SearchResult<T> search(SearchRequest<T> request);
    HighlightedSearchResult<T> search(HighlightedSearchRequest<T> request);
    Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id);
    long currentSequence();
}
