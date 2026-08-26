package io.github.patricklfdm.generalsearch.ranking;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.search.SearchExecutionAccess;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Posting-driven BM25 retrieval with bounded top-K retention. */
public final class RankedSearcher<T> {
    private final CandidatePlanner<T> filterPlanner;

    public RankedSearcher() {
        this(new CandidatePlanner<>());
    }

    public RankedSearcher(CandidatePlanner<T> filterPlanner) {
        this.filterPlanner = Objects.requireNonNull(filterPlanner, "filterPlanner");
    }

    /** Searches one immutable snapshot without changing its unranked query behavior. */
    public List<SearchHit<T>> search(
            SearchSnapshot<T> snapshot,
            RankedSearchRequest<T> request
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        return SearchExecutionAccess.search(snapshot, request, filterPlanner);
    }
}
