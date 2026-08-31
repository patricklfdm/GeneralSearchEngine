package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.TextField;
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
        RankedSearchInput<T> input = RankedSearchInput.from(snapshot, request);
        SearchPlan<T> plan = new SearchPlanner<T>(filterPlanner).plan(input);
        return new SearchResult<>(new SearchExecutor<T>().execute(plan));
    }

    /**
     * Executes one V3.3 first-page request through the internal snapshot-bound
     * pipeline. Built-in continuation is admitted by the engine sibling before this
     * bridge is invoked.
     *
     * @hidden
     */
    public static <T> SearchPageResult<T> searchPage(
            SearchSnapshot<T> snapshot,
            SearchPageRequest<T> request,
            CandidatePlanner<T> filterPlanner
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(filterPlanner, "filterPlanner");
        RankedSearchInput<T> input = RankedSearchInput.from(
                snapshot,
                request.searchRequest()
        );
        SearchPlan<T> plan = new SearchPlanner<T>(filterPlanner).plan(input);
        return new SearchExecutor<T>().executePage(
                plan,
                request.totalHitsMode()
        );
    }

    /**
     * Executes one highlighted request and its recursive evidence through a single
     * prepared plan.
     *
     * @hidden
     */
    public static <T> HighlightedSearchResult<T> searchHighlighted(
            SearchSnapshot<T> snapshot,
            HighlightedSearchRequest<T> request,
            List<TextField<T>> canonicalFields,
            CandidatePlanner<T> filterPlanner
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        List<TextField<T>> fields = List.copyOf(canonicalFields);
        Objects.requireNonNull(filterPlanner, "filterPlanner");
        RankedSearchInput<T> input = RankedSearchInput.from(
                snapshot,
                request.searchRequest()
        );
        SearchPlan<T> plan = new SearchPlanner<T>(filterPlanner).plan(input);
        List<ExecutedSearchHit<T>> hits = new SearchExecutor<T>()
                .executeWithDocumentIds(plan);
        return HighlightAssembler.assemble(
                hits,
                fields,
                plan.root(),
                request.contextCharacters(),
                request.maxFragmentsPerField()
        );
    }

    /**
     * Explains one already-resolved internal document through the canonical V3 plan.
     *
     * @hidden
     */
    public static <T> SearchExplanation<T> explain(
            SearchSnapshot<T> snapshot,
            SearchRequest<T> request,
            int documentId,
            CandidatePlanner<T> filterPlanner
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(filterPlanner, "filterPlanner");
        if (documentId < 0) {
            throw new IllegalArgumentException(
                    "documentId must not be negative");
        }
        T document = snapshot.get(documentId);
        if (document == null) {
            throw new IllegalArgumentException(
                    "documentId must identify an active snapshot document");
        }
        RankedSearchInput<T> input = RankedSearchInput.from(snapshot, request);
        SearchPlan<T> plan = new SearchPlanner<T>(filterPlanner).plan(input);
        return new ExplainExecutor<T>().explain(plan, documentId, document);
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
        RankedSearchInput<T> input = RankedSearchInput.from(snapshot, request);
        SearchPlan<T> plan = new SearchPlanner<T>(filterPlanner).plan(input);
        return new SearchExecutor<T>().execute(plan);
    }
}
