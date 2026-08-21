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
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;

@SuppressWarnings("deprecation")
public final class CandidatePlanner {
    public Optional<CandidateResult> plan(CatalogSnapshot snapshot, Query<Product> filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");

        if (filter instanceof MatchAllQuery<?>) {
            return exact(snapshot.activeProducts());
        }
        if (filter instanceof EqualQuery<?, ?> equal) {
            return planEqual(snapshot, equal);
        }
        if (filter instanceof RangeQuery<?, ?> range) {
            return planRange(snapshot, range);
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

        // Compatibility with the former Product-specific query types.
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
            return complementExact(snapshot, child);
        }
        return Optional.empty();
    }

    private Optional<CandidateResult> planEqual(
            CatalogSnapshot snapshot,
            EqualQuery<?, ?> query
    ) {
        if (query.field() == ProductFields.CATEGORY) {
            Object value = query.expectedValue();
            return value instanceof Category category
                    ? exact(snapshot.categoryIndex().get(category))
                    : exact(ImmutableBitmap.empty());
        }
        if (query.field() == ProductFields.PRIME) {
            Object value = query.expectedValue();
            if (!(value instanceof Boolean prime)) {
                return exact(ImmutableBitmap.empty());
            }
            return exact(prime
                    ? snapshot.primeIndex().primeProducts()
                    : snapshot.activeProducts().andNot(snapshot.primeIndex().primeProducts()));
        }
        if (query.field() == ProductFields.PRICE) {
            Object value = query.expectedValue();
            return value instanceof Double price
                    ? exact(snapshot.priceIndex().get(price))
                    : exact(ImmutableBitmap.empty());
        }
        return Optional.empty();
    }

    private Optional<CandidateResult> planRange(
            CatalogSnapshot snapshot,
            RangeQuery<?, ?> query
    ) {
        if (query.field() != ProductFields.PRICE) {
            return Optional.empty();
        }
        return exact(snapshot.priceIndex().getByRange(
                (Double) query.minValue(),
                (Double) query.maxValue()
        ));
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
