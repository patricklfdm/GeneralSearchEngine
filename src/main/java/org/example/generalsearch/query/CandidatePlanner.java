package org.example.generalsearch.query;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.catalog.CatalogSnapshot;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.filter.ProductFilterAdapter;
import org.example.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public final class CandidatePlanner {
    public Optional<CandidateResult> plan(CatalogSnapshot snapshot, Query<Product> filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");

        Optional<CandidateResult> indexed = snapshot.indexes().candidates(filter);
        if (indexed.isPresent()) {
            return indexed;
        }
        if (filter instanceof MatchAllQuery<?>) {
            return exact(snapshot.activeProducts());
        }
        if (filter instanceof AndQuery<?> and) {
            return planAnd(snapshot, productQueries(and.queries()));
        }
        if (filter instanceof OrQuery<?> or) {
            return planOr(snapshot, productQueries(or.queries()));
        }
        if (filter instanceof NotQuery<?> not) {
            Optional<CandidateResult> child = plan(snapshot, productQuery(not.query()));
            return complementExact(snapshot, child);
        }

        if (filter instanceof ProductFilter legacyFilter) {
            Query<Product> adapted = ProductFilterAdapter.toQuery(legacyFilter);
            if (adapted != filter) {
                return plan(snapshot, adapted);
            }
        }
        return Optional.empty();
    }

    private Optional<CandidateResult> planAnd(
            CatalogSnapshot snapshot,
            List<? extends Query<Product>> filters
    ) {
        List<ImmutableBitmap> indexed = new ArrayList<>();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;

        for (Query<Product> filter : filters) {
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
            CatalogSnapshot snapshot,
            List<? extends Query<Product>> filters
    ) {
        if (filters.isEmpty()) {
            return exact(ImmutableBitmap.empty());
        }

        ImmutableBitmap candidates = ImmutableBitmap.empty();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;
        for (Query<Product> filter : filters) {
            Optional<CandidateResult> child = plan(snapshot, filter);
            if (child.isEmpty()) {
                return Optional.empty();
            }
            candidates = candidates.or(child.get().bitmap());
            if (child.get().accuracy() == CandidateAccuracy.SUPERSET) {
                accuracy = CandidateAccuracy.SUPERSET;
            }
        }
        return Optional.of(new CandidateResult(candidates, accuracy));
    }

    private Optional<CandidateResult> exact(ImmutableBitmap bitmap) {
        return Optional.of(new CandidateResult(bitmap, CandidateAccuracy.EXACT));
    }

    private Optional<CandidateResult> complementExact(
            CatalogSnapshot snapshot,
            Optional<CandidateResult> child
    ) {
        if (child.isEmpty() || child.get().accuracy() != CandidateAccuracy.EXACT) {
            return Optional.empty();
        }
        return exact(snapshot.activeProducts().andNot(child.get().bitmap()));
    }

    @SuppressWarnings("unchecked")
    private Query<Product> productQuery(Query<?> query) {
        return (Query<Product>) query;
    }

    @SuppressWarnings("unchecked")
    private List<? extends Query<Product>> productQueries(List<? extends Query<?>> queries) {
        return (List<? extends Query<Product>>) (List<?>) queries;
    }
}
