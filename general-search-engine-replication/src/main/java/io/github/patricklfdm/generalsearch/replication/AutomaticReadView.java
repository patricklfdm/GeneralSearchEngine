package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.search.*;
import java.util.List;
import java.util.Optional;

/** Callback-scoped facade; never exports engine ownership or permits cross-thread use. */
final class AutomaticReadView<K,T> implements ReplicaReadView<K,T> {
    private final Thread owner = Thread.currentThread();
    private final long sequence;
    private volatile SearchEngine<K,T> engine;

    AutomaticReadView(SearchEngine<K,T> engine, long sequence) {
        this.engine = engine;
        this.sequence = sequence;
    }

    private SearchEngine<K,T> active() {
        var value = engine;
        if (Thread.currentThread() != owner || value == null)
            throw new ReplicaReadException(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,
                    "replica read view is outside its callback thread or lifetime");
        return value;
    }

    void release() { engine = null; }
    @Override public T get(K id) { return active().get(id); }
    @Override public List<T> search(Query<T> query) { return active().search(query); }
    @Override public List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request) { return active().searchTopK(request); }
    @Override public SearchResult<T> search(SearchRequest<T> request) { return active().search(request); }
    @Override public HighlightedSearchResult<T> search(HighlightedSearchRequest<T> request) { return active().search(request); }
    @Override public Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id) { return active().explain(request, id); }
    @Override public long currentSequence() { active(); return sequence; }
}
