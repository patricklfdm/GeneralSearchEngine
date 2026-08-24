package io.github.patricklfdm.generalsearch.query;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

public final class CandidatePlanner<T> {
    public Optional<CandidateResult> plan(SearchSnapshot<T> snapshot, Query<T> filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");

        Optional<CandidateResult> indexed = snapshot.indexes().candidates(filter);
        if (indexed.isPresent()) {
            return indexed;
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
            Optional<CandidateResult> child = plan(snapshot, typedQuery(not.query()));
            return complementExact(snapshot, child);
        }

        return Optional.empty();
    }

    private Optional<CandidateResult> planAnd(
            SearchSnapshot<T> snapshot,
            List<? extends Query<T>> filters
    ) {
        List<ImmutableBitmap> indexed = new ArrayList<>();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;

        for (Query<T> filter : filters) {
            Optional<CandidateResult> child = plan(snapshot, filter);
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
        for (int i = 1; i < indexed.size(); i++) {
            candidates = candidates.and(indexed.get(i));
            if (candidates.isEmpty()) {
                return exact(candidates);
            }
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
            Optional<CandidateResult> child = plan(snapshot, filter);
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

    @SuppressWarnings("unchecked")
    private Query<T> typedQuery(Query<?> query) {
        return (Query<T>) query;
    }

    @SuppressWarnings("unchecked")
    private List<? extends Query<T>> typedQueries(List<? extends Query<?>> queries) {
        return (List<? extends Query<T>>) (List<?>) queries;
    }
}
