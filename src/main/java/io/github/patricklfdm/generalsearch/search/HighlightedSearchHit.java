package io.github.patricklfdm.generalsearch.search;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/** One canonical ranked hit with ordered structured field highlights. */
public final class HighlightedSearchHit<T> {
    private final SearchHit<T> hit;
    private final List<FieldHighlight> highlights;

    /**
     * Creates one highlighted hit.
     *
     * @param hit canonical ranked hit
     * @param highlights requested fields that produced at least one span
     * @throws NullPointerException when an argument or list element is null
     * @throws IllegalArgumentException when a logical field occurs more than once
     */
    public HighlightedSearchHit(
            SearchHit<T> hit,
            List<FieldHighlight> highlights
    ) {
        this.hit = Objects.requireNonNull(hit, "hit");
        this.highlights = List.copyOf(highlights);
        Set<String> names = new HashSet<>();
        for (FieldHighlight highlight : this.highlights) {
            if (!names.add(highlight.fieldName())) {
                throw new IllegalArgumentException(
                        "duplicate highlighted field name: " + highlight.fieldName());
            }
        }
    }

    /** @return the exact canonical ranked hit */
    public SearchHit<T> hit() {
        return hit;
    }

    /** @return immutable highlights in requested-field order */
    public List<FieldHighlight> highlights() {
        return highlights;
    }
}
