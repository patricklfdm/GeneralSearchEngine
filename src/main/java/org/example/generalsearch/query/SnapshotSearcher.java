package org.example.generalsearch.query;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.catalog.CatalogSnapshot;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.model.Product;

public final class SnapshotSearcher {
    private final CandidatePlanner planner;

    public SnapshotSearcher() {
        this(new CandidatePlanner());
    }

    public SnapshotSearcher(CandidatePlanner planner) {
        this.planner = Objects.requireNonNull(planner, "planner");
    }

    public List<Product> search(CatalogSnapshot snapshot, ProductFilter filter) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(filter, "filter");
        ImmutableBitmap candidates = planner.plan(snapshot, filter)
                .map(CandidateResult::bitmap)
                .orElse(snapshot.activeProducts());
        List<Product> products = new ArrayList<>();
        candidates.forEachSetBit(docId -> {
            Product product = snapshot.get(docId);
            if (product != null && filter.matches(product)) {
                products.add(product);
            }
        });
        return products;
    }
}
