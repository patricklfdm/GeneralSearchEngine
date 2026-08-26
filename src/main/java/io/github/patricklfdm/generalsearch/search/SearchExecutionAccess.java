package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/**
 * Unsupported internal bridge used only by built-in sibling-package entry points.
 *
 * @hidden
 */
public final class SearchExecutionAccess {
    private SearchExecutionAccess() {
    }

    /**
     * Executes a V3 request through the internal snapshot-bound pipeline.
     *
     * @hidden
     */
    public static <T> SearchResult<T> search(
            SearchSnapshot<T> snapshot,
            SearchRequest<T> request,
            CandidatePlanner<T> filterPlanner
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(filterPlanner, "filterPlanner");
        TextSearchInput<T> input = TextSearchInput.from(request);
        SearchPlan<T> plan = new SearchPlanner<>(filterPlanner).plan(snapshot, input);
        return new SearchResult<>(new SearchExecutor<T>().execute(plan));
    }

    /**
     * Executes a legacy request through the internal snapshot-bound pipeline.
     *
     * @hidden
     */
    public static <T> List<SearchHit<T>> search(
            SearchSnapshot<T> snapshot,
            RankedSearchRequest<T> request,
            CandidatePlanner<T> filterPlanner
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(filterPlanner, "filterPlanner");
        TextSearchInput<T> input = TextSearchInput.from(request);
        SearchPlan<T> plan = new SearchPlanner<>(filterPlanner).plan(snapshot, input);
        return new SearchExecutor<T>().execute(plan);
    }
}
