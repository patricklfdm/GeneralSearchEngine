package io.github.patricklfdm.generalsearch.query;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

public final class CandidatePlanner<T> {
    private final PlannerConfig config;
    private final PlannerCostModel costModel;

    public CandidatePlanner() {
        this(PlannerConfig.DEFAULT);
    }

    public CandidatePlanner(PlannerConfig config) {
        this(config, new PlannerCostModel());
    }

    CandidatePlanner(PlannerConfig config, PlannerCostModel costModel) {
        this.config = Objects.requireNonNull(config, "config");
        this.costModel = Objects.requireNonNull(costModel, "costModel");
    }

    public Optional<CandidateResult> plan(SearchSnapshot<T> snapshot, Query<T> filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");

        List<EstimatedAccessPath<T>> paths = estimatedPaths(snapshot, filter);
        if (!paths.isEmpty()) {
            if (filter instanceof RangeQuery<?, ?>) {
                if (config.rangePlanningMode() == RangePlanningMode.FORCE_SCAN) {
                    return Optional.empty();
                }
                EstimatedAccessPath<T> selected = bestPath(paths);
                if (config.rangePlanningMode() == RangePlanningMode.COST_AWARE
                        && !costModel.preferIndex(
                                selected.estimate(), activeDocumentCount(snapshot))) {
                    return Optional.empty();
                }
                return selected.materialize();
            }
            return bestPath(paths).materialize();
        }
        if (filter instanceof RangeQuery<?, ?>
                && config.rangePlanningMode() == RangePlanningMode.FORCE_SCAN) {
            return Optional.empty();
        }

        Optional<CandidateResult> legacy = snapshot.indexes().candidates(filter);
        if (legacy.isPresent()) {
            return legacy;
        }
        if (filter instanceof MatchAllQuery<?>) {
            return exact(snapshot.activeDocuments());
        }
        if (filter instanceof AndQuery<?> and) {
            return planAnd(snapshot, typedQueries(and.queries()));
        }
        if (filter instanceof OrQuery<?> or) {
            return planOr(snapshot, typedQueries(or.queries()));
        }
        if (filter instanceof NotQuery<?> not) {
            Optional<CandidateResult> child = planCompatibility(
                    snapshot, typedQuery(not.query()));
            return complementExact(snapshot, child);
        }

        return Optional.empty();
    }

    private Optional<CandidateResult> planAnd(
            SearchSnapshot<T> snapshot,
            List<? extends Query<T>> filters
    ) {
        List<EstimatedAccessPath<T>> estimated = new ArrayList<>();
        List<CandidateResult> compatibilityCandidates = new ArrayList<>();
        boolean allChildrenPlanned = true;
        for (Query<T> filter : filters) {
            List<EstimatedAccessPath<T>> childPaths = estimatedPaths(snapshot, filter);
            if (!childPaths.isEmpty()) {
                estimated.add(bestPath(childPaths));
                continue;
            }
            Optional<CandidateResult> child = planCompatibility(snapshot, filter);
            if (child.isPresent() && child.get().bitmap().isEmpty()) {
                return exact(ImmutableBitmap.empty());
            }
            if (child.isPresent()) {
                compatibilityCandidates.add(child.get());
            } else {
                allChildrenPlanned = false;
            }
        }

        estimated.sort(pathComparator());
        EstimatedAccessPath<T> firstPath = estimated.stream()
                .filter(path -> costModel.preferIndex(
                        path.estimate(), activeDocumentCount(snapshot)))
                .findFirst()
                .orElse(null);

        CandidateResult first = null;
        if (firstPath != null) {
            first = firstPath.materialize().orElse(null);
            if (first == null) {
                allChildrenPlanned = false;
            }
        }
        if (first == null && !compatibilityCandidates.isEmpty()) {
            compatibilityCandidates.sort(Comparator.comparingInt(
                    candidate -> candidate.bitmap().cardinality()
            ));
            first = compatibilityCandidates.removeFirst();
        }
        if (first == null) {
            return Optional.empty();
        }

        ImmutableBitmap candidates = first.bitmap();
        CandidateAccuracy accuracy = first.accuracy();
        if (candidates.isEmpty()) {
            return exact(candidates);
        }

        for (EstimatedAccessPath<T> path : estimated) {
            if (path == firstPath) {
                continue;
            }
            if (!costModel.intersectionPays(
                    path.estimate(), candidates.cardinality())) {
                allChildrenPlanned = false;
                continue;
            }
            Optional<CandidateResult> materialized = path.materialize();
            if (materialized.isEmpty()) {
                allChildrenPlanned = false;
                continue;
            }
            candidates = candidates.and(materialized.get().bitmap());
            if (materialized.get().accuracy() == CandidateAccuracy.SUPERSET) {
                accuracy = CandidateAccuracy.SUPERSET;
            }
            if (candidates.isEmpty()) {
                return exact(candidates);
            }
        }

        for (CandidateResult child : compatibilityCandidates) {
            candidates = candidates.and(child.bitmap());
            if (child.accuracy() == CandidateAccuracy.SUPERSET) {
                accuracy = CandidateAccuracy.SUPERSET;
            }
            if (candidates.isEmpty()) {
                return exact(candidates);
            }
        }
        if (!allChildrenPlanned) {
            accuracy = CandidateAccuracy.SUPERSET;
        }
        return Optional.of(new CandidateResult(candidates, accuracy));
    }

    private Optional<CandidateResult> planOr(
            SearchSnapshot<T> snapshot,
            List<? extends Query<T>> filters
    ) {
        if (filters.isEmpty()) {
            return exact(ImmutableBitmap.empty());
        }

        ImmutableBitmap candidates = null;
        ImmutableBitmapBuilder accumulator = null;
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;
        for (Query<T> filter : filters) {
            Optional<CandidateResult> child = planCompatibility(snapshot, filter);
            if (child.isEmpty()) {
                return Optional.empty();
            }
            if (candidates == null) {
                candidates = child.get().bitmap();
            } else {
                if (accumulator == null) {
                    accumulator = new ImmutableBitmapBuilder(candidates);
                }
                accumulator.or(child.get().bitmap());
            }
            if (child.get().accuracy() == CandidateAccuracy.SUPERSET) {
                accuracy = CandidateAccuracy.SUPERSET;
            }
        }
        ImmutableBitmap result = accumulator == null ? candidates : accumulator.build();
        return Optional.of(new CandidateResult(result, accuracy));
    }

    private Optional<CandidateResult> exact(ImmutableBitmap bitmap) {
        return Optional.of(new CandidateResult(bitmap, CandidateAccuracy.EXACT));
    }

    private Optional<CandidateResult> complementExact(
            SearchSnapshot<T> snapshot,
            Optional<CandidateResult> child
    ) {
        if (child.isEmpty() || child.get().accuracy() != CandidateAccuracy.EXACT) {
            return Optional.empty();
        }
        return exact(snapshot.activeDocuments().andNot(child.get().bitmap()));
    }

    private Optional<CandidateResult> planCompatibility(
            SearchSnapshot<T> snapshot,
            Query<T> filter
    ) {
        List<EstimatedAccessPath<T>> paths = estimatedPaths(snapshot, filter);
        if (!paths.isEmpty()) {
            return bestPath(paths).materialize();
        }
        Optional<CandidateResult> legacy = snapshot.indexes().candidates(filter);
        if (legacy.isPresent()) {
            return legacy;
        }
        if (filter instanceof MatchAllQuery<?>) {
            return exact(snapshot.activeDocuments());
        }
        if (filter instanceof AndQuery<?> and) {
            return planAndCompatibility(snapshot, typedQueries(and.queries()));
        }
        if (filter instanceof OrQuery<?> or) {
            return planOr(snapshot, typedQueries(or.queries()));
        }
        if (filter instanceof NotQuery<?> not) {
            return complementExact(snapshot, planCompatibility(
                    snapshot, typedQuery(not.query())));
        }
        return Optional.empty();
    }

    private Optional<CandidateResult> planAndCompatibility(
            SearchSnapshot<T> snapshot,
            List<? extends Query<T>> filters
    ) {
        List<ImmutableBitmap> indexed = new ArrayList<>();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;
        for (Query<T> filter : filters) {
            Optional<CandidateResult> child = planCompatibility(snapshot, filter);
            if (child.isEmpty()) {
                accuracy = CandidateAccuracy.SUPERSET;
                continue;
            }
            if (child.get().bitmap().isEmpty()) {
                return exact(ImmutableBitmap.empty());
            }
            indexed.add(child.get().bitmap());
            if (child.get().accuracy() == CandidateAccuracy.SUPERSET) {
                accuracy = CandidateAccuracy.SUPERSET;
            }
        }
        if (indexed.isEmpty()) {
            return Optional.empty();
        }
        indexed.sort(Comparator.comparingInt(ImmutableBitmap::cardinality));
        ImmutableBitmap candidates = indexed.getFirst();
        for (int index = 1; index < indexed.size(); index++) {
            candidates = candidates.and(indexed.get(index));
            if (candidates.isEmpty()) {
                return exact(candidates);
            }
        }
        return Optional.of(new CandidateResult(candidates, accuracy));
    }

    private List<EstimatedAccessPath<T>> estimatedPaths(
            SearchSnapshot<T> snapshot,
            Query<T> query
    ) {
        List<EstimatedAccessPath<T>> paths = new ArrayList<>();
        for (IndexSnapshot<T> index : snapshot.indexes().indexes()) {
            if (index instanceof EstimatingIndexSnapshot<T> estimating) {
                Optional<CandidateEstimate> estimate = estimating.estimateCandidates(query);
                estimate.ifPresent(value -> paths.add(
                        new EstimatedAccessPath<>(index, query, value)
                ));
            }
        }
        return paths;
    }

    private EstimatedAccessPath<T> bestPath(List<EstimatedAccessPath<T>> paths) {
        return paths.stream().min(pathComparator()).orElseThrow();
    }

    private Comparator<EstimatedAccessPath<T>> pathComparator() {
        return Comparator
                .comparingDouble((EstimatedAccessPath<T> path) ->
                        costModel.accessPathWork(path.estimate()))
                .thenComparingInt(path ->
                        path.estimate().estimatedCandidateCardinality())
                .thenComparingInt(path ->
                        path.estimate().accuracy() == CandidateAccuracy.EXACT ? 0 : 1);
    }

    private int activeDocumentCount(SearchSnapshot<T> snapshot) {
        return snapshot.activeDocuments().cardinality();
    }

    @SuppressWarnings("unchecked")
    private Query<T> typedQuery(Query<?> query) {
        return (Query<T>) query;
    }

    @SuppressWarnings("unchecked")
    private List<? extends Query<T>> typedQueries(List<? extends Query<?>> queries) {
        return (List<? extends Query<T>>) (List<?>) queries;
    }
}
