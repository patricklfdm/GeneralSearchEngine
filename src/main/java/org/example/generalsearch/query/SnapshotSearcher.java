package org.example.generalsearch.query;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.storage.SearchSnapshot;

public final class SnapshotSearcher<T> {
    private final CandidatePlanner<T> planner;

    public SnapshotSearcher() {
        this(new CandidatePlanner<>());
    }

    public SnapshotSearcher(CandidatePlanner<T> planner) {
        this.planner = Objects.requireNonNull(planner, "planner");
    }

    public List<T> search(SearchSnapshot<T> snapshot, Query<T> query) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(query, "query");
        ImmutableBitmap candidates = planner.plan(snapshot, query)
                .map(CandidateResult::bitmap)
                .orElse(snapshot.activeDocuments());
        List<T> products = new ArrayList<>();
        candidates.forEachSetBit(docId -> {
            T document = snapshot.get(docId);
            if (document != null && query.matches(document)) {
                products.add(document);
            }
        });
        return products;
    }
}
