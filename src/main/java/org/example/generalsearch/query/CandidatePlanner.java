package org.example.generalsearch.query;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.catalog.CatalogSnapshot;
import org.example.generalsearch.filter.AndFilter;
import org.example.generalsearch.filter.CategoryFilter;
import org.example.generalsearch.filter.NotFilter;
import org.example.generalsearch.filter.OrFilter;
import org.example.generalsearch.filter.PriceRangeFilter;
import org.example.generalsearch.filter.PrimeFilter;
import org.example.generalsearch.filter.ProductFilter;

public final class CandidatePlanner {
    public Optional<CandidateResult> plan(CatalogSnapshot snapshot, ProductFilter filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");

        if (filter instanceof CategoryFilter category) {
            return exact(snapshot.categoryIndex().get(category.category()));
        }
        if (filter instanceof PrimeFilter prime) {
            ImmutableBitmap candidates = prime.requirePrime()
                    ? snapshot.primeIndex().primeProducts()
                    : snapshot.activeProducts().andNot(snapshot.primeIndex().primeProducts());
            return exact(candidates);
        }
        if (filter instanceof PriceRangeFilter price) {
            return exact(snapshot.priceIndex().getByRange(price.minPrice(), price.maxPrice()));
        }
        if (filter instanceof AndFilter and) {
            return planAnd(snapshot, and.filters());
        }
        if (filter instanceof OrFilter or) {
            return planOr(snapshot, or.filters());
        }
        if (filter instanceof NotFilter not) {
            Optional<CandidateResult> child = plan(snapshot, not.filter());
            if (child.isEmpty() || child.get().accuracy() != CandidateAccuracy.EXACT) {
                return Optional.empty();
            }
            return exact(snapshot.activeProducts().andNot(child.get().bitmap()));
        }
        return Optional.empty();
    }

    private Optional<CandidateResult> planAnd(
            CatalogSnapshot snapshot,
            List<ProductFilter> filters
    ) {
        List<ImmutableBitmap> indexed = new ArrayList<>();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;

        for (ProductFilter filter : filters) {
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
            List<ProductFilter> filters
    ) {
        if (filters.isEmpty()) {
            return exact(ImmutableBitmap.empty());
        }

        ImmutableBitmap candidates = ImmutableBitmap.empty();
        CandidateAccuracy accuracy = CandidateAccuracy.EXACT;
        for (ProductFilter filter : filters) {
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
}
